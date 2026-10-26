"""
【每日自动备份】scripts/backup_db.py

用 mysqldump 把真实库 ats 完整导出到 1.0/backups/，保留最近 14 份，自动清理更旧的。
配合 Windows 计划任务（ats/自动备份.bat，每日 03:00）实现无人值守备份。

手动执行：.venv\\Scripts\\python scripts\\backup_db.py
数据库密码从 backend/.env 的 DATABASE_URL 解析（不写死在代码里）。
"""
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent.parent
BACKUP_DIR = REPO / "backups"
KEEP = 14

# mysqldump 位置：优先常见安装目录，其次 PATH
MYSQLDUMP_CANDIDATES = [
    r"D:\mysql\mysql8\bin\mysqldump.exe",
    r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe",
    r"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqldump.exe",
    "mysqldump",
]


def db_creds() -> tuple[str, str, str]:
    """从 .env 解析（user, password, database）。密码拿不到就报错退出——备份不能悄悄跳过。"""
    env_file = BACKEND / ".env"
    if not env_file.exists():
        print(f"找不到 {env_file}，无法解析数据库连接")
        sys.exit(1)
    m = re.search(r"mysql\+pymysql://([^:]+):([^@]+)@[^/]+/(\w+)", env_file.read_text(encoding="utf-8"))
    if not m:
        print(".env 里没有合法的 DATABASE_URL")
        sys.exit(1)
    return m.group(1), m.group(2), m.group(3)


def find_mysqldump() -> str:
    from shutil import which

    for c in MYSQLDUMP_CANDIDATES:
        if which(c):
            return c
    print("找不到 mysqldump.exe，请把安装路径加进 MYSQLDUMP_CANDIDATES")
    sys.exit(1)


def rotate(keep: int) -> None:
    files = sorted(BACKUP_DIR.glob("ats_*.sql"), reverse=True)
    for old in files[keep:]:
        old.unlink()
        print(f"清理旧备份：{old.name}")


# ---- 异地镜像（v3.17 P1-14）：设置环境变量 ATS_BACKUP_MIRROR 后，每次备份自动拷一份到该目录 ----
# 用法（计划任务/启动脚本里）：set ATS_BACKUP_MIRROR=E:ts_backup_mirror
import os
import shutil

MIRROR_DIR = os.environ.get("ATS_BACKUP_MIRROR", "").strip()


def mirror_backup(dump_path: Path) -> None:
    if not MIRROR_DIR:
        return
    dest = Path(MIRROR_DIR)
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(dump_path, dest / dump_path.name)
    # 镜像目录同样保留最近 14 份
    mirrors = sorted(dest.glob("ats_*.sql"))
    for old in mirrors[:-14]:
        old.unlink(missing_ok=True)
    print(f"[mirror] 已复制到异地目录 {dest}")


def main() -> int:
    user, pw, database = db_creds()
    dump = find_mysqldump()
    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = BACKUP_DIR / f"ats_{stamp}.sql"

    cmd = [dump, f"--user={user}", f"--password={pw}", "--single-transaction",
           "--default-character-set=utf8mb4", database]
    with open(out, "wb") as f:
        r = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE)
    if r.returncode != 0:
        out.unlink(missing_ok=True)
        print("mysqldump 失败：", r.stderr.decode(errors="replace")[:300])
        return 1

    size = out.stat().st_size
    if size < 1024:
        print(f"备份异常（只有 {size} 字节），疑似失败，已删除")
        out.unlink()
        return 1
    rotate(KEEP)
    print(f"备份完成：{out.name}（{size / 1024:.0f} KB）")
    try:
        mirror_backup(out)
    except Exception as e:  # 镜像失败不影响本地备份的有效性
        print(f"[mirror] 复制失败：{e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
