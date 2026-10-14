# -*- coding: utf-8 -*-
"""职业规划引擎：能力差距诊断、学习路径、岗位匹配、面试准备、风险提示、方向测评。

设计直接对着调研出来的大学生求职痛点：
  * 67.06% 认为"求职目标不明确" → direction_survey() 方向测评 + career_timeline()
  * 50.84% 认为"简历不过关"     → match_jobs() 岗位匹配度 + 关键词覆盖诊断
  * 50.54% 认为"不了解岗位"     → 真实 JD 聚合画像 + 岗位要求可视化
  * 49.95/49.46% 面试紧张/表达差 → interview_prep() 高频题 + 模拟练习清单
  * 57.1% 用人单位看重实践经验  → learning path 里每个技能都给出"可写进简历的产出物"
  * 实习与专业不对口            → major_fit() 专业对口度
  * 实习权益受侵害              → risk_flags() 岗位风险提示
"""
from __future__ import annotations

import re

from . import analyzer, industries, store
from .skills import canonical, skill_category
from .textutil import clean_text

# ---------------------------------------------------------------------------
# 无实时数据时的行业技能先验（会在界面上明确标注"先验，未校准"）
# ---------------------------------------------------------------------------
PRIOR_SKILLS: dict[str, list[tuple[str, float]]] = {
    "internet": [("Python", 1.0), ("SQL", .9), ("Java", .85), ("Git", .8), ("数据结构与算法", .8),
                 ("Linux", .75), ("MySQL", .7), ("Redis", .65), ("Docker", .65), ("沟通表达", .6)],
    "ai": [("Python", 1.0), ("PyTorch", .95), ("机器学习", .95), ("深度学习", .9), ("大模型", .9),
           ("自然语言处理", .75), ("计算机视觉", .7), ("RAG", .65), ("SQL", .65), ("模型部署", .6)],
    "finance": [("Excel", .95), ("财务分析", .9), ("风险管理", .75), ("SQL", .7), ("投资分析", .7),
                ("Python", .65), ("估值建模", .6), ("Wind", .6), ("沟通表达", .8), ("CFA", .5)],
    "insurance": [("保险业务", .9), ("风险管理", .8), ("沟通表达", .85), ("Excel", .8),
                  ("销售技巧", .7), ("数据分析", .6), ("法律文书", .5)],
    "accounting": [("Excel", .95), ("会计核算", .9), ("审计", .85), ("财务分析", .85), ("财务报表", .8),
                   ("CPA", .65), ("税务", .65), ("PPT", .7), ("沟通表达", .7)],
    "education": [("教学能力", .9), ("教师资格证", .8), ("课程设计", .8), ("沟通表达", .9),
                  ("学生管理", .7), ("Office办公", .7), ("新媒体运营", .5)],
    "healthcare": [("临床试验", .8), ("GMP", .7), ("细胞培养", .7), ("PCR", .7), ("药品注册", .6),
                   ("数据分析", .6), ("英语", .7), ("沟通表达", .7)],
    "electronics": [("模拟电路", .9), ("PCB设计", .85), ("Altium Designer", .8), ("单片机", .8),
                    ("嵌入式C", .8), ("FPGA", .7), ("硬件调试", .7), ("Python", .6), ("MATLAB", .6)],
    "machinery": [("SolidWorks", .9), ("AutoCAD", .9), ("机械设计", .9), ("PLC", .75),
                  ("机械结构设计", .75), ("CATIA", .6), ("ANSYS", .6), ("项目管理", .6)],
    "auto": [("CAN总线", .8), ("嵌入式C", .8), ("汽车电子", .8), ("电机控制", .75),
             ("CATIA", .7), ("AutoCAD", .7), ("MATLAB", .7), ("智能驾驶", .6)],
    "energy": [("AutoCAD", .8), ("化工工艺", .8), ("电力系统", .75), ("Aspen Plus", .7),
               ("光伏", .65), ("储能", .6), ("MATLAB", .6), ("数据分析", .6)],
    "construction": [("AutoCAD", .95), ("Revit", .85), ("BIM", .8), ("广联达", .8),
                     ("工程造价", .75), ("PKPM", .7), ("施工管理", .7), ("项目管理", .7)],
    "retail": [("Excel", .9), ("数据分析", .85), ("电商运营", .8), ("沟通表达", .8),
               ("SQL", .7), ("用户运营", .7), ("新媒体运营", .7)],
    "fmcg": [("销售技巧", .85), ("品牌营销", .8), ("市场调研", .75), ("Excel", .8),
             ("沟通表达", .85), ("渠道管理", .7), ("商务谈判", .7)],
    "media": [("文案写作", .9), ("Premiere", .85), ("短视频制作", .85), ("Photoshop", .8),
              ("新媒体运营", .85), ("After Effects", .7), ("摄影摄像", .6)],
    "logistics": [("供应链管理", .85), ("Excel", .9), ("物流管理", .8), ("数据分析", .75),
                  ("ERP", .7), ("采购管理", .65), ("沟通表达", .75)],
    "telecom": [("计算机网络", .85), ("C", .75), ("Python", .7), ("Linux", .7),
                ("服务器运维", .6), ("网络安全", .6)],
    "legal": [("法律文书", .9), ("法律职业资格", .85), ("尽职调查", .8), ("合规管理", .75),
              ("诉讼仲裁", .7), ("公文写作", .8), ("英语", .7)],
    "government": [("公文写作", .9), ("Office办公", .85), ("沟通表达", .85), ("数据分析", .6),
                   ("法律文书", .5), ("英语", .6)],
    "gaming": [("C#", .9), ("C++", .8), ("3D建模", .75), ("Blender", .7), ("动效设计", .6),
               ("交互设计", .55), ("Python", .6)],
    "agriculture": [("数据分析", .6), ("质量管理", .7), ("供应链管理", .6), ("沟通表达", .7),
                    ("Excel", .7), ("市场调研", .6)],
    "tourism": [("沟通表达", .9), ("英语", .8), ("商务谈判", .6), ("市场调研", .6),
                ("Office办公", .7), ("新媒体运营", .6)],
    "defense": [("MATLAB", .8), ("C++", .8), ("ANSYS", .65), ("嵌入式C", .7), ("Python", .7),
                ("项目管理", .7)],
    "environment": [("环保工程", .85), ("安全工程", .75), ("双碳与ESG", .7), ("GIS与遥感", .65),
                    ("分析化学", .65), ("数据分析", .65)],
    "textile": [("品牌设计", .7), ("设计规范", .7), ("质量管理", .75), ("供应链管理", .7),
                ("采购管理", .65), ("Excel", .7)],
    "metallurgy": [("材料工程", .9), ("分析化学", .75), ("质量管理", .75), ("安全工程", .65),
                   ("AutoCAD", .65), ("ANSYS", .6)],
    "professional": [("沟通表达", .9), ("招聘", .8), ("Excel", .8), ("PPT", .8),
                     ("结构化思维", .7), ("商务谈判", .7), ("英语", .7)],
}

