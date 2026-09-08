from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import Application, Position
from app.schemas.position import PositionIn, PositionOut, PositionUpdate

router = APIRouter(prefix="/api/positions", tags=["positions"], dependencies=[Depends(get_current_user)])


def _count_map(db: Session) -> dict[int, int]:
    rows = db.execute(select(Application.pos_id, func.count()).group_by(Application.pos_id)).all()
    return {pos_id: n for pos_id, n in rows}


def _out(p: Position, count: int = 0) -> PositionOut:
    return PositionOut(
        id=p.id,
        position_name=p.position_name,
        owner=p.owner,
        position_requirements=p.position_requirements,
        application_count=count,
    )


def _get_or_404(db: Session, pos_id: int) -> Position:
    p = db.get(Position, pos_id)
    if p is None:
        raise HTTPException(status_code=404, detail="岗位不存在")
    return p


@router.get("", response_model=list[PositionOut])
def list_positions(db: Session = Depends(get_db)):
    counts = _count_map(db)
    positions = db.scalars(select(Position).order_by(Position.id.desc())).all()
    return [_out(p, counts.get(p.id, 0)) for p in positions]


@router.post("", response_model=PositionOut, status_code=status.HTTP_201_CREATED)
def create_position(body: PositionIn, db: Session = Depends(get_db)):
    p = Position(**body.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return _out(p)


@router.get("/{pos_id}", response_model=PositionOut)
def get_position(pos_id: int, db: Session = Depends(get_db)):
    p = _get_or_404(db, pos_id)
    count = db.scalar(select(func.count()).select_from(Application).where(Application.pos_id == pos_id)) or 0
    return _out(p, count)


@router.put("/{pos_id}", response_model=PositionOut)
def update_position(pos_id: int, body: PositionUpdate, db: Session = Depends(get_db)):
    p = _get_or_404(db, pos_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    count = db.scalar(select(func.count()).select_from(Application).where(Application.pos_id == pos_id)) or 0
    return _out(p, count)


@router.delete("/{pos_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_position(pos_id: int, db: Session = Depends(get_db)):
    p = _get_or_404(db, pos_id)
    count = db.scalar(select(func.count()).select_from(Application).where(Application.pos_id == pos_id)) or 0
    if count:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"该岗位下有 {count} 条投递记录，不能删除")
    db.delete(p)
    db.commit()
