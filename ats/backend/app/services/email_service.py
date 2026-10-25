"""
【邮件通知服务】SMTP 配置存取 + 通知邮件发送

配置存 App_Setting（键 email_smtp），由技术管理端维护；发送走标准 SMTP（465=SSL / 587=STARTTLS）。
原则：邮件是「附赠渠道」——发送失败只写运行日志，绝不影响通知本身（站内弹窗才是主通道）。
"""
import json
import re
import smtplib
import socket
import ssl
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Candidate, CandidateNotice, EmailOutbox
from app.services.settings import get_setting, get_system_admin, set_setting

EMAIL_KEY = "email_smtp"

# 邮件正文是通知的富文本 HTML；纯文本兜底版本需要把标签剥掉
_TAG_RE = re.compile(r"<br\s*/?>", re.I)
_TAG_ALL_RE = re.compile(r"<[^>]+>")


def _default() -> dict:
    return {
        "enabled": False,
        "host": "",
        "port": 465,
        "use_ssl": True,
        "username": "",
        "password": "",
        "sender_name": "ATS 招聘系统",
        "site_url": "http://127.0.0.1:5173/portal/login",
    }


def get_email_config(db: Session) -> dict:
    """读 SMTP 配置（密码原样返回——只在后端内部用；给前端的接口自行脱敏）。"""
    admin = get_system_admin(db)
    raw = get_setting(db, admin.id, EMAIL_KEY) if admin else None
    cfg = _default()
    if raw:
        import json

        try:
            saved = json.loads(raw)
            if isinstance(saved, dict):
                cfg.update({k: v for k, v in saved.items() if k in cfg})
        except (ValueError, TypeError):
            pass
    cfg["enabled"] = bool(cfg.get("enabled"))
    cfg["port"] = int(cfg.get("port") or 465)
    cfg["use_ssl"] = bool(cfg.get("use_ssl", True))
    return cfg


def set_email_config(db: Session, cfg: dict) -> dict:
    """保存 SMTP 配置。password 传空字符串 = 保持原密码不变（前端不回显密码）。"""
    admin = get_system_admin(db)
    if admin is None:
        raise ValueError("系统里还没有技术管理员账号")
    current = get_email_config(db)
    password = str(cfg.get("password") or "").strip() or current.get("password") or ""
    clean = {
        "enabled": bool(cfg.get("enabled", False)),
        "host": str(cfg.get("host") or "").strip(),
        "port": int(cfg.get("port") or 465),
        "use_ssl": bool(cfg.get("use_ssl", True)),
        "username": str(cfg.get("username") or "").strip(),
        "password": password,
        "sender_name": str(cfg.get("sender_name") or "").strip()[:50] or "ATS 招聘系统",
        "site_url": str(cfg.get("site_url") or "").strip() or _default()["site_url"],
    }
    set_setting(db, admin.id, EMAIL_KEY, json.dumps(clean, ensure_ascii=False))
    return get_email_config(db)


