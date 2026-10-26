"""
【一键全量测试】scripts/run_all_tests.py

做什么：
  1. 用 alembic 迁移链在本机 MySQL 重建独立测试库 ats_test（**完全不碰真实库 ats**）
  2. 在测试库里创建技术管理员账号（tech / admin）
  3. 用测试库起一个独立后端服务（127.0.0.1:8001）
  4. 依次跑全部 7 套自动化脚本（smoke / stage1 / portal / stage3 / stage4 / tech / mock_llm）
  5. 打印汇总，退出码 0=全绿 1=有失败

用法（在 ats/backend 目录下）：
    .venv\\Scripts\\python scripts\\run_all_tests.py
数据库密码：读 .env 的 DATABASE_URL；也可用环境变量覆盖 ATS_DB_PASSWORD。
"""
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pymysql

BACKEND = Path(__file__).resolve().parents[1]
TEST_DB = "ats_test"
BASE = "http://127.0.0.1:8001"

SCRIPTS = [
    ("smoke", ["scripts/smoke_test.py", BASE]),
    ("stage1 角色矩阵", ["scripts/stage1_role_test.py"]),
    ("portal 候选人登录", ["scripts/portal_smoke_test.py"]),
    ("stage3 文件+表单", ["scripts/stage3_smoke_test.py"]),
    ("stage4 投递+AI首筛", ["scripts/stage4_smoke_test.py"]),
    ("tech 技术管理端", ["scripts/tech_smoke_test.py"]),
    ("stage5 生命周期与负责人", ["scripts/stage5_lifecycle_test.py"]),
    ("stage6 邮件通知", ["scripts/stage6_email_test.py"]),
    ("mock_llm AI录入", ["scripts/mock_llm_test.py", BASE]),
    ("stage7 v3.17新功能", ["scripts/stage7_v317_test.py"]),
]


def db_password() -> str:
    env = os.getenv("ATS_DB_PASSWORD")
    if env:
        return env
    # 从 .env 的 DATABASE_URL 里解析密码
    env_file = BACKEND / ".env"
    if env_file.exists():
        m = re.search(r"://[^:]+:([^@]+)@", env_file.read_text(encoding="utf-8"))
        if m:
            return m.group(1)
    raise RuntimeError(
        "拿不到数据库密码：请设置环境变量 ATS_DB_PASSWORD，或确认 backend/.env 里有 DATABASE_URL"
    )


def rebuild_test_db(pw: str) -> None:
    """重建测试库：只建空库，表结构交给 alembic upgrade head（迁移链保证依赖顺序）。"""
    conn = pymysql.connect(host="127.0.0.1", port=3306, user="root", password=pw, charset="utf8mb4")
    try:
        with conn.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
            cur.execute(f"CREATE DATABASE {TEST_DB} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        conn.commit()
    finally:
        conn.close()
    import subprocess

    env = dict(os.environ, DATABASE_URL=f"mysql+pymysql://root:{pw}@127.0.0.1:3306/{TEST_DB}?charset=utf8mb4")
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env=env, cwd=BACKEND, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if r.returncode != 0:
        print(r.stdout, r.stderr)
        raise RuntimeError("alembic upgrade head 失败")
    print(f"[1/4] 测试库 {TEST_DB} 已按 alembic 迁移链建表")


def seed_admin(pw: str) -> None:
    env = dict(os.environ, DATABASE_URL=f"mysql+pymysql://root:{pw}@127.0.0.1:3306/{TEST_DB}?charset=utf8mb4")
    r = subprocess.run(
        [sys.executable, "scripts/create_user.py", "--role", "admin",
         "--username", "tech", "--password", "admin", "--phone", "13800000000",
         "--real-name", "测试管理员"],
        env=env, cwd=BACKEND, capture_output=True, text=True,
    )
    if r.returncode != 0:
        print(r.stdout, r.stderr)
        raise RuntimeError("创建测试技术管理员失败")
    print("[2/4] 测试库技术管理员（tech / admin）已创建")


def start_server(pw: str) -> subprocess.Popen:
    env = dict(os.environ, DATABASE_URL=f"mysql+pymysql://root:{pw}@127.0.0.1:3306/{TEST_DB}?charset=utf8mb4")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8001"],
        env=env, cwd=BACKEND,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(60):
        try:
            if httpx.get(f"{BASE}/docs", timeout=2).status_code == 200:
                print("[3/4] 测试服务已启动（8001，使用 ats_test 库）")
                return proc
        except Exception:
            pass
        time.sleep(0.5)
    proc.kill()
    raise RuntimeError("测试服务 60 秒内未就绪")


def run_suite() -> bool:
    env = dict(os.environ, ATS_DB_NAME=TEST_DB, ATS_DB_PASSWORD=db_password(), ATS_BASE=BASE,
               PYTHONIOENCODING="utf-8")
    all_ok = True
    print("[4/4] 开始跑测试：")
    for name, cmd in SCRIPTS:
        r = subprocess.run([sys.executable, *cmd], env=env, cwd=BACKEND, text=True,
                           encoding="utf-8", errors="replace", capture_output=True)
        ok = r.returncode == 0
        all_ok &= ok
        tail = (r.stdout or "").strip().splitlines()
        summary = tail[-1] if tail else ""
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}  {summary[:80]}")
        if not ok:
            lines = (r.stdout or "").splitlines() + (r.stderr or "").splitlines()
            for line in lines[-25:]:
                print("        |", line)
    return all_ok


def main() -> int:
    pw = db_password()
    rebuild_test_db(pw)
    seed_admin(pw)
    server = start_server(pw)
    try:
        ok = run_suite()
    finally:
        server.kill()
    print("=" * 50)
    print("全部通过 ✓" if ok else "存在失败 ✗")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
