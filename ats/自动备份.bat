@echo off
rem 每日自动备份 ATS 数据库（由计划任务 ATS_每日备份 调用）
cd /d "D:\桌面\1.0\ats\backend"
"D:\桌面\1.0\ats\backend\.venv\Scripts\python.exe" "D:\桌面\1.0\ats\backend\scripts\backup_db.py" >> "D:\桌面\1.0\backups\backup.log" 2>&1
