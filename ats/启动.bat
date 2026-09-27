@echo off
chcp 936 >nul
title ATS 招聘管理系统 · 启动中
cd /d "%~dp0"

echo ============================================================
echo   ATS 招聘管理系统 · 一键启动
echo ============================================================
echo.

REM ---------- 1. MySQL ----------
echo [1/6] 检查 MySQL ...
tasklist /FI "IMAGENAME eq mysqld.exe" 2>nul | findstr /I "mysqld.exe" >nul
if errorlevel 1 (
    if exist "D:\mysql\mysql8\bin\mysqld.exe" (
        echo        MySQL 未运行，正在启动 ...
        start "MySQL" /MIN "D:\mysql\mysql8\bin\mysqld.exe" --defaults-file="D:\mysql\my.ini" --console
    ) else (
        echo        [警告] 没找到 D:\mysql\mysql8\bin\mysqld.exe
        echo        如果 MySQL 已装成 Windows 服务或已手动启动，可忽略这条。
    )
) else (
    echo        MySQL 已在运行
)

REM 等 MySQL 端口（3306）可连，最多等 20 秒
echo [2/6] 等待 MySQL 就绪 ...
set /a MW=0
:wait_mysql
netstat -ano | findstr ":3306 " | findstr LISTENING >nul
if not errorlevel 1 goto mysql_ok
set /a MW+=1
if %MW% GEQ 20 (
    echo        [警告] 等了 20 秒 MySQL 仍未就绪，继续启动（后端可能连不上库）
    goto mysql_ok
)
ping -n 2 127.0.0.1 >nul
goto wait_mysql
:mysql_ok
echo        MySQL 就绪

REM ---------- 3. 后端 ----------
echo [3/6] 检查后端 (127.0.0.1:8000) ...
netstat -ano | findstr ":8000 " | findstr LISTENING >nul
if not errorlevel 1 (
    echo        后端已在运行，跳过
) else (
    if not exist "%~dp0backend\.venv\Scripts\python.exe" (
        echo        [错误] 没找到后端虚拟环境 backend\.venv
        echo        请先在 backend 目录执行： python -m venv .venv
        echo        再执行： .venv\Scripts\pip install -r requirements.txt
        goto :end
    )
    echo        正在启动后端 ...
    start "ATS 后端 :8000" cmd /k "cd /d "%~dp0backend" && ".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
)

REM 等后端端口起来，最多 30 秒
echo [4/6] 等待后端就绪 ...
set /a BW=0
:wait_backend
netstat -ano | findstr ":8000 " | findstr LISTENING >nul
if not errorlevel 1 goto backend_ok
set /a BW+=1
if %BW% GEQ 30 (
    echo        [警告] 后端 30 秒未就绪，请查看「ATS 后端」窗口里的报错
    goto backend_ok
)
ping -n 2 127.0.0.1 >nul
goto wait_backend
:backend_ok
echo        后端就绪

REM ---------- 5. 前端 ----------
echo [5/6] 检查前端 (127.0.0.1:5173) ...
netstat -ano | findstr ":5173 " | findstr LISTENING >nul
if not errorlevel 1 (
    echo        前端已在运行，跳过
) else (
    if not exist "%~dp0frontend\node_modules" (
        echo        [提示] 没找到 frontend\node_modules，正在安装依赖（首次较慢）...
        pushd "%~dp0frontend"
        call npm install
        popd
    )
    echo        正在启动前端 ...
    start "ATS 前端 :5173" cmd /k "cd /d "%~dp0frontend" && npm run dev -- --host 127.0.0.1 --port 5173"
)

REM 等前端端口起来，最多 40 秒
echo [6/6] 等待前端就绪 ...
set /a WW=0
:wait_web
netstat -ano | findstr ":5173 " | findstr LISTENING >nul
if not errorlevel 1 goto web_ok
set /a WW+=1
if %WW% GEQ 40 (
    echo        [警告] 前端 40 秒未就绪，稍等几秒后手动刷新浏览器
    goto web_done
)
ping -n 2 127.0.0.1 >nul
goto wait_web
:web_ok
echo        前端就绪
:web_done

start "" http://127.0.0.1:5173

echo.
echo ============================================================
echo   启动完成！
echo     前端界面： http://127.0.0.1:5173
echo     接口文档： http://127.0.0.1:8000/docs
echo   后端、前端在各自的新窗口里运行，关闭本窗口不影响它们。
echo   要停止服务请双击「停止.bat」。
echo ============================================================
echo.
:end
pause
