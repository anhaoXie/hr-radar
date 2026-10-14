# -*- coding: utf-8 -*-
"""启动入口。

用法：
    python run.py                 # 启动并自动打开浏览器
    python run.py --port 9000     # 换端口
    python run.py --no-browser    # 不自动开浏览器
    python run.py --refresh       # 启动后立刻按默认设置刷新一次
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import time
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from radar import config, pipeline, server, store  # noqa: E402


def _auto_refresh_loop():
    """按设置里的间隔定时刷新（0 表示关闭）。"""
    while True:
        try:
            minutes = int(config.load_settings().get("auto_refresh_minutes", 0) or 0)
        except Exception:
            minutes = 0
        time.sleep(max(60, minutes * 60) if minutes else 300)
        if not minutes:
            continue
        if pipeline.MANAGER.busy:
            continue
        try:
            settings = config.load_settings()
            inds = settings.get("auto_refresh_industries") or ["internet"]
            st = pipeline.MANAGER.start(inds, [], settings.get("default_city") or "全国")
            print(f"[auto] 定时刷新已启动 run#{st.run_id}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"[auto] 定时刷新失败：{e}", flush=True)


def _already_running(host: str, port: int, timeout: float = 1.5) -> bool:
    """探测该端口上是否已经跑着本工具。

    Windows 上 SO_REUSEADDR 允许两个进程绑定同一端口（与 Linux 不同），
    所以不能依赖 bind 失败来发现重复启动，必须主动探测。
    """
    import json as _json
    import urllib.request
    probe_host = "127.0.0.1" if host in ("0.0.0.0", "", "::") else host
    try:
        with urllib.request.urlopen(
                f"http://{probe_host}:{port}/api/meta", timeout=timeout) as r:
            data = _json.loads(r.read().decode("utf-8", "replace"))
        return bool(data.get("app", {}).get("name"))
    except Exception:
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=f"{config.APP_NAME} v{config.APP_VERSION}")
    ap.add_argument("--host", default="127.0.0.1", help="监听地址，默认 127.0.0.1（仅本机可访问）")
    ap.add_argument("--port", type=int, default=8770, help="监听端口，默认 8770")
    ap.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    ap.add_argument("--refresh", action="store_true", help="启动后立刻刷新一次默认行业")
    ap.add_argument("--industry", default="internet", help="配合 --refresh 指定行业 id")
    args = ap.parse_args()

    store.init_db()

    url = f"http://{args.host}:{args.port}/"
    if _already_running(args.host, args.port):
        print("=" * 66)
        print(f"  本工具已经在运行了，不用重复启动。")
        print(f"  直接打开：{url}")
        print()
        print("  如果想重启，请先关闭之前那个黑色窗口，再运行本命令。")
        print("=" * 66, flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        return 0

    try:
        httpd = server.serve(args.host, args.port)
    except OSError as e:
        print("=" * 66)
        print(f"  启动失败：端口 {args.port} 无法监听（{e}）")
        print()
        print(f"    端口被别的程序占用 —— 换个端口启动：")
        print(f"      python run.py --port {args.port + 1}")
        print("=" * 66, flush=True)
        return 1

    print("=" * 66)
    print(f"  {config.APP_NAME}  v{config.APP_VERSION}")
    print(f"  界面地址 : {url}")
    print(f"  数据目录 : {config.DATA_DIR}")
    print(f"  岗位总数 : {store.total_jobs()}")
    print("  按 Ctrl+C 退出（关闭本窗口即可结束程序）")
    print("=" * 66, flush=True)

    if args.refresh:
        try:
            st = pipeline.MANAGER.start([args.industry], [], config.load_settings().get("default_city"))
            print(f"  已在后台启动刷新 run#{st.run_id}，可在界面「实时刷新」页查看进度", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"  启动刷新失败：{e}", flush=True)

    t = threading.Thread(target=_auto_refresh_loop, daemon=True, name="auto-refresh")
    t.start()

    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n正在退出…", flush=True)
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