def strip_html(html: str) -> str:
    """富文本 HTML → 可读纯文本（邮件的纯文本兜底 / 登录拦截信息用）。"""
    text = _TAG_ALL_RE.sub("", _TAG_RE.sub("\n", html or ""))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _send(cfg: dict, to_email: str, to_name: str, subject: str, html: str) -> None:
    """底层发信：按配置走 SSL(465) 或 STARTTLS(587/25)。失败抛异常，由调用方兜住。"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = formataddr((str(Header(cfg.get("sender_name") or "ATS 招聘系统", "utf-8")), cfg["username"]))
    msg["To"] = formataddr((str(Header(to_name or to_email, "utf-8")), to_email))
    plain = strip_html(html)
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    port = int(cfg.get("port") or 465)
    # smtplib 默认用 socket.getfqdn() 当 EHLO 本机名，本机 DNS 挂起时会白等 9 秒+；
    # gethostname() 瞬时完成且同样可用，避免每封邮件慢十几秒
    local = socket.gethostname()
    if cfg.get("use_ssl", True):
        server = smtplib.SMTP_SSL(cfg["host"], port, timeout=15, local_hostname=local)
    else:
        server = smtplib.SMTP(cfg["host"], port, timeout=15, local_hostname=local)
        if port == 587:  # 587 惯例走 STARTTLS；其他端口（25 / 自建 mock）明文连接
            server.starttls(context=ssl.create_default_context())
    try:
        if cfg.get("password"):  # 内网 relay 可能免认证：没配密码就跳过 login
            server.login(cfg["username"], cfg["password"])
        server.sendmail(cfg["username"], [to_email], msg.as_string())
    finally:
        server.quit()


def send_notice_email(notice_id: int) -> str | None:
    """把一条已发送的站内通知同步发一封邮件给候选人。

    - SMTP 没启用 / 候选人没有 email / 发送失败：返回 None 或错误说明，**绝不抛出**
    - 独立开数据库会话：由 BackgroundTasks 在响应后调用，不依赖请求的 session
    - BackgroundTasks 会吞掉任务异常（服务端毫无痕迹），所以这里兜住一切异常并打印
    """

    try:
        return _send_notice_email_impl(notice_id)
    except Exception:
        import traceback

        print("[email] 后台任务异常：" + traceback.format_exc())
        return None


def _build_html(n, site: str) -> str:
    return (
        f"<div style=\"font-family: sans-serif; max-width: 640px\">"
        f"<h3 style=\"margin: 0 0 8px\">{n.title}</h3>"
        f"<div style=\"line-height: 1.8\">{n.body or ''}</div>"
        f"<hr style=\"border: 0; border-top: 1px solid #eee; margin: 16px 0\">"
        f"<p style=\"color: #888; font-size: 13px\">请登录候选人端查看详情与文件："
        f"<a href=\"{site}\">{site}</a></p></div>"
    )


MAX_ATTEMPTS = 3  # 同一封邮件最多尝试 3 次（首次 + 2 次重试），超过标记 failed


def _upsert_outbox(session, notice, to_email: str, ok: bool, error: str | None) -> None:
    """发件箱记账：一条通知一行；失败 pending（未满次数）/ failed，成功 sent。"""
    from datetime import datetime

    row = session.scalar(select(EmailOutbox).where(EmailOutbox.notice_id == notice.id))
    if row is None:
        row = EmailOutbox(
            notice_id=notice.id, to_email=to_email, subject=notice.title or "招聘通知",
            status="pending", attempts=0, create_time=datetime.now(),
        )
        session.add(row)
    row.attempts += 1
    row.status = "sent" if ok else ("pending" if row.attempts < MAX_ATTEMPTS else "failed")
    row.last_error = None if ok else (error or "")[:500]
    row.update_time = datetime.now()
    session.commit()


def _deliver(session, notice, cand, cfg) -> str | None:
    """构建并发送一封通知邮件，返回 None=成功 / 错误说明。"""
    to_email = (cand.email or "").strip()
    try:
        _send(cfg, to_email, cand.name or to_email, notice.title or "招聘通知",
              _build_html(notice, cfg.get("site_url") or ""))
        return None
    except Exception as e:
        return str(e)


def retry_outbox(session, limit: int = 5) -> int:
    """清扫发件箱：把 pending（未满次数）的邮件重试一遍，返回成功条数。

    触发时机：每次发送新邮件前、后端启动时。配置没启用就跳过。
    """
    cfg = get_email_config(session)
    if not (cfg.get("enabled") and cfg.get("host") and cfg.get("username")):
        return 0
    rows = session.scalars(
        select(EmailOutbox).where(EmailOutbox.status == "pending").order_by(EmailOutbox.id).limit(limit)
    ).all()
    sent = 0
    for row in rows:
        notice = session.get(CandidateNotice, row.notice_id) if row.notice_id else None
        if notice is None:
            continue
        cand = session.get(Candidate, notice.candidate_id)
        if cand is None:
            continue
        err = _deliver(session, notice, cand, cfg)
        _upsert_outbox(session, notice, row.to_email, err is None, err)
        if err is None:
            sent += 1
            print(f"[email] 重试成功 to={row.to_email}: {notice.title}")
    return sent


def startup_retry() -> None:
    """后端启动时清扫一次发件箱（独立会话；异常吞掉，不影响启动）。"""
    from app.core.database import SessionLocal

    try:
        session = SessionLocal()
        try:
            retry_outbox(session)
        finally:
            session.close()
    except Exception as e:
        print(f"[email] 启动清扫失败（忽略）：{e}")


def _send_notice_email_impl(notice_id: int) -> str | None:
    from app.core.database import SessionLocal
    from app.services.log_service import log_action

    session = SessionLocal()
    try:
        n = session.get(CandidateNotice, notice_id)
        if n is None or n.send_time is None:
            return None
        cand = session.get(Candidate, n.candidate_id)
        if cand is None or not (cand.email or "").strip():
            return None
        cfg = get_email_config(session)
        # 密码可选（内网 relay 免认证）；host + username 必需
        if not (cfg.get("enabled") and cfg.get("host") and cfg.get("username")):
            return None

        retry_outbox(session)  # 顺带清扫之前失败的邮件（best effort）

        to_email = cand.email.strip()
        err = _deliver(session, n, cand, cfg)
        _upsert_outbox(session, n, to_email, err is None, err)
        admin = get_system_admin(session)
        if admin is not None:
            log_action(
                session, admin, "update", target_type="notice", target_id=notice_id,
                detail={"email_sent": err is None, "to": to_email, **({"email_error": err[:200]} if err else {})},
            )
            session.commit()
        if err:
            print(f"[email] 发送失败 to={to_email}（已进发件箱重试）: {err}")
            return err
        print(f"[email] 已发送 to={to_email}: {n.title}")
        return None
    finally:
        session.close()


def send_test_email(db: Session, to_email: str) -> str | None:
    """技术管理端「发送测试邮件」：验证 SMTP 配置是否可用。返回 None=成功，或错误说明。"""
    cfg = get_email_config(db)
    admin = get_system_admin(db)
    admin_name = (admin.real_name or admin.username) if admin else "管理员"
    html = (
        f"<p>这是一封测试邮件——你收到它，说明 ATS 的 SMTP 配置可用。</p>"
        f"<p style=\"color: #888\">发件配置：{cfg.get('host')}:{cfg.get('port')} / {cfg.get('username')}</p>"
    )
    try:
        _send(cfg, to_email, admin_name, "【ATS】SMTP 配置测试邮件", html)
        return None
    except Exception as e:
        return str(e)

