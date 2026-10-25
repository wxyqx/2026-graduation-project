"""【技术管理端：操作日志】分页 + 按角色/动作/关键字筛选。"""
import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.models import OperationLog, User

router = APIRouter(prefix="/api/tech", tags=["tech-logs"])


@router.get("/logs")
def list_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    role: str | None = Query(default=None, description="candidate / hr / admin"),
    action: str | None = Query(default=None, description="login / create / update / delete / reset_password / export / backup / config_change"),
    keyword: str | None = Query(default=None, description="用户名或详情关键字"),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_admin),
):
    """操作日志（按时间倒序）"""
    stmt = select(OperationLog)
    count_stmt = select(func.count()).select_from(OperationLog)
    if role:
        stmt = stmt.where(OperationLog.role == role)
        count_stmt = count_stmt.where(OperationLog.role == role)
    if action:
        stmt = stmt.where(OperationLog.action == action)
        count_stmt = count_stmt.where(OperationLog.action == action)
    if keyword:
        like = f"%{keyword.strip()}%"
        cond = or_(OperationLog.username.like(like), OperationLog.detail_json.like(like))
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    total = int(db.scalar(count_stmt) or 0)
    rows = db.scalars(
        stmt.order_by(OperationLog.create_time.desc(), OperationLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = []
    for x in rows:
        detail = None
        if x.detail_json:
            try:
                detail = json.loads(x.detail_json)
            except ValueError:
                detail = x.detail_json
        items.append(
            {
                "id": x.id,
                "username": x.username,
                "role": x.role,
                "action": x.action,
                "target_type": x.target_type,
                "target_id": x.target_id,
                "detail": detail,
                "ip": x.ip,
                "create_time": x.create_time,
            }
        )
    return {"total": total, "page": page, "page_size": page_size, "items": items}
