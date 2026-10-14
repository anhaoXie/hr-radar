# -*- coding: utf-8 -*-
"""全局配置：路径、默认设置、数据源开关。纯标准库。"""
from __future__ import annotations

import json
import os
import threading

APP_NAME = "行业HR需求雷达"
APP_VERSION = "1.0.0"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RADAR_DIR = os.path.join(BASE_DIR, "radar")
WEB_DIR = os.path.join(BASE_DIR, "web")
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "radar.db")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")
EXPORT_DIR = os.path.join(DATA_DIR, "exports")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(EXPORT_DIR, exist_ok=True)

# ----------------------------------------------------------------------------
# 数据源注册表
# ----------------------------------------------------------------------------
# region: cn = 面向中国就业市场；global = 国际/远程岗位
# enabled_by_default: 是否默认参与"全量刷新"
# requires_config: 是否需要用户填 API Key / 自定义地址
SOURCE_META = [
    {
        "id": "shixiseng",
        "name": "实习僧",
        "region": "cn",
        "kind": "实习/校招",
        "enabled_by_default": True,
        "requires_config": False,
        "note": "国内大学生实习岗位主渠道。走站内公开 JSON 检索接口，支持关键词+城市，单次每关键词最多 20 条；可选抓取岗位详情页补充完整 JD。",
    },
    {
        "id": "remoteok",
        "name": "RemoteOK",
        "region": "global",
        "kind": "全职/远程",
        "enabled_by_default": True,
        "requires_config": False,
        "note": "公开 JSON API，含年薪区间与技能标签。",
    },
    {
        "id": "remotive",
        "name": "Remotive",
        "region": "global",
        "kind": "全职/远程",
        "enabled_by_default": True,
        "requires_config": False,
        "note": "公开 JSON API，支持关键词 search 参数。",
    },
    {
        "id": "himalayas",
        "name": "Himalayas",
        "region": "global",
        "kind": "全职/远程",
        "enabled_by_default": True,
        "requires_config": False,
        "note": "公开 JSON API，含薪资区间与结构化标签。",
    },
    {
        "id": "jobicy",
        "name": "Jobicy",
        "region": "global",
        "kind": "全职/远程",
        "enabled_by_default": True,
        "requires_config": False,
        "note": "公开 JSON API，支持行业与关键词过滤。",
    },
    {
        "id": "themuse",
        "name": "The Muse",
        "region": "global",
        "kind": "全职",
        "enabled_by_default": True,
        "requires_config": False,
        "note": "公开 JSON API，按分类分页，含公司规模与地点。",
    },
    {
        "id": "hn_hiring",
        "name": "Hacker News 招聘帖",
        "region": "global",
        "kind": "全职",
        "enabled_by_default": True,
        "requires_config": False,
        "note": "通过 Algolia 检索 HN『Who is hiring』主帖与评论，适合技术岗趋势观察。",
    },
    {
        "id": "custom_json",
        "name": "自定义接口（企业/授权 API）",
        "region": "cn",
        "kind": "自定义",
        "enabled_by_default": False,
        "requires_config": True,
        "note": "填入你已获授权的招聘 API（如猎聘开放平台、聚合数据、校内就业系统）。在设置里配置 URL 模板与字段映射，即可纳入同一套分析。",
    },
]

SOURCE_MAP = {s["id"]: s for s in SOURCE_META}

DEFAULT_SETTINGS = {
    "sources": {s["id"]: s["enabled_by_default"] for s in SOURCE_META},
    "default_city": "全国",
    "max_keywords_per_refresh": 8,      # 每次刷新每个源最多用多少个关键词检索
    "max_pages_per_keyword": 1,         # 分页深度（实习僧目前仅首页可用）
    "fetch_detail_jd": True,            # 是否抓详情页补全 JD（用于技能抽取）
    "detail_jd_limit": 60,              # 每次刷新最多补全多少条 JD
    "request_timeout": 25,
    "request_interval": 0.35,           # 对同一站的请求间隔（秒），做礼貌限速
    "concurrency": 6,
    "auto_refresh_minutes": 0,          # 0 = 关闭定时刷新
    "workdays_per_month": 21.75,        # 日薪 -> 月薪 折算
    "custom_json": {
        "url_template": "",
        "method": "GET",
        "headers": {},
        "body_template": "",
        "list_path": "data.list",
        "field_map": {
            "id": "id",
            "title": "title",
            "company": "company",
            "city": "city",
            "salary": "salary",
            "degree": "degree",
            "industry": "industry",
            "jd": "description",
            "url": "url",
        },
    },
}

_lock = threading.RLock()


def load_settings() -> dict:
    with _lock:
        data = json.loads(json.dumps(DEFAULT_SETTINGS))
        if os.path.exists(SETTINGS_PATH):
            try:
                with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                if isinstance(saved, dict):
                    _deep_merge(data, saved)
            except Exception:
                pass
        return data


def save_settings(patch: dict) -> dict:
    with _lock:
        cur = load_settings()
        if isinstance(patch, dict):
            _deep_merge(cur, patch)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(cur, f, ensure_ascii=False, indent=2)
        return cur


def _deep_merge(base: dict, patch: dict) -> None:
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
