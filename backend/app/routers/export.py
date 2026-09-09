"""
【导出接口】
  GET  /api/export/fields   告诉前端有哪些列可以勾选（key + 中文名）
  POST /api/export          按条件和勾选的列导出，直接回一个文件让浏览器下载

跟别的接口不同：这个接口回的不是 JSON，而是「文件」。
浏览器一收到带 Content-Disposition: attachment 的回应，就会弹出下载。
"""
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
    """可导出字段清单（key + 中文名）。"""
    return [{"key": k, "label": v} for k, v in svc.EXPORT_FIELDS.items()]


@router.post("")
def export(body: ExportIn, db: Session = Depends(get_db)):
    """导出投递记录：filters 选数据范围，fields 勾选字段（空=全部），format 为 xlsx 或 csv；返回文件流。"""
    # ---- 检查参数 ----
    fields = body.fields or list(svc.EXPORT_FIELDS)  # 没勾选 = 全部列
    unknown = [k for k in fields if k not in svc.EXPORT_FIELDS]  # 有没有乱传的列名
    if unknown:
        raise HTTPException(status_code=400, detail=f"不支持的导出字段：{', '.join(unknown)}")
    if body.filters.stage and body.filters.stage not in STAGES:
        raise HTTPException(status_code=400, detail="stage 不是合法阶段值")
    if body.filters.status and body.filters.status not in STATUSES:
        raise HTTPException(status_code=400, detail="status 不是合法状态值")
    fmt = body.format.lower()
    if fmt not in ("xlsx", "csv"):
        raise HTTPException(status_code=400, detail="format 只能是 xlsx 或 csv")

    # ---- 查数据、整理成表、生成文件 ----
    apps = svc.query_applications(db, body.filters)
    headers, rows = svc.build_rows(apps, fields)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # 文件名里带时间，多次导出不会覆盖
    if fmt == "xlsx":
        content = svc.to_xlsx(headers, rows)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"  # Excel 文件的「类型标签」
    else:
        content = svc.to_csv(headers, rows)
        media = "text/csv; charset=utf-8"
    filename = f"投递记录_{stamp}.{fmt}"
    return Response(
        content=content,
        media_type=media,
        headers={
            # attachment = 让浏览器下载而不是直接打开；filename*=UTF-8'' 是让中文文件名不乱码的标准写法
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
            "X-Row-Count": str(len(rows)),  # 顺便告诉前端导了几行，可以弹个提示
        },
    )
