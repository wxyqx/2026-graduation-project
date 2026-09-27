@echo off
chcp 936 >nul
title ATS 招聘管理系统 · 停止
cd /d "%~dp0"

echo ============================================================
echo   停止 ATS 后端与前端
echo ============================================================
echo.

REM --- 后端：占用 8000 端口的进程 ---
call :kill_port 8000 后端
REM --- 前端：占用 5173 端口的进程 ---
call :kill_port 5173 前端

REM 关掉两个服务窗口（按窗口标题）
taskkill /F /FI "WINDOWTITLE eq ATS 后端*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq ATS 前端*" >nul 2>&1

echo.
echo ------------------------------------------------------------
echo   MySQL 保持运行，下次启动更快。
echo   若要把 MySQL 也停掉，双击 D:\mysql\stop_mysql.bat
echo ------------------------------------------------------------
echo.
pause
goto :eof

REM ============ 子过程：停止占用某个端口的进程 ============
REM %1 = 端口号   %2 = 名字（用于显示）
:kill_port
set PORT=%~1
set NAME=%~2
set FOUND=0
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT% " ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
    set FOUND=1
)
if "%FOUND%"=="1" (
    echo   %NAME% 已停止  端口 %PORT%
) else (
    echo   %NAME% 本来就没运行  端口 %PORT%
)
goto :eof
