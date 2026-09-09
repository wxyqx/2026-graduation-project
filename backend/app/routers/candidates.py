"""
【候选人接口】
  GET  /api/candidates?name=张   列表，可按姓名模糊搜
  POST /api/candidates           新建
  GET  /api/candidates/{id}      详情
  PUT  /api/candidates/{id}      改备注

没有删除接口：候选人一旦有投递记录就不该删；设计文档也没要求。
"""
from datetime import datetime

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
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
def list_candidates(
    name: str | None = Query(default=None, description="姓名关键字，模糊搜索。传「张」能搜到张三、小张；不传 = 全部"),
    db: Session = Depends(get_db),
):
    """候选人列表（可按姓名搜索）

**干什么用**：看所有候选人，或者按名字找某个人。

**怎么填**：`name` 可不填。填了就是「名字里含这几个字」的模糊搜索。

**返回什么**：数组，最新录入的在前：
```json
[{"id": 3, "name": "张三", "remark": "内推", "create_time": "2026-09-08T10:00:00"}]
```
"""
    # Query(default=None)：这个参数写在网址问号后面（?name=张），不传也行
    stmt = select(Candidate).order_by(Candidate.id.desc())
    if name:
        stmt = stmt.where(Candidate.name.like(f"%{name}%"))  # % 是通配符：「张」能搜到「张三」「小张」
    return [_out(c) for c in db.scalars(stmt).all()]


@router.post("", response_model=CandidateOut, status_code=status.HTTP_201_CREATED)
def create_candidate(body: CandidateIn, db: Session = Depends(get_db)):
    """手动新建一个候选人

**干什么用**：来了个应聘的人，先把他录进系统。（用「AI 录入」传简历的话不用手动建，AI 会自动建。）

**怎么填**：`name` 必填，`remark` 随意。

**返回什么**：新建好的候选人，带 `id`。建投递时 `can_id` 填它。

**注意**：系统按姓名认人，同名会被当成同一个人。手动建重名不拦你，但 AI 录入遇到同名会直接复用旧的。
"""
    c = Candidate(name=body.name, remark=body.remark, create_time=datetime.now())
    db.add(c)
    db.commit()
    db.refresh(c)
    return _out(c)


@router.get("/{can_id}", response_model=CandidateOut)
def get_candidate(can_id: Annotated[int, Path(description="候选人编号")], db: Session = Depends(get_db)):
    """看一个候选人的详情

**怎么填**：网址里换候选人编号，比如 `/api/candidates/3`。

**可能出错**：
- 404：没有这个编号的候选人
"""
    c = db.get(Candidate, can_id)
    if c is None:
        raise HTTPException(status_code=404, detail="候选人不存在")
    return _out(c)


@router.put("/{can_id}", response_model=CandidateOut)
def update_candidate(
    can_id: Annotated[int, Path(description="候选人编号")], body: CandidateUpdate, db: Session = Depends(get_db)
):
    """改候选人备注

**干什么用**：记点东西，比如「已电话确认到岗时间」「期望薪资 20k」。

**怎么填**：`{"remark": "新备注"}`。传 `{"remark": ""}` 可以清空。姓名不能改（它是认人的依据）。

**可能出错**：
- 404：没有这个候选人
"""
    c = db.get(Candidate, can_id)
    if c is None:
        raise HTTPException(status_code=404, detail="候选人不存在")
    # model_fields_set = 前端真正传了的字段集合。这样能区分「没传 remark」和「传了 remark 但值是空（想清空）」
    if "remark" in body.model_fields_set:
        c.remark = body.remark
    db.commit()
    db.refresh(c)
    return _out(c)
