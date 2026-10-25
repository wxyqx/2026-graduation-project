"""
阶段 2 自检：候选人账号（手机号）与登录

覆盖：
  1. HR 建候选人填手机号 → 自动开通账号（has_account=true，手机号被规范化）
  2. 候选人用手机号 + 默认密码 admin 登录；/me 正常
  3. 错误密码 401；连续失败 5 次后 429
  4. 手机号不存在 401
  5. 改密：旧密码失效、新密码生效
  6. 修改手机号：旧号不能登录、新号能登录
  7. 停用账号 403
  8. 重复手机号 409
  9. 候选人 token 访问 HR 接口 403
  10. AI 回答里的手机号能正确归一化

运行（后端已启动）：
    .venv\\Scripts\\python -B scripts\\portal_smoke_test.py
"""
import os
import sys
import time
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
from app.services import prompt as prompt_svc  # noqa: E402

BASE = os.getenv("ATS_BASE", "http://127.0.0.1:8001")
PASSED = 0
FAILED = 0
BASE_NUM = int(time.time() * 1000) % 100000000


def check(label: str, ok: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f"  [OK]   {label}")
    else:
        FAILED += 1
        print(f"  [FAIL] {label} {detail}")


def gen_phone(offset: int = 0) -> str:
    """生成一个 11 位、看起来合法的手机号（同一轮测试内不重复）。"""
    n = (BASE_NUM + offset) % 100000000
    return f"139{n:08d}"


