# -*- coding: utf-8 -*-
"""验证服务端不会因为客户端强制断开而打印堆栈。

模拟：发一个不完整的 HTTP 请求后立刻关闭 socket（浏览器关标签页/
刷新时就会这样），以及 HTTP/1.1 keep-alive 下直接断开。
"""
import io
import os
import socket
import subprocess
import sys
import time
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8773
LOG = os.path.join(ROOT, "tests", "_server_stderr.log")

env = dict(os.environ, PYTHONIOENCODING="utf-8")
with open(LOG, "w", encoding="utf-8") as lf:
    proc = subprocess.Popen([sys.executable, "run.py", "--port", str(PORT), "--no-browser"],
                            cwd=ROOT, stdout=lf, stderr=lf, env=env)
    try:
        # 等服务起来
        for _ in range(40):
            time.sleep(0.25)
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/meta", timeout=1).read()
                break
            except Exception:
                continue

        print("1) 正常请求 3 次")
        for _ in range(3):
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/meta", timeout=3).read()

        print("2) 发不完整请求后立刻断开（模拟浏览器取消）")
        for _ in range(5):
            s = socket.create_connection(("127.0.0.1", PORT), timeout=3)
            s.sendall(b"GET /api/meta HTTP/1.1\r\nHost: 127.0.0.1\r\n")  # 不发空行
            s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                         b"\x01\x00\x00\x00\x00\x00\x00\x00")  # 强制 RST
            s.close()
            time.sleep(0.15)

        print("3) 建连接后立刻强制 RST")
        for _ in range(5):
            s = socket.create_connection(("127.0.0.1", PORT), timeout=3)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                         b"\x01\x00\x00\x00\x00\x00\x00\x00")
            s.close()
            time.sleep(0.15)

        print("4) 正常请求仍然可用")
        body = urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/meta", timeout=3).read()
        print(f"   /api/meta 返回 {len(body)} 字节")
        time.sleep(1.0)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()

log = open(LOG, encoding="utf-8", errors="replace").read()
bad = [k for k in ("Traceback", "ConnectionResetError", "Exception occurred",
                   "BrokenPipeError", "WinError 10054") if k in log]
print()
print("服务端日志中的异常痕迹:", bad if bad else "无 ✅")
if bad:
    print("--- 日志片段 ---")
    idx = min(log.find(k) for k in bad if k in log)
    print(log[max(0, idx - 200):idx + 900])
