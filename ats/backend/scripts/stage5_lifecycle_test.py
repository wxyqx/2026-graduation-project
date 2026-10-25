"""
【stage5 生命周期与负责人权限测试】

覆盖回归最密集的五块（都曾在真实会话里出过 bug）：
  1. 淘汰确认：advance 打 fail 不带 confirm_eliminate → 400；带了才淘汰
  2. 淘汰通知：fail 后立即生成（stage=eliminated，已发送，占位符渲染）；无手机号的候选人不生成
  3. 销号与恢复：淘汰 2 天内可登录；超期登录 403（拦截信息含淘汰说明）并销号；
     技术端列表标注 close_reason/恢复截止；保存期内恢复成功；超 90 天恢复 400
  4. 负责人权限：阶段认领、跨负责人 403、无主可编辑、资料编辑权限、
     技术端单个/批量/清空改归属（清空候选人负责人不清阶段认领）
  5. 关卡负责人调整接口：指派/换人/清空，非法值 400，HR 侧即时生效

用法：服务跑在 ATS_BASE（默认 8001 测试服务），直连库清理用 ATS_DB_NAME / ATS_DB_PASSWORD。
"""
import os
import sys
import time
from datetime import datetime, timedelta

import httpx
import pymysql
from sqlalchemy import select

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.getenv("ATS_DB_NAME"):
    os.environ["DATABASE_URL"] = (
        f"mysql+pymysql://root:{os.getenv('ATS_DB_PASSWORD', '')}"
        f"@127.0.0.1:3306/{os.environ['ATS_DB_NAME']}?charset=utf8mb4"
    )

from app.core.database import SessionLocal
from app.models import (
    Application,
    Candidate,
    CandidateNotice,
    Position,
    StageOwner,
    User,
)
from app.services.security import create_access_token, hash_password

BASE = os.getenv("ATS_BASE", "http://127.0.0.1:8001")
DB_NAME = os.getenv("ATS_DB_NAME", "ats")
_env_pw = None
_env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(_env_file):
    import re as _re
    _m = _re.search(r"://[^:]+:([^@]+)@", open(_env_file, encoding="utf-8").read())
    if _m:
        _env_pw = _m.group(1)
DB_PW = os.getenv("ATS_DB_PASSWORD") or _env_pw or ""

STAMP = str(int(time.time()))
P_A, P_B, P_C = (f"1399999{STAMP[-3:]}{i}" for i in (1, 2, 3))
_check_n = [0]


def check(cond, msg, detail=""):
    if cond:
        _check_n[0] += 1
        print(f"  ok  {msg}")
    else:
        print(f"  [FAIL] {msg} {str(detail)[:180]}")
        raise AssertionError(msg)


def db_conn():
    return pymysql.connect(host="127.0.0.1", port=3306, user="root", password=DB_PW, database=DB_NAME)


def cleanup():
    conn = db_conn()
    try:
        with conn.cursor() as cur:
            # 按岗位找投递（覆盖无手机号的候选人），外键顺序：通知 → 投递（级联清阶段负责人）→ 候选人/账号 → 岗位
            cur.execute(
                "SELECT ID FROM Position WHERE position_name LIKE %s",
                (f"生命周期测试岗{STAMP}%",),
            )
            for (pid,) in cur.fetchall():
                cur.execute("SELECT ID, Can_ID FROM Application WHERE Pos_ID=%s", (pid,))
                for aid, can_id in cur.fetchall():
                    cur.execute(
                        "DELETE FROM Candidate_Notice WHERE Application_ID=%s", (aid,)
                    )
                    cur.execute("DELETE FROM Application WHERE ID=%s", (aid,))
                    if can_id:
                        cur.execute("DELETE FROM User WHERE candidate_id=%s", (can_id,))
                        cur.execute("DELETE FROM Candidate WHERE ID=%s", (can_id,))
                cur.execute("DELETE FROM Position WHERE ID=%s", (pid,))
            for uname in (f"lc_hr_{STAMP}", f"lc_hrb_{STAMP}"):
                cur.execute("DELETE FROM User WHERE username=%s", (uname,))
        conn.commit()
    finally:
        conn.close()


def make_hr(db, username, phone):
    u = User(username=username, phone=phone, real_name=username[-2:] + "实名", role="hr",
             password_hash=hash_password("x"), is_active=1, create_time=datetime.now())
    db.add(u)
    db.flush()
    return u


