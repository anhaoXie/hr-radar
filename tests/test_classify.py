# -*- coding: utf-8 -*-
"""行业分类回归测试：重点防 ASCII 关键词子串误命中（community/unity、window/wind…）。"""
import io, os, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from radar.industries import classify_industry
from radar.pipeline import classify_job

fails = []

# (说明, 标题/JD文本, 平台行业标签, 期望行业 id)
CASES = [
    ("英文 community 不应命中 unity", "Senior React Developer on our community platform", "", "internet"),
    ("opportunity 不应命中 unity", "A great opportunity to grow", "", "internet"),
    ("window 不应命中 Wind", "Window cleaning technician", "", "internet"),
    ("said/email 不应命中 ai", "We said email available", "", "internet"),
    ("真实 Unity 岗", "Unity引擎开发工程师", "", "gaming"),
    ("真实游戏策划", "游戏策划（二次元）", "", "gaming"),
    ("真实 Wind 终端", "风控建模，使用Wind数据终端", "", "finance"),
    ("平台粗标签：产品经理", "产品经理", "互联网/游戏/软件", "internet"),
    ("平台粗标签+精确岗位：大模型算法", "大模型算法工程师", "互联网/游戏/软件", "ai"),
    ("平台精确标签优先：汽车电子", "汽车电子工程师", "汽车/新能源车", "auto"),
    ("平台精确标签优先：审计", "审计助理", "会计/审计", "accounting"),
    ("半导体工艺", "半导体工艺工程师", "", "electronics"),
    ("注册结构工程师", "注册结构工程师", "", "construction"),
    ("幼儿园教师", "幼儿园教师", "", "education"),
    ("执业律师", "执业律师", "", "legal"),
    ("直播运营", "直播运营专员", "", "retail"),
]

for label, text, src, want in CASES:
    got = classify_job(text, "", src)
    ok = got == want
    if not ok:
        fails.append(label)
    print(("  OK   " if ok else "  FAIL ") + f"{label}: {got}" + ("" if ok else f" (期望 {want})"))

# 直接调 classify_industry 时也应正确（不含平台标签覆盖逻辑）
for label, text, src, want in [("直接分类：community", "our community platform", "", "internet"),
                               ("直接分类：Unity", "Unity引擎开发", "", "gaming")]:
    got = classify_industry(text, src)
    ok = got == want
    if not ok:
        fails.append(label)
    print(("  OK   " if ok else "  FAIL ") + f"{label}: {got}" + ("" if ok else f" (期望 {want})"))

print()
print("失败项:", fails if fails else "无 ✅")
sys.exit(1 if fails else 0)
