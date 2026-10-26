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
from app.models import Candidate, Position, User
from app.services.log_service import log_action
from app.services.state_machine import STAGE_LABELS, STAGES

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
    """整个岗位的各关负责人：{stage: HR 编号或 null(清空)}。一次提交整份，后端逐关落地。"""
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
    keyword: str | None = Query(default=None, description="岗位名关键字"),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_admin),
):
    """岗位清单 + 各关的岗位级负责人（关卡负责人调整页用）。

    负责人按「岗位 × 关卡」指派，对该岗位全部候选人的对应关生效；
    个别投递若已被 HR 首次编辑自动认领，以投递级记录为准（这里看不到、也不覆盖）。
    """
    from app.models import PositionStageOwner

    stmt = select(Position).order_by(Position.id.desc())
    if keyword and keyword.strip():
        stmt = stmt.where(Position.position_name.like(f"%{keyword.strip()}%"))
    positions = db.scalars(stmt).all()
    pos_ids = [p.id for p in positions]
    owner_rows = (
        db.execute(
            select(PositionStageOwner.pos_id, PositionStageOwner.stage, User.id, User.real_name, User.username)
            .join(User, PositionStageOwner.user_id == User.id, isouter=True)
            .where(PositionStageOwner.pos_id.in_(pos_ids), PositionStageOwner.user_id.isnot(None))
        ).all()
        if pos_ids
        else []
    )
    owners: dict[int, dict] = {}
    for pos_id, stage, uid, real, username in owner_rows:
        owners.setdefault(pos_id, {})[stage] = {"user_id": uid, "name": real or username}
    return {
        "options": _hr_options(db),
        "stages": [{"value": st, "label": STAGE_LABELS[st]} for st in STAGES],
        "items": [
            {
                "id": p.id,
                "position_name": p.position_name,
                "is_hidden": p.is_hidden,
                "stage_owners": owners.get(p.id, {}),
            }
            for p in positions
        ],
    }


@router.put("/stage-owners/{pos_id}")
def set_stage_owners(
    pos_id: int, body: StageOwnersIn, db: Session = Depends(get_db), current: User = Depends(get_current_admin)
):
    """整份设置一个岗位的各关负责人（对该岗位全部候选人生效）：有 HR 编号的写入/更新，null 的清除。"""
    from app.models import PositionStageOwner

    p = db.get(Position, pos_id)
    if p is None:
        raise HTTPException(status_code=404, detail="岗位不存在")
    for stage, uid in body.owners.items():
        if stage not in STAGES:
            raise HTTPException(status_code=400, detail=f"{stage} 不是合法阶段值")
        _check_owner(db, uid)
    changed = 0
    for stage, uid in body.owners.items():
        row = db.scalar(
            select(PositionStageOwner).where(PositionStageOwner.pos_id == pos_id, PositionStageOwner.stage == stage)
        )
        if uid is None:
            if row is not None:
                db.delete(row)
                changed += 1
        elif row is None:
            db.add(PositionStageOwner(pos_id=pos_id, stage=stage, user_id=uid, update_time=datetime.now()))
            changed += 1
        elif row.user_id != uid:
            row.user_id = uid
            row.update_time = datetime.now()
            changed += 1
    log_action(
        db, current, "update", target_type="position", target_id=pos_id,
        detail={"position_stage_owners_changed": True, "owners": body.owners},
    )
    db.commit()
    return {"changed": changed}


@router.delete("/candidates/{can_id}/purge")
def purge_candidate(
    can_id: int,
    confirm: bool = Query(description="必须显式传 true；用于响应候选人行使删除权（PIPL 删除权工具）"),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_admin),
):
    """彻底删除候选人（物理删除，不可恢复；v3.17 P1-13 数据删除权工具）

**与 HR 端「删除候选人」的区别**：那个是业务删除（档案+投递级联删除，但仍在备份里）；
本接口是**合规工具**——响应候选人行使删除权时，由技术管理员物理清除其全部数据：
档案、投递、答卷与答案、通知、文件 BLOB、登录账号。**操作前请先确认已有可用备份**
（备份 → 恢复演练通过），删除后只能从备份找回。

**怎么填**：网址带候选人编号，`confirm=true` 必带。

**可能出错**：404 候选人不存在。
"""
    from app.models import Candidate as Cand

    if not confirm:
        raise HTTPException(status_code=400, detail="必须显式传 confirm=true 才能彻底删除")
    c = db.get(Cand, can_id)
    if c is None:
        raise HTTPException(status_code=404, detail="候选人不存在")
    detail = {"purged": True, "name": c.name, "phone": c.phone}
    # 应用层显式物理删除（真实库部分外键无 CASCADE，靠顺序删）：答案→答卷→文件→通知→关负责人→投递→档案→账号
    from app.models import (
        Application,
        CandidateFile,
        CandidateNotice,
        FormAnswer,
        FormSubmission,
        StageOwner,
    )

    db.query(FormAnswer).filter(
        FormAnswer.submission_id.in_(select(FormSubmission.id).where(FormSubmission.candidate_id == can_id))
    ).delete(synchronize_session=False)
    db.query(FormSubmission).filter(FormSubmission.candidate_id == can_id).delete(synchronize_session=False)
    db.query(CandidateFile).filter(CandidateFile.candidate_id == can_id).delete(synchronize_session=False)
    db.query(CandidateNotice).filter(CandidateNotice.candidate_id == can_id).delete(synchronize_session=False)
    app_ids = db.scalars(select(Application.id).where(Application.can_id == can_id)).all()
    if app_ids:
        db.query(StageOwner).filter(StageOwner.application_id.in_(app_ids)).delete(synchronize_session=False)
    db.query(Application).filter(Application.can_id == can_id).delete(synchronize_session=False)
    u = db.scalar(select(User).where(User.candidate_id == can_id))
    db.delete(c)
    if u is not None:
        db.delete(u)
    log_action(db, current, "delete", target_type="candidate", target_id=can_id, detail=detail)
    db.commit()
    return {"purged": can_id, "name": detail["name"]}
