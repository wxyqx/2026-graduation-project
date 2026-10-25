"""
【负责人与编辑权限】候选人 / 关卡的 HR 负责人体系

规则：
  · 候选人负责人（Candidate.owner_id）：默认 = 建档 / 上传简历录入的 HR；
    能查看并编辑该候选人的**全部关卡**；技术管理端可单个或批量改。
  · 阶段负责人（Stage_Owner）：第一次编辑某关（打分推进 / 补写原因评价）的 HR 自动认领；
    只能编辑自己这一关，其他关卡只能看。
  · 没有负责人信息的关：任何 HR 都可以编辑（编辑即认领）。
  · 候选人资料（姓名/手机号/摘录信息）只有负责人能改；暂无负责人的（NULL）任意 HR 可改。
读权限不限制：所有 HR 都能看到全部候选人与关卡。
"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, Candidate, StageOwner, User
from app.services.state_machine import STAGE_FIELDS


def stage_owner_map(db: Session, application_id: int) -> dict[str, StageOwner]:
    """某投递各关的负责人记录，按关卡名索引。"""
    rows = db.scalars(select(StageOwner).where(StageOwner.application_id == application_id)).all()
    return {r.stage: r for r in rows}


def stage_owner_map_bulk(db: Session, application_ids: list[int]) -> dict[int, dict[str, StageOwner]]:
    """一批投递的阶段负责人（列表页一次查完，避免逐行查询）。"""
    if not application_ids:
        return {}
    rows = db.scalars(select(StageOwner).where(StageOwner.application_id.in_(application_ids))).all()
    out: dict[int, dict[str, StageOwner]] = {}
    for r in rows:
        out.setdefault(r.application_id, {})[r.stage] = r
    return out


def claim_stage(db: Session, application_id: int, stage: str, user_id: int) -> None:
    """认领关卡：该关还没有负责人时把当前 HR 记为负责人；已有负责人则不动。"""
    exists = db.scalar(
        select(StageOwner).where(StageOwner.application_id == application_id, StageOwner.stage == stage)
    )
    if exists is None:
        db.add(StageOwner(application_id=application_id, stage=stage, user_id=user_id, update_time=datetime.now()))
        db.flush()


def can_edit_stage(db: Session, app: Application, stage: str, user: User) -> bool:
    """当前 HR 能否编辑这关：候选人负责人=全部能改；阶段负责人=只改本关；无主的关=可编辑（编辑即认领）。"""
    if stage not in STAGE_FIELDS:
        return False
    cand = db.get(Candidate, app.can_id)
    if cand is not None and cand.owner_id == user.id:
        return True
    owner = db.scalar(
        select(StageOwner).where(StageOwner.application_id == app.id, StageOwner.stage == stage)
    )
    return owner is None or owner.user_id == user.id


def ensure_can_edit_stage(db: Session, app: Application, stage: str, user: User) -> None:
    """不能编辑就抛 PermissionError（路由层转 403），提示谁是负责人。"""
    if can_edit_stage(db, app, stage, user):
        return
    owner = db.scalar(
        select(StageOwner).where(StageOwner.application_id == app.id, StageOwner.stage == stage)
    )
    name = _user_display(db, owner.user_id) if owner and owner.user_id else "（已离开的负责人）"
    raise PermissionError(f"「{stage}」关卡由 {name} 负责，你只能查看；如需调整请联系候选人负责人或技术管理员")


def can_edit_candidate(db: Session, candidate: Candidate, user: User) -> bool:
    """当前 HR 能否编辑候选人资料：负责人本人，或该候选人暂无负责人。"""
    return candidate.owner_id is None or candidate.owner_id == user.id


def ensure_can_edit_candidate(db: Session, candidate: Candidate, user: User) -> None:
    if can_edit_candidate(db, candidate, user):
        return
    name = _user_display(db, candidate.owner_id)
    raise PermissionError(f"该候选人由 {name} 负责，你只能查看；如需调整请联系技术管理员变更负责人")


def _user_display(db: Session, user_id: int | None) -> str:
    u = db.get(User, user_id) if user_id else None
    return (u.real_name or u.username) if u and (u.real_name or u.username) else f"#{user_id}"
