from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User
from app.schemas.auth import LoginIn, RegisterIn, TokenOut, UserOut
from app.services.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_out(user: User) -> UserOut:
    return UserOut(id=user.id, username=user.username, create_time=user.create_time)


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    exists = db.scalar(select(User).where(User.username == body.username))
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")
    user = User(username=body.username, password_hash=hash_password(body.password), create_time=datetime.now())
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenOut(token=create_access_token(user.id), user=_user_out(user))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == body.username))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    return TokenOut(token=create_access_token(user.id), user=_user_out(user))


@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)):
    return _user_out(current)
