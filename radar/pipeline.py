# -*- coding: utf-8 -*-
"""刷新流水线：编排数据源 -> 分类行业 -> 抽取技能 -> 入库 -> 补全 JD -> 存快照。"""
from __future__ import annotations

import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from . import config, industries, sources, store
from .skills import extract_skills, skill_category
from .textutil import clean_text, skill_text
from .sources.base import FetchContext


class RefreshState:
    """一次刷新任务的实时状态，供前端轮询展示进度。"""

    def __init__(self, run_id: int, industries_: list[str], keywords: list[str],
                 city: str, source_ids: list[str], timeout_sec: int = 600):
        self.run_id = run_id
        self.industries = industries_
        self.keywords = keywords
        self.city = city
        self.source_ids = source_ids
        self.started = time.time()
        self.deadline = self.started + timeout_sec
        self.finished = False
        self.status = "running"
        self.fetched = 0
        self.inserted = 0
        self.updated = 0
        self.detail_done = 0
        self.errors: list[str] = []
        self.logs: list[str] = []
        self.per_source: dict[str, int] = {s: 0 for s in source_ids}
        self.snapshot: dict | None = None
        self._lock = threading.Lock()

    def expired(self) -> bool:
        return time.time() > self.deadline

    def log(self, msg: str) -> None:
        with self._lock:
            stamp = datetime.now().strftime("%H:%M:%S")
            self.logs.append(f"[{stamp}] {msg}")
            if len(self.logs) > 400:
                del self.logs[:-300]
        print(f"[refresh#{self.run_id}] {msg}", flush=True)

    def err(self, msg: str) -> None:
        with self._lock:
            self.errors.append(msg)
        self.log("!! " + msg)

    def progress(self) -> dict:
        with self._lock:
            return {
                "run_id": self.run_id,
                "status": self.status,
                "finished": self.finished,
                "elapsed": round(time.time() - self.started, 1),
                "industries": self.industries,
                "keywords": self.keywords,
                "city": self.city,
                "sources": self.source_ids,
                "per_source": dict(self.per_source),
                "fetched": self.fetched,
                "inserted": self.inserted,
                "updated": self.updated,
                "detail_done": self.detail_done,
                "errors": list(self.errors)[:20],
                "logs": list(self.logs)[-60:],
                "snapshot": self.snapshot,
            }


