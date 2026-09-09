"""
【投递接口】——系统的主战场
  GET  /api/applications?stage=&status=&pos_id=   列表（三种筛选都可选）
  POST /api/applications                          手动新建一条投递
  GET  /api/applications/{id}                     详情（含 8 关时间线）
  POST /api/applications/{id}/advance             推进：给当前关打分（pass / fail）
  POST /api/applications/{id}/revert              撤回上一步

推进、撤回的具体规则不在这里，在 services/state_machine.py。这里只做检查和调用。
"""
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
    status_: str | None = Query(default=None, alias="status"),  # 网址里叫 status，但 status 这个名字已经被上面 import 的模块占了，所以 Python 里叫 status_
    pos_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """投递列表：可按阶段 stage / 全局状态 status / 岗位 pos_id 筛选，含候选人姓名与岗位名。"""
    # 先把乱传的值挡在门外（枚举值以数据字典为准）
    if stage is not None and stage not in sm.STAGES:
        raise HTTPException(status_code=400, detail="stage 不是合法阶段值")
    if status_ is not None and status_ not in sm.STATUSES:
        raise HTTPException(status_code=400, detail="status 不是合法状态值")
    # 像搭积木一样拼查询：先「查全部、倒序」，传了哪个条件就再加一块 where
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
    """手动新建投递：初始阶段为 AI 筛选（ai）、状态进行中（pending）；重复投递返回 409。"""
    # 先确认「人」和「岗位」都真实存在
    if db.get(Candidate, body.can_id) is None:
        raise HTTPException(status_code=404, detail="候选人不存在")
    if db.get(Position, body.pos_id) is None:
        raise HTTPException(status_code=404, detail="岗位不存在")
    # 再查重：同一个人投同一个岗位只能有一条
    dup = db.scalar(
        select(Application).where(Application.can_id == body.can_id, Application.pos_id == body.pos_id)
    )
    if dup:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该候选人已投递过此岗位")
    now = datetime.now()
    a = Application(
        can_id=body.can_id,
        pos_id=body.pos_id,
        current_stage="ai",  # 新投递永远从第一关开始
        overall_status="pending",
        create_time=now,
        update_time=now,
    )
    db.add(a)
    try:
        db.commit()
    except IntegrityError:
        # 双保险：万一两个请求同一瞬间都通过了上面的查重，数据库的唯一约束会拦住第二个，这里接住它
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该候选人已投递过此岗位")
    db.refresh(a)
    return application_detail(a)


@router.get("/{app_id}")
def get_application(app_id: int, db: Session = Depends(get_db)):
    """投递详情：候选人 + 岗位信息 + 8 阶段时间线（各阶段结果与时间戳）。"""
    return application_detail(_get_or_404(db, app_id))


@router.post("/{app_id}/advance")
def advance(app_id: int, body: AdvanceIn, db: Session = Depends(get_db)):
    """推进阶段：fromStage 必须等于当前阶段（409 防重复操作）；pass 推进、fail 淘汰终止；终面通过即已录用。"""
    a = _get_or_404(db, app_id)
    # 四道检查，一道不过就拒绝
    if body.from_stage not in sm.STAGES:
        raise HTTPException(status_code=400, detail="fromStage 不是合法阶段值")
    if body.result not in sm.RESULTS:
        raise HTTPException(status_code=400, detail="result 只能是 pass 或 fail")
    if body.from_stage != a.current_stage:
        # 前端以为在 A 关，实际已经在 B 关了——多半是手快点了两次，或者两个窗口同时操作
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"fromStage 与当前阶段不一致（当前为 {a.current_stage}），请刷新后重试",
        )
    if a.overall_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该投递已结束（已录用/已淘汰），请先撤回再操作",
        )
    sm.apply_result(a, body.from_stage, body.result, datetime.now())  # 真正的规则在状态机里
    db.commit()
    db.refresh(a)
    return application_detail(a)


@router.post("/{app_id}/revert")
def revert(app_id: int, body: RevertIn, db: Session = Depends(get_db)):
    """撤回：不传 toStage=撤销上一步决定（已淘汰/已录用则原地恢复进行中）；传 toStage=退回该阶段并清掉其后全部数据。"""
    a = _get_or_404(db, app_id)
    try:
        sm.revert(a, body.to_stage, datetime.now())
    except ValueError as e:
        # 状态机用 ValueError 表示「这样退不合规矩」（比如第一关没法再退），这里翻译成 400 给前端
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    db.refresh(a)
    return application_detail(a)