def main() -> int:
    cleanup()
    c = httpx.Client(base_url=BASE, timeout=20)
    db = SessionLocal()
    try:
        # ---- 准备：HR 甲/乙、候选人（甲建档）、岗位、投递 ----
        hr_a = make_hr(db, f"lc_hr_{STAMP}", P_A)
        hr_b = make_hr(db, f"lc_hrb_{STAMP}", P_B)
        from app.services.accounts import ensure_candidate_account

        cand = Candidate(name=f"生命周期{STAMP}", phone=P_C, owner_id=hr_a.id, create_time=datetime.now())
        db.add(cand)
        db.flush()
        ensure_candidate_account(db, cand)
        pos = Position(position_name=f"生命周期测试岗{STAMP}")
        db.add(pos)
        db.flush()
        app = Application(can_id=cand.id, pos_id=pos.id, overall_status="pending",
                          current_stage="test", create_time=datetime.now())
        db.add(app)
        db.commit()
        cand_user = db.scalar(select(User).where(User.candidate_id == cand.id))
        ids = dict(hrA=hr_a.id, hrB=hr_b.id, cand=cand.id, cand_user=cand_user.id, app=app.id)
        db.close()

        TA = {"Authorization": f"Bearer {create_access_token(ids['hrA'], 'hr')}"}
        TB = {"Authorization": f"Bearer {create_access_token(ids['hrB'], 'hr')}"}
        s = SessionLocal()
        aid = s.scalar(select(User).where(User.role == "admin")).id
        s.close()
        TM = {"Authorization": f"Bearer {create_access_token(aid, 'admin')}"}
        APP = ids["app"]

        def stage_owner(stage):
            s = SessionLocal()
            try:
                return s.scalar(select(StageOwner).where(
                    StageOwner.application_id == APP, StageOwner.stage == stage))
            finally:
                s.close()

        # ---- 1. 淘汰确认 ----
        r = c.post(f"/api/applications/{APP}/advance", headers=TA,
                   json={"fromStage": "test", "result": "fail"})
        check(r.status_code == 400, "淘汰不带确认 → 400", r.text[:120])
        r = c.post(f"/api/applications/{APP}/advance", headers=TA,
                   json={"fromStage": "test", "result": "fail", "confirm_eliminate": True})
        check(r.status_code == 200 and r.json()["overall_status"] == "fail", "带确认淘汰成功", r.text[:120])

        # ---- 2. 淘汰通知立即生成 + 无手机号边界 ----
        s = SessionLocal()
        n = s.scalar(select(CandidateNotice).where(
            CandidateNotice.application_id == APP, CandidateNotice.stage == "eliminated"))
        check(n is not None and n.send_time is not None, "淘汰通知已生成并发送")
        check("生命周期测试岗" in (n.body or ""), "占位符已渲染（岗位）")
        # 无手机号的候选人：真实走一遍淘汰，不应生成通知
        c2 = Candidate(name=f"无号{STAMP}", phone=None, owner_id=hr_a.id, create_time=datetime.now())
        s.add(c2)
        s.flush()
        app2 = Application(can_id=c2.id, pos_id=pos.id, overall_status="pending",
                           current_stage="test", create_time=datetime.now())
        s.add(app2)
        s.commit()
        app2_id = app2.id
        s.close()
        r = c.post(f"/api/applications/{app2_id}/advance", headers=TA,
                   json={"fromStage": "test", "result": "fail", "confirm_eliminate": True})
        check(r.status_code == 200, "无手机号候选人也照常淘汰（通知边界在通知侧）", r.text[:120])
        s = SessionLocal()
        n2 = s.scalar(select(CandidateNotice).where(
            CandidateNotice.application_id == app2_id, CandidateNotice.stage == "eliminated"))
        check(n2 is None, "无手机号候选人不生成淘汰通知")
        s.close()

        # ---- 3. 销号与恢复 ----
        CH = {"Authorization": f"Bearer {create_access_token(ids['cand_user'], 'candidate')}"}
        r = c.get("/api/portal/notices", headers=CH)
        check(r.status_code == 200, "淘汰 2 天内候选人可正常访问", r.status_code)
        # 回溯淘汰时间到 3 天前 → 门卫拦截 + 销号
        s = SessionLocal()
        s.get(Application, APP).test_time = datetime.now() - timedelta(days=3)
        s.commit()
        s.close()
        r = c.get("/api/portal/notices", headers=CH)
        d = r.json().get("detail", "")
        check(r.status_code == 403 and any(w in d for w in ("淘汰", "未能通过")),
              "超期访问 403 且拦截信息含淘汰说明", r.text[:120])

        accounts = c.get("/api/tech/accounts", headers=TM, params={"keyword": P_C}).json()
        row = next(x for x in accounts if x["candidate_id"] == ids["cand"])
        check(row["close_reason"] == "eliminated" and row["restore_deadline"],
              "技术端标注已淘汰销号 + 恢复截止")
        r = c.put(f"/api/tech/candidate-owners/stage-owners/{APP}", headers=TM,
                  json={"owners": {}})
        check(r.status_code == 200, "关卡负责人空提交通路")
        r = c.put(f"/api/tech/accounts/{row['id']}/status", headers=TM, json={"is_active": True})
        check(r.status_code == 200, "保存期内恢复成功", r.text[:120])
        r = c.get("/api/portal/notices", headers=CH)
        check(r.status_code == 200, "恢复后候选人可正常访问")
        # 超 90 天保存期
        s = SessionLocal()
        s.get(Application, APP).test_time = datetime.now() - timedelta(days=100)
        u = s.scalar(select(User).where(User.candidate_id == ids["cand"]))
        u.restore_time = None
        u.is_active = 0
        s.commit()
        s.close()
        r = c.put(f"/api/tech/accounts/{row['id']}/status", headers=TM, json={"is_active": True})
        check(r.status_code == 400 and "保存期" in r.json()["detail"], "超 3 个月保存期恢复 400",
              r.text[:120])

        # ---- 4. 负责人权限 ----
        # 投递已淘汰（停在 test，test 由甲淘汰时认领）；候选人负责人仍是甲
        r = client_put_stage_note(c, TA, APP, "test", "甲认领 test")
        check(r["ok"], "候选人负责人（甲）可编辑本关")
        r = client_put_stage_note(c, TB, APP, "test", "乙想改")
        check(not r["ok"] and r["status"] == 403, "乙编辑甲认领的 test 关 → 403", r["text"])
        r = c.put(f"/api/candidates/{ids['cand']}", headers=TB, json={"remark": "乙改"})
        check(r.status_code == 403, "非负责人改资料 → 403", r.text[:120])
        r = client_put_stage_note(c, TA, APP, "test", "甲再改")
        check(r["ok"], "甲（阶段负责人）仍可编辑")

        # 无主候选人的关卡：乙先编辑即认领；甲非负责人也不可改
        s = SessionLocal()
        c3 = Candidate(name=f"无主{STAMP}", phone=None, owner_id=None, create_time=datetime.now())
        s.add(c3)
        s.flush()
        app3 = Application(can_id=c3.id, pos_id=pos.id, overall_status="pending",
                           current_stage="test", create_time=datetime.now())
        s.add(app3)
        s.commit()
        app3_id = app3.id
        cand3_id = c3.id
        s.close()
        r = client_put_stage_note(c, TB, app3_id, "test", "乙先到先得")
        check(r["ok"], "无主候选人的无主关卡：乙可编辑并认领")
        r = client_put_stage_note(c, TA, app3_id, "test", "甲后到")
        check(not r["ok"] and r["status"] == 403, "甲编辑乙认领的关 → 403", r["text"])
        r = c.put(f"/api/candidates/{cand3_id}", headers=TA, json={"remark": "甲改无主候选人"})
        check(r.status_code == 200, "暂无负责人的候选人任意 HR 可改资料")

        # 技术端批量/单个改归属
        r = c.put("/api/tech/candidate-owners/batch", headers=TM,
                  json={"candidate_ids": [ids["cand"]], "owner_id": ids["hrB"]})
        check(r.status_code == 200 and r.json()["updated"] == 1, "技术端批量改归属")
        r = client_put_stage_note(c, TB, APP, "test", "乙全局可改")
        check(r["ok"], "新负责人（乙）全局可编辑")
        r = client_put_stage_note(c, TA, APP, "test", "甲想改")
        check(r["ok"], "甲仍可改自己认领的 test 关（阶段认领不受归属影响）")
        r = c.put(f"/api/tech/candidate-owners/{ids['cand']}", headers=TM, json={"owner_id": None})
        check(r.status_code == 200, "清空候选人负责人")
        r = client_put_stage_note(c, TA, APP, "test", "清空后甲仍认领 test")
        check(r["ok"], "清空归属不清阶段认领")

        # 技术端指派 test 关给甲 → 乙 403
        r = c.put(f"/api/tech/candidate-owners/stage-owners/{APP}", headers=TM,
                  json={"owners": {"test": ids["hrA"], "ai": None, "resume": None,
                                    "pro": None, "hr": None, "final": None}})
        check(r.status_code == 200, "技术端指派 test 关给甲")
        r = client_put_stage_note(c, TB, APP, "test", "乙被换掉")
        check(not r["ok"] and r["status"] == 403, "指派后乙对 test 关 403")
        r = c.put(f"/api/tech/candidate-owners/stage-owners/{APP}", headers=TM,
                  json={"owners": {"test": 99999999}})
        check(r.status_code == 400, "非法 HR → 400")
        r = c.put(f"/api/tech/candidate-owners/stage-owners/{APP}", headers=TM,
                  json={"owners": {"bad": ids["hrB"]}})
        check(r.status_code == 400, "非法关卡 → 400")

        print(f"== 生命周期与负责人权限：通过 {_check_n[0]} 项，失败 0 项")
        return 0
    finally:
        db.close()
        cleanup()


def client_put_stage_note(c, headers, app_id, stage, reason):
    r = c.put(f"/api/applications/{app_id}/stage-note", headers=headers,
              json={"stage": stage, "reason": reason})
    return {"ok": r.status_code == 200, "status": r.status_code, "text": r.text[:150]}


def stage_owner_of(app_id, stage):
    s = SessionLocal()
    try:
        return s.scalar(select(StageOwner).where(
            StageOwner.application_id == app_id, StageOwner.stage == stage))
    finally:
        s.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as e:
        print(f"  [FAIL] {e}")
        sys.exit(1)
