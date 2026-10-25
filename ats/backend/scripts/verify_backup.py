"""
【备份恢复演练】scripts/verify_backup.py

备份没有验证过恢复，就等于没有备份。这个脚本做完整闭环：
  1. 找 backups/ 里最新的一份 mysqldump
  2. 建临时库 ats_drill 并用 mysql 客户端导入（与真实恢复同一工具链）
  3. 逐表对比 ats_drill 与源库的行数，抽查关键数据一致性
  4. 删掉临时库，输出 PASS/FAIL（退出码）

用法：.venv\\Scripts\\python scripts\\verify_backup.py [--keep]
（--keep 保留 ats_drill 便于人工检查）
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

import pymysql

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent.parent
BACKUP_DIR = REPO / "backups"
MYSQL_CLIENTS = [
    r"D:\mysql\mysql8\bin\mysql.exe",
    r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe",
    "mysql",
]
SOURCE_DB = "ats"
DRILL_DB = "ats_drill"
KEY_TABLES = [
    "Candidate", "Position", "Application", "User", "Candidate_File",
    "Candidate_Notice", "Form_Template", "Form_Submission", "Form_Answer",
    "Operation_Log", "App_Setting", "AI_API_Config", "Stage_Owner",
]


def db_password() -> str:
    env_file = BACKEND / ".env"
    m = re.search(r"://[^:]+:([^@]+)@", env_file.read_text(encoding="utf-8"))
    return m.group(1) if m else ""


def find_mysql() -> str:
    from shutil import which

    for c in MYSQL_CLIENTS:
        if which(c):
            return c
    print("找不到 mysql.exe 客户端")
    sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", action="store_true", help="保留 ats_drill 临时库")
    args = parser.parse_args()

    dumps = sorted(BACKUP_DIR.glob("ats_*.sql"), reverse=True)
    if not dumps:
        print("backups/ 里没有任何 ats_*.sql，先跑 scripts/backup_db.py")
        return 1
    dump = dumps[0]
    pw = db_password()
    mysql = find_mysql()

    conn = pymysql.connect(host="127.0.0.1", port=3306, user="root", password=pw, charset="utf8mb4")
    try:
        with conn.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS {DRILL_DB}")
            cur.execute(f"CREATE DATABASE {DRILL_DB} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        conn.commit()

        # 导入：与真实恢复完全相同的工具链（mysql 客户端读 dump 文件）
        with open(dump, "rb") as f:
            r = subprocess.run(
                [mysql, "--user=root", f"--password={pw}", "--default-character-set=utf8mb4", DRILL_DB],
                stdin=f, stderr=subprocess.PIPE,
            )
        if r.returncode != 0:
            print("导入失败：", r.stderr.decode(errors="replace")[:300])
            return 1

        failures = 0
        with conn.cursor() as cur:
            for table in KEY_TABLES:
                cur.execute(f"SELECT COUNT(*) FROM `{SOURCE_DB}`.`{table}`")
                src = cur.fetchone()[0]
                cur.execute(f"SELECT COUNT(*) FROM `{DRILL_DB}`.`{table}`")
                dst = cur.fetchone()[0]
                mark = "OK " if src == dst else "DIFF"
                if src != dst:
                    failures += 1
                print(f"  [{mark}] {table:20s} 源库 {src:6d} / 恢复库 {dst:6d}")

            # 抽查：候选人手机号集合双向一致（业务数据真的进来了，不只是空表）
            cur.execute(
                f"SELECT COUNT(*) FROM `{SOURCE_DB}`.Candidate s "
                f"LEFT JOIN `{DRILL_DB}`.Candidate d ON s.phone = d.phone "
                f"WHERE s.phone IS NOT NULL AND d.phone IS NULL"
            )
            missing = cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM `{SOURCE_DB}`.Candidate WHERE phone IS NOT NULL")
            total = cur.fetchone()[0]
            if missing:
                print(f"  [DIFF] 恢复库缺少 {missing}/{total} 个手机号")
                failures += 1
            else:
                print(f"  [OK ] 候选人手机号全部一致（{total} 个）")

            if not args.keep:
                cur.execute(f"DROP DATABASE IF EXISTS {DRILL_DB}")
            conn.commit()

        if failures:
            print(f"恢复演练失败：{failures} 处不一致（dump：{dump.name}）")
            return 1
        print(f"恢复演练通过 ✓（dump：{dump.name}，{dump.stat().st_size / 1024:.0f} KB）")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