# 技能 -> 怎么学 / 用什么产出物证明（用来对付"缺乏实践经验"这一首要痛点）
_CATEGORY_ACTIONS: dict[str, dict] = {
    "编程语言": {"learn": ["语法过一遍后立刻动手写，不要只看视频", "刷 100 道算法题练边界处理与复杂度",
                        "读一个开源项目源码，提一个真实的 PR"],
               "prove": "一个带 README、能跑起来的 GitHub 仓库（哪怕只有 300 行）"},
    "前端开发": {"learn": ["用框架从零做一个有 3 个页面的站点", "学一遍浏览器渲染与性能优化基础"],
               "prove": "一个部署到公网、能打开链接直接体验的前端项目"},
    "后端开发": {"learn": ["写一个带登录、分页、权限的完整接口服务", "学一遍数据库索引与慢查询排查"],
               "prove": "接口文档 + 压测数据 + 部署说明"},
    "移动端开发": {"learn": ["做一个能装到手机上的完整小 App", "走一遍打包上架流程（或 TestFlight）"],
                 "prove": "可安装的安装包/体验链接 + 功能演示录屏"},
    "数据库": {"learn": ["用真实数据练窗口函数、多表关联、执行计划分析", "做一次索引优化前后对比"],
             "prove": "一份 SQL 优化案例：原始查询 → 执行计划 → 优化后耗时对比"},
    "大数据": {"learn": ["搭一套本地伪分布式环境跑通一条数据链路", "写几个真实的 ETL 任务"],
             "prove": "一个端到端数据管道 + 数据量与耗时说明"},
    "云计算与运维": {"learn": ["用容器把项目部署一次", "配一次监控告警并真的触发它"],
                   "prove": "部署文档 + 监控截图 + 一次故障复盘"},
    "DevOps与工程效能": {"learn": ["给项目配一条 CI 流水线", "把构建/测试/发布自动化起来"],
                       "prove": "流水线配置 + 构建耗时与失败率改善数据"},
    "测试与质量": {"learn": ["给一个真实项目补单元测试与接口自动化用例", "做一次缺陷跟踪全流程"],
                 "prove": "测试用例集 + 覆盖率报告 + 一份缺陷分析"},
    "人工智能与机器学习": {"learn": ["跟完一门体系课并复现 baseline", "在 Kaggle/天池打一次比赛",
                              "学会读论文并复现关键模块"],
                       "prove": "Notebook + 实验对比表，写清你改了什么、指标提升多少"},
    "大模型与AIGC": {"learn": ["搭一个 RAG 知识库问答并接入你自己的资料", "跑一次 LoRA 微调并对比效果",
                            "把提示词工程当成可实验的工程问题来调优"],
                   "prove": "一个能用的 AI 应用链接 + 效果评测表（准确率/幻觉率对比）"},
    "数据分析与BI": {"learn": ["用真实数据集做一次完整分析闭环", "练一套指标体系设计方法",
                           "学 A/B 测试的统计学原理"],
                  "prove": "一份 5 页内的分析报告：问题→数据→结论→行动建议"},
    "产品经理": {"learn": ["拆解 10 个你常用产品的功能与交互", "写 3 份完整 PRD 与原型",
                       "做一次用户访谈并整理成结论"],
               "prove": "作品集：需求文档 + 原型 + 上线后数据反馈（哪怕是自己的小产品）"},
    "运营": {"learn": ["自己开一个账号从 0 做到 1000 粉", "跑一次小额投放并复盘 ROI",
                     "搭建一次私域或活动转化链路"],
             "prove": "增长数据截图 + 复盘文档（这是运营岗最硬的凭证）"},
    "设计": {"learn": ["临摹 20 个优秀界面", "完整走一遍调研→原型→视觉→交付的流程",
                     "学一遍设计规范与组件化"],
             "prove": "站酷/Behance 作品集，3 个以上完整项目"},
    "金融与财会": {"learn": ["用上市公司年报做一次三张表分析与估值", "读 5 份券商深度报告并写摘要",
                        "熟悉核心会计准则或从业资格考试科目"],
                "prove": "自己搭的估值模型 Excel + 投资/财务分析报告"},
    "市场营销与销售": {"learn": ["写一份完整营销策划案", "跑一次真实小额投放或真实销售拜访",
                          "做一次竞品与市场调研"],
                    "prove": "策划案 + 投放/销售数据复盘"},
    "人力资源": {"learn": ["用真实 JD 做岗位画像与人才画像", "模拟组织一次校园招聘或面试评估"],
               "prove": "一套招聘方案 + 面试评估表 + 自己做过的候选人沟通记录"},
    "硬件与制造": {"learn": ["画一块最小系统板并打样", "用示波器/逻辑分析仪调试一次真实波形",
                        "完整做一个零件的三维建模并出工程图"],
                 "prove": "打样实物照片 + 原理图/模型文件 + 调试记录"},
    "土木建筑与能源化工": {"learn": ["建一个完整 BIM 模型并算一次工程量", "跟一个真实施工/工艺现场",
                              "熟悉本专业核心规范条文"],
                       "prove": "模型文件 + 工程量成果表 + 现场实习记录"},
    "生物医药与临床": {"learn": ["熟悉 GCP/GLP 规范", "跟一次实验或临床全流程并写规范记录",
                            "学会用脚本处理实验数据"],
                    "prove": "规范的实验/临床记录 + 数据处理脚本 + 结果图"},
    "供应链与物流": {"learn": ["用真实数据做一次库存或运输优化测算", "跑通一次采购到交付的全流程"],
                   "prove": "优化前后对比：成本/时效/周转率改善数字"},
    "法律与咨询": {"learn": ["精读 20 份真实判决书或合同", "做一次完整的尽职调查或案例分析",
                         "练结构化表达与 PPT 汇报"],
                 "prove": "一份法律意见书/尽调报告/案例分析（脱敏后可作为作品）"},
    "教育与传媒": {"learn": ["完整设计并试讲一节课，或用镜头讲清一件事", "剪一条 3 分钟的成片",
                         "拆解 10 个高传播内容的结构"],
                 "prove": "试讲录像/成片链接 + 数据反馈（播放、完播、转化）"},
    "语言与通用职业能力": {"learn": ["每天精读 1 篇外刊或专业材料", "做 20 次英文/公开专业问答练习",
                              "在社团或课程作业里主动承担项目管理角色"],
                    "prove": "四六级/雅思托福成绩，或一段英文专业汇报视频 + 一段可量化的组织经历"},
    "AI工具素养": {"learn": ["把 AI 工具真正接进你的学习和产出流程", "对比不同工具在同一任务上的效果差异",
                          "学会给 AI 写结构化、可复用的提示词"],
                "prove": "一份『我用 AI 把某件事效率提升 X 倍』的说明 + 产出样例"},
    "网络安全与合规": {"learn": ["在授权靶场完成一套渗透测试流程", "学一遍等级保护/数据安全合规要点",
                            "写一次完整的漏洞报告"],
                    "prove": "靶场通关记录 + 规范漏洞报告（注意：只做授权测试）"},
}
_GENERIC_ACTION = {"learn": ["找 1 门体系课系统学一遍", "找 1 个真实小项目动手做出来"],
                   "prove": "一个可展示的成果（代码/报告/作品/证书）"}

