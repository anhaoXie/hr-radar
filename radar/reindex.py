# -*- coding: utf-8 -*-
"""重新抽取：技能词典或抽取规则升级后，不用重新抓取就能刷新全库技能标签。

用途：升级技能词典、修正误判规则之后，跑一次让历史数据也用上新规则。
"""
from __future__ import annotations

import json

from . import store
from .pipeline import classify_job
from .skills import extract_skills
from .textutil import skill_text


def reextract_skills(industry_id: str | None = None, verbose: bool = False) -> dict:
    """对库内岗位重新做「行业分类 + 技能抽取」，返回统计。

    技能以 JD 正文为准；没有 JD 的岗位退回用标题 + 标签。
    """
    rows = store.query_jobs(industry_id=industry_id or "all", limit=100000)
    if not rows:
        return {"ok": False, "message": "库里还没有岗位", "scanned": 0, "updated": 0}

    c = store._conn()
    updated = 0
    changed = 0
    with_detail = 0
    for r in rows:
        jd = r.get("jd") or ""
        tags = r.get("tags") or []
        if jd:
            text = skill_text(r.get("title", ""), jd, None, "")
            with_detail += 1
        else:
            text = skill_text(r.get("title", ""), "", tags, r.get("source_industry", ""))
        new_skills = extract_skills(text)
        new_ind = classify_job(r.get("title"), jd, r.get("source_industry"))

        old_skills = r.get("skills") or []
        if new_skills != old_skills or new_ind != r.get("industry_id"):
            changed += 1
        c.execute("UPDATE jobs SET skills=?, industry_id=? WHERE id=?",
                  (json.dumps(new_skills, ensure_ascii=False), new_ind, r["id"]))
        updated += 1
        if verbose and updated % 200 == 0:
            print(f"  已处理 {updated}/{len(rows)}", flush=True)
    c.commit()
    return {"ok": True, "scanned": len(rows), "updated": updated,
            "changed": changed, "with_jd": with_detail}
