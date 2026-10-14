# -*- coding: utf-8 -*-
"""系统排查泛化别名：高频出现但专业指向模糊的别名，是跨行业误判的根源。"""
import io, os, re, sys, collections
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from radar import store, skills as S
from radar.textutil import skill_text

rows = store.query_jobs(limit=500)
texts = []
for r in rows:
    t = skill_text(r.get("title", ""), r.get("jd", ""), r.get("tags"), r.get("source_industry", ""))
    if t:
        texts.append(t.lower())
N = len(texts)
print("参与统计的文本数:", N)

# 中文别名：统计子串文档频率；英文别名：词边界
ascii_re = lambda a: re.compile(r"(?<![A-Za-z.])" + re.escape(a) + r"s?(?![A-Za-z])")
rows_out = []
for s in S.ALL_SKILLS:
    for a in s["aliases"]:
        if not a:
            continue
        if re.fullmatch(r"[\x00-\x7f]+", a):
            pat = ascii_re(a)
            df = sum(1 for t in texts if pat.search(t))
        else:
            df = sum(1 for t in texts if a in t)
        if df == 0:
            continue
        rows_out.append((df / N, df, a, s["name"], s["category"]))

rows_out.sort(reverse=True)
print()
print("### 文档频率最高的 45 个别名（越靠前越可疑）###")
print(f"{'DF%':>6} {'命中':>5}  {'别名':<18} {'技能':<16} 分类")
for dfr, df, a, name, cat in rows_out[:45]:
    print(f"{dfr*100:6.1f} {df:5d}  {a:<18} {name:<16} {cat}")

print()
print("### 泛化别名嫌疑清单（DF>=12% 且别名长度<=4 或为通用词）###")
GENERIC_HINT = ["设计", "分析", "管理", "运营", "开发", "研究", "评估", "方案", "策划", "测试",
                "处理", "服务", "office", "word", "ai", "data", "design", "research", "plan",
                "management", "analysis", "support", "sales", "market", "media", "cloud", "test"]
sus = []
for dfr, df, a, name, cat in rows_out:
    if dfr >= 0.12 and (len(a) <= 4 or any(h == a.lower() or (len(a) <= 6 and h in a.lower()) for h in GENERIC_HINT)):
        sus.append((dfr, a, name, cat))
for dfr, a, name, cat in sus[:40]:
    print(f"  {dfr*100:5.1f}%  {a:<16} -> {name}  [{cat}]")
print("  合计:", len(sus))
