"""
【岗位接口：增删改查】
  GET    /api/positions        列表
  POST   /api/positions        新建
  GET    /api/positions/{id}   详情
  PUT    /api/positions/{id}   编辑
  DELETE /api/positions/{id}   删除（有人投过就不让删）
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import Application, Position
from app.schemas.position import PositionIn, PositionOut, PositionUpdate

# dependencies=[Depends(get_current_user)]：这个文件里所有接口都要先过门卫（必须登录）
router = APIRouter(prefix="/api/positions", tags=["positions"], dependencies=[Depends(get_current_user)])


def _count_map(db: Session) -> dict[int, int]:
    """一次查出「每个岗位有多少条投递」，返回 {岗位编号: 数量}。列表页用，比一个岗位查一次快得多。"""
    rows = db.execute(select(Application.pos_id, func.count()).group_by(Application.pos_id)).all()
    return {pos_id: n for pos_id, n in rows}


def _out(p: Position, count: int = 0) -> PositionOut:
    """数据库对象 → 回给前端的样子。"""
    return PositionOut(
        id=p.id,
        position_name=p.position_name,
        owner=p.owner,
        position_requirements=p.position_requirements,
        application_count=count,
    )


def _get_or_404(db: Session, pos_id: int) -> Position:
    """按编号找岗位，找不到直接回 404（「没有这个东西」）。好几个接口都要先找，抽成一个小函数。"""
    p = db.get(Position, pos_id)
    if p is None:
        raise HTTPException(status_code=404, detail="岗位不存在")
    return p


@router.get("", response_model=list[PositionOut])
def list_positions(db: Session = Depends(get_db)):
    """岗位列表（含每个岗位的投递数）。"""
    counts = _count_map(db)
    positions = db.scalars(select(Position).order_by(Position.id.desc())).all()  # 按编号倒序，新建的在最上面
    return [_out(p, counts.get(p.id, 0)) for p in positions]


@router.post("", response_model=PositionOut, status_code=status.HTTP_201_CREATED)
def create_position(body: PositionIn, db: Session = Depends(get_db)):
    """新建岗位。岗位要求用于 AI 筛选匹配。"""
    p = Position(**body.model_dump())  # **：把字典拆成 position_name=..., owner=... 这样的参数
    db.add(p)
    db.commit()
    db.refresh(p)
    return _out(p)


@router.get("/{pos_id}", response_model=PositionOut)
def get_position(pos_id: int, db: Session = Depends(get_db)):
    """岗位详情。"""
    # 网址里的 {pos_id} 会自动变成函数参数 pos_id，并且转成整数（不是数字会回 422）
    p = _get_or_404(db, pos_id)
    count = db.scalar(select(func.count()).select_from(Application).where(Application.pos_id == pos_id)) or 0
    return _out(p, count)


@router.put("/{pos_id}", response_model=PositionOut)
def update_position(pos_id: int, body: PositionUpdate, db: Session = Depends(get_db)):
    """编辑岗位（只更新传入的字段）。"""
    p = _get_or_404(db, pos_id)
    # exclude_unset=True：只拿前端真正传了的字段。没传的不动，避免把没填的字段误改成空
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    count = db.scalar(select(func.count()).select_from(Application).where(Application.pos_id == pos_id)) or 0
    return _out(p, count)


@router.delete("/{pos_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_position(pos_id: int, db: Session = Depends(get_db)):
    """删除岗位：已有投递记录时拒绝（409）。"""
    p = _get_or_404(db, pos_id)
    count = db.scalar(select(func.count()).select_from(Application).where(Application.pos_id == pos_id)) or 0
    if count:
        # 数据库的外键本来也会拦住，但那个报错是英文乱码；我们先查一下，给出人能看懂的提示
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"该岗位下有 {count} 条投递记录，不能删除")
    db.delete(p)
    db.commit()
    # 204 = 「成功了，但没什么要回给你的」，所以不写 return