_RISK_KEYWORDS = [
    (r"押金|保证金|垫付|服装费|体检费|培训费|工本费", "出现『先交钱』类字眼", "极高"),
    (r"日结|当天结|刷单|打字员|录入员|兼职刷", "疑似虚假兼职/刷单岗", "极高"),
    (r"无需经验|零基础|包吃住|轻松月入|高薪急聘|月入过万", "过度承诺型话术", "高"),
    (r"包分配|保证录用|内推名额|买简历", "疑似付费内推/简历买卖", "高"),
    (r"微信联系|加QQ|私下联系|扫码加", "绕过平台私下联系", "中"),
]
_NORMAL_INTERN_DAY_MIN, _NORMAL_INTERN_DAY_MAX = 50, 600

# 伞形技能：市场榜单里经常出现的上位概念。如果学生已经填了下位技能，
# 就不应该再被判成「缺这个上位技能」——否则会出现「你已会大模型，但仍显示缺人工智能」
# 这种明显不合理的结论。只在学生侧做归并，岗位侧不动
#（岗位要求 PyTorch，不能因为学生会「人工智能」就算命中）。
UMBRELLA_SKILLS: dict[str, set[str]] = {
    "人工智能": {"机器学习", "深度学习", "大模型", "自然语言处理", "计算机视觉", "语音识别",
              "推荐算法", "强化学习", "知识图谱", "多模态", "AI Agent", "RAG", "Prompt工程",
              "模型微调", "PyTorch", "TensorFlow", "Scikit-learn", "OpenCV", "YOLO",
              "特征工程", "模型调优", "模型部署", "LangChain", "Hugging Face", "大模型应用开发"},
    "机器学习": {"深度学习", "PyTorch", "TensorFlow", "Scikit-learn", "特征工程", "模型调优",
              "强化学习", "推荐算法", "计算机视觉", "自然语言处理", "多模态"},
    "深度学习": {"PyTorch", "TensorFlow", "计算机视觉", "自然语言处理", "多模态", "模型微调", "CUDA"},
    "数据分析": {"SQL", "Excel", "Tableau", "Power BI", "FineBI", "Pandas", "NumPy", "统计学",
              "A/B测试", "指标体系", "数据可视化", "SPSS", "数据挖掘", "用户画像", "数据埋点",
              "商业分析", "数据仓库"},
    "前端开发": {"HTML", "CSS", "React", "Vue", "Angular", "Next.js", "TypeScript",
              "JavaScript", "微信小程序", "uni-app", "Ant Design", "Element UI"},
    "后端开发": {"Java", "Spring", "Spring Boot", "Spring Cloud", "Django", "Flask", "FastAPI",
              "Node.js", "Go", "微服务", "RESTful API", "gRPC", "MyBatis", ".NET", "Express"},
    "产品规划": {"需求分析", "原型设计", "PRD文档", "竞品分析", "用户研究", "产品迭代",
              "B端产品", "C端产品", "Axure", "数据驱动", "商业化"},
    "项目管理": {"敏捷开发", "Jira", "Trello", "Scrum", "DevOps", "CI/CD"},
    "英语": {"CET-4", "CET-6", "雅思", "托福", "商务英语", "翻译", "小语种", "日语"},
    "沟通表达": {"团队协作", "商务谈判", "销售技巧", "公关", "采访编辑", "播音主持", "学生管理"},
    "Office办公": {"Excel", "PPT", "公文写作"},
    "云计算与运维": {"Linux", "Docker", "Kubernetes", "云原生", "阿里云", "腾讯云", "华为云",
                "AWS", "Azure", "GCP", "Nginx", "监控告警", "Serverless"},
    "数据库": {"SQL", "MySQL", "PostgreSQL", "Oracle", "SQL Server", "MongoDB", "Redis",
             "Elasticsearch", "数据库优化", "数据库设计"},
}


def resolve_umbrella(my: dict) -> tuple[dict, dict]:
    """把下位技能归并到伞形技能上。返回 (归并后的技能表, {伞形技能: 提供依据的下位技能})。"""
    out = dict(my)
    credited: dict[str, list[str]] = {}
    for parent, children in UMBRELLA_SKILLS.items():
        vals = [(c, my[c]) for c in children if c in my]
        if not vals:
            continue
        best = max(v for _, v in vals)
        if best > out.get(parent, 0.0):
            out[parent] = best
            if parent not in my:
                credited[parent] = [c for c, _ in sorted(vals, key=lambda kv: -kv[1])[:4]]
    return out, credited


# ---------------------------------------------------------------------------
# 1. 方向测评：把兴趣/性格倾向映射到行业
# ---------------------------------------------------------------------------
DIMENSIONS = [
    ("data", "和数据、逻辑打交道", "喜欢从数字里找规律、做推理"),
    ("people", "和人打交道", "喜欢沟通、说服、协调、带团队"),
    ("build", "动手做出实物/系统", "喜欢把东西真正造出来、跑起来"),
    ("create", "创意与表达", "喜欢写作、设计、内容创作"),
    ("order", "规则与流程", "喜欢清晰规范、稳定可预期的环境"),
    ("research", "钻研与研究", "喜欢深挖原理、长期研究一个问题"),
]

