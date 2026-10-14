# -*- coding: utf-8 -*-
"""数据源基类与统一岗位结构。

新增一个数据源只要三步：
  1. 在 sources/ 下建一个 .py，定义继承 JobSource 的类；
  2. 实现 fetch()，返回 build_job(...) 产出的 list[dict]；
  3. 在 config.SOURCE_META 里加一条元信息，并在 sources/__init__.py 注册。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..textutil import clean_text, norm_city, norm_degree, parse_salary, truncate


@dataclass
class FetchContext:
    """一次刷新任务的上下文。"""
    keywords: list[str] = field(default_factory=list)
    city: str = "全国"
    settings: dict = field(default_factory=dict)
    log: object = None            # callable(str)
    deadline: float | None = None
    detail_budget: list = field(default_factory=list)   # [剩余可抓详情数]，跨源共享

    def say(self, msg: str) -> None:
        if callable(self.log):
            try:
                self.log(msg)
            except Exception:
                pass

    def expired(self) -> bool:
        return self.deadline is not None and time.time() > self.deadline

    @property
    def timeout(self) -> float:
        return float(self.settings.get("request_timeout", 25) or 25)

    @property
    def interval(self) -> float:
        return float(self.settings.get("request_interval", 0.35) or 0.35)

    def take_detail_slot(self) -> bool:
        if not self.settings.get("fetch_detail_jd", True):
            return False
        if not self.detail_budget:
            return False
        if self.detail_budget[0] <= 0:
            return False
        self.detail_budget[0] -= 1
        return True


class JobSource:
    id: str = ""
    name: str = ""
    region: str = "global"          # cn | global
    kind: str = ""
    supports_keyword: bool = True
    supports_city: bool = False
    supports_detail: bool = False

    def fetch(self, ctx: FetchContext) -> list[dict]:
        raise NotImplementedError

    def fetch_detail_jd(self, job: dict, ctx: FetchContext) -> str | None:
        """可选：补全岗位详情正文。返回 None 表示没抓到。"""
        return None


def build_job(source: str, uid, title="", company="", city="", degree="", job_type="",
              source_industry="", salary_raw=None, pay_min=None, pay_max=None, pay_unit=None,
              currency="CNY", months_per_year=12, tags=None, jd="", url="",
              published_at="", region="global", extra=None) -> dict:
    """把各源千奇百怪的字段统一成一张表。"""
    uid = clean_text(uid) or f"{clean_text(title)}|{clean_text(company)}"
    sal = None
    if pay_min is not None or pay_max is not None:
        unit = pay_unit or "year"
        fake = {"min": pay_min, "max": pay_max if pay_max is not None else pay_min,
                "unit": unit, "currency": currency}
        sal = parse_salary(fake)
        if sal:
            sal["raw"] = clean_text(salary_raw) or _fmt_salary(pay_min, pay_max, unit, currency)
            sal["months_per_year"] = months_per_year
    elif salary_raw:
        sal = parse_salary(salary_raw)
        if sal:
            sal["currency"] = sal.get("currency") or currency

    tg = []
    if isinstance(tags, (list, tuple)):
        for t in tags:
            c = clean_text(t)
            if c and c not in tg:
                tg.append(c)
    elif tags:
        c = clean_text(tags)
        if c:
            tg.append(c)

    return {
        "source": source,
        "uid": uid,
        "region": region,
        "title": clean_text(title)[:300],
        "company": clean_text(company)[:200],
        "city": norm_city(city),
        "degree": norm_degree(degree),
        "job_type": clean_text(job_type)[:40] or "未标注",
        "source_industry": clean_text(source_industry)[:120],
        "salary_raw": (sal or {}).get("raw") or clean_text(salary_raw),
        "pay_unit": (sal or {}).get("unit"),
        "pay_min": (sal or {}).get("min"),
        "pay_max": (sal or {}).get("max"),
        "pay_month_min": (sal or {}).get("month_min"),
        "pay_month_max": (sal or {}).get("month_max"),
        "currency": (sal or {}).get("currency") or currency,
        "months_per_year": (sal or {}).get("months_per_year", months_per_year),
        "tags": tg[:30],
        "jd": truncate(clean_text(jd), 8000),
        "url": clean_text(url),
        "published_at": clean_text(published_at),
        "raw": extra if isinstance(extra, dict) else {},
    }


def _fmt_salary(lo, hi, unit, currency) -> str:
    sym = "$" if currency == "USD" else "¥"
    u = {"day": "/天", "month": "/月", "year": "/年", "hour": "/时"}.get(unit, "")
    if lo is None and hi is None:
        return ""
    if hi is None or lo == hi:
        return f"{sym}{lo or hi:g}{u}"
    return f"{sym}{lo:g}-{hi:g}{u}"