def main() -> int:
    db = SessionLocal()
    client = httpx.Client(base_url=BASE, timeout=15)
    tag = str(int(time.time()))
    hr_username = f"stage2_hr_{tag}"
    hr_user = None
    hr_token = None
    candidate_ids: list[int] = []
    try:
        # ---------- 准备一个 HR ----------
        r = client.post("/api/auth/register", json={"username": hr_username, "password": "secret123", "real_name": "测试HR", "phone": "139" + tag[-8:]})
        check("注册 HR", r.status_code == 201, f"{r.status_code} {r.text[:150]}")
        hr_token = r.json()["token"]
        H = {"Authorization": f"Bearer {hr_token}"}
        hr_user = db.scalar(select(User).where(User.username == hr_username))

        phone1 = gen_phone(1)
        phone_fmt = f"{phone1[:3]}-{phone1[3:7]}-{phone1[7:]}"

        # ---------- 1. 建候选人 + 自动开通账号 ----------
        r = client.post("/api/candidates", headers=H, json={"name": f"阶段2候选人{tag}", "phone": phone_fmt})
        check("HR 新建候选人（带格式手机号）", r.status_code == 201, f"{r.status_code} {r.text[:200]}")
        c1 = r.json()
        check("手机号被规范化成 11 位", c1.get("phone") == phone1, str(c1.get("phone")))
        check("has_account=true（自动开通账号）", c1.get("has_account") is True, str(c1))
        candidate_ids.append(c1["id"])

        r = client.get(f"/api/candidates/{c1['id']}", headers=H)
        check("候选人详情 has_account=true", r.status_code == 200 and r.json().get("has_account") is True)

        r = client.get("/api/candidates", headers=H, params={"name": f"阶段2候选人{tag}"})
        check("候选人列表带 phone/has_account", r.status_code == 200 and r.json()[0].get("has_account") is True)

        # ---------- 2. 默认密码登录 ----------
        r = client.post("/api/portal/auth/login", json={"phone": phone1, "password": "admin"})
        check("候选人默认密码登录成功", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
        login1 = r.json()
        check("角色是 candidate", login1["user"]["role"] == "candidate", str(login1["user"]))
        check("返回关联的候选人编号", login1["user"]["candidate_id"] == c1["id"], str(login1["user"]))
        cand_token = login1["token"]
        C = {"Authorization": f"Bearer {cand_token}"}

        r = client.get("/api/portal/auth/me", headers=C)
        check("/me 返回自己", r.status_code == 200 and r.json()["candidate"]["id"] == c1["id"], r.text[:200])

        r = client.get("/api/candidates", headers=C)
        check("候选人 token 访问 HR 接口 403", r.status_code == 403, f"{r.status_code}")

        # ---------- 3. 错误密码 / 不存在手机号 ----------
        r = client.post("/api/portal/auth/login", json={"phone": phone1, "password": "wrong"})
        check("错误密码 401", r.status_code == 401, f"{r.status_code}")

        r = client.post("/api/portal/auth/login", json={"phone": gen_phone(99), "password": "admin"})
        check("手机号没有档案 401", r.status_code == 401, f"{r.status_code}")

        r = client.post("/api/portal/auth/login", json={"phone": "123", "password": "admin"})
        check("手机号格式错误 400", r.status_code == 400, f"{r.status_code}")

        # ---------- 4. 改密 ----------
        r = client.put("/api/portal/auth/password", headers=C, json={"current_password": "bad", "new_password": "newpass123"})
        check("改密时当前密码错误 400", r.status_code == 400, f"{r.status_code}")

        r = client.put("/api/portal/auth/password", headers=C, json={"current_password": "admin", "new_password": "newpass123"})
        check("改密成功", r.status_code == 200, f"{r.status_code} {r.text[:150]}")
        C = {"Authorization": f"Bearer {r.json()['token']}"}

        r = client.post("/api/portal/auth/login", json={"phone": phone1, "password": "admin"})
        check("旧密码失效 401", r.status_code == 401, f"{r.status_code}")
        r = client.post("/api/portal/auth/login", json={"phone": phone1, "password": "newpass123"})
        check("新密码可登录", r.status_code == 200, f"{r.status_code}")

        # ---------- 5. 改手机号 ----------
        phone2 = gen_phone(2)
        r = client.put(f"/api/candidates/{c1['id']}", headers=H, json={"phone": phone2})
        check("HR 修改手机号", r.status_code == 200 and r.json()["phone"] == phone2, f"{r.status_code} {r.text[:150]}")
        r = client.post("/api/portal/auth/login", json={"phone": phone1, "password": "newpass123"})
        check("旧手机号不能登录 401", r.status_code == 401, f"{r.status_code}")
        r = client.post("/api/portal/auth/login", json={"phone": phone2, "password": "newpass123"})
        check("新手机号可登录", r.status_code == 200, f"{r.status_code}")

        # ---------- 6. 重复手机号 ----------
        r = client.post("/api/candidates", headers=H, json={"name": f"重复手机号{tag}", "phone": phone2})
        check("重复手机号 409", r.status_code == 409, f"{r.status_code} {r.text[:150]}")

        # ---------- 6.1 先建无手机号的候选人，再补手机号 ----------
        r = client.post("/api/candidates", headers=H, json={"name": f"后补手机号{tag}"})
        check("无手机号候选人 has_account=false", r.status_code == 201 and r.json()["has_account"] is False, r.text[:150])
        c3 = r.json()
        candidate_ids.append(c3["id"])
        phone4 = gen_phone(4)
        r = client.put(f"/api/candidates/{c3['id']}", headers=H, json={"phone": phone4})
        check("补手机号后自动开通账号", r.status_code == 200 and r.json()["has_account"] is True, r.text[:150])
        r = client.post("/api/portal/auth/login", json={"phone": phone4, "password": "admin"})
        check("补手机号后可直接登录", r.status_code == 200, f"{r.status_code}")

        # ---------- 7. 停用账号 ----------
        # 上面的接口在别的会话里提交了数据；结束本会话旧事务，才能读到新账号
        db.rollback()
        cand_user = db.scalar(select(User).where(User.candidate_id == c1["id"]))
        check("账号确实已创建", cand_user is not None)
        cand_user.is_active = 0
        db.commit()
        r = client.post("/api/portal/auth/login", json={"phone": phone2, "password": "newpass123"})
        check("停用账号 403", r.status_code == 403, f"{r.status_code}")
        cand_user.is_active = 1
        db.commit()

        # ---------- 8. 登录失败限流 ----------
        phone3 = gen_phone(3)
        r = client.post("/api/candidates", headers=H, json={"name": f"限流候选人{tag}", "phone": phone3})
        check("再建一个候选人", r.status_code == 201, f"{r.status_code}")
        c2 = r.json()
        candidate_ids.append(c2["id"])
        for _ in range(5):
            client.post("/api/portal/auth/login", json={"phone": phone3, "password": "wrong"})
        r = client.post("/api/portal/auth/login", json={"phone": phone3, "password": "admin"})
        check("失败 5 次后正确密码也被限流 429", r.status_code == 429, f"{r.status_code} {r.text[:150]}")

        # ---------- 9. AI 手机号解析 ----------
        parsed = prompt_svc.parse_answer(
            '{"name":"张三","phone":"+86 138-0013-8000","position_id":null,"result":"pass","reason":"ok"}', {}, None
        )
        check("AI 手机号归一化", parsed["phone"] == "13800138000", str(parsed["phone"]))
        parsed = prompt_svc.parse_answer(
            '{"name":"张三","phone":"不是手机号","position_id":null,"result":"pass","reason":"ok"}', {}, None
        )
        check("AI 非法手机号被丢弃", parsed["phone"] is None, str(parsed["phone"]))

    finally:
        # 清理：优先用 HR 删除（会连带删账号），失败则直接删库
        try:
            ids = candidate_ids
            if hr_token:
                for cid in ids:
                    client.delete(f"/api/candidates/{cid}", headers={"Authorization": f"Bearer {hr_token}"})
            db.rollback()
            db.expire_all()
            for cid in ids:
                cand = db.get(Candidate, cid)
                if cand is not None:
                    linked = db.scalar(select(User).where(User.candidate_id == cid))
                    if linked is not None:
                        db.delete(linked)
                        db.commit()
                    db.delete(cand)
                    db.commit()
            if hr_user is not None:
                fresh = db.scalar(select(User).where(User.id == hr_user.id))
                if fresh is not None:
                    db.delete(fresh)
                    db.commit()
        except Exception as e:  # noqa: BLE001
            db.rollback()
            print(f"清理失败：{e}")
        db.close()
        client.close()

    print(f"\n结果：通过 {PASSED} 项，失败 {FAILED} 项")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