_INDUSTRY_AFFINITY: dict[str, dict[str, float]] = {
    "internet":    {"data": .8, "build": .9, "order": .5, "people": .4, "create": .4, "research": .5},
    "ai":          {"data": .9, "research": 1.0, "build": .8, "order": .4, "people": .3, "create": .4},
    "finance":     {"data": 1.0, "order": .8, "people": .6, "research": .6, "build": .2, "create": .2},
    "insurance":   {"people": .9, "order": .7, "data": .7, "research": .4, "create": .3, "build": .2},
    "accounting":  {"data": .9, "order": 1.0, "people": .5, "research": .4, "build": .1, "create": .2},
    "education":   {"people": 1.0, "create": .6, "order": .6, "data": .4, "research": .5, "build": .2},
    "healthcare":  {"research": .9, "order": .8, "people": .7, "data": .6, "build": .3, "create": .2},
    "electronics": {"build": .95, "research": .8, "data": .7, "order": .7, "people": .3, "create": .3},
    "machinery":   {"build": 1.0, "order": .8, "data": .6, "research": .5, "people": .4, "create": .3},
    "auto":        {"build": .95, "research": .7, "data": .7, "order": .7, "people": .4, "create": .4},
    "energy":      {"build": .8, "order": .8, "research": .7, "data": .6, "people": .4, "create": .2},
    "construction": {"build": .9, "order": .85, "data": .6, "people": .5, "research": .4, "create": .3},
    "retail":      {"people": .85, "data": .8, "create": .7, "order": .6, "build": .2, "research": .3},
    "fmcg":        {"people": .9, "create": .8, "data": .7, "order": .6, "research": .4, "build": .2},
    "media":       {"create": 1.0, "people": .7, "data": .5, "order": .3, "research": .4, "build": .3},
    "logistics":   {"order": .9, "data": .8, "people": .6, "build": .4, "research": .3, "create": .2},
    "telecom":     {"build": .85, "research": .7, "data": .7, "order": .7, "people": .4, "create": .3},
    "legal":       {"order": .9, "research": .85, "people": .6, "create": .6, "data": .5, "build": .1},
    "government":  {"order": 1.0, "people": .8, "create": .5, "data": .6, "research": .5, "build": .2},
    "agriculture": {"build": .7, "research": .7, "order": .6, "people": .5, "data": .6, "create": .2},
    "tourism":     {"people": 1.0, "create": .7, "order": .5, "data": .4, "research": .3, "build": .3},
    "gaming":      {"create": .95, "build": .85, "data": .6, "research": .5, "people": .4, "order": .4},
    "defense":     {"research": .9, "build": .85, "order": .8, "data": .6, "people": .3, "create": .2},
    "environment": {"research": .8, "build": .7, "order": .75, "data": .7, "people": .5, "create": .2},
    "textile":     {"create": .8, "build": .6, "order": .7, "people": .5, "data": .5, "research": .3},
    "metallurgy":  {"build": .85, "research": .8, "order": .7, "data": .6, "people": .3, "create": .2},
    "professional": {"people": .95, "data": .75, "order": .6, "create": .6, "research": .5, "build": .2},
}


def direction_survey(scores: dict) -> dict:
    """scores: {dimension_key: 0..5}。返回最匹配的行业排序与理由。"""
    if not scores:
        return {"ok": False, "message": "请先完成测评"}
    ranked = []
    for ind in industries.INDUSTRIES:
        aff = _INDUSTRY_AFFINITY.get(ind["id"])
        if not aff:
            continue
        num = den = 0.0
        detail = []
        for key, w in aff.items():
            v = float(scores.get(key, 0) or 0)
            num += v * w
            den += 5.0 * w
            detail.append((key, v, w))
        score = num / den * 100 if den else 0
        ranked.append({
            "industry_id": ind["id"],
            "industry_name": ind["name"],
            "score": round(score, 1),
            "majors": industries.majors_for(ind["id"])[:6],
            "why": _survey_reason(detail, ind["name"]),
        })
    ranked.sort(key=lambda x: -x["score"])
    return {"ok": True, "ranked": ranked[:8], "dimensions": DIMENSIONS}


def _survey_reason(detail, name: str) -> str:
    top = sorted(detail, key=lambda d: -d[1] * d[2])[:2]
    label = {k: lab for k, lab, _ in DIMENSIONS}
    if not top:
        return f"与{name}的岗位要求匹配度一般"
    return (f"你在「{'、'.join(label.get(k, k) for k, _, _ in top)}」上的倾向，"
            f"正好是{name}岗位日常最主要的工作方式。")


# ---------------------------------------------------------------------------
# 2. 分年级时间线：直接治"不知道该干什么"
# ---------------------------------------------------------------------------
TIMELINE = {
    "大一": [
        ("搞清楚方向，而不是急着实习", ["做完本工具的方向测评", "和 3 位学长学姐聊他们现在做什么",
                                    "把专业课学扎实（GPA 是很多企业的隐形门槛）"]),
        ("开始积累可写进简历的东西", ["加入 1 个能真正做事的社团或实验室", "学 1 门硬技能到能做出小作品",
                                 "英语四六级尽早过"]),
    ],
    "大二": [
        ("补技能 + 做第一个项目", ["按本工具的『学习路径』补齐 3-5 个高频技能",
                              "做 1 个能放进作品集的项目", "把项目写成 STAR 结构写进简历草稿"]),
        ("拿到第一段实践经历", ["尝试远程实习/校园大使/助研", "用本工具监控目标行业的岗位关键词变化",
                          "开始记录自己的技能清单，每学期更新一次"]),
    ],
    "大三": [
        ("冲刺高含金量实习（最关键的一年）", ["提前 3-4 个月开始投递（暑期实习通常在前一年冬天开抢）",
                                      "用本工具的『岗位匹配度』筛掉简历关就会被刷的岗位",
                                      "针对每个岗位做 JD 关键词覆盖检查"]),
        ("把经历变成故事", ["至少完成 1 段对口实习", "针对目标岗位练 20 次模拟面试",
                       "建立 3 个版本的简历（技术/产品/综合）"]),
    ],
    "大四": [
        ("多线程推进，别把鸡蛋放一个篮子", ["秋招 + 考公/考研/留学并行准备", "用本工具持续监控补录与春招岗位",
                                     "维护一份投递台账，记录每家进度与复盘"]),
        ("收口与决策", ["对比 offer 时把『行业岗位量趋势』作为参考（本工具的趋势页可直接看）",
                    "签三方前确认岗位内容、薪资结构、违约金条款"]),
    ],
    "研究生": [
        ("用研究能力换职业筹码", ["把研究方向往目标行业的技术栈上靠", "把论文/项目翻译成业务价值的表达",
                            "补足工程落地能力（很多科研强的同学卡在这里）"]),
        ("精准投递", ["用本工具确认目标岗位的硬技能清单，逐项对齐", "准备 2 段深度项目讲述"]),
    ],
}


