"""
【技术管理端认证】
  POST /api/tech/auth/login     用户名 + 密码（只允许 admin 角色）
  GET  /api/tech/auth/me
  PUT  /api/tech/auth/password  改自己的密码
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status, File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.models import User
from app.schemas.auth import LoginIn, TokenOut, UserOut
from app.schemas.tech import TechPasswordIn
from app.services.log_service import log_action
from app.services.security import create_access_token, hash_password, verify_password
from app.services import avatar_service

router = APIRouter(prefix="/api/tech/auth", tags=["tech-auth"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        phone=user.phone,
        real_name=user.real_name,
        role=user.role,
        candidate_id=user.candidate_id,
        is_active=bool(getattr(user, "is_active", 1)),
        create_time=user.create_time,
    )


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    """技术管理员登录

**前置条件**：账号由 `scripts/create_user.py --role admin` 创建，或由其他技术管理员在「账号管理」里创建。

**可能出错**：
- 401：用户名或密码错误
- 403：不是技术管理员 / 账号已停用
"""
    user = db.scalar(select(User).where(User.username == body.username))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="该账号不是技术管理员")
    if getattr(user, "is_active", 1) == 0:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已停用")

    user.last_login_time = datetime.now()
    user.last_login_ip = _ip(request)
    log_action(db, user, "login", target_type="user", target_id=user.id, ip=_ip(request))
    db.commit()
    db.refresh(user)
    return TokenOut(token=create_access_token(user.id, user.role), user=_out(user))


@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_admin)):
    """我是谁（技术管理端刷新页面用）"""
    return _out(current)


@router.put("/password", response_model=TokenOut)
def change_password(
    body: TechPasswordIn,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_admin),
):
    """修改自己的密码"""
    if not verify_password(body.current_password, current.password_hash):
        raise HTTPException(status_code=400, detail="当前密码不正确")
    if body.current_password == body.new_password:
        raise HTTPException(status_code=400, detail="新密码不能和当前密码相同")
    current.password_hash = hash_password(body.new_password)
    log_action(db, current, "update", target_type="user", target_id=current.id, detail={"field": "password"}, ip=_ip(request))
    db.commit()
    db.refresh(current)
    return TokenOut(token=create_access_token(current.id, current.role), user=_out(current))


@router.put("/avatar")
async def upload_avatar(
    file: UploadFile = File(description="图片：jpg / png / webp / gif，≤5MB"),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_admin),
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
def get_avatar(db: Session = Depends(get_db), current: User = Depends(get_current_admin)):
    """获取我的头像图片（没设置时返回 404，前端用用户名首字占位）"""
    return avatar_service.avatar_response(current)
