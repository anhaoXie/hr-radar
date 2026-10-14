@echo off
chcp 65001 >nul
title 行业HR需求雷达 · 大学生职业规划工具
cd /d "%~dp0"

echo ============================================================
echo   行业HR需求雷达 · 大学生职业规划工具
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 没有找到 python 命令。
    echo        请先安装 Python 3.10 或更高版本：https://www.python.org/downloads/
    echo        安装时请勾选 "Add Python to PATH"。
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo   检测到 Python %PYVER%
echo   本工具零第三方依赖，无需 pip install。
echo.
echo   启动后浏览器会自动打开；关闭这个窗口即可退出。
echo ============================================================
echo.

python run.py %*
if errorlevel 1 (
    echo.
    echo [提示] 启动失败。常见原因：
    echo        1. 端口被占用 —— 换个端口试试：  python run.py --port 9000
    echo        2. Python 版本过低 —— 需要 3.10 及以上
    echo.
    pause
)