def career_timeline(grade: str) -> dict:
    key = grade if grade in TIMELINE else "大三"
    return {"grade": key, "stages": [{"title": t, "actions": a} for t, a in TIMELINE[key]],
            "all_grades": list(TIMELINE.keys())}


# ---------------------------------------------------------------------------
# 3. 能力差距诊断（核心）
# ---------------------------------------------------------------------------
def _market_requirements(industry_id: str, city: str, days: int | None, top_n: int) -> tuple[dict, list, str]:
    a = analyzer.analyze(industry_id=industry_id, city=city, days=days, top_n=top_n)
    skills = a.get("skills") or []
    if skills:
        top_share = skills[0]["share"] or 1.0
        req = {}
        for s in skills:
            req[s["name"]] = {
                "level": round(min(5.0, s["share"] / top_share * 5.0), 2),
                "share": s["share"], "count": s["count"],
                "category": s["category"], "demand": s["demand"],
            }
        return req, skills, "live"

    prior = PRIOR_SKILLS.get(industry_id) or []
    if not prior:
        prior = PRIOR_SKILLS["internet"]
    req = {}
    skills = []
    for name, w in prior:
        c = canonical(name) or name
        req[c] = {"level": round(w * 5.0, 2), "share": round(w * 100, 1), "count": 0,
                  "category": skill_category(c), "demand": 1.0}
        skills.append({"name": c, "share": round(w * 100, 1), "count": 0,
                       "category": skill_category(c), "demand": 1.0, "score": round(w * 100, 1)})
    return req, skills, "prior"


def diagnose(profile: dict, industry_id: str = "all", city: str = "全国",
             days: int | None = None, top_n: int = 22) -> dict:
    """核心诊断：我的技能 vs 市场要求 -> 匹配度 / 差距 / 学习路径。"""
    my_raw = profile.get("skills") or {}
    my: dict[str, float] = {}
    for k, v in my_raw.items():
        c = canonical(clean_text(k)) or clean_text(k)
        try:
            lv = float(v)
        except (TypeError, ValueError):
            lv = 0.0
        if c and lv > 0:
            my[c] = max(my.get(c, 0.0), min(5.0, lv))
    my, umbrella_credited = resolve_umbrella(my)

    req, market_skills, data_source = _market_requirements(industry_id, city, days, top_n)
    my_skills_display = list(my_raw.keys()) or list(my.keys())

    # --- 匹配度：市场要求的技能里，我覆盖了多少（按需求强度加权）---------
    num = den = 0.0
    radar = []
    gaps = []
    strengths = []
    for name, info in req.items():
        need = info["level"]
        have = my.get(name, 0.0)
        covered = min(have, need)
        num += covered * info["demand"]
        den += need * info["demand"]
        radar.append({"skill": name, "market": round(need, 2), "me": round(have, 2),
                      "category": info["category"]})
        if need - have >= 0.8:
            gap = need - have
            priority = gap * info["demand"] * (1 + info["share"] / 100.0)
            gaps.append({
                "skill": name, "category": info["category"],
                "market_level": round(need, 2), "my_level": round(have, 2),
                "gap": round(gap, 2), "market_share": info["share"],
                "priority": round(priority, 2),
                "in_market_top": any(s["name"] == name for s in market_skills[:12]),
            })
        elif have >= need and need > 0:
            strengths.append({"skill": name, "my_level": round(have, 2),
                              "market_level": round(need, 2)})

    match_score = round(num / den * 100, 1) if den else 0.0
    gaps.sort(key=lambda g: -g["priority"])

    # --- 我有但市场没要求的技能（可能是差异化优势，也可能是方向偏了）-----
    extra = [s for s in my_skills_display if s not in req]

    # --- 学历/岗位硬门槛检查 ---------------------------------------------
    hard_checks = _hard_checks(profile, industry_id, city, days)

    return {
        "ok": True,
        "data_source": data_source,
        "data_note": ("匹配度基于实时抓取的真实岗位数据计算" if data_source == "live"
                      else "当前行业库里还没有真实岗位数据，匹配度基于内置行业技能先验估算；"
                           "请先到「实时刷新」抓一次数据以获得校准结果"),
        "industry_id": industry_id,
        "industry_name": industries.industry_name(industry_id) if industry_id not in ("all", "") else "全部行业",
        "city": city,
        "profile": {"major": profile.get("major", ""), "grade": profile.get("grade", ""),
                    "target_job": profile.get("target_job", ""),
                    "skill_count": len(my)},
        "match_score": match_score,
        "market_skill_count": len(req),
        "umbrella_credited": umbrella_credited,
        "radar": radar[:top_n],
        "gaps": gaps[:14],
        "strengths": strengths[:12],
        "extra_skills": extra[:20],
        "learning_path": _learning_path(gaps, profile),
        "hard_checks": hard_checks,
        "timeline": career_timeline(profile.get("grade") or "大三"),
        "major_fit": major_fit(profile, industry_id),
        "summary": _diagnose_summary(match_score, gaps, strengths, industry_id),
    }


def _diagnose_summary(score: float, gaps: list, strengths: list, industry_id: str) -> str:
    name = industries.industry_name(industry_id) if industry_id not in ("all", "") else "目标行业"
    if score >= 75:
        base = f"你和{name}岗位的要求已经很接近了（匹配度 {score}%），重点是把经历讲清楚。"
    elif score >= 50:
        base = f"你有一定基础（匹配度 {score}%），但还有明显缺口，补齐 2-3 个高频技能就能过简历关。"
    elif score > 0:
        base = f"目前匹配度 {score}%，缺口比较集中——这其实是好事，说明提升路径很清晰。"
    else:
        base = "你还没有填写技能，先把会的填进去，诊断才有意义。"
    if gaps:
        top = "、".join(g["skill"] for g in gaps[:3])
        base += f" 最该先补的三项：{top}。"
    if strengths:
        base += f" 已经有优势的是：{'、'.join(s['skill'] for s in strengths[:3])}。"
    return base


