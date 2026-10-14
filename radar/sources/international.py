# -*- coding: utf-8 -*-
"""国际公开招聘板块适配器（均为无需鉴权的公开 JSON API）。

这些源用于两个目的：
  1. 给"任意行业"提供第二视角（尤其是远程/全球化岗位的技能风向）；
  2. 在没有中国源可用时，保证工具仍然有真实数据可分析。

注意：它们的薪资币种是 USD，统一按"年"存入，由分析层按币种分组统计，
不会和中国岗位的人民币日薪混在一起算平均值。
"""
from __future__ import annotations

import urllib.parse

from ..textutil import clean_text
from .base import FetchContext, JobSource, build_job

MAX_KEEP = 260


class _BoardSource(JobSource):
    region = "global"
    supports_keyword = False
    supports_city = False

    def _keep(self, items: list[dict]) -> list[dict]:
        return items[:MAX_KEEP]


# ---------------------------------------------------------------------------
class RemoteOKSource(_BoardSource):
    id = "remoteok"
    name = "RemoteOK"
    kind = "全职/远程"

    def fetch(self, ctx: FetchContext) -> list[dict]:
        from .. import http
        try:
            data = http.get_json("https://remoteok.com/api", timeout=ctx.timeout,
                                 interval=ctx.interval)
        except Exception as e:  # noqa: BLE001
            ctx.say(f"[RemoteOK] 抓取失败：{e}")
            return []
        items = [x for x in (data or []) if isinstance(x, dict) and x.get("position")]
        out = []
        for it in self._keep(items):
            out.append(build_job(
                source=self.id,
                uid=it.get("id") or it.get("slug"),
                title=it.get("position"),
                company=it.get("company"),
                city=clean_text(it.get("location")) or "远程/不限",
                job_type="全职",
                # 注意：RemoteOK 的 tags 是板块标签汤（marketing/crypto/game dev…），
                # 不能当行业标签用，否则会把大量岗位误分类。行业交给标题+JD 判断。
                source_industry="",
                pay_min=it.get("salary_min"), pay_max=it.get("salary_max"),
                pay_unit="year", currency="USD",
                tags=it.get("tags"),
                jd=it.get("description"),
                url=it.get("url") or it.get("apply_url"),
                published_at=it.get("date"),
                region="global",
                extra={"slug": it.get("slug")},
            ))
        ctx.say(f"[RemoteOK] 取回 {len(out)} 条")
        return out


# ---------------------------------------------------------------------------
class RemotiveSource(_BoardSource):
    id = "remotive"
    name = "Remotive"
    kind = "全职/远程"
    supports_keyword = True

    def fetch(self, ctx: FetchContext) -> list[dict]:
        from .. import http
        jobs: list[dict] = []
        seen: set = set()
        kws = (ctx.keywords or [""])[:max(1, int(ctx.settings.get("max_keywords_per_refresh", 8) or 8))]
        for kw in kws:
            if ctx.expired():
                break
            url = "https://remotive.com/api/remote-jobs?limit=40"
            if kw:
                url += "&search=" + urllib.parse.quote(kw)
            try:
                data = http.get_json(url, timeout=ctx.timeout, interval=ctx.interval)
            except Exception as e:  # noqa: BLE001
                ctx.say(f"[Remotive] 「{kw}」失败：{e}")
                continue
            for it in (data or {}).get("jobs") or []:
                jid = it.get("id")
                if jid in seen:
                    continue
                seen.add(jid)
                jobs.append(build_job(
                    source=self.id,
                    uid=jid,
                    title=it.get("title"),
                    company=it.get("company_name"),
                    city=clean_text(it.get("candidate_required_location")) or "远程/不限",
                    job_type=clean_text(it.get("job_type")) or "全职",
                    source_industry=clean_text(it.get("category")),
                    salary_raw=it.get("salary"),
                    currency="USD",
                    tags=it.get("tags"),
                    jd=it.get("description"),
                    url=it.get("url"),
                    published_at=it.get("publication_date"),
                    region="global",
                    extra={"search": kw},
                ))
        out = self._keep(jobs)
        ctx.say(f"[Remotive] 取回 {len(out)} 条")
        return out


# ---------------------------------------------------------------------------
class HimalayasSource(_BoardSource):
    id = "himalayas"
    name = "Himalayas"
    kind = "全职/远程"

    def fetch(self, ctx: FetchContext) -> list[dict]:
        from .. import http
        out: list[dict] = []
        offset = 0
        limit = 100
        for _ in range(3):  # 最多取 300 条
            if ctx.expired():
                break
            url = f"https://himalayas.app/jobs/api?limit={limit}&offset={offset}"
            try:
                data = http.get_json(url, timeout=ctx.timeout, interval=ctx.interval)
            except Exception as e:  # noqa: BLE001
                ctx.say(f"[Himalayas] 失败：{e}")
                break
            items = (data or {}).get("jobs") or []
            if not items:
                break
            for it in items:
                uid = (it.get("guid") or it.get("id") or it.get("applicationLink")
                       or f"{it.get('title')}|{it.get('companyName')}")
                locs = it.get("locationRestrictions") or []
                city = ", ".join(clean_text(x) for x in locs[:3]) if locs else "远程/不限"
                cats = [clean_text(c) for c in (it.get("parentCategories") or [])]
                cats += [clean_text(c) for c in (it.get("categories") or [])][:4]
                out.append(build_job(
                    source=self.id,
                    uid=uid,
                    title=it.get("title"),
                    company=it.get("companyName"),
                    city=city,
                    job_type=clean_text(it.get("employmentType")) or "全职",
                    source_industry=", ".join([c for c in cats if c][:6]),
                    pay_min=it.get("minSalary"), pay_max=it.get("maxSalary"),
                    pay_unit=_period(it.get("salaryPeriod")),
                    currency=(clean_text(it.get("currency")) or "USD").upper(),
                    tags=[clean_text(s) for s in (it.get("seniority") or [])] + cats,
                    jd=it.get("description") or it.get("excerpt"),
                    url=it.get("applicationLink") or it.get("guid"),
                    published_at=_ts(it.get("pubDate")),
                    region="global",
                    extra={"slug": it.get("companySlug")},
                ))
            if len(items) < limit:
                break
            offset += limit
        out = self._keep(out)
        ctx.say(f"[Himalayas] 取回 {len(out)} 条")
        return out


