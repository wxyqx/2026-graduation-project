@echo off
rem 每日自动备份 ATS 数据库（由计划任务 ATS_每日备份 调用）
cd /d "D:\桌面\1.0\ats\backend"
"D:\桌面\1.0\ats\backend\.venv\Scripts\python.exe" "D:\桌面\1.0\ats\backend\scripts\backup_db.py" >> "D:\桌面\1.0\backups\backup.log" 2>&1
rem ---- 异地镜像（v3.17 P1-14）：第二存放点，目录可改 ----
set ATS_BACKUP_MIRROR=D:\ats_backup_mirror
if not exist "%ATS_BACKUP_MIRROR%" mkdir "%ATS_BACKUP_MIRROR%"
for /f "delims=" %%f in ('dir /b /o-d "D:\桌面\1.0\backups\ats_*.sql" 2^>nul') do (
    if not exist "%ATS_BACKUP_MIRROR%\%%f" copy /y "D:\桌面\1.0\backups\%%f" "%ATS_BACKUP_MIRROR%\%%f" >> "D:\桌面\1.0\backups\backup.log" 2>&1
    goto :mirror_done
)
:mirror_done