def _learning_path(gaps: list, profile: dict) -> dict:
    """按优先级分三阶段，每个技能给「怎么学」+「拿什么证明」。"""
    phases = [
        {"key": "now", "title": "立刻开始（0-4 周）", "desc": "投简历前就能补上、性价比最高的部分"},
        {"key": "mid", "title": "1-3 个月", "desc": "决定你能不能过技术面/专业面的硬技能"},
        {"key": "long", "title": "3-6 个月", "desc": "拉开差距、支撑长期职业发展的能力"},
    ]
    buckets = [[], [], []]
    for i, g in enumerate(gaps):
        buckets[0 if i < 4 else (1 if i < 9 else 2)].append(g)

    out_phases = []
    for ph, items in zip(phases, buckets):
        tasks = []
        for g in items:
            act = _CATEGORY_ACTIONS.get(g["category"], _GENERIC_ACTION)
            tasks.append({
                "skill": g["skill"],
                "category": g["category"],
                "why": f"市场 {g['market_share']}% 的岗位要求它，你目前自评 {g['my_level']}/5",
                "learn": act["learn"],
                "prove": act["prove"],
                "project": _project_idea(g["skill"], g["category"], profile),
            })
        out_phases.append({**ph, "tasks": tasks})
    return {"phases": out_phases,
            "advice": "每个技能都要落到一个『能给别人看的东西』上——这是解决『缺乏实践经验』最直接的办法。"}


def _project_idea(skill: str, category: str, profile: dict) -> str:
    job = profile.get("target_job") or "目标岗位"
    templates = {
        "编程语言": f"用 {skill} 写一个解决你身边真实小问题的工具（比如课表提醒、成绩分析），推到 GitHub",
        "前端开发": f"用 {skill} 做一个部署上线、能直接打开链接体验的站点",
        "后端开发": f"用 {skill} 写一个带登录和权限的完整接口服务，附接口文档",
        "移动端开发": f"用 {skill} 做一个能装到手机上的小 App，录一段演示",
        "数据库": f"用 {skill} 对一个真实数据集做查询优化，记录优化前后耗时",
        "大数据": f"用 {skill} 搭一条从采集到分析的数据链路，记录数据量",
        "云计算与运维": f"用 {skill} 把项目部署上线并配好监控告警",
        "DevOps与工程效能": f"用 {skill} 给一个项目配自动化流水线，统计构建耗时变化",
        "测试与质量": f"用 {skill} 给一个真实项目补测试用例，输出覆盖率报告",
        "人工智能与机器学习": f"用 {skill} 复现一个小模型并写清实验对比，最好用你专业的真实数据",
        "大模型与AIGC": f"用 {skill} 做一个能用的 AI 小应用（比如你专业资料的知识库问答），并做效果评测",
        "数据分析与BI": f"找一份你专业相关的公开数据，用 {skill} 做完整分析并输出 5 页报告",
        "产品经理": f"选一个你常用的产品，用 {skill} 相关方法写一份改进 PRD 与原型",
        "运营": f"自己运营一个账号或社群，用 {skill} 相关方法做一次从 0 到 1 的增长实验",
        "设计": f"用 {skill} 完整做一个项目（调研→原型→视觉），放进作品集",
        "金融与财会": f"挑一家上市公司，用 {skill} 做分析或估值并写清逻辑",
        "市场营销与销售": f"用 {skill} 相关方法为一个小品牌写完整方案并做小成本验证",
        "人力资源": f"用 {skill} 相关方法做一份岗位画像+人才画像，附面试评估表",
        "硬件与制造": f"用 {skill} 画一块最小系统板/做一个零件并打样，记录调试过程",
        "土木建筑与能源化工": f"用 {skill} 建一个完整模型并输出工程量或工艺参数表",
        "生物医药与临床": f"用 {skill} 相关方法完成一次规范实验并写记录",
        "供应链与物流": f"用 {skill} 对一个真实场景做优化测算，给出成本/时效改善数字",
        "法律与咨询": f"用 {skill} 相关方法写一份法律意见书/尽调报告/案例分析",
        "教育与传媒": f"用 {skill} 完整设计并试讲一节课，或剪一条 3 分钟成片",
        "语言与通用职业能力": f"用 {skill} 做一次英文专业汇报（录成 3 分钟视频）或一次可量化的组织经历",
        "AI工具素养": f"用 {skill} 相关工具重做一件你以前做过的事，量化效率提升",
        "网络安全与合规": f"在授权靶场用 {skill} 相关方法完成一次测试并写规范报告",
    }
    return templates.get(category, f"围绕 {skill} 做一个和「{job}」相关的小项目，产出可展示的成果")


def _hard_checks(profile: dict, industry_id: str, city: str, days: int | None) -> list[dict]:
    """简历关上最容易直接被刷掉的几条硬门槛。"""
    checks: list[dict] = []
    degree = profile.get("degree") or profile.get("expected_degree") or ""
    dist = store.counts_by("degree", industry_id, days, 10)
    if dist:
        total = sum(n for _, n in dist) or 1
        unnamed_map = {k: v for k, v in dist}
        if degree:
            ok = sum(v for k, v in unnamed_map.items()
                     if _degree_ok(degree, k)) / total
            checks.append({
                "name": "学历门槛", "pass": ok >= 0.5,
                "detail": f"{ok * 100:.0f}% 的岗位接受「{degree}」，"
                          f"分布：{'、'.join(f'{k} {v * 100 // total}%' for k, v in dist[:4])}",
                "fix": "" if ok >= 0.5 else "优先投『学历不限/大专』标签的岗位，或补充作品集抵消学历劣势",
            })
        else:
            checks.append({"name": "学历门槛", "pass": True,
                           "detail": "岗位学历分布：" +
                                     "、".join(f"{k} {v * 100 // total}%" for k, v in dist[:4]),
                           "fix": ""})

    major = profile.get("major") or ""
    mf = major_fit(profile, industry_id)
    if major:
        checks.append({
            "name": "专业对口", "pass": mf["fit_level"] != "低",
            "detail": mf["message"], "fix": mf["advice"],
        })

    exp = profile.get("experiences") or []
    checks.append({
        "name": "实习/项目经历", "pass": bool(exp),
        "detail": (f"已填写 {len(exp)} 段经历" if exp
                   else "还没填写任何实习或项目经历——用人单位中 59.6% 会首先看这个（浙江省统计局数据）"),
        "fix": "" if exp else "先去「学习路径」里挑 1 个项目做出来，哪怕是自己做的也算经历",
    })
    return checks


