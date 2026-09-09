"""
【认证接口：注册 / 登录 / 我是谁】
这是整个系统唯一「不用先登录」就能访问的一组接口（不然怎么登录呢）。

三个网址：
  POST /api/auth/register  注册（成功顺便帮你登录，直接发 token）
  POST /api/auth/login     登录
  GET  /api/auth/me        拿着 token 问「我是谁」——前端刷新页面后用它确认还在登录状态
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User
from app.schemas.auth import LoginIn, RegisterIn, TokenOut, UserOut
from app.services.security import create_access_token, hash_password, verify_password

# prefix：这个文件里所有网址都以 /api/auth 开头；tags：在 /docs 文档页里归到「auth」这一组
router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_out(user: User) -> UserOut:
    """把数据库里的用户对象变成回给前端的样子（去掉密码哈希）。"""
    return UserOut(id=user.id, username=user.username, create_time=user.create_time)


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    """注册：用户名重复返回 409；成功直接返回 token（自动登录）。"""
    # body 是浏览器发来的 JSON，已经按 RegisterIn 模板检查过了（用户名长度、密码长度）
    exists = db.scalar(select(User).where(User.username == body.username))  # 查一下这个用户名有没有人用
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")  # 409 = 冲突
    user = User(username=body.username, password_hash=hash_password(body.password), create_time=datetime.now())
    db.add(user)  # 放进小推车
    db.commit()  # 结账，真正写入数据库
    db.refresh(user)  # 重新读一遍，拿到数据库分配的 ID
    return TokenOut(token=create_access_token(user.id), user=_user_out(user))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    """登录：返回 JWT token（7 天有效）；用户名或密码错误返回 401。"""
    user = db.scalar(select(User).where(User.username == body.username))
    # 用户不存在、或密码对不上，都回同一句话——不告诉攻击者「用户名是对的，只是密码错了」
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    return TokenOut(token=create_access_token(user.id), user=_user_out(user))


@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)):
    """当前登录用户信息。"""
    # Depends(get_current_user)：门卫先验 token，验过了把用户对象塞给 current 参数
    return _user_out(current)
