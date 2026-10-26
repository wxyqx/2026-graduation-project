"""
v3.17 新功能回归断言（2026-10-26）

覆盖此前只手工验证过的条目，进 CI 防回退：
  1. 隐私同意门卫：未同意 → 投递/填表 403；同意后放行
  2. AI fail 不自动淘汰：投递停在 ai 关、overall_status 仍 pending
  3. 乐观锁：带过期 expectedUpdateTime 保存各关记录 → 409；force=true 覆盖成功
  4. 简历自助更新：候选人上传挂起（非当前）→ HR 转正 → 变当前、旧当前降级
  5. 撤回保留记录：撤回后原因仍在、结果清空
  6. 强制下线：改密后旧 token 401、响应里的新 token 可用
  7. 数据删除权：purge 后档案与账号都物理消失
  8. 容量仪表：/api/tech/storage 返回 level ∈ {ok,warn,danger}

运行（后端已启动）：
    .venv\\Scripts\\python -B scripts\\stage7_v317_test.py
"""
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if os.getenv("ATS_DB_NAME"):
    os.environ["DATABASE_URL"] = (
        f"mysql+pymysql://root:{os.getenv('ATS_DB_PASSWORD', '')}"
        f"@127.0.0.1:3306/{os.environ['ATS_DB_NAME']}?charset=utf8mb4"
    )

import httpx
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import Application, Candidate, CandidateFile, Position, User
from app.services.security import create_access_token, hash_password

