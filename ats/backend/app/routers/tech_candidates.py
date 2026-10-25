"""
【技术管理端：候选人负责人调整】

  GET  /api/tech/candidate-owners            候选人清单（含当前负责人，支持关键字搜）
  PUT  /api/tech/candidate-owners/{id}       单个改负责人（owner_id 传 null = 清空）
  PUT  /api/tech/candidate-owners/batch      批量改负责人

候选人负责人默认 = 建档 / 上传简历录入的 HR；负责人能编辑该候选人的全部关卡。
这里只动「谁负责」，不展示岗位 / 投递进度等招聘业务数据。
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.models import Application, Candidate, Position, StageOwner, User
from app.services.state_machine import STAGES, STAGE_LABELS
from app.services.log_service import log_action

router = APIRouter(prefix="/api/tech/candidate-owners", tags=["tech-candidate-owners"])


def _display(u: User | None) -> str | None:
    if u is None:
        return None
    return u.real_name or u.username


def _hr_options(db: Session) -> list[dict]:
    """可选负责人 = 启用中的 HR（实名优先显示）。"""
    rows = db.scalars(select(User).where(User.role == "hr", User.is_active == 1).order_by(User.id)).all()
    return [{"id": u.id, "name": _display(u) or f"#{u.id}"} for u in rows]


class OwnerSetIn(BaseModel):
    owner_id: int | None = Field(default=None, description="新负责人 HR 编号；null = 清空负责人（任意 HR 可编辑）")


class StageOwnersIn(BaseModel):
    """整条投递的各关负责人：{stage: HR 编号或 null(清空)}。一次提交整份，后端逐关落地。"""
    owners: dict[str, int | None] = Field(description='各关负责人，如 {"phone": 3, "resume": null}')


class OwnerBatchIn(BaseModel):
    candidate_ids: list[int] = Field(description="要改的候选人编号列表")
    owner_id: int | None = Field(default=None, description="新负责人 HR 编号；null = 清空")


def _check_owner(db: Session, owner_id: int | None) -> None:
    if owner_id is None:
        return
    u = db.get(User, owner_id)
    if u is None or u.role != "hr" or getattr(u, "is_active", 1) != 1:
        raise HTTPException(status_code=400, detail="负责人必须是启用中的 HR")


@router.get("")
def list_candidate_owners(
    keyword: str | None = Query(default=None, description="姓名 / 手机号关键字"),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_admin),
):
    """候选人清单（含当前负责人）；附带可选的 HR 负责人选项。"""
    stmt = select(Candidate).order_by(Candidate.id.desc())
    if keyword and keyword.strip():
        like = f"%{keyword.strip()}%"
        stmt = stmt.where((Candidate.name.like(like)) | (Candidate.phone.like(like)))
    cands = db.scalars(stmt).all()
    owner_ids = {c.owner_id for c in cands if c.owner_id}
    owners = {u.id: u for u in db.scalars(select(User).where(User.id.in_(owner_ids))).all()} if owner_ids else {}
    return {
        "options": _hr_options(db),
        "items": [
            {
                "id": c.id,
                "name": c.name,
                "phone": c.phone,
                "owner_id": c.owner_id,
                "owner_name": _display(owners.get(c.owner_id)),
            }
            for c in cands
        ],
    }


@router.put("/batch")
def set_owner_batch(
    body: OwnerBatchIn, db: Session = Depends(get_db), current: User = Depends(get_current_admin)
):
    """批量改负责人（选中的候选人全部设为同一个 HR；owner_id=null = 全部清空）"""
    if not body.candidate_ids:
        raise HTTPException(status_code=400, detail="请先勾选候选人")
    _check_owner(db, body.owner_id)
    rows = db.scalars(select(Candidate).where(Candidate.id.in_(body.candidate_ids))).all()
    for c in rows:
        c.owner_id = body.owner_id
    log_action(
        db, current, "update", target_type="candidate", target_id=None,
        detail={"owner_batch": True, "count": len(rows), "to": body.owner_id},
    )
    db.commit()
    return {"updated": len(rows)}


@router.put("/{candidate_id}")
def set_owner(
    candidate_id: int, body: OwnerSetIn, db: Session = Depends(get_db), current: User = Depends(get_current_admin)
):
    """改单个候选人的负责人"""
    c = db.get(Candidate, candidate_id)
    if c is None:
        raise HTTPException(status_code=404, detail="候选人不存在")
    _check_owner(db, body.owner_id)
    old = c.owner_id
    c.owner_id = body.owner_id
    log_action(
        db, current, "update", target_type="candidate", target_id=c.id,
        detail={"owner_changed": True, "from": old, "to": body.owner_id},
    )
    db.commit()
    return {"id": c.id, "owner_id": c.owner_id}


@router.get("/stage-owners")
def list_stage_owners(
    keyword: str | None = Query(default=None, description="候选人姓名 / 手机号 / 岗位名关键字"),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_admin),
):
    """投递清单 + 各关负责人（关卡负责人调整页用）。"""
    stmt = (
        select(Application, Candidate, Position)
        .join(Candidate, Application.can_id == Candidate.id)
        .join(Position, Application.pos_id == Position.id)
        .order_by(Application.id.desc())
    )
    if keyword and keyword.strip():
        like = f"%{keyword.strip()}%"
        stmt = stmt.where(
            (Candidate.name.like(like)) | (Candidate.phone.like(like)) | (Position.position_name.like(like))
        )
    rows = db.execute(stmt.limit(200)).all()
    app_ids = [r[0].id for r in rows]
    so_rows = (
        db.execute(
            select(StageOwner.application_id, StageOwner.stage, User.id, User.real_name, User.username)
            .join(User, StageOwner.user_id == User.id, isouter=True)
            .where(StageOwner.application_id.in_(app_ids))
        ).all()
        if app_ids
        else []
    )
    owners: dict[int, dict] = {}
    for app_id, stage, uid, real, username in so_rows:
        owners.setdefault(app_id, {})[stage] = {
            "user_id": uid,
            "name": (real or username) if uid else None,
        }
    return {
        "options": _hr_options(db),
        "stages": [{"value": st, "label": STAGE_LABELS[st]} for st in STAGES],
        "items": [
            {
                "id": a.id,
                "candidate_name": c.name,
                "phone": c.phone,
                "position_name": p.position_name,
                "current_stage": a.current_stage,
                "overall_status": a.overall_status,
                "stage_owners": owners.get(a.id, {}),
            }
            for a, c, p in rows
        ],
    }


@router.put("/stage-owners/{app_id}")
def set_stage_owners(
    app_id: int, body: StageOwnersIn, db: Session = Depends(get_db), current: User = Depends(get_current_admin)
):
    """整份设置一条投递的各关负责人：有 HR 编号的写入/更新，null 的清除认领记录。"""
    a = db.get(Application, app_id)
    if a is None:
        raise HTTPException(status_code=404, detail="投递不存在")
    for stage, uid in body.owners.items():
        if stage not in STAGES:
            raise HTTPException(status_code=400, detail=f"{stage} 不是合法阶段值")
        if uid is not None:
            u = db.get(User, uid)
            if u is None or u.role != "hr" or getattr(u, "is_active", 1) != 1:
                raise HTTPException(status_code=400, detail="负责人必须是启用中的 HR")
    changed = 0
    for stage, uid in body.owners.items():
        row = db.scalar(
            select(StageOwner).where(StageOwner.application_id == app_id, StageOwner.stage == stage)
        )
        if uid is None:
            if row is not None:
                db.delete(row)
                changed += 1
        elif row is None:
            db.add(StageOwner(application_id=app_id, stage=stage, user_id=uid, update_time=datetime.now()))
            changed += 1
        elif row.user_id != uid:
            row.user_id = uid
            row.update_time = datetime.now()
            changed += 1
    log_action(
        db, current, "update", target_type="application", target_id=app_id,
        detail={"stage_owners_changed": True, "owners": body.owners},
    )
    db.commit()
    return {"changed": changed}