def _degree_ok(mine: str, required: str) -> bool:
    order = ["不限", "高中", "中专", "大专", "本科", "硕士", "博士"]
    try:
        return order.index(mine) >= order.index(required)
    except ValueError:
        return True


# ---------------------------------------------------------------------------
# 4. 专业对口度
# ---------------------------------------------------------------------------
def major_fit(profile: dict, industry_id: str) -> dict:
    major = clean_text(profile.get("major"))
    target_job = clean_text(profile.get("target_job"))
    majors = industries.majors_for(industry_id)
    if not major:
        return {"fit_level": "未知", "matched": [], "suggested": majors[:8],
                "message": "未填写专业，无法判断对口度。", "advice": ""}
    matched = [m for m in majors if m and (m in major or major in m)]
    if not matched:
        # 关键词宽松匹配
        for m in majors:
            for token in re.findall(r"[\u4e00-\u9fa5A-Za-z]{2,}", m):
                if token and token in major:
                    matched.append(m)
                    break
    if matched:
        level = "高"
        msg = f"你的专业「{major}」与{industries.industry_name(industry_id)}高度对口（匹配：{'、'.join(matched[:4])}）。"
        advice = "对口是优势，但别只靠专业——用人单位仍会优先看你有没有把专业知识用出来的实践经历。"
    else:
        rel = [m for m in majors if m][:8]
        level = "低"
        msg = (f"你的专业「{major}」不在{industries.industry_name(industry_id)}的常见对口专业里"
               f"（常见：{'、'.join(rel[:5])}）。")
        advice = ("跨专业完全可以，但要用『项目+作品』补上可信度：先做 1 个该行业的小项目，"
                  "再在简历里用『可迁移能力』（数据分析、沟通、项目管理）搭桥。"
                  "注意：调查显示超半数学生的实习与专业不挂钩，这类实习对就业能力提升有限，"
                  "所以宁可少而精，选一个真正对口或可迁移的岗位。")
    if target_job:
        msg += f" 目标岗位：{target_job}。"
    return {"fit_level": level, "matched": matched, "suggested": majors[:10],
            "message": msg, "advice": advice}


# ---------------------------------------------------------------------------
# 5. 岗位匹配：把真实岗位按学生画像打分
# ---------------------------------------------------------------------------
def match_jobs(profile: dict, industry_id: str = "all", city: str = "全国",
               days: int | None = None, limit: int = 30, keyword: str = "") -> dict:
    my_raw = profile.get("skills") or {}
    my = {}
    for k, v in my_raw.items():
        c = canonical(clean_text(k)) or clean_text(k)
        try:
            lv = float(v)
        except (TypeError, ValueError):
            lv = 0.0
        if c and lv > 0:
            my[c] = max(my.get(c, 0.0), min(5.0, lv))
    # 学生侧做伞形归并（会 PyTorch 就不算「缺人工智能」）；岗位侧不动
    my, _ = resolve_umbrella(my)

    rows = store.query_jobs(industry_id=industry_id, city=city, days=days,
                            keyword=keyword, limit=1500)
    if not rows:
        return {"ok": False, "message": "库里还没有岗位数据，请先到「实时刷新」抓取。", "jobs": []}

    scored = []
    for r in rows:
        job_skills = set(r.get("skills") or [])
        # 技能少于 2 项的岗位样本太薄，算出来的匹配度会虚高，直接跳过
        if len(job_skills) < 2:
            continue
        hit = [s for s in job_skills if s in my]
        miss = [s for s in job_skills if s not in my]
        overlap = len(hit) / len(job_skills)
        # 学历
        deg_ok = _degree_ok(profile.get("degree") or "本科", r.get("degree") or "不限")
        score = overlap * 78 + (12 if deg_ok else 0)
        score += 6 if (profile.get("city_pref") and r.get("city") == profile.get("city_pref")) else 0
        score += 4 if len(hit) >= 3 else 0
        scored.append({
            "score": round(min(100.0, score), 1),
            "title": r.get("title"), "company": r.get("company"), "city": r.get("city"),
            "salary_raw": r.get("salary_raw"), "degree": r.get("degree"),
            "job_type": r.get("job_type"), "source": r.get("source"), "url": r.get("url"),
            "industry_id": r.get("industry_id"),
            "hit": hit[:12], "miss": miss[:12],
            "overlap": round(overlap * 100, 1),
            "evidence": len(job_skills),
            "degree_ok": deg_ok,
            "reason": _match_reason(hit, miss, deg_ok, overlap, len(job_skills)),
            "jd_excerpt": (r.get("jd") or "")[:300],
        })
    scored.sort(key=lambda x: (-x["score"], -x["evidence"]))
    return {"ok": True, "jobs": scored[:limit], "scanned": len(rows),
            "matched_pool": len(scored),
            "advice": "投递优先级：命中技能多、缺失技能少、学历符合的岗位，过简历关的概率最高。"}


def _match_reason(hit, miss, deg_ok, overlap, evidence=0) -> str:
    parts = []
    if hit:
        parts.append(f"你会的 {'、'.join(hit[:4])} 正好是它的要求")
    if miss:
        parts.append(f"但它还要求 {'、'.join(miss[:3])}，简历里最好补上相关经历")
    if not deg_ok:
        parts.append("学历要求可能高于你当前学历，建议谨慎投递")
    if overlap >= 0.6:
        parts.append("整体匹配度高，值得优先投")
    elif overlap <= 0.2:
        parts.append("匹配度偏低，投了大概率卡在简历关")
    if evidence and evidence < 4:
        parts.append(f"注意：该 JD 只识别出 {evidence} 项技能，匹配度参考价值有限")
    return "；".join(parts) if parts else "岗位技能要求不明确，建议先看 JD 原文"


