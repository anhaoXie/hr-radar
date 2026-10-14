# -*- coding: utf-8 -*-
"""前端一致性检查。

这个项目没有构建步骤，前端是手写的 HTML/CSS/JS，所以拼错一个 DOM id
不会被任何编译器发现，只会在运行时静默报错。这个测试用来兜住这类问题。
"""
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")

html = open(os.path.join(WEB, "index.html"), encoding="utf-8").read()
js = open(os.path.join(WEB, "app.js"), encoding="utf-8").read()
css = open(os.path.join(WEB, "styles.css"), encoding="utf-8").read()

fails = []

# ---------------------------------------------------------------- 1. DOM id
html_ids = set(re.findall(r'id="([^"]+)"', html))
# 匹配 $('xxx') 与 document.getElementById('xxx')
js_ids = set(re.findall(r"\$\('([^']+)'\)", js))
js_ids |= set(re.findall(r"getElementById\('([^']+)'\)", js))

missing_ids = sorted(i for i in js_ids if i not in html_ids)
print(f"[1] DOM id：HTML {len(html_ids)} 个，JS 引用 {len(js_ids)} 个")
if missing_ids:
    fails.append("DOM id 缺失")
    print("    ✗ JS 引用但 HTML 中不存在：", missing_ids)
else:
    print("    ✓ JS 引用的 id 全部存在")

# ---------------------------------------------------------------- 2. 事件绑定目标
# nav-item 通过 data-tab 与 tab-xxx 区块对应
tabs = set(re.findall(r'data-tab="([^"]+)"', html))
sections = set(re.findall(r'id="tab-([^"]+)"', html))
missing_tabs = sorted(t for t in tabs if t not in sections)
print(f"[2] 导航页签：按钮 {len(tabs)} 个，区块 {len(sections)} 个")
if missing_tabs:
    fails.append("页签区块缺失")
    print("    ✗ 有按钮但没有对应区块：", missing_tabs)
else:
    print("    ✓ 每个导航按钮都有对应内容区块")

# ---------------------------------------------------------------- 3. CSS 类
# 只检查 JS 里静态写死的 class="..."（模板拼接的无法静态校验）
js_static_classes = set()
for m in re.finditer(r'class="([^"$]*)"', js):
    for c in m.group(1).split():
        if c and re.fullmatch(r"[A-Za-z][A-Za-z0-9_\-]*", c):
            js_static_classes.add(c)
# 也检查带条件拼接但出现的字面量类名，例如 'gap-item ' + (...) + 'p1'
js_literal_classes = set(re.findall(r"'([a-z][a-z0-9\-]{2,})'", js))
candidates = js_static_classes | {c for c in js_literal_classes if len(c) > 3}

css_classes = set(re.findall(r"\.([A-Za-z][A-Za-z0-9_\-]*)", css))
# 一些类由后端/通用工具类产生，或在 CSS 里以组合选择器出现，做白名单
WHITELIST = {"html", "body", "hidden", "request", "response", "text", "json", "get", "post",
             "delete", "join", "name", "value", "type", "count", "items", "data", "list",
             "score", "jobs", "ok", "error", "running", "done", "prior", "live", "profiles",
             "settings", "sources", "industries", "skills", "radar", "today", "median", "share",
             "share_delta", "job_count", "evidence", "overlap", "reason", "url", "city", "degree"}
missing_css = sorted(c for c in candidates if c not in css_classes and c not in WHITELIST)
print(f"[3] CSS 类：JS 静态使用 {len(candidates)} 个，CSS 中定义 {len(css_classes)} 个")
if missing_css:
    print("    ! 可能未定义的类（如为运行时拼接产物可忽略）：", missing_css[:20])
else:
    print("    ✓ JS 静态使用的类都有对应样式")

# ---------------------------------------------------------------- 4. 资源引用
for asset in re.findall(r'(?:href|src)="(/[^"]+)"', html):
    path = os.path.join(WEB, asset.lstrip("/"))
    if asset in ("/app.js", "/styles.css"):
        ok = os.path.isfile(path)
        print(f"[4] 资源 {asset}: {'✓ 存在' if ok else '✗ 缺失'}")
        if not ok:
            fails.append("资源缺失 " + asset)

# ---------------------------------------------------------------- 5. 离线可用性
cdn_refs = re.findall(r'(?:src|href)="https?://[^"]+"', html)
cdn_refs += re.findall(r'<script[^>]+src="https?://', html)
print(f"[5] 离线可用性：外部 CDN 资源引用 {len(cdn_refs)} 处（应为 0）")
if cdn_refs:
    fails.append("存在外部 CDN 依赖")
    print("    ✗ 检测到外部资源引用：", cdn_refs[:5])
else:
    print("    ✓ 无任何外部 CDN 依赖，断网也能正常使用")

print()
print("失败项:", fails if fails else "无 ✅")
sys.exit(1 if fails else 0)
