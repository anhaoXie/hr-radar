# -*- coding: utf-8 -*-
"""文本清洗、薪资解析、城市归一化。招聘平台的原始数据脏得很，这里是第一道关。"""
from __future__ import annotations

import html
import re

# 招聘站点常用图标字体，把数字/汉字塞在 Unicode 私用区（PUA）里，
# 直接抓接口会拿到一堆乱码字符。这里统一清掉。
_PUA = re.compile(r"[\ue000-\uf8ff]")
_TAGS = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t\u00a0\u3000]+")
_MULTI_NL = re.compile(r"\n{3,}")

# 常见的"HR 黑话"近义写法归一
_CITY_ALIAS = {
    "北京市": "北京", "上海市": "上海", "天津市": "天津", "重庆市": "重庆",
    "广州市": "广州", "深圳市": "深圳", "杭州市": "杭州", "南京市": "南京",
    "成都市": "成都", "武汉市": "武汉", "西安市": "西安", "苏州市": "苏州",
    "青岛市": "青岛", "长沙市": "长沙", "郑州市": "郑州", "合肥市": "合肥",
    "厦门市": "厦门", "福州市": "福州", "济南市": "济南", "沈阳市": "沈阳",
    "大连市": "大连", "哈尔滨市": "哈尔滨", "长春市": "长春", "昆明市": "昆明",
    "南昌市": "南昌", "贵阳市": "贵阳", "南宁市": "南宁", "太原市": "太原",
    "石家庄市": "石家庄", "无锡市": "无锡", "宁波市": "宁波", "佛山市": "佛山",
}


def clean_text(value) -> str:
    """把任意来源的字段清洗成可分析的纯文本。"""
    if value is None:
        return ""
    if not isinstance(value, str):
        if isinstance(value, (list, tuple)):
            parts = []
            for v in value:
                if isinstance(v, dict):
                    parts.append(clean_text(v.get("name") or v.get("label") or v.get("value") or ""))
                else:
                    parts.append(clean_text(v))
            return " ".join(p for p in parts if p)
        if isinstance(value, dict):
            return " ".join(
                p for p in (clean_text(v) for v in value.values()) if p
            )
        return str(value)
    s = html.unescape(value)
    s = _PUA.sub("", s)
    s = s.replace("\\u002F", "/").replace("\\/", "/")
    s = _TAGS.sub(" ", s)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = _WS.sub(" ", s)
    s = re.sub(r"\n[ \t]+", "\n", s)
    s = _MULTI_NL.sub("\n\n", s)
    return s.strip()


def strip_emoji_noise(s: str) -> str:
    """去掉岗位标题里常见的装饰符号，保留文字。"""
    if not s:
        return ""
    s = re.sub(r"[【】\[\]（）()<>《》|丨·•●◆★☆★▶►→←~～]+", " ", s)
    return _WS.sub(" ", s).strip()


_MONTH_DAYS = 21.75


