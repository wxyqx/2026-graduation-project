"""
【候选人通知服务】关卡通过后按模板发通知。

谁触发：applications 的 advance 接口在 pass 了 test/pro/hr/final 后按模板生成**草稿**（候选人不可见）；
HR 在投递详情「候选人通知」里逐人编辑后确认发送，发送后候选人登录弹窗展示。
去重：同一候选人 + 同一投递 + 同一关卡只生成一条草稿（撤回再重新通过不会重复生成）。
模板占位符：{候选人} {岗位} {关卡}，生成草稿时渲染，之后 HR 还可逐人修改。
"""
import re
from datetime import datetime, timedelta

import nh3
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, Candidate, CandidateFile, CandidateNotice, Position, StageOwner, User
from app.services import settings as settings_svc
from app.services.state_machine import STAGE_FIELDS, STAGE_LABELS, STAGES

# 淘汰候选人的账号保留期：淘汰后多少天内还能登录查看通知，过期销号
ELIMINATE_KEEP_DAYS = 2
# 销号后数据保存期：候选人资料/投递/通知全部保留，技术管理员在此期限内可恢复账号
RETENTION_DAYS = 90


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
    values = _template_values(db, app, stage, owner_stage=_next_stage(stage))
    def render(text: str) -> str:
        return _render(text, values)

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


def _next_stage(stage: str) -> str | None:
    """7 关里的下一关；final / 非流程关（onboard）没有下一关。"""
    if stage in STAGES:
        i = STAGES.index(stage)
        return STAGES[i + 1] if i + 1 < len(STAGES) else None
    return None


def _resolve_owner_name(db: Session, app: Application, owner_stage: str | None) -> str:
    """占位符 {负责人} 的取值链：指定关卡的负责人 → 候选人负责人 → 通用称呼。

    通过通知传「下一关」（告知候选人接下来由谁负责）；淘汰通知传「本关」（评估人）；
    final 通过 / 入职没有下一关 → 自然落到候选人负责人。
    """
    if owner_stage:
        row = db.scalar(
            select(StageOwner).where(StageOwner.application_id == app.id, StageOwner.stage == owner_stage)
        )
        if row and row.user_id:
            u = db.get(User, row.user_id)
            if u and (u.real_name or u.username):
                return u.real_name or u.username
    cand = db.get(Candidate, app.can_id)
    if cand and cand.owner_id:
        u = db.get(User, cand.owner_id)
        if u and (u.real_name or u.username):
            return u.real_name or u.username
    return "招聘负责人"


def _template_values(db: Session, app: Application, stage: str, owner_stage: str | None = None) -> dict[str, str]:
    """模板占位符取值：{候选人} {岗位} {关卡} {负责人}。"""
    cand = db.get(Candidate, app.can_id)
    pos = db.get(Position, app.pos_id) if app.pos_id else None
    return {
        "候选人": (cand.name if cand else None) or "候选人",
        "岗位": (pos.position_name if pos else None) or "在招岗位",
        # onboard（入职通知）不在 7 关流程里，关卡名直接叫「入职」
        "关卡": "入职" if stage == "onboard" else STAGE_LABELS.get(stage, stage),
        "负责人": _resolve_owner_name(db, app, owner_stage),
    }


def _render(text: str, values: dict[str, str]) -> str:
    for k, v in values.items():
        text = text.replace("{" + k + "}", v)
    return text


def send_eliminate_notice(db: Session, app: Application, stage: str) -> None:
    """这关被打 fail 且投递就此淘汰（overall_status=fail）时，按「淘汰」模板**立即**发一条通知。

    立即写入发送时间：候选人保留期内登录，未读弹窗就能看到淘汰通知；
    超过保留期登录被拦时，拦截信息也用这份模板渲染。同投递去重（撤回再淘汰不重发）。
    调用方负责 commit。
    """
    cfg = settings_svc.get_stage_notice(db).get("eliminated") or {}
    if not cfg.get("enabled"):
        return
    cand = db.get(Candidate, app.can_id)
    # 与通过通知同样的边界：没手机号 = 没候选人端账号，发不出去
    if not (cand and cand.phone):
        return
    exists = db.scalar(
        select(CandidateNotice).where(
            CandidateNotice.candidate_id == app.can_id,
            CandidateNotice.application_id == app.id,
            CandidateNotice.stage == "eliminated",
        )
    )
    if exists is not None:
        return
    values = _template_values(db, app, stage, owner_stage=stage)  # 淘汰：本关负责人
    notice = CandidateNotice(
        candidate_id=app.can_id,
        application_id=app.id,
        stage="eliminated",
        title=_render(cfg.get("title") or "", values)[:100] or "应聘结果通知",
        body=_render(cfg.get("body") or "", values)[:5000] or None,
        send_time=datetime.now(),  # 立即发送，不等 HR 确认
    )
    db.add(notice)
    db.flush()
    return notice.id  # 交给 BackgroundTasks 异步补发邮件


