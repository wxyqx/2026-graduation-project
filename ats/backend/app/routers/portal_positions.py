"""
【候选人端岗位接口】
  GET /api/portal/positions        在招岗位列表
  GET /api/portal/positions/{id}   岗位详情

只返回 is_hidden=0 的岗位；隐藏岗位对候选人一律 404。
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_candidate
from app.models import Position, User
from app.services import portal_views

router = APIRouter(prefix="/api/portal/positions", tags=["portal-positions"])

PosId = Annotated[int, Path(description="岗位编号")]


def _candidate_id(user: User) -> int:
    if user.candidate_id is None:
        raise HTTPException(status_code=401, detail="账号未关联候选人档案，请联系 HR")
    return user.candidate_id


def _visible_or_404(db: Session, pos_id: int) -> Position:
    p = db.get(Position, pos_id)
    if p is None or p.is_hidden:
        raise HTTPException(status_code=404, detail="岗位不存在或已停止招聘")
    return p


@router.get("")
def list_positions(db: Session = Depends(get_db), user: User = Depends(get_current_candidate)):
    """在招岗位列表

**返回什么**：岗位名、负责人、JD 摘要、我是否已投、是否配了申请表。
已设为「暂不招」的岗位不会出现。
"""
    cid = _candidate_id(user)
    rows = db.scalars(select(Position).where(Position.is_hidden == 0).order_by(Position.id.desc())).all()
    return [portal_views.position_summary(db, p, cid) for p in rows]


@router.get("/{pos_id}")
def get_position(
    pos_id: PosId,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_candidate),
):
    """岗位详情：完整 JD + 表单要求 + 我是否已投"""
    cid = _candidate_id(user)
    p = _visible_or_404(db, pos_id)
    return portal_views.position_detail(db, p, cid)
