# -*- coding: utf-8 -*-
"""行业知识库（纯标准库，无第三方依赖）。

用于「大学生行业 HR 需求雷达 + 职业规划」工具：
  * INDUSTRIES         : 中国就业市场主流行业（27 个）
  * INDUSTRY_BY_ID     : id -> 行业 dict
  * classify_industry  : 依据招聘平台行业标签 / 岗位标题 / JD 判断行业
  * industry_name / majors_for / all_industries

字段说明：
  id            行业英文 id（前端路由、缓存键用）
  name          行业中文名
  keywords      匹配招聘平台自带行业标签的关键词（子串匹配）
  job_keywords  匹配岗位名称 / JD 正文的关键词
  major_hint    对口专业（供职业规划使用）
"""

from __future__ import annotations

import re

__all__ = [
    "INDUSTRIES",
    "INDUSTRY_BY_ID",
    "DEFAULT_INDUSTRY_ID",
    "classify_industry",
    "industry_name",
    "majors_for",
    "job_keywords",
    "all_industries",
]

INDUSTRIES: list = [
    {
        "id": "internet",
        "name": "互联网/软件",
        "keywords": ["互联网", "软件", "it服务", "信息技术", "计算机软件", "saas",
                     "云计算", "系统集成", "网络科技", "互联网服务"],
        "job_keywords": ["后端开发", "前端开发", "java开发", "python开发", "运维工程师",
                         "测试工程师", "软件开发", "架构师", "技术总监", "程序员",
                         "全栈", "it支持", "系统工程师", "小程序"],
        "major_hint": ["计算机科学与技术", "软件工程", "网络工程", "信息管理与信息系统",
                       "数据科学与大数据技术", "物联网工程"],
    },
    {
        "id": "ai",
        "name": "人工智能",
        "keywords": ["人工智能", "ai", "机器学习", "深度学习", "大模型", "智能算法",
                     "计算机视觉", "智能科技"],
        "job_keywords": ["算法工程师", "机器学习工程师", "算法研究员", "nlp",
                         "计算机视觉工程师", "大模型", "推荐算法", "数据科学家",
                         "ai工程师", "自动驾驶算法"],
        "major_hint": ["人工智能", "计算机科学与技术", "自动化", "数学与应用数学",
                       "统计学", "电子信息工程", "智能科学与技术"],
    },
    {
        "id": "finance",
        "name": "金融/银行证券",
        "keywords": ["银行", "证券", "基金", "信托", "金融", "期货", "投资", "券商",
                     "资产管理", "融资租赁", "小额贷款", "交易所", "金融科技"],
        "job_keywords": ["客户经理", "信贷", "风控", "研究员", "交易员", "理财经理",
                         "柜员", "投行", "并购", "量化", "风险管理", "投资顾问",
                         "金融科技"],
        "major_hint": ["金融学", "金融工程", "经济学", "会计学", "统计学",
                       "财务管理", "国际经济与贸易"],
    },
    {
        "id": "insurance",
        "name": "保险",
        "keywords": ["保险", "财险", "寿险", "再保险", "保险经纪", "保险代理",
                     "保险公估"],
        "job_keywords": ["核保", "理赔", "保险销售", "精算", "保险产品", "保险代理人",
                         "续期管理", "保险内勤"],
        "major_hint": ["保险学", "金融学", "精算学", "经济学", "统计学", "临床医学"],
    },
    {
        "id": "accounting",
        "name": "会计审计/咨询",
        "keywords": ["会计", "审计", "税务", "会计师事务所", "管理咨询", "战略咨询",
                     "财务咨询", "资产评估", "咨询"],
        "job_keywords": ["会计师", "审计师", "税务师", "咨询顾问", "财务经理", "出纳",
                         "财务分析", "评估师", "税务专员", "审计助理", "管理咨询顾问"],
        "major_hint": ["会计学", "财务管理", "审计学", "财政学", "工商管理", "经济学"],
    },
    {
        "id": "education",
        "name": "教育培训",
        "keywords": ["教育", "培训", "学校", "k12", "在线教育", "职业培训", "留学",
                     "早教", "教育科技"],
        "job_keywords": ["教师", "讲师", "教研", "课程顾问", "教务", "班主任", "培训师",
                         "助教", "辅导老师", "留学顾问", "校长"],
        "major_hint": ["教育学", "汉语言文学", "英语", "数学与应用数学", "应用心理学",
                       "学前教育", "小学教育"],
    },
    {
        "id": "healthcare",
        "name": "医疗健康/生物医药",
        "keywords": ["医疗", "医药", "生物", "制药", "健康", "医院", "医疗器械",
                     "基因", "生物科技", "药品", "诊断"],
        "job_keywords": ["医生", "护士", "药师", "临床", "医药代表", "注册专员",
                         "临床监查员", "医学检验", "生物信息", "药品研发", "qc", "qa"],
        "major_hint": ["临床医学", "药学", "生物技术", "生物医学工程", "护理学",
                       "医学检验技术", "制药工程"],
    },
    {
        "id": "electronics",
        "name": "电子/半导体/硬件",
        "keywords": ["电子", "半导体", "芯片", "集成电路", "硬件", "元器件", "光电",
                     "显示", "pcb", "传感器", "消费电子"],
        "job_keywords": ["硬件工程师", "电子工程师", "嵌入式", "pcb", "版图", "模拟电路",
                         "数字电路", "射频工程师", "ic设计", "验证工程师", "封装测试",
                         "半导体工艺", "晶圆"],
        "major_hint": ["电子信息工程", "微电子科学与工程", "电子科学与技术",
                       "集成电路设计与集成系统", "通信工程", "自动化"],
    },
    {
        "id": "machinery",
        "name": "机械制造/自动化",
        "keywords": ["机械", "制造", "工业自动化", "装备", "机床", "重工", "机电",
                     "仪器仪表", "机器人"],
        "job_keywords": ["机械工程师", "结构工程师", "工艺工程师", "plc", "电气工程师",
                         "设备工程师", "数控", "装配", "质量工程师", "售后服务工程师"],
        "major_hint": ["机械设计制造及其自动化", "机械工程", "材料成型及控制工程",
                       "电气工程及其自动化", "工业工程", "测控技术与仪器"],
    },
    {
        "id": "auto",
        "name": "汽车/新能源车",
        "keywords": ["汽车", "新能源车", "新能源汽车", "整车", "汽车零部件", "自动驾驶",
                     "车联网", "主机厂", "动力电池"],
        "job_keywords": ["汽车工程师", "电控", "整车", "底盘", "车身", "adas",
                         "智能驾驶", "三电", "标定", "汽车电子", "试验工程师", "bms"],
        "major_hint": ["车辆工程", "汽车服务工程", "机械工程", "电气工程及其自动化",
                       "自动化", "能源与动力工程"],
    },
    {
        "id": "energy",
        "name": "能源电力/化工",
        "keywords": ["能源", "电力", "化工", "石油", "燃气", "煤炭", "石化", "新能源",
                     "光伏", "储能", "电网", "环保能源"],
        "job_keywords": ["电气工程师", "化工工艺", "热能", "光伏", "储能", "运行值班",
                         "仪表工程师", "安全工程师", "电力工程师", "反应工程"],
        "major_hint": ["电气工程及其自动化", "能源与动力工程", "化学工程与工艺",
                       "应用化学", "新能源科学与工程", "自动化"],
    },
    {
        "id": "construction",
        "name": "建筑/房地产",
        "keywords": ["建筑", "房地产", "施工", "设计院", "建材", "市政", "装饰", "监理",
                     "工程造价", "物业", "土木"],
        "job_keywords": ["结构工程师", "建筑师", "施工员", "预算员", "造价工程师", "监理",
                         "土建", "给排水", "暖通", "资料员", "地产开发", "项目管理",
                         "注册结构"],
        "major_hint": ["土木工程", "建筑学", "工程管理", "工程造价",
                       "给排水科学与工程", "建筑环境与能源应用工程", "测绘工程"],
    },
    {
        "id": "retail",
        "name": "消费零售/电商",
        "keywords": ["零售", "电商", "电子商务", "商贸", "连锁", "超市", "百货",
                     "跨境电商", "消费品", "新零售"],
        "job_keywords": ["电商运营", "店长", "招商", "商品运营", "零售运营", "客服",
                         "仓储", "渠道", "直播运营", "买手"],
        "major_hint": ["市场营销", "电子商务", "工商管理", "国际经济与贸易",
                       "物流管理", "汉语言文学"],
    },
    {
        "id": "fmcg",
        "name": "快消/食品饮料",
        "keywords": ["快消", "快速消费品", "食品", "饮料", "日化", "乳业", "酒业", "粮油",
                     "调味品", "fmcg", "个护"],
        "job_keywords": ["销售代表", "品牌经理", "城市经理", "督导", "品控", "食品研发",
                         "渠道拓展", "经销商"],
        "major_hint": ["市场营销", "食品科学与工程", "工商管理", "生物工程", "化学",
                       "广告学"],
    },
    {
        "id": "media",
        "name": "文化传媒/广告",
        "keywords": ["传媒", "广告", "文化", "影视", "媒体", "公关", "出版", "新闻",
                     "mcn", "短视频"],
        "job_keywords": ["编辑", "记者", "文案", "策划", "剪辑", "编导", "摄影", "主播",
                         "媒介投放", "公关专员"],
        "major_hint": ["新闻学", "传播学", "广告学", "汉语言文学", "广播电视编导",
                       "数字媒体艺术"],
    },
    {
        "id": "logistics",
        "name": "物流/供应链",
        "keywords": ["物流", "供应链", "运输", "仓储", "快递", "货运", "航运", "港口",
                     "冷链", "国际货运"],
        "job_keywords": ["物流专员", "供应链专员", "仓管", "关务", "调度", "运力", "单证",
                         "货代", "采购专员"],
        "major_hint": ["物流管理", "供应链管理", "交通运输", "国际经济与贸易", "工商管理"],
    },
    {
        "id": "telecom",
        "name": "通信",
        "keywords": ["通信", "运营商", "电信", "移动通信", "光通信", "5g", "通信设备",
                     "网络通信"],
        "job_keywords": ["通信工程师", "网络优化", "核心网", "基站", "传输", "无线",
                         "光网络", "售前工程师", "射频"],
        "major_hint": ["通信工程", "电子信息工程", "信息工程", "网络工程",
                       "电子科学与技术"],
    },
    {
        "id": "legal",
        "name": "法律",
        "keywords": ["法律", "律所", "律师事务所", "法律服务", "知识产权服务", "司法"],
        "job_keywords": ["律师", "法务", "法律顾问", "实习律师", "专利代理", "诉讼",
                         "法律助理", "合规专员"],
        "major_hint": ["法学", "知识产权", "社会学", "政治学与行政学"],
    },
    {
        "id": "government",
        "name": "政府/公共事业",
        "keywords": ["政府", "公共事业", "事业单位", "国企", "水务", "公用", "社会组织",
                     "非营利", "公务员"],
        "job_keywords": ["公务员", "事业编", "行政", "党务", "社区工作者", "窗口服务",
                         "公共管理", "选调生"],
        "major_hint": ["行政管理", "公共事业管理", "政治学与行政学", "法学", "社会学",
                       "汉语言文学"],
    },
    {
        "id": "agriculture",
        "name": "农业",
        "keywords": ["农业", "农资", "种业", "畜牧", "养殖", "林业", "渔业", "农产品",
                     "饲料", "园艺"],
        "job_keywords": ["农艺师", "养殖技术员", "兽医", "植保", "育种", "饲料销售",
                         "农产品品控"],
        "major_hint": ["农学", "园艺", "动物科学", "动物医学", "植物保护",
                       "农业经济管理", "食品科学与工程"],
    },
    {
        "id": "tourism",
        "name": "旅游酒店",
        "keywords": ["旅游", "酒店", "住宿", "餐饮", "景区", "民宿", "旅行", "文旅",
                     "航空服务"],
        "job_keywords": ["导游", "酒店管理", "前台", "客房", "餐厅", "旅游顾问", "票务",
                         "管培生", "收益管理"],
        "major_hint": ["旅游管理", "酒店管理", "会展经济与管理", "英语", "汉语言文学"],
    },
    {
        "id": "gaming",
        "name": "游戏/动漫",
        "keywords": ["游戏", "动漫", "动画", "二次元", "电竞", "漫画", "游戏开发"],
        "job_keywords": ["游戏策划", "原画", "游戏开发", "unity", "ue4", "数值策划",
                         "角色设计", "游戏运营", "关卡设计", "游戏美术"],
        "major_hint": ["数字媒体技术", "数字媒体艺术", "动画", "计算机科学与技术",
                       "视觉传达设计", "美术学"],
    },
    {
        "id": "defense",
        "name": "军工/航天",
        "keywords": ["军工", "航天", "航空", "兵器", "船舶", "国防", "卫星", "雷达",
                     "科研院所"],
        "job_keywords": ["总体设计", "制导", "雷达", "仿真", "试验工程师", "总装",
                         "保密管理", "研究所", "飞行器"],
        "major_hint": ["飞行器设计与工程", "航空航天工程", "探测制导与控制技术",
                       "自动化", "电子信息工程", "材料科学与工程"],
    },
    {
        "id": "environment",
        "name": "环境/环保",
        "keywords": ["环保", "环境", "固废", "节能", "生态", "碳", "环境监测", "水处理"],
        "job_keywords": ["环保工程师", "环境工程", "水处理", "环评", "检测工程师",
                         "碳管理", "采样员", "环保咨询"],
        "major_hint": ["环境工程", "环境科学", "给排水科学与工程", "化学工程与工艺",
                       "生态学"],
    },
    {
        "id": "textile",
        "name": "纺织服装",
        "keywords": ["纺织", "服装", "服饰", "鞋帽", "箱包", "家纺", "面料"],
        "job_keywords": ["服装设计", "打版", "面料", "跟单", "生产管理", "质检", "陈列",
                         "买手", "样衣工"],
        "major_hint": ["服装设计与工程", "纺织工程", "轻化工程", "视觉传达设计",
                       "市场营销"],
    },
    {
        "id": "metallurgy",
        "name": "冶金/材料",
        "keywords": ["冶金", "钢铁", "金属", "材料", "矿业", "有色", "水泥", "玻璃",
                     "陶瓷", "新材料"],
        "job_keywords": ["材料工程师", "冶金工程师", "热处理", "铸造", "焊接", "材料研发",
                         "工艺工程师"],
        "major_hint": ["材料科学与工程", "冶金工程", "金属材料工程",
                       "无机非金属材料工程", "化学工程与工艺"],
    },
    {
        "id": "professional",
        "name": "专业服务",
        "keywords": ["专业服务", "人力资源服务", "猎头", "检测认证", "翻译服务",
                     "商务服务", "外包服务", "咨询外包"],
        "job_keywords": ["猎头顾问", "招聘顾问", "招聘专员", "人事专员", "认证工程师",
                         "翻译", "外包专员", "检测工程师", "评审员", "咨询顾问"],
        "major_hint": ["人力资源管理", "英语", "工商管理", "行政管理", "翻译",
                       "商务英语"],
    },
]