# ---- 淘汰销号：淘汰后 ELIMINATE_KEEP_DAYS 天内还能登录看通知，过期登录被拦 ----

_TAG_RE = re.compile(r"<[^>]+>")


def _fail_stage_time(app: Application) -> tuple[str, datetime | None]:
    """这投递是在哪一关被打 fail 的、那一关的时间戳（ai 关没有时间列，退回 update_time）。"""
    for stage in reversed(STAGES):
        result_field, time_field = STAGE_FIELDS[stage]
        if getattr(app, result_field, None) == "fail":
            return stage, (getattr(app, time_field) if time_field else None) or app.update_time
    return "", None


def latest_elimination(db: Session, candidate_id: int) -> tuple[Application, str, datetime] | None:
    """这位候选人最近一次被淘汰的记录：(投递, 关卡, 淘汰时间)。没有就 None。"""
    best = None
    for a in db.scalars(
        select(Application).where(Application.can_id == candidate_id, Application.overall_status == "fail")
    ).all():
        stage, t = _fail_stage_time(a)
        if t and (best is None or t > best[2]):
            best = (a, stage, t)
    return best


def eliminate_notice_text(db: Session, app: Application, stage: str) -> str:
    """把淘汰通知模板渲染成纯文字（去掉富文本标签），给登录拦截信息用。"""
    cfg = settings_svc.get_stage_notice(db).get("eliminated") or {}
    values = _template_values(db, app, stage, owner_stage=stage)
    title = _render(cfg.get("title") or "", values)
    body = _render(cfg.get("body") or "", values)
    text = _TAG_RE.sub("", f"{title}　{body}" if body else title)
    return text.strip() or "很遗憾，您应聘的岗位未能通过，账号已按规则注销。如有疑问请联系 HR。"


def elimination_block(db: Session, candidate_id: int, *, deactivate: bool = False) -> str | None:
    """淘汰保留期检查（候选人登录、候选人门卫都走这里）。

    - 淘汰后保留期内：返回 None，正常放行（淘汰通知由通知体系的未读弹窗展示）。
    - 超过保留期：deactivate=True 时顺手销号（is_active=0），并返回给候选人看的淘汰说明文字。
    - 技术管理员恢复过（restore_time 晚于这次淘汰时间）：不再拦截，恢复期内数据一直保留。
    """
    from app.services.accounts import get_candidate_user

    user = get_candidate_user(db, candidate_id)
    info = latest_elimination(db, candidate_id)
    if info is None:
        return None
    app, stage, t = info
    if datetime.now() <= t + timedelta(days=ELIMINATE_KEEP_DAYS):
        return None
    if user is not None and user.restore_time and user.restore_time > t:
        return None
    if deactivate and user is not None and getattr(user, "is_active", 1) != 0:
        user.is_active = 0
    return eliminate_notice_text(db, app, stage)


def list_app_notices(db: Session, application_id: int) -> list[CandidateNotice]:
    """HR 视角：某次投递的全部通知（草稿 + 已发送），新的在前。"""
    return list(
        db.scalars(
            select(CandidateNotice)
            .where(CandidateNotice.application_id == application_id)
            .order_by(CandidateNotice.id.desc())
        ).all()
    )


# 富文本白名单：与前端 RichTextEditor 的能力一一对应（加粗/斜体/字号/对齐/链接/列表）
_ALLOWED_TAGS = {"b", "strong", "i", "em", "u", "s", "br", "p", "div", "span",
                 "font", "a", "ul", "ol", "li", "h1", "h2", "h3", "blockquote"}
_ALLOWED_ATTRS = {
    "*": {"style"},
    "a": {"href", "target"},
    "font": {"size", "color", "face"},
}


def sanitize_html(text: str) -> str:
    """通知正文允许少量排版 HTML（加粗/字号/链接），用 nh3（Rust ammonia 的绑定）按白名单清洗。

    不再手写正则：手写 sanitizer 是经典 XSS 来源（属性边界、mutation XSS 等），
    白名单重建 HTML 天然免疫这些绕过。
    """
    cleaned = nh3.clean(
        text or "",
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        url_schemes={"http", "https", "mailto"},
        link_rel="noopener noreferrer",
    )
    return cleaned.strip()


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
