"""
【操作日志服务】——技术管理端排查问题用

调用方式：
    log_action(db, user, "login", ip=ip)
    log_action(db, user, "update", target_type="candidate", target_id=3, detail={"phone": "..."})

注意：这里只 db.add，不 commit——跟主业务在同一个事务里，主业务提交时一起落库。
写日志失败不能影响主业务，所以内部全部 try/except。
"""
import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import OperationLog, User


def log_action(
    db: Session,
    user: User | None,
    action: str,
    *,
    target_type: str | None = None,
    target_id: int | None = None,
    detail: dict | None = None,
    ip: str | None = None,
) -> None:
    try:
        entry = OperationLog(
            user_id=user.id if user else None,
            username=(user.username or (user.candidate.phone if user.candidate else None)) if user else None,
            role=user.role if user else None,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail_json=json.dumps(detail, ensure_ascii=False) if detail else None,
            ip=ip,
            create_time=datetime.now(),
        )
        db.add(entry)
    except Exception:
        # 日志是辅助功能，绝不能因为它让主流程报错
        pass
