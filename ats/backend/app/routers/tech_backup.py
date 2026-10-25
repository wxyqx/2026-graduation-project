"""【技术管理端：数据备份导出】"""
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.models import User
from app.services import backup_service
from app.services.log_service import log_action

router = APIRouter(prefix="/api/tech", tags=["tech-backup"])


@router.get("/backup/export")
def export_backup(db: Session = Depends(get_db), current: User = Depends(get_current_admin)):
    """导出全库 ZIP（CSV + 候选人文件 + manifest）

**注意**：备份包含候选人个人信息，只应由技术管理员保管；恢复是手工操作。
"""
    data, counts = backup_service.export_zip(db)
    log_action(
        db, current, "backup", target_type="backup",
        detail={"tables": counts, "bytes": len(data)},
    )
    db.commit()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"ats_backup_{stamp}.zip"
    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
            "X-Backup-Rows": str(sum(counts.values())),
        },
    )
