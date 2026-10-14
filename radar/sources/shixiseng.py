# -*- coding: utf-8 -*-
"""实习僧（shixiseng.com）——国内大学生实习岗位主渠道。

使用站内前端同款公开检索接口 /app/interns/search/v2（GET，返回 JSON）。
已实测：keyword / city 过滤有效，单页最多 20 条，翻页仅首页有数据；
岗位薪资为「元/天」。详情页 SSR 里含完整 JD，可用来做技能抽取。
"""
from __future__ import annotations

import html as html_mod
import json
import re
import urllib.parse

from ..textutil import clean_text, truncate
from .base import FetchContext, JobSource, build_job

API = "https://www.shixiseng.com/app/interns/search/v2"
DETAIL = "https://www.shixiseng.com/intern/{uid}"
PAGE_SIZE = 20

_JSON_FIELD_PATTERNS = [
    re.compile(r'"job_detail"\s*:\s*"((?:[^"\\]|\\.)*)"'),
    re.compile(r'"job_desc(?:ription)?"\s*:\s*"((?:[^"\\]|\\.)*)"'),
    re.compile(r'"contents"\s*:\s*"((?:[^"\\]|\\.)*)"'),
    re.compile(r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"'),
    re.compile(r'"description"\s*:\s*"((?:[^"\\]|\\.)*)"'),
]
_TAG = re.compile(r"<[^>]+>")
_PUA = re.compile(r"[\ue000-\uf8ff]")

# JD 正文起点：这些词之后才是真正的岗位描述
_JD_START = r"(职位描述|岗位描述|岗位职责|工作内容|工作职责|职位要求|任职要求|岗位要求|实习内容)"
# JD 正文终点：出现任何一个就截断（站点页脚、推荐位、导航都在这些词之后）
_STOP_MARKERS = [
    "找实习", "找校招", "看空宣", "旗下产品", "实习僧", "关于我们", "了解我们", "加入我们",
    "免责声明", "联系我们", "客户服务", "商务合作", "版权所有", "经营资质", "ICP备",
    "公司介绍", "企业介绍", "公司简介", "工作地址", "公司地址", "办公地址",
    "相似职位", "热门职位", "推荐职位", "猜你喜欢", "你可能喜欢", "热门企业", "最新职位",
    "投递要求", "简历要求", "截止日期", "收起地图", "求职中若出现",
    "投递简历", "立即投递", "上一篇", "下一篇", "工商信息", "经营信息",
]
# DOM 容器结束标志（job_detail 之后紧跟的兄弟区块）
_BLOCK_END = [
    'class="job-detail', 'class="company', 'class="similar', 'class="recommend',
    'class="footer', 'id="footer', 'class="job-list', 'class="el-footer', 'class="bottom',
]


class ShixisengSource(JobSource):
    id = "shixiseng"
    name = "实习僧"
    region = "cn"
    kind = "实习/校招"
    supports_keyword = True
    supports_city = True
    supports_detail = True

    # ---------------------------------------------------------------- 列表
    def fetch(self, ctx: FetchContext) -> list[dict]:
        from .. import http
        out: list[dict] = []
        seen: set[str] = set()
        max_pages = max(1, int(ctx.settings.get("max_pages_per_keyword", 1) or 1))
        city = None if ctx.city in ("", "全国", "远程/不限", None) else ctx.city

        for kw in ctx.keywords:
            if ctx.expired():
                break
            for page in range(1, max_pages + 1):
                if ctx.expired():
                    break
                params = {"keyword": kw, "page": page, "pageSize": PAGE_SIZE, "type": "intern"}
                if city:
                    params["city"] = city
                url = API + "?" + urllib.parse.urlencode(params)
                try:
                    data = http.get_json(
                        url,
                        headers={"Referer": "https://www.shixiseng.com/interns?keyword="
                                             + urllib.parse.quote(kw),
                                 "X-Requested-With": "XMLHttpRequest"},
                        timeout=ctx.timeout, interval=ctx.interval,
                    )
                except Exception as e:  # noqa: BLE001
                    ctx.say(f"[实习僧] 关键词「{kw}」第{page}页抓取失败：{e}")
                    break
                items = ((data or {}).get("msg") or {}).get("data") or []
                if not items:
                    if page == 1:
                        ctx.say(f"[实习僧] 关键词「{kw}」无结果")
                    break
                for it in items:
                    uid = clean_text(it.get("uuid"))
                    if not uid or uid in seen:
                        continue
                    seen.add(uid)
                    job = self._to_job(it, kw)
                    if job:
                        out.append(job)
                if len(items) < PAGE_SIZE:
                    break
            ctx.say(f"[实习僧] 关键词「{kw}」累计 {len(out)} 条")
        return out

    def _to_job(self, it: dict, kw: str) -> dict | None:
        title = clean_text(it.get("name"))
        if not title:
            return None
        uid = clean_text(it.get("uuid"))
        # 校招岗偶尔返回月薪，用数量级做兜底判断（实习生日薪极少超过 1000 元）
        lo, hi = it.get("minsalary"), it.get("maxsalary")
        unit = "day"
        try:
            top = max([v for v in (lo, hi) if isinstance(v, (int, float))] or [0])
        except Exception:
            top = 0
        if top > 2000:
            unit = "month"
        tags = []
        for key in ("i_tags", "c_tags", "hope_you"):
            v = it.get(key)
            if isinstance(v, list):
                tags += [clean_text(x) for x in v]
        return build_job(
            source=self.id,
            uid=uid,
            title=title,
            company=clean_text(it.get("cname")),
            city=clean_text(it.get("city")),
            degree=clean_text(it.get("degree")),
            job_type="实习",
            source_industry=clean_text(it.get("industry")),
            pay_min=lo if isinstance(lo, (int, float)) else None,
            pay_max=hi if isinstance(hi, (int, float)) else None,
            pay_unit=unit,
            currency="CNY",
            tags=tags,
            jd="",
            url=DETAIL.format(uid=uid),
            published_at=clean_text(it.get("refresh")),
            region="cn",
            extra={"keyword": kw, "scale": clean_text(it.get("scale")), "ftype": it.get("ftype")},
        )

    # ---------------------------------------------------------------- 详情
    def fetch_detail_jd(self, job: dict, ctx: FetchContext) -> str | None:
        from .. import http
        url = job.get("url") or DETAIL.format(uid=job.get("uid"))
        try:
            page = http.get_text(url, headers={"Referer": "https://www.shixiseng.com/interns"},
                                 timeout=ctx.timeout, interval=ctx.interval)
        except Exception as e:  # noqa: BLE001
            ctx.say(f"[实习僧] 详情页失败 {job.get('uid')}: {e}")
            return None
        jd = extract_jd(page)
        return jd or None


# ---------------------------------------------------------------------------
# JD 抽取：先试内嵌 JSON 字段，再试 DOM 文本切段，取最长且像样的那段
# ---------------------------------------------------------------------------
def extract_jd(page: str) -> str:
    if not page:
        return ""
    cands: list[str] = []

    # 策略 1：直接切 SSR 里的 job_detail 容器（最干净）
    cands.append(_job_detail_block(page))

    # 策略 2：内嵌 JSON 字段
    for pat in _JSON_FIELD_PATTERNS:
        for m in pat.finditer(page):
            raw = m.group(1)
            try:
                text = json.loads('"' + raw + '"')
            except Exception:
                text = raw
            cands.append(_to_plain(text))

    # 策略 3：正文关键词切段
    cands.append(_dom_slice(page))

    best = ""
    for c in cands:
        c = _trim_boilerplate(c.strip())
        if len(c) > len(best) and _looks_like_jd(c):
            best = c
    return truncate(best, 6000)


def _job_detail_block(page: str) -> str:
    m = re.search(r'<div[^>]*class="[^"]*job_detail[^"]*"[^>]*>', page)
    if not m:
        return ""
    seg = page[m.end():m.end() + 60000]
    cut = len(seg)
    for mk in _BLOCK_END:
        i = seg.find(mk)
        if 0 <= i < cut:
            cut = i
    return _to_plain(seg[:cut])


def _trim_boilerplate(text: str) -> str:
    """在最早的页脚/推荐位标志词处截断。"""
    if not text:
        return ""
    cut = len(text)
    for mk in _STOP_MARKERS:
        i = text.find(mk, 30)
        if 30 < i < cut:
            cut = i
    out = text[:cut].strip()
    # 掐掉结尾残留的导航碎词
    out = re.sub(r"[\s\n]*(投递|收藏|分享|举报|展开|收起)\s*$", "", out)
    return out.strip()


def _to_plain(text: str) -> str:
    if not text:
        return ""
    s = text.replace("\\u002F", "/").replace("\\n", "\n").replace("\\r", "\n")
    s = html_mod.unescape(s)
    s = _TAG.sub("\n", s)
    s = _PUA.sub("", s)
    s = re.sub(r"[ \t\u00a0\u3000]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()


def _dom_slice(page: str) -> str:
    """从 SSR 后的正文里，按「职位描述」等关键词切一段。"""
    body = re.sub(r"<script.*?</script>", " ", page, flags=re.S | re.I)
    body = re.sub(r"<style.*?</style>", " ", body, flags=re.S | re.I)
    plain = _to_plain(body)
    if not plain:
        return ""
    starts = [m.start() for m in re.finditer(_JD_START, plain)]
    starts = [s for s in starts if s < len(plain) - 30]
    if not starts:
        return ""
    # 取第一个起点开始的连续正文，而不是把多段拼起来（拼接会把页脚也带进来）
    best = ""
    for s in starts[:3]:
        seg = _trim_boilerplate(plain[s:s + 5000])
        if len(seg) > len(best):
            best = seg
    return best


def _looks_like_jd(text: str) -> bool:
    if len(text) < 40:
        return False
    markers = ("职责", "要求", "负责", "任职", "工作内容", "岗位", "技能", "熟悉", "掌握", "参与")
    return sum(1 for m in markers if m in text) >= 2
