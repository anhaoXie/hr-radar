# -*- coding: utf-8 -*-
"""HTTP 服务：静态页面 + JSON API。只用标准库，学生 clone 下来直接就能跑。"""
from __future__ import annotations

import csv
import io
import json
import mimetypes
import os
import posixpath
import sys
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import analyzer, career, config, industries, pipeline, sources, store

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")


class Handler(BaseHTTPRequestHandler):
    server_version = f"HRRadar/{config.APP_VERSION}"
    protocol_version = "HTTP/1.1"

    # ------------------------------------------------------------------ 基础
    def log_message(self, fmt, *args):  # 把默认的 stderr 噪音关掉
        if os.environ.get("RADAR_VERBOSE"):
            super().log_message(fmt, *args)

    def _send(self, code: int, body: bytes, ctype="application/json; charset=utf-8",
              extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj, code: int = 200):
        self._send(code, json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8"))

    def _err(self, msg: str, code: int = 400):
        self._json({"ok": False, "error": str(msg)}, code)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        raw = self.rfile.read(n)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def _q(self) -> dict:
        qs = urllib.parse.urlsplit(self.path).query
        out = {}
        for k, v in urllib.parse.parse_qsl(qs, keep_blank_values=True):
            out[k] = v
        return out

    def do_OPTIONS(self):  # noqa: N802
        self._send(204, b"")

    def do_HEAD(self):  # noqa: N802
        self.do_GET()

    # ------------------------------------------------------------------ GET
    def do_GET(self):  # noqa: N802
        path = urllib.parse.urlsplit(self.path).path
        try:
            if path.startswith("/api/"):
                return self._api_get(path, self._q())
            return self._static(path)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return self._err(f"{type(e).__name__}: {e}", 500)

    def do_POST(self):  # noqa: N802
        path = urllib.parse.urlsplit(self.path).path
        try:
            if not path.startswith("/api/"):
                return self._err("not found", 404)
            return self._api_post(path, self._body())
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return self._err(f"{type(e).__name__}: {e}", 500)

    def do_DELETE(self):  # noqa: N802
        path = urllib.parse.urlsplit(self.path).path
        try:
            if path == "/api/profiles":
                store.delete_profile(int(self._q().get("id") or 0))
                return self._json({"ok": True})
            if path == "/api/watch":
                store.delete_watch(int(self._q().get("id") or 0))
                return self._json({"ok": True})
            return self._err("not found", 404)
        except Exception as e:  # noqa: BLE001
            return self._err(f"{type(e).__name__}: {e}", 500)

    # ------------------------------------------------------------------ 静态
    def _static(self, path: str):
        if path in ("/", "/index.html"):
            path = "/index.html"
        rel = posixpath.normpath(urllib.parse.unquote(path)).lstrip("/\\")
        if rel.startswith("..") or os.path.isabs(rel):
            return self._err("bad path", 400)
        full = os.path.join(config.WEB_DIR, rel)
        if not os.path.isfile(full):
            return self._send(404, b"404 not found", "text/plain; charset=utf-8")
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            data = f.read()
        return self._send(200, data, ctype)

    # ------------------------------------------------------------------ API: GET
    def _api_get(self, path: str, q: dict):
        if path == "/api/meta":
            return self._json({
                "app": {"name": config.APP_NAME, "version": config.APP_VERSION},
                "industries": industries.all_industries(),
                "sources": sources.describe(),
                "settings": config.load_settings(),
                "coverage": analyzer.coverage(),
                "db": {"jobs": store.total_jobs(), "runs": store.recent_runs(5)},
                "cities": store.distinct_values("city", limit=60),
                "grades": ["大一", "大二", "大三", "大四", "研究生"],
            })

        if path == "/api/skills":
            from .skills import ALL_SKILLS, SKILL_CATEGORIES
            return self._json({
                "ok": True,
                "names": [s["name"] for s in ALL_SKILLS],
                "categories": {k: [s["name"] for s in v] for k, v in SKILL_CATEGORIES.items()},
            })

        if path == "/api/settings":
            return self._json({"ok": True, "settings": config.load_settings()})

        if path == "/api/analysis":
            return self._json({"ok": True, "data": analyzer.analyze(
                industry_id=q.get("industry") or "all",
                city=q.get("city") or "全国",
                source=q.get("source") or "all",
                keyword=q.get("keyword") or "",
                region=q.get("region") or "all",
                days=_int(q.get("days")),
                top_n=_int(q.get("top_n")) or 24,
            )})

        if path == "/api/trend":
            return self._json({"ok": True, "data": analyzer.trend(
                q.get("industry") or "all", q.get("city") or "全国")})

        if path == "/api/jobs":
            rows = store.query_jobs(
                industry_id=q.get("industry") or "all",
                city=q.get("city") or "全国",
                source=q.get("source") or "all",
                keyword=q.get("keyword") or "",
                region=q.get("region") or "all",
                days=_int(q.get("days")),
                limit=_int(q.get("limit")) or 60,
            )
            offset = _int(q.get("offset")) or 0
            return self._json({"ok": True, "total": len(rows),
                               "jobs": [_job_brief(r) for r in rows[offset:offset + (_int(q.get("page_size")) or 30)]]})

        if path == "/api/job":
            job = store.job_by_uid(q.get("source") or "", q.get("uid") or "")
            if not job:
                return self._err("岗位不存在", 404)
            job["risk"] = career.risk_flags(job)
            return self._json({"ok": True, "job": job})

        if path == "/api/interview":
            return self._json({"ok": True, "data": career.interview_prep(
                industry_id=q.get("industry") or "all",
                city=q.get("city") or "全国",
                target_job=q.get("target_job") or "",
                days=_int(q.get("days")),
            )})

        if path == "/api/timeline":
            return self._json({"ok": True, "data": career.career_timeline(q.get("grade") or "大三")})

        if path == "/api/risk-guide":
            return self._json({"ok": True, "data": career.risk_guide()})

        if path == "/api/refresh/status":
            st = pipeline.MANAGER.current()
            return self._json({"ok": True, "busy": pipeline.MANAGER.busy,
                               "progress": st.progress() if st else None})

        if path == "/api/history":
            return self._json({"ok": True, "runs": store.recent_runs(_int(q.get("limit")) or 20)})

        if path == "/api/profiles":
            return self._json({"ok": True, "profiles": store.list_profiles()})

        if path == "/api/watch":
            return self._json({"ok": True, "watch": store.list_watch()})

        if path == "/api/export":
            return self._export(q)

        return self._err("未知接口: " + path, 404)

    # ------------------------------------------------------------------ API: POST
    def _api_post(self, path: str, body: dict):
        if path == "/api/settings":
            patch = body.get("settings") if isinstance(body.get("settings"), dict) else body
            return self._json({"ok": True, "settings": config.save_settings(patch or {})})

        if path == "/api/refresh":
            inds = body.get("industries") or []
            if isinstance(inds, str):
                inds = [inds]
            kws = body.get("keywords") or []
            if isinstance(kws, str):
                kws = [k for k in kws.replace("，", ",").split(",") if k.strip()]
            srcs = body.get("sources")
            if srcs is not None and not isinstance(srcs, list):
                srcs = None
            city = body.get("city") or config.load_settings().get("default_city") or "全国"
            st = pipeline.MANAGER.start(inds, kws, city, srcs)
            return self._json({"ok": True, "progress": st.progress()})

        if path == "/api/diagnose":
            return self._json({"ok": True, "data": career.diagnose(
                body.get("profile") or {},
                industry_id=body.get("industry") or "all",
                city=body.get("city") or "全国",
                days=_int(body.get("days")),
            )})

        if path == "/api/match":
            return self._json({"ok": True, "data": career.match_jobs(
                body.get("profile") or {},
                industry_id=body.get("industry") or "all",
                city=body.get("city") or "全国",
                days=_int(body.get("days")),
                limit=_int(body.get("limit")) or 30,
                keyword=body.get("keyword") or "",
            )})

        if path == "/api/survey":
            return self._json({"ok": True, "data": career.direction_survey(body.get("scores") or {})})

        if path == "/api/profiles":
            name = body.get("name") or "未命名档案"
            pid = _int(body.get("id"))
            new_id = store.save_profile(name, body.get("data") or {}, pid)
            return self._json({"ok": True, "id": new_id})

        if path == "/api/watch":
            wid = store.add_watch(body.get("label") or "关注方向", body.get("query") or {})
            return self._json({"ok": True, "id": wid})

        if path == "/api/reindex":
            from .reindex import reextract_skills
            return self._json({"ok": True, "data": reextract_skills(
                industry_id=body.get("industry") or None)})

        if path == "/api/major-fit":
            return self._json({"ok": True, "data": career.major_fit(
                body.get("profile") or {}, body.get("industry") or "all")})

        return self._err("未知接口: " + path, 404)

    # ------------------------------------------------------------------ 导出
    def _export(self, q: dict):
        rows = store.query_jobs(
            industry_id=q.get("industry") or "all",
            city=q.get("city") or "全国",
            source=q.get("source") or "all",
            keyword=q.get("keyword") or "",
            region=q.get("region") or "all",
            days=_int(q.get("days")),
            limit=20000,
        )
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["来源", "岗位名称", "公司", "城市", "行业", "学历", "类型", "薪资",
                    "月薪下限", "月薪上限", "币种", "技能", "标签", "链接", "首次入库", "最近更新"])
        for r in rows:
            w.writerow([
                r.get("source"), r.get("title"), r.get("company"), r.get("city"),
                industries.industry_name(r.get("industry_id")), r.get("degree"),
                r.get("job_type"), r.get("salary_raw"), r.get("pay_month_min"),
                r.get("pay_month_max"), r.get("currency"),
                "、".join(r.get("skills") or []), "、".join(r.get("tags") or []),
                r.get("url"), r.get("first_seen"), r.get("last_seen"),
            ])
        data = ("\ufeff" + buf.getvalue()).encode("utf-8")
        fname = f"hr-radar-{q.get('industry') or 'all'}-{store.today()}.csv"
        return self._send(200, data, "text/csv; charset=utf-8",
                          {"Content-Disposition": f'attachment; filename="{fname}"'})


