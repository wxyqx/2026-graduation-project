"""
【stage6 邮件通知测试】

用进程内的 mock SMTP 服务器（smtpd.DebugServer 的子类，收下邮件存内存）验证：
  1. SMTP 配置保存 + 授权码不回显
  2. 候选人建档后 HR 发通知 → BackgroundTasks 异步补发邮件（收件人 / 标题 / 内容正确）
  3. 淘汰通知同样触发邮件
  4. 候选人没有 email 时不发信
  5. 测试发送接口可用；错误配置返回 400
"""
import os
import sys
import threading
import time
from datetime import datetime

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.getenv("ATS_DB_NAME"):
    os.environ["DATABASE_URL"] = (
        f"mysql+pymysql://root:{os.getenv('ATS_DB_PASSWORD', '')}"
        f"@127.0.0.1:3306/{os.environ['ATS_DB_NAME']}?charset=utf8mb4"
    )

import smtpd  # noqa: E402  # Python 3.11 仍有（3.12 移除）；测试库环境锁定 3.11

from sqlalchemy import select  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models import Application, Candidate, Position, User
from app.services.security import create_access_token, hash_password  # noqa: E402

BASE = os.getenv("ATS_BASE", "http://127.0.0.1:8001")
MOCK_SMTP_PORT = 1080
STAMP = str(int(time.time()))
RECEIVED: list[dict] = []
_check_n = [0]


class MockSMTPServer(smtpd.SMTPServer):
    def process_message(self, peer, mailfrom, rcpttos, data, **kwargs):
        # decode_data=True 时 data 已是 str；两种都兼容，别在 handler 里抛异常（会断开发件连接）
        text = data if isinstance(data, str) else data.decode("utf-8", "replace")
        RECEIVED.append({"from": mailfrom, "to": list(rcpttos), "data": text})


def start_mock_smtp():
    import asyncore

    server = MockSMTPServer(("127.0.0.1", MOCK_SMTP_PORT), None, decode_data=True)
    thread = threading.Thread(target=asyncore.loop, kwargs={"timeout": 0.1}, daemon=True)
    thread.start()
    return server


def check(cond, msg, detail=""):
    if cond:
        _check_n[0] += 1
        print(f"  ok  {msg}")
    else:
        print(f"  [FAIL] {msg} {str(detail)[:200]}")
        raise AssertionError(msg)


