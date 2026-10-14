# -*- coding: utf-8 -*-
"""单元测试：薪资解析 + 实习僧 JD 抽取。"""
import io, os, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from radar.textutil import parse_salary, _norm_unit
from radar.sources.shixiseng import extract_jd
from radar import http

fails = []


def check(name, got, want):
    ok = got == want
    if not ok:
        fails.append(name)
    print(("  OK   " if ok else "  FAIL ") + name + f"  got={got!r}" + ("" if ok else f" want={want!r}"))


print("### 单位识别 ###")
for u, w in [("day", "day"), ("month", "month"), ("year", "year"), ("hour", "hour"),
             ("annual", "year"), ("Hourly", "hour"), ("/天", "day"), ("元/天", "day"),
             ("/月", "month"), ("年薪", "year"), ("/年", "year"), ("", "unknown")]:
    check(f"_norm_unit({u!r})", _norm_unit(u), w)

print()
print("### 薪资解析 ###")


def mm(raw):
    r = parse_salary(raw)
    return None if not r else (r["min"], r["max"], r["unit"], r["currency"], r["month_min"], r["month_max"])


check("'300-500元/天'", mm("300-500元/天"), (300.0, 500.0, "day", "CNY", 6525.0, 10875.0))
check("dict day 200-300", mm({"min": 200, "max": 300, "unit": "day", "currency": "CNY"}),
      (200.0, 300.0, "day", "CNY", 4350.0, 6525.0))
check("dict year 10875-320000 USD",
      mm({"min": 10875, "max": 320000, "unit": "year", "currency": "USD"}),
      (10875.0, 320000.0, "year", "USD", 906.25, 26666.67))
check("'8-12K'", mm("8-12K"), (8000.0, 12000.0, "month", "CNY", 8000.0, 12000.0))
check("'1.5-2万/月'", mm("1.5-2万/月"), (15000.0, 20000.0, "month", "CNY", 15000.0, 20000.0))
check("'$120,000 - $160,000'", mm("$120,000 - $160,000"),
      (120000.0, 160000.0, "year", "USD", 10000.0, 13333.33))
check("'20k-40k/月'", mm("20k-40k/月"), (20000.0, 40000.0, "month", "CNY", 20000.0, 40000.0))
check("'15-25万/年'", mm("15-25万/年"), (150000.0, 250000.0, "year", "CNY", 12500.0, 20833.33))
check("'OTE $25k - $35k'", mm("OTE $25k - $35k"), (25000.0, 35000.0, "year", "USD", 2083.33, 2916.67))
check("'6000元/月'", mm("6000元/月"), (6000.0, 6000.0, "month", "CNY", 6000.0, 6000.0))
check("'面议' 标记为可议价", mm("面议"), (None, None, "unknown", "CNY", None, None))
check("'300元/天'", mm("300元/天"), (300.0, 300.0, "day", "CNY", 6525.0, 6525.0))
r13 = parse_salary("1.5-2万/月·13薪")
print("  13薪 months_per_year =", r13["months_per_year"], "(期望 13)")
if r13["months_per_year"] != 13:
    fails.append("13薪")

print()
print("### 实习僧 JD 抽取（真实页面）###")
for uid in ["inn_gfnbdfmmpht1", "inn_zuene9iqfsmh", "inn_h79rkwack5mk", "inn_shfozmuxfnhm", "inn_mz8b1aexey65"]:
    try:
        page = http.get_text(f"https://www.shixiseng.com/intern/{uid}",
                             headers={"Referer": "https://www.shixiseng.com/interns"})
        jd = extract_jd(page)
    except Exception as e:
        print(f"  {uid}: 抓取失败 {e}")
        continue
    dirty = [k for k in ("版权所有", "ICP备", "关于我们", "客户服务", "经营资质", "加入我们") if k in jd]
    print(f"  {uid}: len={len(jd)} 污染={dirty or '无'}")
    print("      head:", repr(jd[:150]))
    print("      tail:", repr(jd[-130:]))
    if dirty:
        fails.append("JD污染 " + uid)
    if len(jd) < 60:
        fails.append("JD过短 " + uid)

print()
print("失败项:", fails if fails else "无 ✅")
