"""【技术管理端：运行概览】账号、业务数据、文件、表单、日志与数据库体积。"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.models import (
    AiApiConfig,
    Application,
    Candidate,
    CandidateFile,
    FormSubmission,
    FormTemplate,
    OperationLog,
    Position,
    User,
)

router = APIRouter(prefix="/api/tech", tags=["tech-overview"])


def _count(db: Session, model, *where) -> int:
    stmt = select(func.count()).select_from(model)
    if where:
        stmt = stmt.where(*where)
    return int(db.scalar(stmt) or 0)


@router.get("/overview")
def overview(db: Session = Depends(get_db), current: User = Depends(get_current_admin)):
    """运行概览：一眼看到账号、业务量、文件、表单、日志与数据库大小"""
    week_ago = datetime.now() - timedelta(days=7)
    file_count = _count(db, CandidateFile)
    file_bytes = int(db.scalar(select(func.coalesce(func.sum(CandidateFile.size_bytes), 0))) or 0)
    db_bytes = int(
        db.scalar(
            text(
                "SELECT COALESCE(SUM(data_length + index_length), 0) "
                "FROM information_schema.TABLES WHERE table_schema = DATABASE()"
            )
        )
        or 0
    )
    recent = db.scalars(select(OperationLog).order_by(OperationLog.create_time.desc()).limit(8)).all()
    return {
        "users": {
            "total": _count(db, User),
            "hr": _count(db, User, User.role == "hr"),
            "admin": _count(db, User, User.role == "admin"),
            "candidate": _count(db, User, User.role == "candidate"),
            "inactive": _count(db, User, User.is_active == 0),
        },
        "business": {
            "candidates": _count(db, Candidate),
            "positions": _count(db, Position),
            "positions_hidden": _count(db, Position, Position.is_hidden == 1),
            "applications": _count(db, Application),
            "pending": _count(db, Application, Application.overall_status == "pending"),
            "pass": _count(db, Application, Application.overall_status == "pass"),
            "fail": _count(db, Application, Application.overall_status == "fail"),
            "portal_applications": _count(db, Application, Application.source == "portal"),
        },
        "system": {
            "ai_configs": _count(db, AiApiConfig),
            "ai_enabled": _count(db, AiApiConfig, AiApiConfig.is_enabled == 1),
            "form_templates": _count(db, FormTemplate),
            "form_submissions": _count(db, FormSubmission),
            "files": file_count,
            "file_bytes": file_bytes,
            "db_bytes": db_bytes,
            "logs_7d": _count(db, OperationLog, OperationLog.create_time >= week_ago),
        },
        "recent_logs": [
            {
                "id": x.id,
                "username": x.username,
                "role": x.role,
                "action": x.action,
                "target_type": x.target_type,
                "target_id": x.target_id,
                "ip": x.ip,
                "create_time": x.create_time,
            }
            for x in recent
        ],
    }
