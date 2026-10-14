# -*- coding: utf-8 -*-
"""Hacker News『Who is hiring?』月度招聘帖。

通过 Algolia 公开检索接口拿最新一期主帖的评论，每条评论通常是
「公司 | 职位 | 地点 | REMOTE | 薪资」这种自由格式，本身就是很好的
技术岗需求 + 技能关键词样本。适合观察技术行业的技能风向变化。
"""
from __future__ import annotations

import html as html_mod
import re

from ..textutil import clean_text, truncate
from .base import FetchContext, JobSource, build_job

ALGOLIA = "https://hn.algolia.com/api/v1"
MAX_COMMENTS = 200

_TAG = re.compile(r"<[^>]+>")
_LINK = re.compile(r'href="([^"]+)"')
_REMOTE = re.compile(r"\bREMOTE\b", re.I)
_ONSITE = re.compile(r"\bONSITE\b", re.I)
_INTERN = re.compile(r"\bINTERN(SHIPS?)?\b", re.I)
_VISA = re.compile(r"\bVISA\b", re.I)


class HNHiringSource(JobSource):
    id = "hn_hiring"
    name = "Hacker News 招聘帖"
    region = "global"
    kind = "全职"
    supports_keyword = False
    supports_city = False

    def fetch(self, ctx: FetchContext) -> list[dict]:
        from .. import http
        try:
            sid = self._latest_story(ctx)
        except Exception as e:  # noqa: BLE001
            ctx.say(f"[HN] 找主帖失败：{e}")
            return []
        if not sid:
            ctx.say("[HN] 未找到『Who is hiring』主帖")
            return []
        ctx.say(f"[HN] 使用主帖 story_id={sid}")

        out: list[dict] = []
        for page in range(0, 2):
            if ctx.expired():
                break
            url = (f"{ALGOLIA}/search?tags=comment,story_{sid}"
                   f"&hitsPerPage=100&page={page}")
            try:
                data = http.get_json(url, timeout=ctx.timeout, interval=ctx.interval)
            except Exception as e:  # noqa: BLE001
                ctx.say(f"[HN] 评论第{page + 1}页失败：{e}")
                break
            hits = (data or {}).get("hits") or []
            if not hits:
                break
            for h in hits:
                job = self._to_job(h, sid)
                if job:
                    out.append(job)
            if len(hits) < 100 or len(out) >= MAX_COMMENTS:
                break
        out = out[:MAX_COMMENTS]
        ctx.say(f"[HN] 取回 {len(out)} 条招聘评论")
        return out

    def _latest_story(self, ctx: FetchContext) -> str | None:
        from .. import http
        data = http.get_json(
            f"{ALGOLIA}/search_by_date?query=" + "%22Ask%20HN%3A%20Who%20is%20hiring%22"
            "&tags=story&hitsPerPage=10",
            timeout=ctx.timeout, interval=ctx.interval)
        for h in (data or {}).get("hits") or []:
            title = (h.get("title") or "").lower()
            if "who is hiring" in title:
                return str(h.get("objectID"))
        return None

    def _to_job(self, h: dict, sid: str) -> dict | None:
        raw_html = h.get("comment_text") or ""
        if not raw_html:
            return None
        text = html_mod.unescape(_TAG.sub(" ", raw_html)).replace("\n", " \n ")
        text = re.sub(r"[ \t\u00a0]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n", text).strip()
        if len(text) < 30:
            return None

        first_line = text.split("\n")[0].strip()
        parts = [p.strip() for p in first_line.split("|")]
        company = clean_text(parts[0])[:120] if parts else ""
        title = clean_text(parts[1])[:160] if len(parts) > 1 else company
        loc_parts = [p for p in parts[2:] if p]

        flags = []
        if _REMOTE.search(text):
            flags.append("REMOTE")
        if _ONSITE.search(text):
            flags.append("ONSITE")
        if _INTERN.search(text):
            flags.append("INTERN")
        if _VISA.search(text):
            flags.append("VISA")

        city = "远程/不限" if "REMOTE" in flags else (clean_text(loc_parts[0]) if loc_parts else "远程/不限")
        url = ""
        m = _LINK.search(raw_html)
        if m:
            url = html_mod.unescape(m.group(1))
        else:
            for tok in text.split():
                if tok.startswith("http"):
                    url = tok.strip("()[],.")
                    break

        return build_job(
            source=self.id,
            uid=h.get("objectID"),
            title=title or "未标注岗位",
            company=company or "未标注公司",
            city=city,
            job_type="实习" if "INTERN" in flags else "全职",
            source_industry=", ".join(flags),
            tags=flags,
            jd=truncate(text, 4000),
            url=url or f"https://news.ycombinator.com/item?id={h.get('objectID')}",
            published_at=clean_text(h.get("created_at")),
            region="global",
            extra={"story_id": sid, "flags": flags},
        )
