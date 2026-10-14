# -*- coding: utf-8 -*-
"""SQLite 持久层：岗位库、刷新日志、行业快照（趋势用）、学生档案。"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

from . import config

CN_TZ = timezone(timedelta(hours=8))
_local = threading.local()


def now_iso() -> str:
    return datetime.now(CN_TZ).replace(microsecond=0).isoformat()


def today() -> str:
    return datetime.now(CN_TZ).strftime("%Y-%m-%d")


def _conn() -> sqlite3.Connection:
    c = getattr(_local, "conn", None)
    if c is None:
        os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
        c = sqlite3.connect(config.DB_PATH, timeout=30, check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        _local.conn = c
    return c


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    source         TEXT NOT NULL,
    uid            TEXT NOT NULL,
    region         TEXT DEFAULT 'cn',
    title          TEXT,
    company        TEXT,
    industry_id    TEXT,
    source_industry TEXT,
    city           TEXT,
    degree         TEXT,
    job_type       TEXT,
    pay_unit       TEXT,
    pay_min        REAL,
    pay_max        REAL,
    pay_month_min  REAL,
    pay_month_max  REAL,
    currency       TEXT DEFAULT 'CNY',
    salary_raw     TEXT,
    months_per_year INTEGER DEFAULT 12,
    skills         TEXT,
    tags           TEXT,
    jd             TEXT,
    url            TEXT,
    published_at   TEXT,
    first_seen     TEXT,
    last_seen      TEXT,
    raw            TEXT,
    UNIQUE(source, uid)
);
CREATE INDEX IF NOT EXISTS idx_jobs_industry ON jobs(industry_id);
CREATE INDEX IF NOT EXISTS idx_jobs_city     ON jobs(city);
CREATE INDEX IF NOT EXISTS idx_jobs_lastseen ON jobs(last_seen);
CREATE INDEX IF NOT EXISTS idx_jobs_source   ON jobs(source);

CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT,
    finished_at TEXT,
    industries  TEXT,
    keywords    TEXT,
    city        TEXT,
    sources     TEXT,
    fetched     INTEGER DEFAULT 0,
    inserted    INTEGER DEFAULT 0,
    updated     INTEGER DEFAULT 0,
    detail_done INTEGER DEFAULT 0,
    status      TEXT DEFAULT 'running',
    errors      TEXT
);

CREATE TABLE IF NOT EXISTS snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER,
    ts          TEXT,
    day         TEXT,
    industry_id TEXT,
    job_count   INTEGER,
    payload     TEXT
);
CREATE INDEX IF NOT EXISTS idx_snap ON snapshots(industry_id, day);

CREATE TABLE IF NOT EXISTS profiles (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT,
    created_at TEXT,
    updated_at TEXT,
    data       TEXT
);

CREATE TABLE IF NOT EXISTS watchlist (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT,
    label      TEXT,
    query      TEXT
);
"""


def init_db() -> None:
    c = _conn()
    c.executescript(SCHEMA)
    c.commit()


# ---------------------------------------------------------------------------
# 岗位写入
# ---------------------------------------------------------------------------
JOB_FIELDS = [
    "source", "uid", "region", "title", "company", "industry_id", "source_industry",
    "city", "degree", "job_type", "pay_unit", "pay_min", "pay_max", "pay_month_min",
    "pay_month_max", "currency", "salary_raw", "months_per_year", "skills", "tags",
    "jd", "url", "published_at", "first_seen", "last_seen", "raw",
]


def upsert_jobs(rows: list[dict]) -> tuple[int, int]:
    """按 (source, uid) 去重写入。返回 (新增, 更新)。"""
    if not rows:
        return 0, 0
    c = _conn()
    ts = now_iso()
    inserted = updated = 0
    for r in rows:
        r = dict(r)
        r.setdefault("first_seen", ts)
        r["last_seen"] = ts
        for k in ("skills", "tags", "raw"):
            if isinstance(r.get(k), (list, dict)):
                r[k] = json.dumps(r[k], ensure_ascii=False)
        vals = [r.get(f) for f in JOB_FIELDS]
        placeholders = ",".join("?" * len(JOB_FIELDS))
        exists = c.execute(
            "SELECT id FROM jobs WHERE source=? AND uid=?", (r.get("source"), r.get("uid"))
        ).fetchone()
        if exists:
            sets = ",".join(f"{f}=?" for f in JOB_FIELDS if f not in ("source", "uid", "first_seen"))
            upd_vals = [r.get(f) for f in JOB_FIELDS if f not in ("source", "uid", "first_seen")]
            upd_vals.append(exists["id"])
            c.execute(f"UPDATE jobs SET {sets} WHERE id=?", upd_vals)
            updated += 1
        else:
            c.execute(f"INSERT INTO jobs ({','.join(JOB_FIELDS)}) VALUES ({placeholders})", vals)
            inserted += 1
    c.commit()
    return inserted, updated


