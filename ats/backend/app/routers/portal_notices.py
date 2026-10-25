"""
【候选人端通知接口】
  GET /api/portal/notices            我的通知（未读在前，新的在前）
  PUT /api/portal/notices/{id}/read  标记某条为已读
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_candidate
from app.models import User
from app.services import notice_service

router = APIRouter(prefix="/api/portal/notices", tags=["portal-notices"])

NoticeId = Annotated[int, Path(description="通知编号")]


def _out(n) -> dict:
    return {
        "id": n.id,
        "application_id": n.application_id,
        "stage": n.stage,
        "title": n.title,
        "body": n.body,
        "send_time": n.send_time,
        "read_time": n.read_time,
    }


@router.get("")
def my_notices(db: Session = Depends(get_db), user: User = Depends(get_current_candidate)):
    """我的通知列表（未读在前，新的在前）

**干什么用**：候选人登录后前端拉取，有未读就弹窗展示（类似邮件通知）。
**注意**：只返回已发送的通知；草稿是 HR 底稿，不对候选人展示。
"""
    if user.candidate_id is None:
        return []
    # 草稿（Send_Time 为空）是 HR 的底稿，绝不返回给候选人
    notices = [
        n for n in notice_service.list_notices(db, user.candidate_id) if n.send_time is not None
    ]
    return [_out(n) for n in notices]


class ReadOut(BaseModel):
    id: int
    read_time: object | None = None


@router.put("/{notice_id}/read")
def read_notice(notice_id: NoticeId, db: Session = Depends(get_db), user: User = Depends(get_current_candidate)):
    """标记通知为已读（弹窗点「知道了」时调用）"""
    if user.candidate_id is None:
        raise HTTPException(status_code=401, detail="账号未关联候选人档案")
    ok = notice_service.mark_read(db, user.candidate_id, notice_id)
    if not ok:
        raise HTTPException(status_code=404, detail="通知不存在")
    return {"id": notice_id, "read": True}