def parse_salary(raw, workdays_per_month: float = _MONTH_DAYS) -> dict | None:
    """把五花八门的薪资写法解析成结构化区间。

    支持：'150-200/天'、'200元/天'、'8-12K'、'8k-12k·13薪'、'1.5-2万/月'、
    '15-25万/年'、'20k-40k/月'、'$120,000 - $160,000'、'6000元/月'、'面议'。
    返回 {'min': , 'max': , 'unit': 'day|month|year|hour', 'currency': 'CNY|USD',
          'month_min': , 'month_max': , 'raw': , 'months_per_year': }
    month_* 是折算后的"月薪"（人民币/原始币种），用于跨岗位比较。
    """
    if raw is None:
        return None
    if isinstance(raw, dict):
        lo = raw.get("min") or raw.get("minSalary") or raw.get("salary_min")
        hi = raw.get("max") or raw.get("maxSalary") or raw.get("salary_max")
        unit = _norm_unit(raw.get("unit") or raw.get("period") or "year")
        cur = (raw.get("currency") or "CNY").upper()
        if isinstance(lo, (int, float)) or isinstance(hi, (int, float)):
            return _build(float(lo or hi or 0), float(hi or lo or 0), unit, cur, str(raw),
                          workdays_per_month)
        raw = raw.get("text") or raw.get("salary") or raw.get("raw") or ""
    if isinstance(raw, (int, float)):
        return None
    s = clean_text(raw)
    if not s:
        return None
    low = re.sub(r"\s+", " ", s.lower().replace("，", ","))
    if any(k in low for k in ("面议", "negotiable", "不限", "保密", "competitive")):
        return {"min": None, "max": None, "unit": "unknown", "currency": "CNY",
                "month_min": None, "month_max": None, "raw": s, "months_per_year": 12,
                "negotiable": True}

    currency = "USD" if ("$" in s or "usd" in low or "€" in s or "£" in s) else "CNY"
    unit = _norm_unit(s)
    months_per_year = 12
    m13 = re.search(r"(\d{1,2})\s*薪", s)
    if m13:
        try:
            months_per_year = max(12, min(24, int(m13.group(1))))
        except ValueError:
            pass

    nums = _extract_numbers(low)
    if not nums:
        return None
    if len(nums) == 1:
        lo = hi = nums[0]
    else:
        lo, hi = nums[0], nums[1]
        if hi < lo:
            lo, hi = hi, lo
    if unit == "unknown":
        # 没有单位标记时按量级和币种猜：美元的大额数字基本是年薪
        if currency == "USD" and hi >= 30000:
            unit = "year"
        elif lo >= 100000:
            unit = "year"
        else:
            unit = "month"
    return _build(lo, hi, unit, currency, s, workdays_per_month, months_per_year)


def _extract_numbers(low: str) -> list[float]:
    """抽取薪资数字，正确处理 K/千/万 乘数的范围传导与千分位逗号。

    '8-12K'            -> [8000, 12000]     （乘数要传导到左边）
    '1.5-2万/月'        -> [15000, 20000]
    '$120,000-$160,000' -> [120000, 160000] （先去千分位逗号）
    '20k-40k'          -> [20000, 40000]
    '300-500'          -> [300, 500]
    """
    num = r"\d[\d,]*(?:\.\d+)?"
    cur = r"[¥$€£]?"          # 币种符号可能夹在连字符和数字之间（'$120,000 - $160,000'）
    # "13薪"、"14薪" 这类不是薪资数字，先剔除
    low = re.sub(r"\d{1,2}\s*薪", " ", low)

    rng = re.compile(cur + r"(" + num + r")\s*(k|千|万|w)?\s*(?:-|~|—|–|ー|至|到)\s*"
                     + cur + r"(" + num + r")\s*(k|千|万|w)?")
    m = rng.search(low)
    if m:
        a_s, a_u, b_s, b_u = m.group(1), m.group(2), m.group(3), m.group(4)
        a, b = _to_float(a_s), _to_float(b_s)
        ma, mb = _mult(a_u), _mult(b_u)
        if ma == 1.0 and mb > 1.0:
            ma = mb
        if mb == 1.0 and ma > 1.0:
            mb = ma
        vals = [a * ma, b * mb]
        return [v for v in vals if v > 0] or []

    ones = [
        (_to_float(mm.group(1)) * _mult(mm.group(2)), _mult(mm.group(2)))
        for mm in re.compile(cur + r"(" + num + r")\s*(k|千|万|w)?").finditer(low)
    ]
    if not ones:
        return []
    with_unit = [v for v, mu in ones if mu > 1.0]
    if with_unit:
        return [max(with_unit)]
    vals = [v for v, _ in ones if v > 0]
    if not vals:
        return []
    # 没有乘数时，取最大的那个数字（避免把 "3人"、"第1年" 之类当薪资）
    return [max(vals)]