def update_job_jd(source: str, uid: str, jd: str, skills=None) -> None:
    c = _conn()
    if skills is not None:
        c.execute("UPDATE jobs SET jd=?, skills=?, last_seen=? WHERE source=? AND uid=?",
                  (jd, json.dumps(skills, ensure_ascii=False), now_iso(), source, uid))
    else:
        c.execute("UPDATE jobs SET jd=?, last_seen=? WHERE source=? AND uid=?",
                  (jd, now_iso(), source, uid))
    c.commit()


def jobs_missing_jd(source: str, limit: int, industry_id: str | None = None) -> list[dict]:
    c = _conn()
    sql = ("SELECT id, source, uid, title, company, url, industry_id FROM jobs "
           "WHERE source=? AND (jd IS NULL OR jd='') ")
    args: list = [source]
    if industry_id:
        sql += "AND industry_id=? "
        args.append(industry_id)
    sql += "ORDER BY last_seen DESC LIMIT ?"
    args.append(limit)
    return [dict(r) for r in c.execute(sql, args).fetchall()]


# ---------------------------------------------------------------------------
# 岗位查询
# ---------------------------------------------------------------------------
def query_jobs(industry_id: str | None = None, city: str | None = None, source: str | None = None,
               keyword: str | None = None, region: str | None = None, days: int | None = None,
               degree: str | None = None, limit: int = 5000) -> list[dict]:
    c = _conn()
    sql = "SELECT * FROM jobs WHERE 1=1 "
    args: list = []
    if industry_id and industry_id not in ("all", ""):
        sql += "AND industry_id=? "
        args.append(industry_id)
    if city and city not in ("全国", "all", ""):
        sql += "AND city=? "
        args.append(city)
    if source and source not in ("all", ""):
        sql += "AND source=? "
        args.append(source)
    if region and region not in ("all", ""):
        sql += "AND region=? "
        args.append(region)
    if degree and degree not in ("all", ""):
        sql += "AND degree=? "
        args.append(degree)
    if keyword:
        kw = f"%{keyword.strip()}%"
        sql += "AND (title LIKE ? OR company LIKE ? OR jd LIKE ? OR tags LIKE ?) "
        args += [kw, kw, kw, kw]
    if days:
        cutoff = (datetime.now(CN_TZ) - timedelta(days=days)).replace(microsecond=0).isoformat()
        sql += "AND last_seen>=? "
        args.append(cutoff)
    sql += "ORDER BY last_seen DESC LIMIT ?"
    args.append(limit)
    rows = [dict(r) for r in c.execute(sql, args).fetchall()]
    for r in rows:
        for k in ("skills", "tags"):
            try:
                r[k] = json.loads(r[k]) if r[k] else []
            except Exception:
                r[k] = []
    return rows


def distinct_values(field: str, industry_id: str | None = None, limit: int = 200) -> list[str]:
    if field not in ("city", "source", "degree", "industry_id", "company", "job_type"):
        return []
    c = _conn()
    sql = f"SELECT {field} AS v, COUNT(*) AS n FROM jobs WHERE {field} IS NOT NULL AND {field}<>'' "
    args: list = []
    if industry_id and industry_id not in ("all", ""):
        sql += "AND industry_id=? "
        args.append(industry_id)
    sql += f"GROUP BY {field} ORDER BY n DESC LIMIT ?"
    args.append(limit)
    return [r["v"] for r in c.execute(sql, args).fetchall() if r["v"]]


def counts_by(field: str, industry_id: str | None = None, days: int | None = None,
              limit: int = 40) -> list[tuple[str, int]]:
    if field not in ("city", "source", "degree", "company", "job_type", "industry_id"):
        return []
    c = _conn()
    sql = f"SELECT {field} AS v, COUNT(*) AS n FROM jobs WHERE 1=1 "
    args: list = []
    if industry_id and industry_id not in ("all", ""):
        sql += "AND industry_id=? "
        args.append(industry_id)
    if days:
        cutoff = (datetime.now(CN_TZ) - timedelta(days=days)).replace(microsecond=0).isoformat()
        sql += "AND last_seen>=? "
        args.append(cutoff)
    sql += f"GROUP BY {field} ORDER BY n DESC LIMIT ?"
    args.append(limit)
    return [(r["v"] or "未知", r["n"]) for r in c.execute(sql, args).fetchall()]


def total_jobs() -> int:
    return _conn().execute("SELECT COUNT(*) AS n FROM jobs").fetchone()["n"]


def job_by_uid(source: str, uid: str) -> dict | None:
    r = _conn().execute("SELECT * FROM jobs WHERE source=? AND uid=?", (source, uid)).fetchone()
    if not r:
        return None
    d = dict(r)
    for k in ("skills", "tags"):
        try:
            d[k] = json.loads(d[k]) if d[k] else []
        except Exception:
            d[k] = []
    return d