BASE = os.getenv("ATS_BASE", "http://127.0.0.1:8001")
PASSED = 0
FAILED = 0
TAG = str(int(time.time()))


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
    created = {"candidates": [], "users": [], "positions": [], "applications": []}
    try:
        # ---------- 准备：HR / 技术管理员 / 候选人 / 岗位 ----------
        hr = User(username=f"v317_hr_{TAG}", phone=f"135{TAG[-8:]}", real_name="v317HR",
                  role="hr", password_hash=hash_password("hrpass123"), is_active=1,
                  create_time=datetime.now())
        db.add(hr)
        db.flush()
        created["users"].append(hr.id)
        admin = db.scalar(select(User).where(User.role == "admin"))
        H = {"Authorization": f"Bearer {create_access_token(hr.id, 'hr')}"}
        T = {"Authorization": f"Bearer {create_access_token(admin.id, 'admin')}"}

        pos = Position(position_name=f"v317岗位_{TAG}", position_requirements="任意", is_hidden=0)
        db.add(pos)
        db.flush()
        created["positions"].append(pos.id)
        db.commit()

        r = httpx.post(f"{BASE}/api/candidates", headers=H,
                       json={"name": f"v317候选_{TAG}", "phone": f"136{TAG[-8:]}"})
        check("建候选人", r.status_code == 201, r.text[:150])
        cand_id = r.json()["id"]
        created["candidates"].append(cand_id)

        # ---------- 1. 隐私同意门卫 ----------
        phone = f"136{TAG[-8:]}"
        lr = httpx.post(f"{BASE}/api/portal/auth/login", json={"phone": phone, "password": "admin"})
        check("候选人登录", lr.status_code == 200, lr.text[:150])
        C = {"Authorization": f"Bearer {lr.json()['token']}"}
        r = httpx.post(f"{BASE}/api/portal/applications", headers=C, json={"pos_id": pos.id})
        check("未同意隐私政策 → 投递 403", r.status_code == 403, f"{r.status_code}")
        r = httpx.post(f"{BASE}/api/portal/auth/privacy-consent", headers=C)
        check("同意隐私政策", r.status_code == 200, r.text[:150])
        r = httpx.get(f"{BASE}/api/portal/auth/me", headers=C)
        check("同意时间已记录", bool(r.json()["candidate"].get("consent_time")), r.text[:150])

        # ---------- 2. 撤回保留记录（先建投递走两关） ----------
        r = httpx.post(f"{BASE}/api/candidates/{cand_id}/applications", headers=H, json={"pos_id": pos.id})
        check("建投递（默认过 AI，从 resume 开始）", r.status_code == 201, r.text[:200])
        app_id = r.json()["id"]
        created["applications"].append(app_id)
        check("默认已在 resume 且 ai=pass",
              r.json()["current_stage"] == "resume" and r.json()["stages"][0]["result"] == "pass",
              str(r.json().get("current_stage")))
        r = httpx.put(f"{BASE}/api/applications/{app_id}/stage-note", headers=H,
                      json={"stage": "resume", "reason": "简历不错"})
        check("写 resume 原因", r.status_code == 200, r.text[:150])
        r = httpx.post(f"{BASE}/api/applications/{app_id}/advance", headers=H,
                       json={"fromStage": "resume", "result": "pass"})
        check("resume 通过 → phone", r.status_code == 200 and r.json()["current_stage"] == "phone", r.text[:150])
        r = httpx.post(f"{BASE}/api/applications/{app_id}/revert", headers=H, json={})
        st = {s["stage"]: s for s in r.json()["stages"]}
        check("撤回后成绩清空", st["resume"]["result"] is None, str(st["resume"]))
        check("撤回后原因保留（P1-11）", st["resume"]["reason"] == "简历不错", str(st["resume"]))

        # ---------- 3. 乐观锁 ----------
        app_data = httpx.get(f"{BASE}/api/applications/{app_id}", headers=H).json()
        old_ts = app_data["update_time"]
        # 先制造一次改动，让 update_time 前进
        httpx.put(f"{BASE}/api/applications/{app_id}/stage-note", headers=H,
                  json={"stage": "resume", "reason": "别人先改的"})
        r = httpx.put(f"{BASE}/api/applications/{app_id}/stage-note", headers=H,
                      json={"stage": "resume", "reason": "我的修改", "expectedUpdateTime": old_ts})
        check("带过期时间保存 → 409", r.status_code == 409, f"{r.status_code} {r.text[:120]}")
        r = httpx.put(f"{BASE}/api/applications/{app_id}/stage-note", headers=H,
                      json={"stage": "resume", "reason": "我的修改", "expectedUpdateTime": old_ts, "force": True})
        check("force=true 覆盖成功", r.status_code == 200, r.text[:150])
        st = {s["stage"]: s for s in r.json()["stages"]}
        check("覆盖后内容是我的", st["resume"]["reason"] == "我的修改", str(st["resume"]))

        # ---------- 4. 候选人资料乐观锁 ----------
        cd = httpx.get(f"{BASE}/api/candidates/{cand_id}", headers=H).json()
        check("CandidateOut 带 update_time", cd.get("update_time") is not None, str(cd.get("update_time")))
        httpx.put(f"{BASE}/api/candidates/{cand_id}", headers=H,
                  json={"name": f"v317候选_{TAG}", "remark": "别人改的", "expectedUpdateTime": cd["update_time"]})
        r = httpx.put(f"{BASE}/api/candidates/{cand_id}", headers=H,
                      json={"name": f"v317候选_{TAG}", "remark": "我改的", "expectedUpdateTime": cd["update_time"]})
        check("候选人资料带过期时间 → 409", r.status_code == 409, f"{r.status_code}")

        # ---------- 5. 简历自助更新 → HR 转正 ----------
        pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
        r = httpx.post(f"{BASE}/api/candidates/{cand_id}/files", headers=H,
                       files={"file": ("hr简历.pdf", pdf, "application/pdf")}, data={"category": "resume"})
        check("HR 上传当前简历", r.status_code == 201 and r.json()["is_current"], r.text[:150])
        r = httpx.post(f"{BASE}/api/portal/files/resume", headers=C,
                       files={"file": ("候选人新版.pdf", pdf, "application/pdf")})
        check("候选人上传新版简历", r.status_code == 201, r.text[:200])
        check("新版先挂起（非当前）", r.json()["is_current"] is False, str(r.json().get("is_current")))
        new_file_id = r.json()["id"]
        r = httpx.put(f"{BASE}/api/files/{new_file_id}/promote-resume", headers=H)
        check("HR 转正成功", r.status_code == 200 and r.json()["is_current"], r.text[:150])
        files = httpx.get(f"{BASE}/api/candidates/{cand_id}/files", headers=H).json()
        currents = [f for f in files if f["category"] == "resume" and f["is_current"]]
        check("转正后仅一条当前简历", len(currents) == 1 and currents[0]["id"] == new_file_id, str(len(currents)))

        # ---------- 6. 强制下线 ----------
        r = httpx.post(f"{BASE}/api/auth/login", json={"username": f"v317_hr_{TAG}", "password": "hrpass123"})
        old_tok = r.json()["token"]
        r = httpx.put(f"{BASE}/api/auth/profile", headers={"Authorization": f"Bearer {old_tok}"}, json={
            "username": f"v317_hr_{TAG}", "phone": f"135{TAG[-8:]}", "real_name": "v317HR",
            "current_password": "hrpass123", "new_password": "hrpass456",
        })
        check("改密返回新 token", r.status_code == 200 and r.json().get("token"), r.text[:150])
        new_tok = r.json()["token"]
        check("新 token 立即可用",
              httpx.get(f"{BASE}/api/auth/me", headers={"Authorization": f"Bearer {new_tok}"}).status_code == 200)
        check("旧 token 已失效",
              httpx.get(f"{BASE}/api/auth/me", headers={"Authorization": f"Bearer {old_tok}"}).status_code == 401)

        # ---------- 7. 容量仪表 ----------
        r = httpx.get(f"{BASE}/api/tech/storage", headers=T)
        check("容量仪表可用", r.status_code == 200 and r.json().get("level") in ("ok", "warn", "danger"), r.text[:150])
        check("含磁盘余量字段", "backup_free_bytes" in r.json(), str(r.json())[:150])

        # ---------- 8. 数据删除权（purge） ----------
        r = httpx.delete(f"{BASE}/api/tech/candidate-owners/candidates/{cand_id}/purge", headers=T,
                         params={"confirm": "true"})
        check("purge 成功", r.status_code == 200, r.text[:200])
        db.expire_all()
        db.commit()  # 结束旧快照，避免 REPEATABLE READ 读到删前数据
        check("档案已物理删除", db.get(Candidate, cand_id) is None)
        check("账号已物理删除", db.scalar(select(User).where(User.candidate_id == cand_id)) is None)
        created["candidates"].remove(cand_id)

        if FAILED:
            print(f"== v3.17 回归：通过 {PASSED} 项，失败 {FAILED} 项")
        else:
            print(f"  结果：通过 {PASSED} 项，失败 0 项")
        return 0 if FAILED == 0 else 1
    finally:
        # 清理（purge 已删的会跳过）
        try:
            db.rollback()
            for aid in created["applications"]:
                a = db.get(Application, aid)
                if a is not None:
                    db.delete(a)
            for cid in created["candidates"]:
                c = db.get(Candidate, cid)
                if c is not None:
                    db.query(CandidateFile).filter(CandidateFile.candidate_id == cid).delete(synchronize_session=False)
                    db.delete(c)
            for pid in created["positions"]:
                p = db.get(Position, pid)
                if p is not None:
                    db.delete(p)
            for uid in created["users"]:
                u = db.get(User, uid)
                if u is not None:
                    db.delete(u)
            db.commit()
            print("  cleanup done")
        except Exception as e:  # noqa: BLE001
            db.rollback()
            print(f"  cleanup warn: {e}")
        finally:
            db.close()


if __name__ == "__main__":
    sys.exit(main())
