# -*- coding: utf-8 -*-
"""需求分析引擎：技能需求榜、薪资基准、学历/城市分布、趋势对比。

所有数字都来自真实抓取入库的岗位，不掺样例数据。样本量为 0 时会明确返回
空结果 + 提示，而不是编造内容。
"""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from . import industries, store
from .skills import ALL_SKILLS, SKILL_CATEGORIES, skill_category
from .textutil import clean_text

CN_TZ = store.CN_TZ
_SKILL_DEMAND = {s["name"]: float(s.get("demand", 1.0) or 1.0) for s in ALL_SKILLS}


def _round(v, n=1):
    if v is None:
        return None
    try:
        return round(float(v), n)
    except (TypeError, ValueError):
        return None


def _pct(part: int, total: int) -> float:
    return round(part * 100.0 / total, 1) if total else 0.0


# ---------------------------------------------------------------------------
def analyze(industry_id: str = "all", city: str = "全国", source: str = "all",
            keyword: str = "", region: str = "all", days: int | None = None,
            top_n: int = 24) -> dict:
    rows = store.query_jobs(industry_id=industry_id, city=city, source=source,
                            keyword=keyword, region=region, days=days, limit=8000)
    total = len(rows)
    out: dict = {
        "query": {"industry_id": industry_id, "industry_name": industries.industry_name(industry_id)
                  if industry_id not in ("all", "") else "全部行业",
                  "city": city, "source": source, "keyword": keyword, "region": region, "days": days},
        "job_count": total,
        "generated_at": store.now_iso(),
        "skills": [], "skill_categories": [], "salary": {}, "degree": [], "city_top": [],
        "company_top": [], "source_mix": [], "job_type": [], "freshness": {}, "insights": [],
    }
    if not total:
        out["insights"].append("当前筛选条件下库里没有岗位。请先到「实时刷新」抓取数据。")
        return out

    # --- 技能需求榜 -------------------------------------------------------
    skill_counter: Counter = Counter()
    cat_counter: Counter = Counter()
    skill_by_jobtype: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        sk = r.get("skills") or []
        for s in set(sk):
            skill_counter[s] += 1
            cat_counter[skill_category(s)] += 1
        jt = r.get("job_type") or "未标注"
        for s in set(sk):
            skill_by_jobtype[jt][s] += 1

    top = skill_counter.most_common(top_n)
    out["skills"] = [{
        "name": name,
        "count": cnt,
        "share": _pct(cnt, total),
        "category": skill_category(name),
        "demand": _round(_SKILL_DEMAND.get(name, 1.0), 2),
        "score": _round(cnt / total * _SKILL_DEMAND.get(name, 1.0) * 100, 2),
    } for name, cnt in top]

    out["skill_categories"] = [
        {"name": k, "count": v, "share": _pct(v, total)}
        for k, v in cat_counter.most_common(14)
    ]

    # --- 薪资 -------------------------------------------------------------
    out["salary"] = _salary_stats(rows)

    # --- 学历 / 城市 / 公司 / 来源 / 岗位类型 ----------------------------
    out["degree"] = [{"name": k, "count": v, "share": _pct(v, total)}
                     for k, v in store.counts_by("degree", industry_id, days, 10)]
    out["city_top"] = [{"name": k, "count": v, "share": _pct(v, total)}
                       for k, v in Counter(r["city"] or "未知" for r in rows).most_common(12)]
    out["company_top"] = [{"name": k, "count": v}
                          for k, v in Counter(r["company"] or "未知" for r in rows).most_common(12)]
    out["source_mix"] = [{"name": k, "count": v, "share": _pct(v, total)}
                         for k, v in Counter(r["source"] for r in rows).most_common()]
    out["job_type"] = [{"name": k, "count": v, "share": _pct(v, total)}
                       for k, v in Counter(r["job_type"] or "未标注" for r in rows).most_common(8)]

    # --- 新鲜度（"实时"到底有多实时）-------------------------------------
    today = store.today()
    d7 = (datetime.now(CN_TZ) - timedelta(days=7)).strftime("%Y-%m-%d")
    d1 = (datetime.now(CN_TZ) - timedelta(days=1)).strftime("%Y-%m-%d")
    new_today = sum(1 for r in rows if (r.get("first_seen") or "")[:10] == today)
    new_yest = sum(1 for r in rows if d1 <= (r.get("first_seen") or "")[:10] < today)
    new_7 = sum(1 for r in rows if (r.get("first_seen") or "")[:10] >= d7)
    out["freshness"] = {"new_today": new_today, "new_yesterday": new_yest, "new_7d": new_7,
                        "total": total, "today": today}

    # --- 洞察 -------------------------------------------------------------
    out["insights"] = _insights(out, rows)
    return out