# ---------------------------------------------------------------------------
# 刷新日志
# ---------------------------------------------------------------------------
def start_run(industries, keywords, city, sources) -> int:
    c = _conn()
    cur = c.execute(
        "INSERT INTO runs (started_at, industries, keywords, city, sources, status) VALUES (?,?,?,?,?,?)",
        (now_iso(), json.dumps(industries, ensure_ascii=False),
         json.dumps(keywords, ensure_ascii=False), city or "", json.dumps(sources, ensure_ascii=False),
         "running"))
    c.commit()
    return int(cur.lastrowid)


def finish_run(run_id: int, status: str, fetched=0, inserted=0, updated=0,
               detail_done=0, errors=None) -> None:
    c = _conn()
    c.execute("UPDATE runs SET finished_at=?, status=?, fetched=?, inserted=?, updated=?, "
              "detail_done=?, errors=? WHERE id=?",
              (now_iso(), status, fetched, inserted, updated, detail_done,
               json.dumps(errors or [], ensure_ascii=False), run_id))
    c.commit()


def recent_runs(limit: int = 20) -> list[dict]:
    rows = _conn().execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("industries", "keywords", "sources", "errors"):
            try:
                d[k] = json.loads(d[k]) if d[k] else []
            except Exception:
                d[k] = []
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# 快照（趋势）
# ---------------------------------------------------------------------------
def save_snapshot(run_id: int | None, industry_id: str, payload: dict) -> None:
    c = _conn()
    c.execute(
        "INSERT INTO snapshots (run_id, ts, day, industry_id, job_count, payload) VALUES (?,?,?,?,?,?)",
        (run_id, now_iso(), today(), industry_id, payload.get("job_count", 0),
         json.dumps(payload, ensure_ascii=False)))
    c.commit()


def snapshots(industry_id: str, limit: int = 120) -> list[dict]:
    rows = _conn().execute(
        "SELECT * FROM snapshots WHERE industry_id=? ORDER BY id ASC LIMIT ?",
        (industry_id, limit)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["payload"] = json.loads(d["payload"]) if d["payload"] else {}
        except Exception:
            d["payload"] = {}
        out.append(d)
    return out


def latest_snapshot(industry_id: str, before_ts: str | None = None) -> dict | None:
    c = _conn()
    if before_ts:
        r = c.execute("SELECT * FROM snapshots WHERE industry_id=? AND ts<? ORDER BY id DESC LIMIT 1",
                      (industry_id, before_ts)).fetchone()
    else:
        r = c.execute("SELECT * FROM snapshots WHERE industry_id=? ORDER BY id DESC LIMIT 1",
                      (industry_id,)).fetchone()
    if not r:
        return None
    d = dict(r)
    try:
        d["payload"] = json.loads(d["payload"]) if d["payload"] else {}
    except Exception:
        d["payload"] = {}
    return d


# ---------------------------------------------------------------------------
# 学生档案
# ---------------------------------------------------------------------------
def save_profile(name: str, data: dict, pid: int | None = None) -> int:
    c = _conn()
    ts = now_iso()
    if pid:
        c.execute("UPDATE profiles SET name=?, data=?, updated_at=? WHERE id=?",
                  (name, json.dumps(data, ensure_ascii=False), ts, pid))
        c.commit()
        return pid
    cur = c.execute("INSERT INTO profiles (name, created_at, updated_at, data) VALUES (?,?,?,?)",
                    (name, ts, ts, json.dumps(data, ensure_ascii=False)))
    c.commit()
    return int(cur.lastrowid)


def list_profiles() -> list[dict]:
    rows = _conn().execute("SELECT * FROM profiles ORDER BY updated_at DESC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["data"] = json.loads(d["data"]) if d["data"] else {}
        except Exception:
            d["data"] = {}
        out.append(d)
    return out


def delete_profile(pid: int) -> None:
    c = _conn()
    c.execute("DELETE FROM profiles WHERE id=?", (pid,))
    c.commit()


def get_profile(pid: int) -> dict | None:
    r = _conn().execute("SELECT * FROM profiles WHERE id=?", (pid,)).fetchone()
    if not r:
        return None
    d = dict(r)
    try:
        d["data"] = json.loads(d["data"]) if d["data"] else {}
    except Exception:
        d["data"] = {}
    return d


# ---------------------------------------------------------------------------
# 关注方向
# ---------------------------------------------------------------------------
def add_watch(label: str, query: dict) -> int:
    c = _conn()
    cur = c.execute("INSERT INTO watchlist (created_at, label, query) VALUES (?,?,?)",
                    (now_iso(), label, json.dumps(query, ensure_ascii=False)))
    c.commit()
    return int(cur.lastrowid)


def list_watch() -> list[dict]:
    rows = _conn().execute("SELECT * FROM watchlist ORDER BY id DESC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["query"] = json.loads(d["query"]) if d["query"] else {}
        except Exception:
            d["query"] = {}
        out.append(d)
    return out


def delete_watch(wid: int) -> None:
    c = _conn()
    c.execute("DELETE FROM watchlist WHERE id=?", (wid,))
    c.commit()
