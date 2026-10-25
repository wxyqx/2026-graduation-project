"""
【候选人通知服务】关卡通过后按模板发通知。

谁触发：applications 的 advance 接口在 pass 了 test/pro/hr/final 后按模板生成**草稿**（候选人不可见）；
HR 在投递详情「候选人通知」里逐人编辑后确认发送，发送后候选人登录弹窗展示。
去重：同一候选人 + 同一投递 + 同一关卡只生成一条草稿（撤回再重新通过不会重复生成）。
模板占位符：{候选人} {岗位} {关卡}，生成草稿时渲染，之后 HR 还可逐人修改。
"""
import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, Candidate, CandidateFile, CandidateNotice, Position
from app.services import settings as settings_svc
from app.services.state_machine import STAGE_LABELS


def send_stage_notice(db: Session, app: Application, stage: str) -> None:
    """这一关通过后按模板发通知；开关关了或已发过就跳过。调用方负责 commit。"""
    if stage not in settings_svc.STAGE_NOTICE_STAGES:
        return
    cfg = settings_svc.get_stage_notice(db).get(stage) or {}
    if not cfg.get("enabled"):
        return
    # 去重：撤回再通过不重复发
    exists = db.scalar(
        select(CandidateNotice).where(
            CandidateNotice.candidate_id == app.can_id,
            CandidateNotice.application_id == app.id,
            CandidateNotice.stage == stage,
        )
    )
    if exists is not None:
        return
    cand = db.get(Candidate, app.can_id)
    pos = db.get(Position, app.pos_id) if app.pos_id else None
    values = {
        "候选人": (cand.name if cand else None) or "候选人",
        "岗位": (pos.position_name if pos else None) or "在招岗位",
        # onboard（入职通知）不在 7 关流程里，关卡名直接叫「入职」
        "关卡": "入职" if stage == "onboard" else STAGE_LABELS.get(stage, stage),
    }
    def render(text: str) -> str:
        for k, v in values.items():
            text = text.replace("{" + k + "}", v)
        return text

    # 生成草稿：Send_Time 为空，候选人不可见；HR 在投递详情逐人编辑后再发送
    db.add(
        CandidateNotice(
            candidate_id=app.can_id,
            application_id=app.id,
            stage=stage,
            title=render(cfg.get("title") or "")[:100] or "通过通知",
            body=render(cfg.get("body") or "") or None,
            send_time=None,
        )
    )
    db.flush()


def list_app_notices(db: Session, application_id: int) -> list[CandidateNotice]:
    """HR 视角：某次投递的全部通知（草稿 + 已发送），新的在前。"""
    return list(
        db.scalars(
            select(CandidateNotice)
            .where(CandidateNotice.application_id == application_id)
            .order_by(CandidateNotice.id.desc())
        ).all()
    )


# 危险标签：<script> 等（成对或自闭合都清）
_SCRIPT_RE = re.compile(r"<\s*(script|style|iframe|object|embed|link|meta)\b[^>]*>.*?<\s*/\s*\1\s*>|<\s*(script|style|iframe|object|embed|link|meta)\b[^>]*/?>", re.I | re.S)
# 事件属性：onclick=… / onerror=… 等
_ON_ATTR_RE = re.compile(r'''\s+on\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)''', re.I)
# javascript: 伪协议链接
_JS_URL_RE = re.compile(r'(href|src)\s*=\s*(["\']?)\s*javascript:', re.I)


def sanitize_html(text: str) -> str:
    """通知正文允许少量排版 HTML（加粗/字号/链接），其余危险内容清洗掉。"""
    text = _SCRIPT_RE.sub("", text or "")
    text = _ON_ATTR_RE.sub("", text)
    text = _JS_URL_RE.sub(r"\1=\2", text)
    return text.strip()


def edit_notice(db: Session, notice_id: int, title: str, body: str) -> CandidateNotice | None:
    """HR 编辑通知内容；只允许改还没发送的草稿。"""
    n = db.get(CandidateNotice, notice_id)
    if n is None:
        raise LookupError("通知不存在")
    if n.send_time is not None:
        raise PermissionError("已发送的通知不能修改")
    n.title = sanitize_html((title or "").strip())[:100] or n.title
    n.body = sanitize_html((body or "")[:5000]) or None
    db.flush()
    return n


OFFER_FILE_LABELS = {"offer_agreement": "录用协议", "offer": "Offer", "background_check": "背景调查"}
FILE_LIST_MARKER = "offer-file-list"


def offer_file_list_html(db: Session, application_id: int) -> str:
    """这次投递的 Offer 文件清单（HTML），用于附进通知：什么文件是什么，一目了然。"""
    from app.services.file_service import OFFER_CATEGORIES

    files = db.scalars(
        select(CandidateFile)
        .where(
            CandidateFile.application_id == application_id,
            CandidateFile.category.in_(OFFER_CATEGORIES),
        )
        .order_by(CandidateFile.category, CandidateFile.id)
    ).all()
    if not files:
        return ""
    rows = "".join(
        f"<li>{OFFER_FILE_LABELS.get(f.category, f.category)}：{f.original_name}</li>" for f in files
    )
    return (
        f'<div class="{FILE_LIST_MARKER}"><b>随通知附上以下文件</b>（请到「文件」页下载填写）：'
        f"<ul>{rows}</ul></div>"
    )


def send_notice(db: Session, notice_id: int) -> CandidateNotice | None:
    """HR 确认发送：写入发送时间，候选人端立即可见（Offer 文件也随之可见）。已发送重复调用幂等。"""
    n = db.get(CandidateNotice, notice_id)
    if n is None:
        raise LookupError("通知不存在")
    # 边界：候选人没有手机号 = 没开通候选人端账号，通知发出去也没人能收到
    cand = db.get(Candidate, n.candidate_id)
    if not (cand and cand.phone):
        raise PermissionError("发送失败：该候选人没有手机号，未开通候选人端账号；请先在候选人档案补上手机号，再重试发送")
    if n.send_time is None:
        # 把这次投递的 Offer 文件清单附进正文（HR 预览时已看到同一份清单，这里兜底补齐）
        listing = offer_file_list_html(db, n.application_id) if n.application_id else ""
        if listing and FILE_LIST_MARKER not in (n.body or ""):
            body = (n.body or "")
            n.body = (body + ("<br>" if body and not body.endswith(">") else "") + listing)[:5000]
        n.send_time = datetime.now()
        db.flush()
    return n


def discard_notice(db: Session, notice_id: int) -> None:
    """HR 放弃一条草稿（不发送）。已发送的不能删——那是发给候选人的记录。"""
    n = db.get(CandidateNotice, notice_id)
    if n is None:
        raise LookupError("通知不存在")
    if n.send_time is not None:
        raise PermissionError("已发送的通知是发送记录，不能删除")
    db.delete(n)
    db.flush()


def list_notices(db: Session, candidate_id: int) -> list[CandidateNotice]:
    """候选人通知列表，新的在前（未读的排前面靠前端弹窗处理）。"""
    return list(
        db.scalars(
            select(CandidateNotice)
            .where(CandidateNotice.candidate_id == candidate_id)
            .order_by(CandidateNotice.read_time.isnot(None), CandidateNotice.send_time.desc())
        ).all()
    )


def mark_read(db: Session, candidate_id: int, notice_id: int) -> bool:
    """把自己的某条通知标记为已读。返回是否存在。"""
    n = db.get(CandidateNotice, notice_id)
    if n is None or n.candidate_id != candidate_id or n.read_time is not None:
        return n is not None and n.candidate_id == candidate_id
    n.read_time = datetime.now()
    db.commit()
    return True