def _to_float(s: str) -> float:
    try:
        return float(str(s).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def _mult(suffix) -> float:
    if suffix in ("k", "千"):
        return 1000.0
    if suffix in ("万", "w"):
        return 10000.0
    return 1.0


_CANON_UNITS = {
    "day": "day", "daily": "day", "perday": "day", "per day": "day", "dayrate": "day",
    "month": "month", "monthly": "month", "permonth": "month", "per month": "month",
    "year": "year", "yearly": "year", "annual": "year", "annually": "year", "annum": "year",
    "hour": "hour", "hourly": "hour", "perhour": "hour", "per hour": "hour",
}


def _norm_unit(s: str) -> str:
    if not s:
        return "unknown"
    low = str(s).lower().strip()
    # 先认规范 token（数据源直接给 'day' / 'annual' 这种）
    if low in _CANON_UNITS:
        return _CANON_UNITS[low]
    if "/天" in s or "元/天" in s or "每天" in s or "perday" in low or "per day" in low or "/day" in low:
        return "day"
    if "/时" in s or "小时" in s or "/hour" in low:
        return "hour"
    if "/年" in s or "年薪" in s or "/year" in low or "annum" in low or "annual" in low:
        return "year"
    if "/月" in s or "月薪" in s or "/month" in low or "permonth" in low or "/mo" in low:
        return "month"
    if "万" in s and "年" in s:
        return "year"
    return "unknown"


def _build(lo: float, hi: float, unit: str, currency: str, raw: str,
           workdays_per_month: float = _MONTH_DAYS,
           months_per_year: int = 12) -> dict:
    """折算成月薪。日薪按每月 workdays_per_month 个工作日折算。"""
    if lo is None or hi is None:
        return {"min": None, "max": None, "unit": unit, "currency": currency,
                "month_min": None, "month_max": None, "raw": raw,
                "months_per_year": months_per_year}
    if unit == "day":
        ml, mh = lo * workdays_per_month, hi * workdays_per_month
    elif unit == "hour":
        ml, mh = lo * 8 * workdays_per_month, hi * 8 * workdays_per_month
    elif unit == "year":
        ml, mh = lo / 12.0 * (months_per_year / 12.0), hi / 12.0 * (months_per_year / 12.0)
    else:
        ml, mh = lo, hi
    return {
        "min": round(lo, 2), "max": round(hi, 2), "unit": unit, "currency": currency,
        "month_min": round(ml, 2), "month_max": round(mh, 2), "raw": raw,
        "months_per_year": months_per_year,
    }


def norm_city(value) -> str:
    s = clean_text(value)
    if not s:
        return "未知"
    s = s.strip()
    # 实习僧偶尔给 "省-石家庄市" 这种写法
    if "-" in s:
        s = s.split("-")[-1]
    s = re.sub(r"(市|地区|特别行政区)$", "", s)
    s = _CITY_ALIAS.get(s + "市", s)
    s = s.replace(" ", "")
    if s in ("", "不限", "全国", "remote", "Remote", "anywhere", "Anywhere", "全球"):
        return "远程/不限"
    if len(s) > 12:
        s = s[:12]
    return s


_DEGREE_ORDER = ["不限", "大专", "本科", "硕士", "博士"]


def norm_degree(value) -> str:
    s = clean_text(value)
    if not s:
        return "不限"
    for d in ("博士", "硕士", "本科", "大专", "中专", "高中"):
        if d in s:
            return d
    if "不限" in s or "学历不限" in s or "无要求" in s:
        return "不限"
    return "不限"


def degree_rank(d: str) -> int:
    try:
        return _DEGREE_ORDER.index(d)
    except ValueError:
        return 0


def norm_industry_tag(value) -> str:
    return clean_text(value)


def skill_text(title: str, jd: str, tags=None, extra: str = "") -> str:
    """拼出用于技能抽取的合并文本。标题权重最高（重复一次以提权）。"""
    parts = [title or "", title or "", jd or "", extra or ""]
    if tags:
        if isinstance(tags, (list, tuple)):
            parts.append(" ".join(clean_text(t) for t in tags))
        else:
            parts.append(clean_text(tags))
    return "\n".join(p for p in parts if p)


def truncate(s: str, n: int = 4000) -> str:
    s = s or ""
    return s if len(s) <= n else s[:n] + "…"
