"""
【这个文件是干什么的？】——「暂不招」岗位的统一出口

岗位可以设成「暂不招」（is_hidden=1）。设了之后，这个岗位**以及它名下所有投递**都要从
统计和列表里彻底消失，像不存在一样（数据还在库里，随时能改回来）。

为什么要单独一个文件？因为「排除隐藏岗位」这件事要在很多地方做（投递列表、统计、交叉表、
导出、AI 筛选……）。如果每个地方各写一遍，早晚会漏掉一处、出现「岗位藏了但数字还在」的怪现象。
所以集中在这里，所有地方都调这几个函数。
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Position


def hidden_ids(db: Session) -> set[int]:
    """拿到所有「暂不招」岗位的编号集合。"""
    rows = db.scalars(select(Position.id).where(Position.is_hidden == 1)).all()
    return set(rows)


def visible_positions(db: Session, order_desc: bool = False) -> list[Position]:
    """只拿「在招」的岗位（排除暂不招的）。"""
    stmt = select(Position).where(Position.is_hidden == 0)
    stmt = stmt.order_by(Position.id.desc() if order_desc else Position.id)
    return list(db.scalars(stmt).all())


def is_hidden(db: Session, pos_id: int) -> bool:
    """这个岗位是不是「暂不招」？"""
    p = db.get(Position, pos_id)
    return bool(p and p.is_hidden)


def exclude_hidden_apps(stmt, db: Session):
    """给「查投递」的语句加上「排除暂不招岗位」的条件。

    用法：stmt = exclude_hidden_apps(select(Application), db)
    没有隐藏岗位时原样返回（不加多余条件，保持 SQL 简单）。
    """
    from app.models import Application

    ids = hidden_ids(db)
    if not ids:
        return stmt
    return stmt.where(Application.pos_id.notin_(ids))
