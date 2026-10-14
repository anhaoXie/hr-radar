# -*- coding: utf-8 -*-
"""排查技能误判：找出 JD 里到底哪段文字命中了可疑技能。"""
import io, os, re, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from radar import store, skills as S
from radar.textutil import skill_text

SUSPECT = ["建筑设计", "量化投资", "Office办公", "人工智能", "审计", "电商运营", "法律文书", "环保工程"]

# 建立 别名 -> 规范名 的反查
alias2canon = {}
for s in S.ALL_SKILLS:
    for a in s["aliases"]:
        alias2canon.setdefault(a, set()).add(s["name"])

rows = store.query_jobs(limit=400)
print("库内样本:", len(rows), "其中有 JD:", sum(1 for r in rows if r.get("jd")))
for name in SUSPECT:
    hits = []
    for r in rows:
        if name not in (r.get("skills") or []):
            continue
        text = skill_text(r.get("title", ""), r.get("jd", ""), r.get("tags"), r.get("source_industry", ""))
        low = text.lower()
        matched = [a for a in alias2canon if name in alias2canon[a] and a and a in low]
        hits.append((r.get("title"), r.get("company"), matched[:6], len(text)))
    print()
    print("##", name, "-> 命中", len(hits), "个岗位")
    for t, c, m, L in hits[:4]:
        print(f"   {t} | {c} | 触发别名={m} | 文本长度={L}")

print()
print("### 可疑技能的别名表 ###")
for name in ["建筑设计", "量化投资", "Office办公", "人工智能"]:
    for s in S.ALL_SKILLS:
        if s["name"] == name:
            print(f"  {name}: {s['aliases']}")

print()
print("### 具体上下文 ###")
for r in rows:
    jd = r.get("jd") or ""
    for kw in ["建筑", "量化"]:
        for m in re.finditer(kw, jd):
            print(f"  [{r.get('title')[:18]}] ...{jd[max(0,m.start()-40):m.start()+40]}...")
            break
