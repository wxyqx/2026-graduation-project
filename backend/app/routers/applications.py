from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import Application, Candidate, Position
from app.schemas.application import AdvanceIn, ApplicationCreate, RevertIn
from app.services import state_machine as sm
from app.services.views import application_detail, application_summary

router = APIRouter(prefix="/api/applications", tags=["applications"], dependencies=[Depends(get_current_user)])


def _get_or_404(db: Session, app_id: int) -> Application:
    a = db.get(Application, app_id)
    if a is None:
        raise HTTPException(status_code=404, detail="投递记录不存在")
    return a


@router.get("")
def list_applications(
    stage: str | None = Query(default=None),
    status_: str | None = Query(default=None, alias="status"),
    pos_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if stage is not None and stage not in sm.STAGES:
        raise HTTPException(status_code=400, detail="stage 不是合法阶段值")
    if status_ is not None and status_ not in sm.STATUSES:
        raise HTTPException(status_code=400, detail="status 不是合法状态值")
    stmt = select(Application).order_by(Application.id.desc())
    if stage:
        stmt = stmt.where(Application.current_stage == stage)
    if status_:
        stmt = stmt.where(Application.overall_status == status_)
    if pos_id:
        stmt = stmt.where(Application.pos_id == pos_id)
    return [application_summary(a) for a in db.scalars(stmt).all()]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_application(body: ApplicationCreate, db: Session = Depends(get_db)):
    if db.get(Candidate, body.can_id) is None:
        raise HTTPException(status_code=404, detail="候选人不存在")
    if db.get(Position, body.pos_id) is None:
        raise HTTPException(status_code=404, detail="岗位不存在")
    dup = db.scalar(
        select(Application).where(Application.can_id == body.can_id, Application.pos_id == body.pos_id)
    )
    if dup:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该候选人已投递过此岗位")
    now = datetime.now()
    a = Application(
        can_id=body.can_id,
        pos_id=body.pos_id,
        current_stage="ai",
        overall_status="pending",
        create_time=now,
        update_time=now,
    )
    db.add(a)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该候选人已投递过此岗位")
    db.refresh(a)
    return application_detail(a)


@router.get("/{app_id}")
def get_application(app_id: int, db: Session = Depends(get_db)):
    return application_detail(_get_or_404(db, app_id))


@router.post("/{app_id}/advance")
def advance(app_id: int, body: AdvanceIn, db: Session = Depends(get_db)):
    a = _get_or_404(db, app_id)
    if body.from_stage not in sm.STAGES:
        raise HTTPException(status_code=400, detail="fromStage 不是合法阶段值")
    if body.result not in sm.RESULTS:
        raise HTTPException(status_code=400, detail="result 只能是 pass 或 fail")
    if body.from_stage != a.current_stage:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"fromStage 与当前阶段不一致（当前为 {a.current_stage}），请刷新后重试",
        )
    if a.overall_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该投递已结束（已录用/已淘汰），请先撤回再操作",
        )
    sm.apply_result(a, body.from_stage, body.result, datetime.now())
    db.commit()
    db.refresh(a)
    return application_detail(a)


@router.post("/{app_id}/revert")
def revert(app_id: int, body: RevertIn, db: Session = Depends(get_db)):
    a = _get_or_404(db, app_id)
    try:
        sm.revert(a, body.to_stage, datetime.now())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    db.refresh(a)
    return application_detail(a)
