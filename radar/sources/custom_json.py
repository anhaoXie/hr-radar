# -*- coding: utf-8 -*-
"""自定义接口源：把任何你已获授权的招聘 API 接进同一套分析流程。

适用场景：
  * 学校就业中心/校企合作的内部岗位接口；
  * 你购买了配额的聚合数据、猎聘开放平台、天眼查类商业接口；
  * 自己整理好的 JSON 服务。

在「设置」里填写：
  url_template   例：https://api.example.com/jobs?kw={keyword}&city={city}&page={page}
  headers        例：{"Authorization": "Bearer xxx"}
  list_path      响应中岗位数组的点号路径，例：data.list / result.items / （留空表示响应本身就是数组）
  field_map      把响应的字段名映射到本工具的规范字段
"""
from __future__ import annotations

import json
import urllib.parse

from ..textutil import clean_text
from .base import FetchContext, JobSource, build_job

CANON = ["id", "title", "company", "city", "salary", "degree", "industry", "jd", "url",
         "job_type", "published_at", "tags"]


class CustomJSONSource(JobSource):
    id = "custom_json"
    name = "自定义接口（企业/授权 API）"
    region = "cn"
    kind = "自定义"
    supports_keyword = True
    supports_city = True

    def _cfg(self, ctx: FetchContext) -> dict:
        cfg = (ctx.settings or {}).get("custom_json") or {}
        return cfg if isinstance(cfg, dict) else {}

    def available(self, ctx: FetchContext) -> tuple[bool, str]:
        cfg = self._cfg(ctx)
        tpl = (cfg.get("url_template") or "").strip()
        if not tpl:
            return False, "未配置 url_template"
        if not tpl.lower().startswith(("http://", "https://")):
            return False, "url_template 必须是 http(s) 地址"
        return True, ""

    def fetch(self, ctx: FetchContext) -> list[dict]:
        from .. import http
        ok, why = self.available(ctx)
        if not ok:
            ctx.say(f"[自定义接口] 跳过：{why}")
            return []
        cfg = self._cfg(ctx)
        tpl: str = cfg["url_template"]
        method = (cfg.get("method") or "GET").upper()
        headers = cfg.get("headers") or {}
        if isinstance(headers, str):
            try:
                headers = json.loads(headers)
            except Exception:
                headers = {}
        list_path = (cfg.get("list_path") or "").strip()
        fmap = cfg.get("field_map") or {}
        if not isinstance(fmap, dict):
            fmap = {}
        fmap = {k: v for k, v in fmap.items() if v}
        body_tpl = cfg.get("body_template") or ""

        out: list[dict] = []
        seen: set[str] = set()
        for kw in ctx.keywords:
            if ctx.expired():
                break
            url = _fill(tpl, kw, ctx.city, 1)
            data = None
            try:
                if method == "POST":
                    body = _fill(body_tpl, kw, ctx.city, 1) or {
                        "keyword": kw, "city": ctx.city, "page": 1}
                    data = _post_json(url, headers, body, ctx)
                else:
                    data = http.get_json(url, headers=headers, timeout=ctx.timeout,
                                         interval=ctx.interval)
            except Exception as e:  # noqa: BLE001
                ctx.say(f"[自定义接口] 关键词「{kw}」失败：{e}")
                continue
            items = _pick_list(data, list_path)
            if not items:
                ctx.say(f"[自定义接口] 关键词「{kw}」未取到列表（检查 list_path）")
                continue
            for it in items:
                if not isinstance(it, dict):
                    continue
                job = self._to_job(it, fmap, kw)
                if job and job["uid"] not in seen:
                    seen.add(job["uid"])
                    out.append(job)
            ctx.say(f"[自定义接口] 关键词「{kw}」累计 {len(out)} 条")
        return out

    def _to_job(self, it: dict, fmap: dict, kw: str) -> dict | None:
        def g(key, default=""):
            path = fmap.get(key)
            if path:
                return _dig(it, path, default)
            return it.get(key, default)

        title = clean_text(g("title"))
        if not title:
            return None
        tags = g("tags", [])
        return build_job(
            source=self.id,
            uid=clean_text(g("id")) or f"{title}|{clean_text(g('company'))}",
            title=title,
            company=clean_text(g("company")),
            city=clean_text(g("city")),
            degree=clean_text(g("degree")),
            job_type=clean_text(g("job_type")) or "未标注",
            source_industry=clean_text(g("industry")),
            salary_raw=clean_text(g("salary")),
            tags=tags if isinstance(tags, (list, tuple)) else [clean_text(tags)],
            jd=clean_text(g("jd")),
            url=clean_text(g("url")),
            published_at=clean_text(g("published_at")),
            region="cn",
            extra={"keyword": kw, "custom": True},
        )


def _post_json(url, headers, body, ctx: FetchContext):
    from .. import http
    h = dict(headers)
    h.setdefault("Content-Type", "application/json")
    txt = http.request(url, method="POST", headers=h, data=body, timeout=ctx.timeout,
                       interval=ctx.interval)
    return json.loads(txt)


def _fill(tpl: str, kw: str, city: str, page: int) -> str:
    if not tpl:
        return ""
    city = "" if city in ("全国", "远程/不限", None) else city
    return (tpl.replace("{keyword}", urllib.parse.quote(str(kw)))
               .replace("{city}", urllib.parse.quote(str(city or "")))
               .replace("{page}", str(page)))


def _dig(obj, path: str, default=None):
    cur = obj
    for part in path.split("."):
        if not part:
            continue
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return default
        else:
            return default
        if cur is None:
            return default
    return cur


def _pick_list(data, list_path: str) -> list:
    if isinstance(data, list):
        return data
    if list_path:
        got = _dig(data, list_path)
        if isinstance(got, list):
            return got
    if isinstance(data, dict):
        for key in ("data", "list", "items", "results", "rows", "jobs", "content", "records"):
            got = data.get(key)
            if isinstance(got, list):
                return got
            if isinstance(got, dict):
                for k2 in ("list", "items", "records", "rows", "data"):
                    if isinstance(got.get(k2), list):
                        return got[k2]
    return []
