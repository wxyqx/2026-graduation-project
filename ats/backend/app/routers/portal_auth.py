"""
【候选人端认证接口】
  POST /api/portal/auth/login     手机号 + 密码登录
  GET  /api/portal/auth/me        我是谁（刷新页面恢复登录）
  PUT  /api/portal/auth/password  修改密码（可选，不强制）

规则：
  · 候选人账号 = 手机号；手机号必须先在系统里有候选人档案
  · 档案有手机号但还没账号时，第一次登录自动补建账号（默认密码 admin）
  · 登录失败 5 次锁定 10 分钟（内存限流，重启清零）
  · 不提供注册、不提供找回密码——找 HR
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status, File, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_candidate
from app.models import Candidate, User
from app.schemas.portal_auth import (
    PortalCandidateOut,
    PortalLoginIn,
    PortalMeOut,
    PortalPasswordIn,
    PortalTokenOut,
    PortalUserOut,
)
from app.services import accounts, notice_service, ratelimit
from app.services.log_service import log_action
from app.services.phone import is_valid_phone, normalize_phone
from app.services.security import create_access_token, hash_password, verify_password
from app.services import avatar_service

router = APIRouter(prefix="/api/portal/auth", tags=["portal-auth"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _candidate_out(c: Candidate) -> PortalCandidateOut:
    return PortalCandidateOut(id=c.id, name=c.name, phone=c.phone, email=c.email, create_time=c.create_time)


def _user_out(u: User) -> PortalUserOut:
    return PortalUserOut(
        id=u.id, role=u.role, candidate_id=u.candidate_id, is_active=bool(getattr(u, "is_active", 1))
    )


def _token_out(user: User, candidate: Candidate) -> PortalTokenOut:
    return PortalTokenOut(
        token=create_access_token(user.id, user.role),
        user=_user_out(user),
        candidate=_candidate_out(candidate),
    )


@router.post("/login", response_model=PortalTokenOut)
def login(body: PortalLoginIn, request: Request, db: Session = Depends(get_db)):
    """候选人登录（手机号 + 密码）

**干什么用**：候选人在 `/portal/login` 输入手机号和密码进入候选人端。

**前置条件**：HR 已经在系统里为这位候选人录入了手机号（新建候选人时填，或 AI 录入时从简历识别）。
手机号不存在时不会自动建档，会提示联系 HR。

**默认密码**：`admin`。登录后可在「我的资料」里修改（不强制）。

**返回什么**：
```json
{
  "token": "eyJhbGciOi...",
  "token_type": "bearer",
  "user": {"id": 12, "role": "candidate", "candidate_id": 8, "is_active": true},
  "candidate": {"id": 8, "name": "张三", "phone": "13800138000", "email": null, "create_time": "..."}
}
```

**可能出错**：
- 400：手机号格式不对
- 401：手机号没有档案 / 密码错误
- 403：账号被停用
- 429：失败次数过多，请稍后再试
"""
    phone = normalize_phone(body.phone)
    if not is_valid_phone(phone):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="手机号格式不正确")

    # 限流：同一手机号 10 分钟内最多失败 5 次
    window = settings.login_lock_minutes * 60
    key = f"portal_login:{phone}"
    if ratelimit.too_many(key, settings.login_max_failures, window):
        wait = ratelimit.remaining_seconds(key, window)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"登录失败次数过多，请 {max(1, wait // 60)} 分钟后再试",
        )

    candidate = accounts.find_candidate_by_phone(db, phone)
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未找到你的档案，请联系 HR 录入手机号后再登录",
        )

    user = accounts.get_candidate_user(db, candidate.id)
    if user is None:
        # 档案有手机号但还没有账号：自动补建（默认密码 admin）
        user = accounts.ensure_candidate_account(db, candidate)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号未开通，请联系 HR")

    if not verify_password(body.password, user.password_hash):
        ratelimit.record_failure(key, window)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="手机号或密码错误")

    # 淘汰销号检查：淘汰超 2 天的账号登录被拦，拦截信息 = 淘汰通知模板渲染的说明（顺手销号）。
    # 放在密码验证之后：不给不知道密码的人探测「这个人被淘汰了」的机会
    blocked = notice_service.elimination_block(db, candidate.id, deactivate=True)
    if blocked:
        db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=blocked)

    # 被管理员手动停用的账号（与淘汰销号区分开，提示联系 HR）
    if getattr(user, "is_active", 1) == 0:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已停用，请联系 HR")

    # 登录成功：清空失败记录、记录登录时间与 IP、写操作日志
    ratelimit.reset(key)
    user.last_login_time = datetime.now()
    user.last_login_ip = _ip(request)
    log_action(db, user, "login", target_type="user", target_id=user.id, ip=_ip(request))
    db.commit()
    db.refresh(user)
    return _token_out(user, candidate)


@router.get("/me", response_model=PortalMeOut)
def me(current: User = Depends(get_current_candidate)):
    """我是谁（候选人端刷新页面时用）

**干什么用**：前端刷新后拿 token 问「我还在登录吗、我是谁」，顺便拿到自己的资料。

**可能出错**：
- 401：没登录或 token 过期
- 403：账号停用 / 不是候选人账号
"""
    if current.candidate is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号未关联候选人档案，请联系 HR")
    return PortalMeOut(user=_user_out(current), candidate=_candidate_out(current.candidate))


@router.put("/password", response_model=PortalTokenOut)
def change_password(
    body: PortalPasswordIn,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_candidate),
):
    """修改密码（可选，不强制）

**怎么填**：`current_password` 当前密码 + `new_password` 新密码（至少 6 位）。

**返回什么**：新的 token 和账号信息，前端替换本地登录状态即可。

**可能出错**：
- 400：当前密码不对
- 422：新密码太短
"""
    if not verify_password(body.current_password, current.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前密码不正确")
    if body.new_password == body.current_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="新密码不能和当前密码相同")

    current.password_hash = hash_password(body.new_password)
    log_action(db, current, "update", target_type="user", target_id=current.id, detail={"field": "password"}, ip=_ip(request))
    db.commit()
    db.refresh(current)
    if current.candidate is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号未关联候选人档案，请联系 HR")
    return _token_out(current, current.candidate)


@router.put("/avatar")
async def upload_avatar(
    file: UploadFile = File(description="图片：jpg / png / webp / gif，≤5MB"),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_candidate),
):
    """上传我的头像（当前登录用户）

**干什么用**：三个端通用——HR、候选人、技术管理员都给当前账号设置头像；再次上传即替换。
"""
    try:
        await avatar_service.save_avatar(db, current, file)
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@router.get("/avatar")
def get_avatar(db: Session = Depends(get_db), current: User = Depends(get_current_candidate)):
    """获取我的头像图片（没设置时返回 404，前端用用户名首字占位）"""
    return avatar_service.avatar_response(current)
