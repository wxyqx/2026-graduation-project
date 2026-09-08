from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.schemas.export import ExportIn
from app.services import export as svc
from app.services.state_machine import STAGES, STATUSES

router = APIRouter(prefix="/api/export", tags=["export"], dependencies=[Depends(get_current_user)])


@router.get("/fields")
def export_fields():
    return [{"key": k, "label": v} for k, v in svc.EXPORT_FIELDS.items()]


@router.post("")
def export(body: ExportIn, db: Session = Depends(get_db)):
    fields = body.fields or list(svc.EXPORT_FIELDS)
    unknown = [k for k in fields if k not in svc.EXPORT_FIELDS]
    if unknown:
        raise HTTPException(status_code=400, detail=f"不支持的导出字段：{', '.join(unknown)}")
    if body.filters.stage and body.filters.stage not in STAGES:
        raise HTTPException(status_code=400, detail="stage 不是合法阶段值")
    if body.filters.status and body.filters.status not in STATUSES:
        raise HTTPException(status_code=400, detail="status 不是合法状态值")
    fmt = body.format.lower()
    if fmt not in ("xlsx", "csv"):
        raise HTTPException(status_code=400, detail="format 只能是 xlsx 或 csv")

    apps = svc.query_applications(db, body.filters)
    headers, rows = svc.build_rows(apps, fields)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if fmt == "xlsx":
        content = svc.to_xlsx(headers, rows)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        content = svc.to_csv(headers, rows)
        media = "text/csv; charset=utf-8"
    filename = f"投递记录_{stamp}.{fmt}"
    return Response(
        content=content,
        media_type=media,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
            "X-Row-Count": str(len(rows)),
        },
    )
