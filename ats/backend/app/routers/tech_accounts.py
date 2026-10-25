"""
【技术管理端账号管理】
  GET  /api/tech/accounts                 账号列表（HR / 技术管理员 / 候选人）
  POST /api/tech/accounts                 新建 HR 或技术管理员
  PUT  /api/tech/accounts/{id}/status     启用 / 停用
  PUT  /api/tech/accounts/{id}/reset-password  重置为默认密码 admin

候选人账号不能在这里新建：候选人档案有手机号时系统会自动开通。
技术管理员不能停用自己，也不能停用最后一个启用的技术管理员。
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_admin
from app.models import Candidate, User
from app.schemas.tech import TechAccountIn, TechAccountOut, TechStatusIn
from app.services import notice_service
from app.services.log_service import log_action
from app.services.phone import is_valid_phone, normalize_phone
from app.services.security import hash_password

router = APIRouter(prefix="/api/tech/accounts", tags=["tech-accounts"])


def _out(u: User, close_reason: str | None = None, restore_deadline: datetime | None = None) -> TechAccountOut:
    cand = u.candidate
    return TechAccountOut(
        id=u.id,
        username=u.username,
        name=(cand.name if cand else None) or u.real_name or u.username or "（无用户名）",
        role=u.role,
        # 候选人的手机号在 Candidate 表；HR / 管理员的在 User 表
        phone=(cand.phone if cand else None) or u.phone,
        real_name=u.real_name,
        candidate_id=u.candidate_id,
        is_active=bool(getattr(u, "is_active", 1)),
        close_reason=close_reason,
        restore_deadline=restore_deadline,
        last_login_time=u.last_login_time,
        create_time=u.create_time,
    )


@router.get("", response_model=list[TechAccountOut])
def list_accounts(
    role: str | None = Query(default=None, description="candidate / hr / admin"),
    status: str | None = Query(default=None, description="active / inactive"),
    keyword: str | None = Query(default=None, description="用户名 / 候选人姓名 / 手机号"),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_admin),
):
    """账号列表（支持角色、状态、关键字筛选）"""
    if role not in (None, "", "candidate", "hr", "admin"):
        raise HTTPException(status_code=400, detail="role 不合法")
    if status not in (None, "", "active", "inactive"):
        raise HTTPException(status_code=400, detail="status 不合法")

    stmt = (
        select(User)
        .outerjoin(Candidate, User.candidate_id == Candidate.id)
        .order_by(User.id)
    )
    if role:
        stmt = stmt.where(User.role == role)
    if status == "active":
        stmt = stmt.where(User.is_active == 1)
    elif status == "inactive":
        stmt = stmt.where(User.is_active == 0)
    if keyword:
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(
            or_(User.username.like(like), Candidate.name.like(like), Candidate.phone.like(like))
        )
    items = []
    for u in db.scalars(stmt).all():
        close_reason, restore_deadline = None, None
        # 候选人账号：淘汰超期即视为销号（实际停用惰性发生在登录/门卫处），标注原因与恢复截止供技术员恢复
        if u.role == "candidate" and u.candidate_id:
            info = notice_service.latest_elimination(db, u.candidate_id)
            if info:
                _, _, t = info
                closed = t + timedelta(days=notice_service.ELIMINATE_KEEP_DAYS)
                if datetime.now() > closed and not (u.restore_time and u.restore_time > t):
                    close_reason = "eliminated"
                    restore_deadline = closed + timedelta(days=notice_service.RETENTION_DAYS)
        items.append(_out(u, close_reason, restore_deadline))
    return items


@router.post("", response_model=TechAccountOut, status_code=201)
def create_account(body: TechAccountIn, db: Session = Depends(get_db), current: User = Depends(get_current_admin)):
    """新建 HR 或技术管理员账号"""
    if body.role not in ("hr", "admin"):
        raise HTTPException(status_code=400, detail="role 只能是 hr 或 admin")
    username = body.username.strip()
    if len(username) < 2:
        raise HTTPException(status_code=400, detail="用户名至少 2 个字")
    if db.scalar(select(User.id).where(User.username == username)):
        raise HTTPException(status_code=409, detail="用户名已存在")
    # HR 必有手机号：这里建号时一并强制收集
    phone = normalize_phone(body.phone)
    if not is_valid_phone(phone):
        raise HTTPException(status_code=400, detail="手机号格式不正确（11 位，1 开头）")
    if db.scalar(select(User.id).where(User.phone == phone)):
        raise HTTPException(status_code=409, detail="手机号已被其他账号使用")
    user = User(
        username=username,
        phone=phone,
        real_name=body.real_name.strip(),
        password_hash=hash_password(body.password or settings.default_candidate_password),
        role=body.role,
        is_active=1,
        create_time=datetime.now(),
    )
    db.add(user)
    db.flush()
    log_action(
        db, current, "create", target_type="user", target_id=user.id, detail={"role": body.role}
    )
    db.commit()
    db.refresh(user)
    return _out(user)


@router.put("/{user_id}/status", response_model=TechAccountOut)
def set_status(
    user_id: int,
    body: TechStatusIn,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_admin),
):
    """启用 / 停用账号

启用候选人账号时，若该账号是因淘汰超期被销号的，本次启用即「恢复」：
写入 restore_time（之后那次淘汰不再拦截登录），且必须在销号后 3 个月保存期内，过期返回 400。
"""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    if user.id == current.id and not body.is_active:
        raise HTTPException(status_code=400, detail="不能停用当前登录的账号")
    if user.role == "admin" and not body.is_active:
        active_admins = db.scalar(
            select(func.count()).select_from(User).where(User.role == "admin", User.is_active == 1)
        ) or 0
        if active_admins <= 1:
            raise HTTPException(status_code=400, detail="至少保留一个启用的技术管理员")
    if body.is_active and user.role == "candidate" and user.candidate_id:
        # 淘汰销号的恢复：保存期（3 个月）内才允许
        info = notice_service.latest_elimination(db, user.candidate_id)
        if info:
            _, _, t = info
            closed = t + timedelta(days=notice_service.ELIMINATE_KEEP_DAYS)
            already_restored = user.restore_time and user.restore_time > t
            if datetime.now() > closed and not already_restored:
                deadline = closed + timedelta(days=notice_service.RETENTION_DAYS)
                if datetime.now() > deadline:
                    raise HTTPException(
                        status_code=400,
                        detail=f"该账号已超过 3 个月保存期（{deadline:%Y-%m-%d} 截止），无法恢复",
                    )
                user.restore_time = datetime.now()
                log_action(
                    db, current, "update", target_type="user", target_id=user.id,
                    detail={"restored": True, "eliminated_at": t.isoformat()},
                )
    user.is_active = 1 if body.is_active else 0
    log_action(
        db, current, "update", target_type="user", target_id=user.id,
        detail={"is_active": body.is_active},
    )
    db.commit()
    db.refresh(user)
    return _out(user)


@router.put("/{user_id}/reset-password", response_model=TechAccountOut)
def reset_password(user_id: int, db: Session = Depends(get_db), current: User = Depends(get_current_admin)):
    """把账号密码重置为默认密码（admin），不改变启用状态"""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="账号不存在")
    user.password_hash = hash_password(settings.default_candidate_password)
    log_action(db, current, "reset_password", target_type="user", target_id=user.id)
    db.commit()
    db.refresh(user)
    return _out(user)