# ---------------------------------------------------------------------------
def _int(v, default=None):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _job_brief(r: dict) -> dict:
    return {
        "source": r.get("source"), "uid": r.get("uid"), "title": r.get("title"),
        "company": r.get("company"), "city": r.get("city"), "degree": r.get("degree"),
        "job_type": r.get("job_type"), "salary_raw": r.get("salary_raw"),
        "pay_month_min": r.get("pay_month_min"), "pay_month_max": r.get("pay_month_max"),
        "currency": r.get("currency"), "url": r.get("url"),
        "industry_id": r.get("industry_id"),
        "industry_name": industries.industry_name(r.get("industry_id")),
        "skills": (r.get("skills") or [])[:14],
        "tags": (r.get("tags") or [])[:8],
        "first_seen": r.get("first_seen"), "last_seen": r.get("last_seen"),
        "has_jd": bool(r.get("jd")),
    }


class RadarHTTPServer(ThreadingHTTPServer):
    """在标准库服务器上加两处防噪处理。

    浏览器关闭 keep-alive 连接、或在刷新中切页时会触发 ConnectionResetError /
    BrokenPipeError。这是完全正常的现象，但 socketserver 默认会把整段堆栈打到
    控制台，看起来像服务崩了。这里静默掉，只有真正的异常才打印。
    """

    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionResetError, ConnectionAbortedError,
                            BrokenPipeError, TimeoutError)):
            return
        super().handle_error(request, client_address)

    def service_actions(self):
        # 触发一次，让 Ctrl+C 在 Windows 上能及时响应
        pass


def serve(host: str = "127.0.0.1", port: int = 8770) -> RadarHTTPServer:
    store.init_db()
    httpd = RadarHTTPServer((host, port), Handler)
    return httpd