def _salary_stats(rows: list[dict]) -> dict:
    per_cur: dict[str, dict] = defaultdict(lambda: {"month": [], "day": [], "year": [],
                                                    "raw_samples": []})
    for r in rows:
        cur = (r.get("currency") or "CNY").upper()
        lo, hi = r.get("pay_month_min"), r.get("pay_month_max")
        nums = [v for v in (lo, hi) if isinstance(v, (int, float))]
        if nums:
            per_cur[cur]["month"].append(sum(nums) / len(nums))
        if r.get("pay_unit") == "day":
            d = [v for v in (r.get("pay_min"), r.get("pay_max")) if isinstance(v, (int, float))]
            if d:
                per_cur[cur]["day"].append(sum(d) / len(d))
        if r.get("pay_unit") == "year":
            y = [v for v in (r.get("pay_min"), r.get("pay_max")) if isinstance(v, (int, float))]
            if y:
                per_cur[cur]["year"].append(sum(y) / len(y))

    out: dict[str, dict] = {}
    for cur, buckets in per_cur.items():
        entry: dict = {"currency": cur}
        for key in ("month", "day", "year"):
            vals = sorted(buckets[key])
            if not vals:
                entry[key] = None
                continue
            n = len(vals)
            entry[key] = {
                "n": n,
                "avg": _round(sum(vals) / n, 0),
                "median": _round(statistics.median(vals), 0),
                "p25": _round(vals[max(0, int(n * 0.25) - 1)], 0),
                "p75": _round(vals[min(n - 1, int(n * 0.75))], 0),
                "min": _round(vals[0], 0),
                "max": _round(vals[-1], 0),
            }
        out[cur] = entry
    return out


def _insights(out: dict, rows: list[dict]) -> list[str]:
    tips: list[str] = []
    total = out["job_count"]
    tips.append(f"当前样本 {total} 条岗位，覆盖 {len(out['source_mix'])} 个数据源。")

    if out["skills"]:
        top3 = "、".join(s["name"] for s in out["skills"][:3])
        tips.append(f"需求最集中的技能：{top3}。")
        top = out["skills"][0]
        tips.append(f"「{top['name']}」出现在 {top['share']}% 的岗位里，是当前最高频的硬门槛。")
        rare_but_hot = [s for s in out["skills"] if s["demand"] >= 1.15]
        if rare_but_hot:
            tips.append("高增长技能（市场热度权重高）："
                        + "、".join(s["name"] for s in rare_but_hot[:5]) + "。")

    cny = (out["salary"] or {}).get("CNY")
    if cny and cny.get("day"):
        d = cny["day"]
        tips.append(f"实习日薪中位数 ¥{d['median']:.0f}/天，"
                    f"中位区间 ¥{d['p25']:.0f}–¥{d['p75']:.0f}。")
    if cny and cny.get("month"):
        m = cny["month"]
        tips.append(f"折算月薪中位数 ¥{m['median']:.0f}。")

    if out["degree"]:
        top_deg = out["degree"][0]
        tips.append(f"学历要求以「{top_deg['name']}」为主（{top_deg['share']}%）。")

    f = out["freshness"]
    if f.get("new_today"):
        tips.append(f"今日新入库 {f['new_today']} 条，占样本 {_pct(f['new_today'], total)}%。")
    elif f.get("new_7d"):
        tips.append(f"近 7 天新入库 {f['new_7d']} 条。")
    return tips


