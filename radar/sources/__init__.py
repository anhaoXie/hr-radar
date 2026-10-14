# -*- coding: utf-8 -*-
"""数据源注册表。想加源就在这里注册一行。"""
from __future__ import annotations

from .. import config
from .base import FetchContext, JobSource, build_job
from .custom_json import CustomJSONSource
from .hn_hiring import HNHiringSource
from .international import (
    HimalayasSource,
    JobicySource,
    RemoteOKSource,
    RemotiveSource,
    TheMuseSource,
)
from .shixiseng import ShixisengSource

_INSTANCES: list[JobSource] = [
    ShixisengSource(),
    RemoteOKSource(),
    RemotiveSource(),
    HimalayasSource(),
    JobicySource(),
    TheMuseSource(),
    HNHiringSource(),
    CustomJSONSource(),
]

ALL_SOURCES: dict[str, JobSource] = {s.id: s for s in _INSTANCES}


def get_source(source_id: str) -> JobSource | None:
    return ALL_SOURCES.get(source_id)


def resolve(ids=None, settings: dict | None = None) -> list[JobSource]:
    """按设置把要跑的数据源实例解出来。"""
    settings = settings or config.load_settings()
    enabled = (settings.get("sources") or {})
    out: list[JobSource] = []
    for s in _INSTANCES:
        if ids:
            if s.id in ids:
                out.append(s)
            continue
        if enabled.get(s.id, config.SOURCE_MAP.get(s.id, {}).get("enabled_by_default", False)):
            out.append(s)
    return out


def describe() -> list[dict]:
    """给前端用的数据源清单（含可用性状态）。"""
    settings = config.load_settings()
    enabled = settings.get("sources") or {}
    items = []
    for meta in config.SOURCE_META:
        s = ALL_SOURCES.get(meta["id"])
        note = meta.get("note", "")
        ready = True
        if meta["id"] == "custom_json" and s is not None:
            ok, why = s.available(FetchContext(settings=settings))  # type: ignore[attr-defined]
            ready = ok
            if not ok:
                note = f"{note}（当前状态：{why}）"
        items.append({
            **{k: meta[k] for k in ("id", "name", "region", "kind", "requires_config")},
            "note": note,
            "enabled": bool(enabled.get(meta["id"], meta["enabled_by_default"])),
            "ready": ready,
            "registered": s is not None,
            "supports_keyword": getattr(s, "supports_keyword", False),
            "supports_city": getattr(s, "supports_city", False),
            "supports_detail": getattr(s, "supports_detail", False),
        })
    return items


__all__ = ["ALL_SOURCES", "FetchContext", "JobSource", "build_job", "describe", "get_source",
           "resolve"]