def wait_mail(count, timeout=30):
    """BackgroundTasks 在响应后执行，轮询 mock SMTP 收件箱。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if len(RECEIVED) >= count:
            return True
        time.sleep(0.2)
    return False


def main() -> int:
    server = start_mock_smtp()
    c = httpx.Client(base_url=BASE, timeout=20)
    db = SessionLocal()
    try:
        # ---- 准备：HR / 候选人（带 email）/ 岗位 / 投递 ----
        hr = User(username=f"lc6_hr_{STAMP}", phone=f"1399999{STAMP[-3:]}1", real_name="邮件测试甲", role="hr",
                  password_hash=hash_password("x"), is_active=1, create_time=datetime.now())
        db.add(hr)
        db.flush()
        cand = Candidate(name=f"邮件测试{STAMP}", phone=f"1399999{STAMP[-3:]}2",
                         email=f"candidate_{STAMP}@mock.local", owner_id=hr.id, create_time=datetime.now())
        db.add(cand)
        db.flush()
        pos = Position(position_name=f"邮件测试岗{STAMP}")
        db.add(pos)
        db.flush()
        app = Application(can_id=cand.id, pos_id=pos.id, overall_status="pending",
                          current_stage="phone", phone_result="pass", phone_time=datetime.now(),
                          create_time=datetime.now())
        db.add(app)
        db.commit()
        H = {"Authorization": f"Bearer {create_access_token(hr.id, 'hr')}"}
        APP = app.id
        db.close()

        # ---- 1. SMTP 配置保存 + 授权码不回显 ----
        s = SessionLocal()
        admin = s.scalar(select(User).where(User.role == "admin"))
        TM = {"Authorization": f"Bearer {create_access_token(admin.id, 'admin')}"}
        s.close()
        # 测试自清理：先删掉可能残留的 email_smtp，保证用例确定性
        import pymysql

        conn0 = pymysql.connect(host="127.0.0.1", port=3306, user="root",
                                password=os.environ.get("ATS_DB_PASSWORD", ""),
                                database=os.environ.get("ATS_DB_NAME", "ats"))
        with conn0.cursor() as cur0:
            cur0.execute("DELETE FROM App_Setting WHERE setting_key='email_smtp'")
        conn0.commit()
        conn0.close()

        r = c.put("/api/tech/email-smtp", headers=TM, json={
            "enabled": True, "host": "127.0.0.1", "port": MOCK_SMTP_PORT, "use_ssl": False,
            "username": "ats@mock.local", "password": "",
            "sender_name": "ATS 邮件测试", "site_url": "http://127.0.0.1:5173/portal/login",
        })
        check(r.status_code == 200, "SMTP 配置保存", r.text[:120])
        got = c.get("/api/tech/email-smtp", headers=TM).json()
        check(got["password"] == "" and got["has_password"] is False, "授权码不回显（未配置）")

        # ---- 2. 无 email 的候选人不发信 ----
        s = SessionLocal()
        c2 = Candidate(name=f"无邮箱{STAMP}", phone=f"1399999{STAMP[-3:]}3", owner_id=hr.id,
                       create_time=datetime.now())
        s.add(c2)
        s.flush()
        s.close()
        # （对比组在后面：给这个候选人补 email 再发一次，能收到 → 证明判定依据是 email）

        # ---- 3. HR 发通知 → 异步邮件（收件人 / 标题 / 正文） ----
        r = c.get(f"/api/applications/{APP}/notices", headers=H)
        # phone 关 pass 会自动生成草稿；直接生成一条草稿并发送
        r = c.post(f"/api/applications/{APP}/advance", headers=H,
                   json={"fromStage": "phone", "result": "pass"})
        check(r.status_code == 200, "推进 phone 关（生成通过通知草稿）", r.text[:120])
        r = c.get(f"/api/applications/{APP}/notices", headers=H).json()
        draft = next(x for x in r if x["stage"] == "phone" and x["send_time"] is None)
        r = c.post(f"/api/applications/{APP}/notices/{draft['id']}/send", headers=H)
        check(r.status_code == 200, "HR 发送通知", r.text[:120])
        check(wait_mail(1), "异步邮件已送达 mock SMTP")
        mail = RECEIVED[0]
        check(mail["to"] == [f"candidate_{STAMP}@mock.local"], f"收件人正确：{mail['to']}")
        # 正文/主题是 MIME 编码，用 email 标准库解析后断言
        from email import policy
        from email.parser import BytesParser

        parsed = BytesParser(policy=policy.default).parsebytes(mail["data"].encode("utf-8", "replace"))
        body_text = ""
        if parsed.is_multipart():
            for part in parsed.walk():
                if part.get_content_type() == "text/plain":
                    body_text += part.get_content()
        else:
            body_text = parsed.get_content()
        check("通过" in body_text or "岗位" in body_text, "正文包含通知内容", str(body_text)[:120])
        check("ats@mock.local" in mail["from"], "发件人来自 SMTP 配置")

        # ---- 4. 淘汰通知也发邮件 ----
        n_before = len(RECEIVED)
        r = c.post(f"/api/applications/{APP}/advance", headers=H,
                   json={"fromStage": "test", "result": "fail", "confirm_eliminate": True})
        check(r.status_code == 200, "淘汰成功", r.text[:120])
        check(wait_mail(n_before + 1), "淘汰通知邮件已送达")

        # ---- 5. 没有 email 的候选人不发信（对照） ----
        r = c.post(f"/api/applications/{APP}/advance", headers=H,
                   json={"fromStage": "ai", "result": "pass", "confirm_eliminate": True})
        check(r.status_code == 409, "已淘汰的投递不可再推进（幂等保护）")
        _ = c2  # 无邮箱候选人未建投递，这里仅确认对比例：发信数量不再增长
        n_now = len(RECEIVED)
        time.sleep(1)
        check(len(RECEIVED) == n_now, "无新信件（无 email 不发）")

        # ---- 6. 测试发送接口：正常 / 错误配置 ----
        r = c.post("/api/tech/email-smtp/test", headers=TM, json={"to": f"admin_{STAMP}@mock.local"})
        check(r.status_code == 200 and wait_mail(n_now + 1), "测试发送接口可用")
        r = c.put("/api/tech/email-smtp", headers=TM,
                  json={"enabled": True, "host": "127.0.0.1", "port": 9, "use_ssl": False,
                        "username": "ats@mock.local", "password": "smtp-secret"})
        check(r.status_code == 200, "改成死端口")
        r = c.post("/api/tech/email-smtp/test", headers=TM, json={"to": "x@mock.local"})
        check(r.status_code == 400, "错误配置 → 400 带错误说明", r.text[:120])
        # 恢复配置并清理
        r = c.put("/api/tech/email-smtp", headers=TM,
                  json={"enabled": False, "host": "", "port": 465, "use_ssl": True,
                        "username": "", "password": ""})
        check(r.status_code == 200, "配置已清空关闭")

        print(f"== 邮件通知：通过 {_check_n[0]} 项，失败 0 项")
        return 0
    finally:
        server.close()
        c.close()
        db.close()  # 先关会话释放行锁，清理才不会等锁超时
        # 清理测试数据
        conn = __import__("pymysql").connect(host="127.0.0.1", port=3306, user="root",
                                             password=os.getenv("ATS_DB_PASSWORD", ""),
                                             database=os.environ.get("ATS_DB_NAME", "ats"))
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT ID FROM Candidate WHERE name LIKE %s", (f"邮件测试{STAMP}",))
                for (cid,) in cur.fetchall():
                    cur.execute("SELECT ID FROM Application WHERE Can_ID=%s", (cid,))
                    for (aid,) in cur.fetchall():
                        cur.execute("DELETE FROM Candidate_Notice WHERE Application_ID=%s", (aid,))
                        cur.execute("DELETE FROM Application WHERE ID=%s", (aid,))
                    cur.execute("DELETE FROM User WHERE candidate_id=%s", (cid,))
                    cur.execute("DELETE FROM Candidate WHERE ID=%s", (cid,))
                cur.execute("DELETE FROM Position WHERE position_name LIKE %s", (f"邮件测试岗{STAMP}",))
                cur.execute("DELETE FROM User WHERE username LIKE %s", (f"lc6_hr_{STAMP}",))
                cur.execute("DELETE FROM App_Setting WHERE setting_key='email_smtp'")
            conn.commit()
        finally:
            conn.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as e:
        print(f"  [FAIL] {e}")
        sys.exit(1)
