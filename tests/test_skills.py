# -*- coding: utf-8 -*-
"""技能抽取回归测试：重点防跨行业误判。"""
import io, os, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from radar.skills import extract_skills

# (说明, 文本, 必须包含, 必须不包含)
CASES = [
    ("中文办公软件", "熟练使用PPT，Excel，Word等办公软件", ["Office办公"], []),
    ("英文按字数计酬", "Writers are paid on a per-word basis. $20 per 100 words", [], ["Office办公"]),
    ("英文办公场所", "Home office or a quiet place to work", [], ["Office办公"]),
    ("时薪写法", "Typical rates: $120-$170/hr Remote", [], ["人力资源"]),
    ("HR 岗位", "HR manager，负责招聘与薪酬绩效", ["人力资源"], []),
    ("泛指增长", "high-growth companies that value growth and autonomy", [], ["用户增长"]),
    ("用户增长", "负责用户增长与增长运营", ["用户增长"], []),
    ("AI Agent 语境", "跟踪大模型、AI Agent、RAG 等前沿技术", ["AI Agent", "大模型", "RAG"], []),
    ("房产销售代理", "We are hiring a real estate sales agent in Chicago", [], ["AI Agent"]),
    ("产品方案设计", "参与产品方案设计、撰写需求文档", [], ["建筑设计"]),
    ("建筑方案设计", "负责建筑方案设计与施工图设计", ["建筑设计"], []),
    ("量化评估（动词）", "跟进业务规则调整对核心指标的影响，量化评估变更效果", [], ["量化投资"]),
    ("量化投研（真实）", "量化研究实习（投研） 私募基金 因子挖掘", ["量化投资"], []),
    ("React 不等于 R", "React开发工程师", ["React"], ["R"]),
    ("Google Cloud 不等于 Go", "使用Google Cloud平台", ["GCP"], ["Go"]),
    ("边界回归", "reactor 与 reactive 编程", [], ["R", "React"]),
    ("C 系列", "C语言与C++、C#", ["C", "C++", "C#"], []),
    ("JavaScript 不等于 Java", "JavaScript开发", ["JavaScript"], []),
    ("Node.js", "Node.js 与 nodejs 后端", ["Node.js"], []),
    ("大模型长 JD", "使用PyTorch做LoRA微调，搭建RAG向量数据库，掌握Prompt工程与LangChain",
     ["PyTorch", "模型微调", "RAG", "向量数据库", "Prompt工程", "LangChain"], []),
    # JD 自述型用语不应被当成技能要求
    ("招聘要求（自述）", "招聘要求：1、数学、计算机等相关专业；2、熟悉Python", ["Python"], ["招聘"]),
    ("现招实习生（自述）", "鉴于工作发展需要，现特招聘实习生，招聘条件如下", [], ["招聘"]),
    ("招聘领域大模型（真实）", "负责招聘领域大模型的后训练（SFT/RL）", ["大模型", "招聘"], []),
    ("招聘专员（真实）", "协助招聘专员完成招聘渠道维护与简历筛选", ["招聘"], []),
    ("五险一金（福利）", "福利：五险一金、带薪年假、节日福利", [], ["社保公积金"]),
    ("社保办理（真实）", "负责社保公积金的办理与缴纳", ["社保公积金"], []),
    ("薪酬优厚（福利）", "薪酬优厚，提供免费班车", [], ["薪酬绩效"]),
]

fails = []
for label, text, must, mustnot in CASES:
    got = extract_skills(text)
    miss = [m for m in must if m not in got]
    bad = [m for m in mustnot if m in got]
    if miss or bad:
        fails.append(label)
    print(("  OK   " if not (miss or bad) else "  FAIL ") + f"{label}: {got}")
    if miss:
        print(f"         缺少 {miss}")
    if bad:
        print(f"         误判 {bad}")

print()
print("失败项:", fails if fails else "无 ✅")
sys.exit(1 if fails else 0)