class RefreshManager:
    """同一时刻只允许一个刷新任务，避免把对方站点打爆。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._current: RefreshState | None = None
        self._thread: threading.Thread | None = None

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._current is not None and not self._current.finished

    def current(self) -> RefreshState | None:
        with self._lock:
            return self._current

    def start(self, industry_ids: list[str], keywords: list[str], city: str,
              source_ids: list[str] | None = None, timeout_sec: int = 900) -> RefreshState:
        with self._lock:
            if self._current is not None and not self._current.finished:
                raise RuntimeError("已有刷新任务正在运行，请等它结束")
            settings = config.load_settings()
            picked = sources.resolve(source_ids, settings)
            if not picked:
                raise RuntimeError("没有启用任何数据源，请先到「数据源」里勾选")
            src_ids = [s.id for s in picked]
            run_id = store.start_run(industry_ids or [], keywords or [], city, src_ids)
            st = RefreshState(run_id, industry_ids or [], keywords or [], city, src_ids,
                              timeout_sec=timeout_sec)
            self._current = st

        t = threading.Thread(target=self._run, args=(st, picked, settings), daemon=True,
                             name=f"refresh-{run_id}")
        self._thread = t
        t.start()
        return st

    # ------------------------------------------------------------------
    def _run(self, st: RefreshState, picked, settings: dict) -> None:
        try:
            self._execute(st, picked, settings)
        except Exception as e:  # noqa: BLE001
            st.err(f"刷新异常终止：{e}")
            st.log(traceback.format_exc()[-1500:])
            st.status = "error"
            store.finish_run(st.run_id, "error", st.fetched, st.inserted, st.updated,
                             st.detail_done, st.errors)
        finally:
            st.finished = True
            if st.status == "running":
                st.status = "done"

    # ------------------------------------------------------------------
    def _execute(self, st: RefreshState, picked, settings: dict) -> None:
        keywords = self._keywords(st, settings)
        st.log(f"关键词 {len(keywords)} 个：{'、'.join(keywords)}" if keywords else "无关键词，按源默认全量拉取")
        st.log(f"城市：{st.city}；数据源：{'、'.join(s.name for s in picked)}")

        budget = [int(settings.get("detail_jd_limit", 60) or 0)]
        ctx = FetchContext(keywords=keywords, city=st.city, settings=settings, log=st.log,
                           deadline=st.deadline, detail_budget=budget)

        # 1) 并发抓各源
        all_rows: list[dict] = []
        with ThreadPoolExecutor(max_workers=max(1, min(len(picked), int(settings.get("concurrency", 6) or 6)))) as ex:
            futs = {ex.submit(self._fetch_one, src, ctx, st): src for src in picked}
            for fut in as_completed(futs):
                src = futs[fut]
                try:
                    rows = fut.result() or []
                    st.per_source[src.id] = len(rows)
                    all_rows += rows
                except Exception as e:  # noqa: BLE001
                    st.err(f"{src.name} 抓取失败：{e}")
        st.fetched = len(all_rows)
        st.log(f"原始岗位 {st.fetched} 条")

        # 2) 归一：行业分类 + 技能抽取 + 去重
        rows = self._normalize(all_rows, st)
        st.log(f"清洗去重后 {len(rows)} 条")

        # 3) 入库
        try:
            ins, upd = store.upsert_jobs(rows)
            st.inserted, st.updated = ins, upd
            st.log(f"入库完成：新增 {ins}，更新 {upd}")
        except Exception as e:  # noqa: BLE001
            st.err(f"入库失败：{e}")

        # 4) 补全 JD（可选，限量）
        if settings.get("fetch_detail_jd", True) and budget[0] > 0:
            self._enrich_details(st, ctx, picked, settings)

        # 5) 存快照（趋势）：既记本次筛选条件，也记一份全国基线，便于长期对比
        try:
            from . import analyzer
            cities = []
            for c in (st.city, "全国"):
                if c and c not in cities:
                    cities.append(c)
            for ind in (st.industries or []):
                for c in cities:
                    snap = analyzer.snapshot_payload(ind, city=c, days=None)
                    store.save_snapshot(st.run_id, ind, snap)
                    if c == st.city:
                        st.snapshot = snap
            st.log("已写入行业快照，可用于趋势对比")
        except Exception as e:  # noqa: BLE001
            st.err(f"写快照失败：{e}")

        store.finish_run(st.run_id, "done", st.fetched, st.inserted, st.updated,
                         st.detail_done, st.errors)
        st.log("刷新完成 ✅")

    # ------------------------------------------------------------------
    def _fetch_one(self, src, ctx: FetchContext, st: RefreshState) -> list[dict]:
        t0 = time.time()
        try:
            rows = src.fetch(ctx)
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"{type(e).__name__}: {e}") from e
        st.log(f"{src.name}：{len(rows)} 条，用时 {time.time() - t0:.1f}s")
        return rows

    def _keywords(self, st: RefreshState, settings: dict) -> list[str]:
        kws: list[str] = []
        for k in st.keywords:
            k = clean_text(k)
            if k and k not in kws:
                kws.append(k)
        for ind in st.industries:
            for k in _job_keywords(ind):
                k = clean_text(k)
                if k and k not in kws:
                    kws.append(k)
        cap = int(settings.get("max_keywords_per_refresh", 8) or 8)
        if cap > 0:
            kws = kws[:cap]
        return kws

    def _normalize(self, rows: list[dict], st: RefreshState) -> list[dict]:
        seen: set[tuple] = set()
        out: list[dict] = []
        for r in rows:
            key = (r.get("source"), r.get("uid"))
            if key in seen:
                continue
            seen.add(key)
            try:
                ind = classify_job(r.get("title"), r.get("jd"), r.get("source_industry"))
                r["industry_id"] = ind
                # 技能以 JD 正文为准；JD 缺失时才退回用岗位标签补充信号
                if clean_text(r.get("jd")):
                    text = skill_text(r.get("title", ""), r.get("jd", ""), None, "")
                else:
                    text = skill_text(r.get("title", ""), "", r.get("tags"),
                                      r.get("source_industry", ""))
                r["skills"] = extract_skills(text)
                out.append(r)
            except Exception as e:  # noqa: BLE001
                st.err(f"归一化失败 {r.get('title')}: {e}")
        return out

    def _enrich_details(self, st: RefreshState, ctx: FetchContext, picked, settings: dict) -> None:
        """对支持详情页的源，补全 JD 并重新抽技能。JD 是技能信号最丰富的来源。"""
        limit = int(settings.get("detail_jd_limit", 60) or 0)
        for src in picked:
            if not getattr(src, "supports_detail", False) or st.expired():
                continue
            todo = store.jobs_missing_jd(src.id, limit)
            if not todo:
                continue
            st.log(f"{src.name}：补全 {len(todo)} 条岗位详情")
            workers = max(1, min(int(settings.get("concurrency", 6) or 6), 6))

            def one(job):
                if ctx.expired():
                    return None
                jd = src.fetch_detail_jd(job, ctx)
                if not jd:
                    return None
                try:
                    text = skill_text(job.get("title", ""), jd, None, "")
                    found = extract_skills(text)
                except Exception:
                    found = []
                return job["source"], job["uid"], jd, found

            with ThreadPoolExecutor(max_workers=workers) as ex:
                futs = [ex.submit(one, j) for j in todo]
                for fut in as_completed(futs):
                    try:
                        res = fut.result()
                    except Exception:  # noqa: BLE001
                        continue
                    if not res:
                        continue
                    s, uid, jd, found = res
                    store.update_job_jd(s, uid, jd, found)
                    st.detail_done += 1
            st.log(f"{src.name}：JD 补全完成，累计 {st.detail_done} 条")


def _job_keywords(industry_id: str) -> list[str]:
    """取行业的代表岗位关键词；对 industries 模块的接口做兼容。"""
    fn = getattr(industries, "job_keywords", None)
    if callable(fn):
        try:
            return list(fn(industry_id) or [])
        except Exception:
            pass
    d = getattr(industries, "INDUSTRY_BY_ID", {}).get(industry_id) or {}
    return list(d.get("job_keywords") or [])


# 招聘平台自带的行业标签往往很粗（「互联网/游戏/软件」会盖住所有技术岗），
# 这些桶里的岗位应该让「岗位名 + JD」的精确信号优先。
_GENERIC_SOURCE_BUCKETS = {"internet", "professional", "government"}


def classify_job(title, jd, source_industry) -> str:
    """行业分类：精确岗位词 > 平台粗标签。

    例：实习僧把「大模型算法工程师」标成「互联网/游戏/软件」，
    按内容应归到 ai；而「汽车工程」标成「汽车/新能源车」时应保留平台标签。
    """
    text = " ".join([clean_text(title), clean_text(jd)])
    src = clean_text(source_industry)
    by_text = industries.classify_industry(text, "")
    by_source = industries.classify_industry("", src)
    default_id = getattr(industries, "DEFAULT_INDUSTRY_ID", "internet")
    if by_text != default_id and by_source in _GENERIC_SOURCE_BUCKETS:
        return by_text
    return industries.classify_industry(text, src)


MANAGER = RefreshManager()
