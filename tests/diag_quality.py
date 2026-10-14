# -*- coding: utf-8 -*-
"""诊断：薪资单位解析 + 实习僧 JD 抽取质量。"""
import io, os, re, sys, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from radar import http, store
from radar.textutil import parse_salary, _norm_unit
from radar.sources.shixiseng import extract_jd, _JSON_FIELD_PATTERNS, _to_plain, _dom_slice

print("### A. 薪资单位解析 ###")
for u in ["day", "month", "year", "hour", "annual", "/天", "元/天", "/月", "年薪", "day rate"]:
    print(f"  _norm_unit({u!r}) = {_norm_unit(u)}")
print()
print("  parse_salary dict day 200-300:", parse_salary({"min": 200, "max": 300, "unit": "day", "currency": "CNY"}))
print("  parse_salary dict year 10875-320000 USD:",
      parse_salary({"min": 10875, "max": 320000, "unit": "year", "currency": "USD"}))
print("  parse_salary text '300-500元/天':", parse_salary("300-500元/天"))
print("  parse_salary text '8-12K':", parse_salary("8-12K"))
print("  parse_salary text '1.5-2万/月·13薪':", parse_salary("1.5-2万/月·13薪"))
print("  parse_salary text '$120,000 - $160,000':", parse_salary("$120,000 - $160,000"))

print()
print("### B. 实习僧 JD 抽取质量 ###")
rows = store.query_jobs(source="shixiseng", limit=15)
print(f"  库内实习僧样本 {len(rows)} 条")
for r in rows[:4]:
    jd = r.get("jd") or ""
    print("  " + "-" * 70)
    print("  岗位:", r["title"], "|", r["company"])
    print("  JD 长度:", len(jd), "| 技能:", (r.get("skills") or [])[:10])
    tail = jd[-500:]
    print("  JD 尾部:", repr(tail[-260:]))

print()
print("### C. 哪个抽取策略命中最多 ###")
todo = store.jobs_missing_jd("shixiseng", 0)  # just to touch
uids = [r["uid"] for r in rows[:3]]
for uid in uids:
    url = f"https://www.shixiseng.com/intern/{uid}"
    try:
        page = http.get_text(url, headers={"Referer": "https://www.shixiseng.com/interns"})
    except Exception as e:
        print("  FAIL", uid, e); continue
    print("  " + "=" * 66)
    print("  uid:", uid, " page len:", len(page))
    for pat in _JSON_FIELD_PATTERNS:
        hits = pat.findall(page)
        if hits:
            lens = sorted((len(_to_plain(h)), i) for i, h in enumerate(hits))[-3:]
            print(f"    JSON {pat.pattern[:36]!r}: {len(hits)} hits, top lens={[l for l,_ in lens]}")
            for l, i in lens[-1:]:
                print("        longest head:", repr(_to_plain(hits[i])[:200]))
    dom = _dom_slice(page)
    print("    DOM slice len:", len(dom), "head:", repr(dom[:160]))
    print("    final extract_jd len:", len(extract_jd(page)))
    fin = extract_jd(page)
    print("    final tail:", repr(fin[-220:]))

print()
print("### D. 关键词污染计数（全库 JD 里出现多少次样板词）###")
allrows = store.query_jobs(limit=5000)
cnt = {}
for r in allrows:
    jd = r.get("jd") or ""
    for kw in ["校园招聘", "公众号运营", "招聘", "关注我们", "版权所有", "友情链接", "热门职位", "相似职位", "你可能喜欢"]:
        if kw in jd:
            cnt[kw] = cnt.get(kw, 0) + 1
print("  含 JD 的岗位数:", sum(1 for r in allrows if r.get("jd")))
print("  污染词出现岗位数:", cnt)