INDUSTRY_BY_ID: dict = {ind["id"]: ind for ind in INDUSTRIES}
DEFAULT_INDUSTRY_ID: str = "internet"

_KEYWORD_WEIGHT = 1
_JOB_KEYWORD_WEIGHT = 3
_SOURCE_KEYWORD_WEIGHT = 3
_SOURCE_JOB_KEYWORD_WEIGHT = 1


def _norm(value) -> str:
    return str(value or "").strip().lower()


def _is_ascii(term: str) -> bool:
    return all(ord(ch) < 128 for ch in term)


# 纯 ASCII 关键词必须按词边界匹配，否则会出现严重误判：
#   'unity' 命中 comm**unity** / opport**unity**
#   'ai'    命中 s**ai**d / em**ai**l / av**ai**lable
#   'wind'  命中 **wind**ow
# 边界额外排除连字符和斜杠（'pcb' 不应命中 'pcb-board' 之外的写法差异）。
_ASCII_TERM_RE: dict = {}


def _ascii_re(term: str):
    r = _ASCII_TERM_RE.get(term)
    if r is None:
        body = re.escape(term)
        if term and term[-1].isalpha():
            body += "s?"
        r = re.compile(r"(?<![A-Za-z.\-/])" + body + r"(?![A-Za-z])")
        _ASCII_TERM_RE[term] = r
    return r


