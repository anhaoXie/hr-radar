# -*- coding: utf-8 -*-
"""极简 HTTP 客户端：gzip、重试、按主机限速。只用标准库，学生不用装任何依赖。"""
from __future__ import annotations

import gzip
import json
import random
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE

_host_lock = threading.Lock()
_host_last: dict[str, float] = {}


class HttpError(Exception):
    pass


def _throttle(host: str, interval: float) -> None:
    if interval <= 0:
        return
    while True:
        with _host_lock:
            last = _host_last.get(host, 0.0)
            wait = interval - (time.time() - last)
            if wait <= 0:
                _host_last[host] = time.time()
                return
        time.sleep(min(wait, 0.5))


def request(url: str, method: str = "GET", headers: dict | None = None, data=None,
            timeout: float = 25, retries: int = 2, interval: float = 0.35,
            encoding: str = "utf-8") -> str:
    """发起请求并返回解码后的文本。失败抛 HttpError。"""
    host = urllib.parse.urlsplit(url).netloc
    h = {
        "User-Agent": DEFAULT_UA,
        "Accept": "application/json, text/plain, text/html, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
    }
    if headers:
        h.update({k: v for k, v in headers.items() if v is not None})
    body = None
    if data is not None:
        if isinstance(data, (dict, list)):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            h.setdefault("Content-Type", "application/json")
        elif isinstance(data, str):
            body = data.encode("utf-8")
        else:
            body = data

    last_err: Exception | None = None
    for attempt in range(max(1, retries + 1)):
        _throttle(host, interval)
        req = urllib.request.Request(url, headers=h, data=body, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_ctx) as resp:
                raw = resp.read()
                enc = (resp.headers.get("Content-Encoding") or "").lower()
                if "gzip" in enc:
                    try:
                        raw = gzip.decompress(raw)
                    except Exception:
                        pass
                elif "deflate" in enc:
                    try:
                        raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                    except Exception:
                        pass
                ctype = resp.headers.get("Content-Type") or ""
                cs = "utf-8"
                if "charset=" in ctype.lower():
                    cs = ctype.lower().split("charset=")[-1].split(";")[0].strip() or "utf-8"
                if cs in ("gb2312", "gbk", "gb18030"):
                    cs = "gb18030"
                try:
                    return raw.decode(cs, "replace")
                except LookupError:
                    return raw.decode(encoding, "replace")
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (400, 401, 403, 404, 405, 422):
                break  # 这类错误重试无意义
            time.sleep(0.6 * (attempt + 1) + random.random() * 0.3)
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(0.6 * (attempt + 1) + random.random() * 0.3)
    raise HttpError(f"{type(last_err).__name__}: {last_err} :: {url}")


def get_json(url: str, headers: dict | None = None, timeout: float = 25, retries: int = 2,
             interval: float = 0.35):
    txt = request(url, headers=headers, timeout=timeout, retries=retries, interval=interval)
    try:
        return json.loads(txt)
    except Exception as e:  # noqa: BLE001
        raise HttpError(f"返回不是合法 JSON ({e}) :: {url} :: {txt[:180]!r}")


def get_text(url: str, headers: dict | None = None, timeout: float = 25, retries: int = 2,
             interval: float = 0.35) -> str:
    return request(url, headers=headers, timeout=timeout, retries=retries, interval=interval)