# ---------------------------------------------------------------------------
def snapshot_payload(industry_id: str, city: str = "全国", days: int | None = None) -> dict:
    """趋势用的精简快照，避免把整个库塞进一个字段。"""
    a = analyze(industry_id=industry_id, city=city, days=days, top_n=60)
    return {
        "job_count": a["job_count"],
        "city": city,
        "generated_at": a["generated_at"],
        "skills": {s["name"]: s["count"] for s in a["skills"]},
        "city_top": {c["name"]: c["count"] for c in a["city_top"]},
        "source_mix": {s["name"]: s["count"] for s in a["source_mix"]},
        "salary_cny_day_median": ((a["salary"].get("CNY") or {}).get("day") or {}).get("median"),
        "freshness": a["freshness"],
    }


def trend(industry_id: str, city: str = "全国", limit: int = 60) -> dict:
    """对比历史快照，给出岗位量和技能需求的升降。快照按城市对齐，避免混算。"""
    snaps = [s for s in store.snapshots(industry_id, limit=limit)
             if (s.get("payload") or {}).get("city", "全国") == city]
    result = {"industry_id": industry_id, "industry_name": industries.industry_name(industry_id),
              "city": city, "points": [], "skill_delta": [], "note": ""}
    if not snaps:
        result["note"] = ("还没有该城市的行业快照。每次「实时刷新」都会自动存一份"
                          "（同时记一份全国基线），刷新两次以上就能看到趋势。")
        return result

    for s in snaps:
        p = s.get("payload") or {}
        result["points"].append({
            "ts": s.get("ts"), "day": s.get("day"),
            "job_count": s.get("job_count") or p.get("job_count") or 0,
            "day_median": p.get("salary_cny_day_median"),
        })

    if len(snaps) >= 2:
        first, last = snaps[0], snaps[-1]
        pf, pl = first.get("payload") or {}, last.get("payload") or {}
        sf, sl = pf.get("skills") or {}, pl.get("skills") or {}
        nf = max(1, pf.get("job_count") or 1)
        nl = max(1, pl.get("job_count") or 1)
        deltas = []
        for name in set(sf) | set(sl):
            a, b = sf.get(name, 0), sl.get(name, 0)
            ra, rb = a / nf, b / nl
            deltas.append({
                "name": name,
                "before": a, "after": b,
                "share_before": round(ra * 100, 1), "share_after": round(rb * 100, 1),
                "share_delta": round((rb - ra) * 100, 1),
                "count_delta": b - a,
            })
        deltas.sort(key=lambda d: (-d["share_delta"], -d["after"]))
        result["skill_delta"] = deltas[:30]
        jc_f = pf.get("job_count") or 0
        jc_l = pl.get("job_count") or 0
        result["job_count_delta"] = jc_l - jc_f
        result["compare"] = {"from": first.get("ts"), "to": last.get("ts"),
                             "from_count": jc_f, "to_count": jc_l}
    return result


# ---------------------------------------------------------------------------
def market_skill_profile(industry_id: str = "all", city: str = "全国", days: int | None = None,
                         top_n: int = 30) -> dict[str, float]:
    """返回 {技能: 0-5 的市场要求强度}，用于和学生的自评做雷达图对比。"""
    a = analyze(industry_id=industry_id, city=city, days=days, top_n=top_n)
    if not a["skills"]:
        return {}
    top = a["skills"][0]["share"] or 1.0
    prof: dict[str, float] = {}
    for s in a["skills"]:
        prof[s["name"]] = round(min(5.0, s["share"] / top * 5.0), 2)
    return prof


def skill_gap_map(industry_id: str = "all", city: str = "全国", days: int | None = None,
                  top_n: int = 26) -> list[dict]:
    """技能需求明细，含分类与需求强度，供前端列表/图表使用。"""
    a = analyze(industry_id=industry_id, city=city, days=days, top_n=top_n)
    return a["skills"]


def coverage() -> dict:
    """技能词典与行业词典的规模，前端用来展示知识库覆盖。"""
    return {
        "skill_count": len(ALL_SKILLS),
        "skill_category_count": len(SKILL_CATEGORIES),
        "industry_count": len(industries.INDUSTRIES),
        "skills_by_category": {k: len(v) for k, v in SKILL_CATEGORIES.items()},
    }
