"""
【候选人接口】
  GET  /api/candidates?name=张   列表，可按姓名模糊搜
  POST /api/candidates           新建
  GET  /api/candidates/{id}      详情
  PUT  /api/candidates/{id}      改备注

没有删除接口：候选人一旦有投递记录就不该删；设计文档也没要求。
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import Candidate
from app.schemas.candidate import CandidateIn, CandidateOut, CandidateUpdate

router = APIRouter(prefix="/api/candidates", tags=["candidates"], dependencies=[Depends(get_current_user)])


def _out(c: Candidate) -> CandidateOut:
    return CandidateOut(id=c.id, name=c.name, remark=c.remark, create_time=c.create_time)


@router.get("", response_model=list[CandidateOut])
def list_candidates(name: str | None = Query(default=None), db: Session = Depends(get_db)):
    """候选人列表：name 参数可做姓名模糊查询。"""
    # Query(default=None)：这个参数写在网址问号后面（?name=张），不传也行
    stmt = select(Candidate).order_by(Candidate.id.desc())
    if name:
        stmt = stmt.where(Candidate.name.like(f"%{name}%"))  # % 是通配符：「张」能搜到「张三」「小张」
    return [_out(c) for c in db.scalars(stmt).all()]


@router.post("", response_model=CandidateOut, status_code=status.HTTP_201_CREATED)
def create_candidate(body: CandidateIn, db: Session = Depends(get_db)):
    """新建候选人。"""
    c = Candidate(name=body.name, remark=body.remark, create_time=datetime.now())
    db.add(c)
    db.commit()
    db.refresh(c)
    return _out(c)


@router.get("/{can_id}", response_model=CandidateOut)
def get_candidate(can_id: int, db: Session = Depends(get_db)):
    """候选人详情。"""
    c = db.get(Candidate, can_id)
    if c is None:
        raise HTTPException(status_code=404, detail="候选人不存在")
    return _out(c)


@router.put("/{can_id}", response_model=CandidateOut)
def update_candidate(can_id: int, body: CandidateUpdate, db: Session = Depends(get_db)):
    """修改候选人备注。"""
    c = db.get(Candidate, can_id)
    if c is None:
        raise HTTPException(status_code=404, detail="候选人不存在")
    # model_fields_set = 前端真正传了的字段集合。这样能区分「没传 remark」和「传了 remark 但值是空（想清空）」
    if "remark" in body.model_fields_set:
        c.remark = body.remark
    db.commit()
    db.refresh(c)
    return _out(c)
