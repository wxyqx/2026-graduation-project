"""
阶段 1 自检：三角色权限矩阵

做四件事：
  1. 通过 /api/auth/register 建一个临时 HR，确认注册出来的角色是 hr
  2. 直接建一个临时候选人账号（绑定临时 Candidate），确认候选人 token 打 HR 接口全部 403
  3. 用已有的 tech 账号生成管理员 token，确认管理员也进不了 HR 业务接口
  4. 停用候选人账号，确认 403；最后清理测试数据

运行（后端已启动）：
    .venv\\Scripts\\python -B scripts\\stage1_role_test.py
"""
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# 支持独立测试库：设了 ATS_DB_NAME 就把 DATABASE_URL 指到测试库（须在 import app.* 之前）
if os.getenv("ATS_DB_NAME"):
    os.environ["DATABASE_URL"] = (
        f"mysql+pymysql://root:{os.getenv('ATS_DB_PASSWORD', '')}"
        f"@127.0.0.1:3306/{os.environ['ATS_DB_NAME']}?charset=utf8mb4"
    )

import httpx  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models import Candidate, User  # noqa: E402
from app.services.security import create_access_token, hash_password  # noqa: E402

BASE = os.getenv("ATS_BASE", "http://127.0.0.1:8001")
PASSED = 0
FAILED = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f"  [OK]   {label}")
    else:
        FAILED += 1
        print(f"  [FAIL] {label} {detail}")


def main() -> int:
    db = SessionLocal()
    tag = str(int(time.time()))
    hr_username = f"stage1_hr_{tag}"
    hr_user = None
    candidate = None
    cand_user = None
    try:
        # ---------- 1. 注册 HR ----------
        r = httpx.post(
            f"{BASE}/api/auth/register",
            json={"username": hr_username, "password": "secret123", "real_name": "测试HR", "phone": "139" + tag[-8:]},
            timeout=10,
        )
        check("注册 HR 返回 201", r.status_code == 201, f"实际 {r.status_code} {r.text[:200]}")
        data = r.json()
        check("注册出来的角色是 hr", data["user"]["role"] == "hr", str(data["user"]))
        hr_token = data["token"]
        hr_user = db.scalar(select(User).where(User.username == hr_username))

        # ---------- 2. 登录 ----------
        r = httpx.post(f"{BASE}/api/auth/login", json={"username": hr_username, "password": "secret123"}, timeout=10)
        check("HR 登录成功", r.status_code == 200, f"实际 {r.status_code}")
        r = httpx.post(f"{BASE}/api/auth/login", json={"username": "tech", "password": "admin"}, timeout=10)
        check("技术管理员不能从 HR 入口登录（403）", r.status_code == 403, f"实际 {r.status_code}")

        # ---------- 3. 临时候选人账号 ----------
        candidate = Candidate(name=f"阶段1测试候选人{tag}", create_time=datetime.now())
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        cand_user = User(
            username=None,
            password_hash=hash_password("admin"),
            role="candidate",
            candidate_id=candidate.id,
            is_active=1,
            create_time=datetime.now(),
        )
        db.add(cand_user)
        db.commit()
        db.refresh(cand_user)
        cand_token = create_access_token(cand_user.id, "candidate")

        tech = db.scalar(select(User).where(User.username == "tech"))
        check("tech 账号存在且角色是 admin", tech is not None and tech.role == "admin")
        admin_token = create_access_token(tech.id, "admin")

        # ---------- 4. 权限矩阵 ----------
        endpoints = [
            "/api/positions",
            "/api/candidates",
            "/api/applications",
            "/api/stats/overview",
            "/api/form-templates",
            "/api/export/fields",
        ]
        print("\n权限矩阵（HR=200，候选人/管理员=403）：")
        for path in endpoints:
            rh = httpx.get(f"{BASE}{path}", headers={"Authorization": f"Bearer {hr_token}"}, timeout=10)
            rc = httpx.get(f"{BASE}{path}", headers={"Authorization": f"Bearer {cand_token}"}, timeout=10)
            ra = httpx.get(f"{BASE}{path}", headers={"Authorization": f"Bearer {admin_token}"}, timeout=10)
            check(f"{path} HR 可访问", rh.status_code == 200, f"实际 {rh.status_code}")
            check(f"{path} 候选人被拒", rc.status_code == 403, f"实际 {rc.status_code}")
            check(f"{path} 管理员被拒", ra.status_code == 403, f"实际 {ra.status_code}")

        # 技术管理端的边界反过来：只有 admin 能进，HR / 候选人 403
        check(
            "HR 访问技术概览 403",
            httpx.get(f"{BASE}/api/tech/overview", headers={"Authorization": f"Bearer {hr_token}"}, timeout=10).status_code == 403,
        )
        check(
            "候选人访问技术概览 403",
            httpx.get(f"{BASE}/api/tech/overview", headers={"Authorization": f"Bearer {cand_token}"}, timeout=10).status_code == 403,
        )
        check(
            "技术管理员访问技术概览 200",
            httpx.get(f"{BASE}/api/tech/overview", headers={"Authorization": f"Bearer {admin_token}"}, timeout=10).status_code == 200,
        )

        # ---------- 5. 无 token / 停用 ----------
        r = httpx.get(f"{BASE}/api/positions", timeout=10)
        check("无 token 返回 401", r.status_code == 401, f"实际 {r.status_code}")

        cand_user.is_active = 0
        db.commit()
        r = httpx.get(f"{BASE}/api/positions", headers={"Authorization": f"Bearer {cand_token}"}, timeout=10)
        check("停用账号返回 403", r.status_code == 403, f"实际 {r.status_code} {r.text[:120]}")

        r = httpx.get(f"{BASE}/api/health", timeout=10)
        check("健康检查 200", r.status_code == 200)

        # ---------- 6. 登记接口仍可用（HR）----------
        r = httpx.get(f"{BASE}/api/positions", headers={"Authorization": f"Bearer {hr_token}"}, timeout=10)
        check("HR 能拿岗位列表", r.status_code == 200 and isinstance(r.json(), list))

    finally:
        # 清理：先删账号，再删候选人
        try:
            if cand_user is not None:
                db.delete(cand_user)
                db.commit()
            if hr_user is not None:
                db.delete(hr_user)
                db.commit()
            if candidate is not None:
                db.delete(candidate)
                db.commit()
        except Exception as e:  # noqa: BLE001
            db.rollback()
            print(f"清理测试数据失败：{e}")
        db.close()

    print(f"\n结果：通过 {PASSED} 项，失败 {FAILED} 项")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
