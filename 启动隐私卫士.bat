@echo off
chcp 65001 >nul 2>&1
title Windows 隐私卫士

:: ── 检查管理员权限 ──
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] 正在请求管理员权限...
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

:: ── 切换到脚本所在目录 ──
cd /d "%~dp0"

:: ── 检查 Python ──
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [错误] 未检测到 Python！
    echo 请先安装 Python 3.10+：https://www.python.org/downloads/
    echo 安装时务必勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

:: ── 首次运行自动安装依赖 ──
if not exist ".deps_installed" (
    echo.
    echo [*] 首次运行，正在安装依赖...
    echo.
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo.
        echo [错误] 依赖安装失败，请检查网络连接
        pause
        exit /b 1
    )
    echo. > .deps_installed
    echo [OK] 依赖安装完成
    echo.
)

:: ── 启动程序 ──
echo [*] 正在启动 Windows 隐私卫士...
echo.
python main.py
if %errorlevel% neq 0 (
    echo.
    echo [错误] 程序异常退出
    pause
)
