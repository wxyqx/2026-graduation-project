"""
【负责人与编辑权限】候选人 / 关卡的 HR 负责人体系

规则：
  · 候选人负责人（Candidate.owner_id）：默认 = 建档 / 上传简历录入的 HR；
    能查看并编辑该候选人的**全部关卡**；技术管理端可单个或批量改。
  · 阶段负责人：技术管理端按「岗位 × 关卡」指派（Position_Stage_Owner），对该岗位全部候选人生效；
    投递级记录（Stage_Owner，HR 首次编辑某关自动认领）优先于岗位级。
  · 阶段负责人只能编辑自己这一关，其他关卡只能看。
  · 两边都没有负责人的关：任何 HR 都可以编辑（编辑即认领）。
  · 候选人资料（姓名/手机号/摘录信息）只有负责人能改；暂无负责人的（NULL）任意 HR 可改。
读权限不限制：所有 HR 都能看到全部候选人与关卡。
"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, Candidate, PositionStageOwner, StageOwner, User
from app.services.state_machine import STAGE_FIELDS


def position_owner_ids(db: Session, pos_id: int) -> dict[str, int]:
    """某岗位各关的岗位级负责人：{stage: user_id}，只含有人的关。"""
    rows = db.scalars(
        select(PositionStageOwner).where(
            PositionStageOwner.pos_id == pos_id, PositionStageOwner.user_id.isnot(None)
        )
    ).all()
    return {r.stage: r.user_id for r in rows}


def position_owner_ids_bulk(db: Session, pos_ids: list[int]) -> dict[int, dict[str, int]]:
    """一批岗位的岗位级负责人（列表页一次查完）。"""
    if not pos_ids:
        return {}
    rows = db.scalars(
        select(PositionStageOwner).where(
            PositionStageOwner.pos_id.in_(pos_ids), PositionStageOwner.user_id.isnot(None)
        )
    ).all()
    out: dict[int, dict[str, int]] = {}
    for r in rows:
        out.setdefault(r.pos_id, {})[r.stage] = r.user_id
    return out


def _effective_owner_id(db: Session, app: Application, stage: str) -> int | None:
    """某投递某关「实际生效」的负责人：岗位级指派优先（对该岗位全部候选人生效）；
    没指派的关落到投递级认领记录（HR 首次编辑自动认领）；都没有返回 None。"""
    pos_owner = position_owner_ids(db, app.pos_id).get(stage)
    if pos_owner is not None:
        return pos_owner
    row = db.scalar(
        select(StageOwner).where(StageOwner.application_id == app.id, StageOwner.stage == stage)
    )
    return row.user_id if row is not None else None


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
    """认领关卡：该关还没有负责人时把当前 HR 记为负责人；已有负责人则不动。

    岗位级已指派的关不写认领记录——负责人由岗位指派决定，写了也不会生效。
    两个 HR 同时抢编辑同一个未认领的关：用 SAVEPOINT 包住插入，撞 UK_App_Stage
    唯一约束时回滚到保存点、以先到者为准，不炸外层事务（v3.17 P0-3）。
    """
    pos_id = db.scalar(select(Application.pos_id).where(Application.id == application_id))
    if pos_id is not None and stage in position_owner_ids(db, pos_id):
        return
    exists = db.scalar(
        select(StageOwner).where(StageOwner.application_id == application_id, StageOwner.stage == stage)
    )
    if exists is None:
        from sqlalchemy.exc import IntegrityError

        try:
            with db.begin_nested():
                db.add(StageOwner(application_id=application_id, stage=stage, user_id=user_id, update_time=datetime.now()))
                db.flush()
        except IntegrityError:
            pass  # 对方抢先认领成功：保留对方的记录，本方放弃认领


def can_edit_stage(db: Session, app: Application, stage: str, user: User) -> bool:
    """当前 HR 能否编辑这关：候选人负责人=全部能改；阶段负责人=只改本关；无主的关=可编辑（编辑即认领）。"""
    if stage not in STAGE_FIELDS:
        return False
    cand = db.get(Candidate, app.can_id)
    if cand is not None and cand.owner_id == user.id:
        return True
    owner_id = _effective_owner_id(db, app, stage)
    return owner_id is None or owner_id == user.id


def ensure_can_edit_stage(db: Session, app: Application, stage: str, user: User) -> None:
    """不能编辑就抛 PermissionError（路由层转 403），提示谁是负责人。"""
    if can_edit_stage(db, app, stage, user):
        return
    owner_id = _effective_owner_id(db, app, stage)
    name = _user_display(db, owner_id) if owner_id else "（已离开的负责人）"
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


# ---- 主要 / 协助负责人与私密附件 ----
# 主要负责人 = 候选人负责人（建档 / 上传简历的 HR），能看全部内容；
# 协助负责人（岗位级指派的关卡负责人、自动认领的 HR）只能编辑自己那一关、其他关只读，
# 且看不到私密附件——证书 / 作品 / 其他 / Offer 三件套；简历与全部答卷（个人资料表 /
# 面试登记表 / 职业底色图）对协助负责人可见。
# 没有负责人的候选人（owner_id 为空）视同人人都是主要负责人，不做限制。

def is_primary_owner(candidate: Candidate, user: User) -> bool:
    """主要负责人 = 候选人负责人；候选人还没指派负责人时所有 HR 都视同主要负责人。"""
    return candidate.owner_id is None or candidate.owner_id == user.id


def filter_private_files(files: list, candidate: Candidate, user: User) -> list:
    """非主要负责人只保留简历类文件（证书 / 作品 / 其他 / Offer 三件套都是私密附件）。"""
    if is_primary_owner(candidate, user):
        return files
    return [f for f in files if f.category == "resume"]
