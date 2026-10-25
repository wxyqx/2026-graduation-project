"""
【候选人账号服务】

规则（v3.15）：
  · 候选人账号 = 手机号，手机号存在 Candidate.phone 里
  · 只要 Candidate.phone 有值，就自动开通一个 User(role='candidate')
  · 默认密码统一 admin（.env 可改），不强制修改
  · 一个候选人只能有一个账号（User.candidate_id 唯一）

HR 保存候选人手机号、AI 录入识别到手机号、候选人第一次登录，都会调用这里，
保证「有手机号 = 有账号」。
"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Candidate, User
from app.services.phone import is_valid_phone, normalize_phone
from app.services.security import hash_password


def find_candidate_by_phone(db: Session, phone: str | None) -> Candidate | None:
    """按手机号找候选人（调用前先 normalize）。"""
    p = normalize_phone(phone)
    if not p:
        return None
    return db.scalar(select(Candidate).where(Candidate.phone == p))


def get_candidate_user(db: Session, candidate_id: int) -> User | None:
    """找某个候选人绑定的账号。"""
    return db.scalar(select(User).where(User.candidate_id == candidate_id))


def ensure_candidate_account(db: Session, candidate: Candidate, *, create: bool = True) -> User | None:
    """确保候选人有账号；没有就建一个（默认密码 admin）。返回账号或 None。

    · 候选人没有手机号 → 返回 None（不能登录）
    · 已有账号 → 原样返回（停用的也返回，登录时再拦）
    · create=False → 只查不建
    """
    phone = normalize_phone(candidate.phone)
    if not is_valid_phone(phone):
        return None

    user = get_candidate_user(db, candidate.id)
    if user is not None:
        return user
    if not create:
        return None

    user = User(
        username=None,  # 候选人没有用户名，登录走 Candidate.phone
        password_hash=hash_password(settings.default_candidate_password),
        role="candidate",
        candidate_id=candidate.id,
        is_active=1,
        create_time=datetime.now(),
    )
    db.add(user)
    db.flush()  # 先拿到 ID，事务由调用方 commit
    return user


def reset_candidate_password(user: User) -> None:
    """把密码重置为默认密码（admin），并重新启用账号。"""
    user.password_hash = hash_password(settings.default_candidate_password)
    user.is_active = 1