# ---------------------------------------------------------------------------
# 6. 面试准备
# ---------------------------------------------------------------------------
def interview_prep(industry_id: str = "all", city: str = "全国", target_job: str = "",
                   days: int | None = None, top_n: int = 12) -> dict:
    a = analyzer.analyze(industry_id=industry_id, city=city, days=days, top_n=top_n)
    skills = [s["name"] for s in (a.get("skills") or [])]
    common = [s["name"] for s in (a.get("skills") or [])[:6]]
    job = target_job or "该岗位"

    technical = [{
        "q": f"请介绍一个你用 {s} 做过的项目，重点说你的具体动作和最终结果。",
        "why": f"{s} 在 {a['job_count']} 条岗位样本里出现频率很高，几乎必问。",
        "how": "用 STAR：背景→你的任务→你做了哪三步→量化结果（数字优先）。不要背模板，面试官能听出来。",
    } for s in common]

    behavioral = [
        {"q": "你为什么选择这个行业/这个岗位？", "why": "企业在意的『动机维度』，也是学生思维和职场思维差距最大的地方。",
         "how": "讲行业理解 + 个人经历的交点，别只说『我很感兴趣』。可以引用你在这类工具里看到的行业趋势。"},
        {"q": "你最大的缺点是什么？", "why": "考的是自我认知，不是让你自夸。",
         "how": "说一个真实但可改进的点 + 你正在怎么改。避开岗位核心能力。"},
        {"q": "讲一次你和别人意见不合最后怎么解决的。", "why": "考团队协作与沟通，49.46% 的受访者认为表达沟通是求职失败主因。",
         "how": "体现你倾听→找共同目标→推进落地的过程。"},
        {"q": "你对我们公司/这个业务了解多少？", "why": "信息差最容易在这里暴露。",
         "how": "面试前查 3 件事：公司主营、最近一条新闻、这个岗位在业务链条里的位置。"},
        {"q": "你还有什么想问我们的？", "why": "反问是加分项。",
         "how": "问『这个岗位前三个月最重要的产出是什么』『团队现在最大的挑战是什么』。"},
    ]
    if "实习" in job or industry_id in ("internet", "ai"):
        technical.append({
            "q": "如果给你一个真实业务问题，你会怎么拆解？",
            "why": "考察结构化思维，是区分『背题的』和『真做过的』的关键题。",
            "how": "先澄清目标与约束，再拆成 2-3 个可验证的子问题，最后说验证方式。"})

    checklist = [
        "用本工具的『岗位匹配度』筛出 5 个最匹配的岗位，逐条抄下它们的技能要求",
        "针对每个岗位做一次 JD 关键词覆盖检查：简历里有没有出现这些词",
        "准备 3 个可讲 3 分钟的项目故事（STAR 结构），其中至少 1 个带量化结果",
        "对着镜子或录屏做 5 次自我介绍，控制在 90 秒内",
        "把『面试太紧张』拆掉：提前查清路线/平台、提前 10 分钟到、准备 2 句开场缓冲话术",
        "准备 3 个反问问题和一个 30 秒的收尾总结",
        "面试后 24 小时内写复盘：被问到什么、答得不好的是什么、下次怎么改",
    ]
    return {
        "ok": True,
        "job_count": a.get("job_count", 0),
        "target_job": job,
        "technical": technical,
        "behavioral": behavioral,
        "checklist": checklist,
        "note": ("题目的技能部分来自实时抓取的高频要求" if a.get("job_count")
                 else "当前没有实时数据，题目来自该行业的通用技能先验"),
        "evidence": "中国青年报×粉笔对北京 10 所高校 1011 名受访者的调查显示："
                    "分别有 63.8%、60.73%、55.49% 的受访者认为『参加模拟面试』"
                    "『参考他人成功经验』『刷题』最能提升求职成功率。",
    }


# ---------------------------------------------------------------------------
# 7. 岗位风险提示（实习权益）
# ---------------------------------------------------------------------------
def risk_flags(job: dict) -> list[dict]:
    text = " ".join([clean_text(job.get("title")), clean_text(job.get("jd")),
                     clean_text(job.get("company"))])
    flags: list[dict] = []
    for pat, desc, level in _RISK_KEYWORDS:
        if re.search(pat, text):
            flags.append({"level": level, "desc": desc,
                          "advice": "优先在平台内沟通与投递，任何要求先付款、私下转账的都要停下来核实。"})
    unit = job.get("pay_unit")
    lo, hi = job.get("pay_min"), job.get("pay_max")
    vals = [v for v in (lo, hi) if isinstance(v, (int, float))]
    if unit == "day" and vals:
        avg = sum(vals) / len(vals)
        if avg < _NORMAL_INTERN_DAY_MIN:
            flags.append({"level": "中", "desc": f"日薪偏低（约 ¥{avg:.0f}/天），低于常见实习水平",
                          "advice": "可以先确认工作内容是否与专业相关，低薪且打杂的实习对就业能力帮助有限。"})
        elif avg > _NORMAL_INTERN_DAY_MAX:
            flags.append({"level": "中", "desc": f"日薪偏高（约 ¥{avg:.0f}/天），请注意核实岗位真实性",
                          "advice": "高薪实习常被用作引流。核实公司主体、办公地点，别交任何费用。"})
    if not clean_text(job.get("company")):
        flags.append({"level": "高", "desc": "岗位没有显示公司名称",
                      "advice": "无法核实雇主主体的岗位风险较高，建议避开。"})
    if not clean_text(job.get("jd")):
        flags.append({"level": "低", "desc": "岗位缺少详细 JD",
                      "advice": "投递前主动问清工作内容、带教安排、时长与结算方式。"})
    if not flags:
        flags.append({"level": "低", "desc": "未发现明显风险信号",
                      "advice": "仍然建议：签实习协议、保留沟通记录、明确薪资结算方式与离职条款。"})
    return flags


def risk_guide() -> dict:
    return {
        "title": "实习权益自查清单",
        "items": [
            "投递前后任何环节要求交押金、培训费、服装费、体检费的，一律拒绝",
            "要求加私人微信/QQ 绕过平台沟通、或让你先垫付的，高度警惕",
            "入职前确认是否需要签实习协议，明确实习期、薪资、结算日、工作时长",
            "保留所有聊天记录、offer 截图、考勤记录，出现纠纷时是唯一凭证",
            "警惕『日结高薪』『无需经验月入过万』类话术，正规实习不会这样描述",
            "确认办公地点是真实企业地址，面试尽量选择白天、公共场所或线上",
            "校内就业中心、学校校企合作项目、官方平台（如国家大学生就业服务平台）优先级更高",
        ],
        "source": "依据清华大学教育研究院李锋亮教授关于大学生实习权益受侵害问题的分析整理",
    }