# ---------------------------------------------------------------------------
class JobicySource(_BoardSource):
    id = "jobicy"
    name = "Jobicy"
    kind = "全职/远程"

    def fetch(self, ctx: FetchContext) -> list[dict]:
        from .. import http
        out: list[dict] = []
        for count, geo in ((50, None), (50, "anywhere")):
            if ctx.expired():
                break
            url = f"https://jobicy.com/api/v2/remote-jobs?count={count}"
            if geo:
                url += f"&geo={geo}"
            try:
                data = http.get_json(url, timeout=ctx.timeout, interval=ctx.interval)
            except Exception as e:  # noqa: BLE001
                ctx.say(f"[Jobicy] 失败：{e}")
                continue
            for it in (data or {}).get("jobs") or []:
                out.append(build_job(
                    source=self.id,
                    uid=it.get("id") or it.get("jobSlug"),
                    title=it.get("jobTitle"),
                    company=it.get("companyName"),
                    city=clean_text(it.get("jobGeo")) or "远程/不限",
                    job_type=", ".join(clean_text(t) for t in (it.get("jobType") or [])) or "全职",
                    source_industry=", ".join(clean_text(t) for t in (it.get("jobIndustry") or [])),
                    pay_min=_num(it.get("annualSalaryMin")), pay_max=_num(it.get("annualSalaryMax")),
                    pay_unit="year", currency=(clean_text(it.get("salaryCurrency")) or "USD").upper(),
                    tags=[clean_text(t) for t in (it.get("jobType") or [])] + [clean_text(it.get("jobLevel"))],
                    jd=it.get("jobDescription") or it.get("jobExcerpt"),
                    url=it.get("url"),
                    published_at=_ts(it.get("pubDate")),
                    region="global",
                    extra={"level": clean_text(it.get("jobLevel"))},
                ))
        # 去重
        dedup, seen = [], set()
        for j in out:
            if j["uid"] in seen:
                continue
            seen.add(j["uid"])
            dedup.append(j)
        dedup = self._keep(dedup)
        ctx.say(f"[Jobicy] 取回 {len(dedup)} 条")
        return dedup


# ---------------------------------------------------------------------------
class TheMuseSource(_BoardSource):
    id = "themuse"
    name = "The Muse"
    kind = "全职"

    def fetch(self, ctx: FetchContext) -> list[dict]:
        from .. import http
        out: list[dict] = []
        for page in range(0, 3):
            if ctx.expired():
                break
            url = f"https://www.themuse.com/api/public/jobs?page={page}"
            try:
                data = http.get_json(url, timeout=ctx.timeout, interval=ctx.interval)
            except Exception as e:  # noqa: BLE001
                ctx.say(f"[The Muse] 第{page + 1}页失败：{e}")
                break
            items = (data or {}).get("results") or []
            if not items:
                break
            for it in items:
                comp = it.get("company") or {}
                locs = [clean_text(l.get("name")) for l in (it.get("locations") or []) if isinstance(l, dict)]
                cats = [clean_text(c.get("name")) for c in (it.get("categories") or []) if isinstance(c, dict)]
                levels = [clean_text(l.get("name")) for l in (it.get("levels") or []) if isinstance(l, dict)]
                refs = it.get("refs") or {}
                out.append(build_job(
                    source=self.id,
                    uid=it.get("id") or it.get("short_name"),
                    title=it.get("name"),
                    company=comp.get("name") or comp.get("short_name"),
                    city=", ".join([l for l in locs if l][:2]) or "远程/不限",
                    job_type=clean_text(it.get("type")) or "全职",
                    source_industry=", ".join([c for c in cats if c][:4]),
                    tags=[c for c in cats + levels if c],
                    jd=it.get("contents"),
                    url=refs.get("landing_page"),
                    published_at=it.get("publication_date"),
                    region="global",
                    extra={"level": ", ".join(levels)},
                ))
        ctx.say(f"[The Muse] 取回 {len(out)} 条")
        return out


# ---------------------------------------------------------------------------
def _num(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _period(p) -> str:
    p = (clean_text(p) or "").lower()
    if "hour" in p:
        return "hour"
    if "month" in p:
        return "month"
    if "day" in p:
        return "day"
    return "year"


def _ts(v) -> str:
    if v is None:
        return ""
    if isinstance(v, (int, float)):
        import datetime
        try:
            return datetime.datetime.fromtimestamp(int(v), datetime.timezone.utc).strftime("%Y-%m-%d")
        except Exception:
            return ""
    return clean_text(v)