def _term_score(text: str, terms: list, weight: int) -> int:
    """按命中关键词长度加权计分（长关键词更具区分度，如 '新能源汽车' > '汽车'）。

    中文关键词走子串匹配；纯 ASCII 关键词走词边界匹配，避免 community/unity
    这类子串误命中。
    """
    score = 0
    for term in terms:
        term = _norm(term)
        if not term:
            continue
        if _is_ascii(term):
            hit = _ascii_re(term).search(text) is not None
        else:
            hit = term in text
        if hit:
            score += max(len(term), 2) * weight
    return score


def classify_industry(text: str, source_industry: str = "") -> str:
    """返回行业 id。

    source_industry 是招聘平台自带的行业字符串，优先用它映射；
    text 是岗位标题 / JD 正文；都识别不到时返回 DEFAULT_INDUSTRY_ID。
    """
    src = _norm(source_industry)
    if src:
        for ind in INDUSTRIES:  # 平台行业标签与行业名完全一致时直接命中
            if _norm(ind["name"]) == src:
                return ind["id"]
        best_id, best_score = "", 0
        for ind in INDUSTRIES:
            score = (_term_score(src, ind["keywords"], _SOURCE_KEYWORD_WEIGHT)
                     + _term_score(src, ind["job_keywords"], _SOURCE_JOB_KEYWORD_WEIGHT))
            if score > best_score:
                best_id, best_score = ind["id"], score
        if best_id:
            return best_id

    body = _norm(text)
    if body:
        best_id, best_score = "", 0
        for ind in INDUSTRIES:
            score = (_term_score(body, ind["job_keywords"], _JOB_KEYWORD_WEIGHT)
                     + _term_score(body, ind["keywords"], _KEYWORD_WEIGHT))
            if score > best_score:
                best_id, best_score = ind["id"], score
        if best_id:
            return best_id

    return DEFAULT_INDUSTRY_ID


def industry_name(industry_id: str) -> str:
    """行业 id -> 中文名；未知 id 返回 '未知行业'。"""
    ind = INDUSTRY_BY_ID.get(str(industry_id or "").strip())
    return ind["name"] if ind else "未知行业"


def majors_for(industry_id: str) -> list:
    """行业 id -> 对口专业列表（返回副本，未知 id 返回 []）。"""
    ind = INDUSTRY_BY_ID.get(str(industry_id or "").strip())
    return list(ind["major_hint"]) if ind else []


def job_keywords(industry_id: str) -> list:
    """行业 id -> 代表岗位关键词列表（供采集/检索构造查询词，未知 id 返回 []）。"""
    ind = INDUSTRY_BY_ID.get(str(industry_id or "").strip())
    return list(ind["job_keywords"]) if ind else []


def all_industries() -> list:
    """供前端下拉使用：[{id, name, major_hint}, ...]"""
    return [{"id": ind["id"], "name": ind["name"],
             "major_hint": list(ind["major_hint"])} for ind in INDUSTRIES]


if __name__ == "__main__":  # pragma: no cover
    print("行业数:", len(INDUSTRIES))
    print(classify_industry("", "互联网/游戏/软件"))
    print(classify_industry("新能源汽车电控工程师"))
