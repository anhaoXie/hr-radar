# -*- coding: utf-8 -*-
"""抽样可疑别名的真实上下文，判断是误判还是真实要求。"""
import io, os, re, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from radar import store
from radar.textutil import skill_text

CASES = ["word", "office", "agent", "growth", "hr", "ai", "方案设计", "量化", "roadmap"]
rows = store.query_jobs(limit=500)
texts = []
for r in rows:
    t = skill_text(r.get("title", ""), r.get("jd", ""), r.get("tags"), r.get("source_industry", ""))
    if t:
        texts.append((r.get("title"), r.get("company"), r.get("source"), t))

for a in CASES:
    pat = re.compile(r"(?<![A-Za-z.])" + re.escape(a) + r"s?(?![A-Za-z])", re.I) \
        if re.fullmatch(r"[\x00-\x7f]+", a) else re.compile(re.escape(a))
    print("=" * 20, repr(a), "=" * 20)
    n = 0
    for title, comp, src, t in texts:
        for m in pat.finditer(t):
            s = re.sub(r"\s+", " ", t[max(0, m.start() - 60):m.start() + 60])
            print(f"   [{title[:20]}|{src}] ...{s}...")
            n += 1
            break
        if n >= 4:
            break
    if n == 0:
        print("   (无命中)")
