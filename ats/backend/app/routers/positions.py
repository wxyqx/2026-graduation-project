"""
【岗位接口：增删改查】
  GET    /api/positions        列表
  POST   /api/positions        新建
  GET    /api/positions/{id}   详情
  PUT    /api/positions/{id}   编辑
  DELETE /api/positions/{id}   删除（有人投过就不让删）
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
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
        is_hidden=bool(p.is_hidden),
    )


def _get_or_404(db: Session, pos_id: int) -> Position:
    """按编号找岗位，找不到直接回 404（「没有这个东西」）。好几个接口都要先找，抽成一个小函数。"""
    p = db.get(Position, pos_id)
    if p is None:
        raise HTTPException(status_code=404, detail="岗位不存在")
    return p


@router.get("", response_model=list[PositionOut])
def list_positions(
    include_hidden: bool = Query(
        default=False,
        description="是否包含「暂不招」的岗位。默认 false=只返回在招岗位（各处下拉用）；岗位管理页传 true 拿全部",
    ),
    db: Session = Depends(get_db),
):
    """岗位列表（带每个岗位收到了几条投递）

**干什么用**：看看现在有哪些岗位在招。前端「岗位管理」页的表格就是它。

**怎么填**：不用填。

**返回什么**：一个数组，最新建的排最前面：
```json
[
  {"id": 2, "position_name": "前端工程师", "owner": "李HR", "position_requirements": "熟悉Vue3", "application_count": 0},
  {"id": 1, "position_name": "Java高级工程师", "owner": "王HR", "position_requirements": "3年以上Java…", "application_count": 5}
]
```
`application_count` 大于 0 的岗位不能删除。
"""
    counts = _count_map(db)
    stmt = select(Position).order_by(Position.id.desc())  # 按编号倒序，新建的在最上面
    if not include_hidden:
        stmt = stmt.where(Position.is_hidden == 0)  # 默认不返回「暂不招」的岗位
    positions = db.scalars(stmt).all()
    return [_out(p, counts.get(p.id, 0)) for p in positions]


@router.post("", response_model=PositionOut, status_code=status.HTTP_201_CREATED)
def create_position(body: PositionIn, db: Session = Depends(get_db)):
    """新建一个岗位

**干什么用**：开始招一个新职位。这是用系统的第一步——没有岗位，候选人没地方投。

**怎么填**：只有 `position_name` 必填。**强烈建议把 `position_requirements` 写详细**，
因为 AI 筛简历时就是拿简历和这段话比对：写「3年以上Java，熟悉Spring Boot」比只写「Java」准得多。

**返回什么**：新建好的岗位，带上数据库分配的 `id`。记住这个 id，建投递时要用。

**可能出错**：
- 422：`position_name` 没填或超过 100 字
"""
    p = Position(**body.model_dump())  # **：把字典拆成 position_name=..., owner=... 这样的参数
    db.add(p)
    db.commit()
    db.refresh(p)
    return _out(p)


@router.get("/{pos_id}", response_model=PositionOut)
def get_position(pos_id: Annotated[int, Path(description="岗位编号（列表里的 id）")], db: Session = Depends(get_db)):
    """看一个岗位的详情

**干什么用**：点开某个岗位看完整信息（列表里岗位要求可能被截断显示）。

**怎么填**：网址里的 `pos_id` 换成岗位编号，比如 `/api/positions/1`。

**可能出错**：
- 404：没有这个编号的岗位
"""
    # 网址里的 {pos_id} 会自动变成函数参数 pos_id，并且转成整数（不是数字会回 422）
    p = _get_or_404(db, pos_id)
    count = db.scalar(select(func.count()).select_from(Application).where(Application.pos_id == pos_id)) or 0
    return _out(p, count)


@router.put("/{pos_id}", response_model=PositionOut)
def update_position(
    pos_id: Annotated[int, Path(description="岗位编号")], body: PositionUpdate, db: Session = Depends(get_db)
):
    """编辑岗位（只改你传的字段）

**干什么用**：改名字、换负责人、补充岗位要求。

**怎么填**：想改哪个就传哪个，**没传的字段保持原样**。比如只想换负责人：`{"owner": "李HR"}`。

**返回什么**：改完后的完整岗位。

**可能出错**：
- 404：没有这个岗位
- 422：传的值不合规（比如名称传了空字符串）
"""
    p = _get_or_404(db, pos_id)
    # exclude_unset=True：只拿前端真正传了的字段。没传的不动，避免把没填的字段误改成空
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    count = db.scalar(select(func.count()).select_from(Application).where(Application.pos_id == pos_id)) or 0
    return _out(p, count)


@router.delete("/{pos_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_position(pos_id: Annotated[int, Path(description="岗位编号")], db: Session = Depends(get_db)):
    """删除岗位（已经有人投递的不让删）

**干什么用**：招满了或不招了，把岗位删掉。

**怎么填**：网址里换岗位编号。

**返回什么**：成功是 204，没有内容（就是「删好了，没别的要说」）。

**可能出错**：
- 404：没有这个岗位
- 409：这个岗位下已有投递记录，不能删——否则那些投递就变成「投了一个不存在的岗位」。想删得先处理掉投递。
"""
    p = _get_or_404(db, pos_id)
    count = db.scalar(select(func.count()).select_from(Application).where(Application.pos_id == pos_id)) or 0
    if count:
        # 数据库的外键本来也会拦住，但那个报错是英文乱码；我们先查一下，给出人能看懂的提示
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"该岗位下有 {count} 条投递记录，不能删除")
    db.delete(p)
    db.commit()
    # 204 = 「成功了，但没什么要回给你的」，所以不写 return
