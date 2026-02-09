@echo off
REM 虚拟环境快捷管理脚本 (Windows)
REM 使用: venv.bat [command]

set VENV_DIR=.venv

REM 检查虚拟环境是否存在
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [31m❌ 虚拟环境不存在[0m
    echo 请先运行: python -m venv %VENV_DIR%
    exit /b 1
)

REM 显示帮助
if "%~1"=="help" goto help
if "%~1"=="h" goto help
if "%~1"=="-h" goto help
if "%~1"=="--help" goto help

REM 激活虚拟环境
echo [32m✅ 正在激活虚拟环境...[0m
call %VENV_DIR%\Scripts\activate.bat
echo Python: %~dp0%VENV_DIR%\Scripts\python.exe
python --version
goto end

:help
echo 虚拟环境管理脚本 (Windows)
echo.
echo 用法: venv.bat
echo.
echo 此脚本将激活虚拟环境
echo.
echo 手动命令:
echo   %VENV_DIR%\Scripts\activate.bat  - 激活虚拟环境
echo   deactivate                      - 退出虚拟环境
echo.
echo 确保在运行测试前激活虚拟环境!

:end
