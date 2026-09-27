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
from app.models import User
from app.schemas.export import ExportIn
from app.services import export as svc
from app.services import settings as settings_svc
from app.services import summary
from app.services.state_machine import STAGES, STATUSES

router = APIRouter(prefix="/api/export", tags=["export"], dependencies=[Depends(get_current_user)])


@router.get("/fields")
def export_fields():
    """可导出的列有哪些（给勾选框用）

**干什么用**：前端「汇总导出」页的字段勾选框，就是从这里拿列表。导出时把勾中的 `key` 放进 `fields`。

**返回什么**：21 列，顺序就是导出时的列顺序：
```json
[
  {"key": "id", "label": "投递编号"},
  {"key": "candidate_name", "label": "候选人姓名"},
  {"key": "position_name", "label": "岗位名称"},
  {"key": "current_stage", "label": "当前阶段"},
  {"key": "overall_status", "label": "全局状态"},
  {"key": "ai_result", "label": "AI筛选结果"},
  {"key": "ai_comment", "label": "AI筛选理由"},
  "……7 关的时间和结果……",
  {"key": "create_time", "label": "投递创建时间"},
  {"key": "update_time", "label": "更新时间"}
]
```
"""
    return [{"key": k, "label": v} for k, v in svc.EXPORT_FIELDS.items()]


@router.post("")
def export(body: ExportIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """导出投递记录为 Excel / csv 文件

**干什么用**：把系统里的投递记录导成表格，发给领导、存档、或用 Excel 做进一步分析。

**怎么填**：
- `filters`：筛选条件，都可不填。时间段按投递创建时间算，`start_date` 和 `end_date` 都包含当天
- `fields`：想要哪些列（`key` 见上面 /fields 接口），空 = 全部 21 列
- `format`：`xlsx`（Excel）或 `csv`

**返回什么**：不是 JSON，是**文件本身**。在 /docs 网页上点 Execute 后，Response body 会出现一个 **Download file** 链接，点它下载。
表头是中文，`pass/fail/pending` 这类值也翻成了中文（通过 / 淘汰 / 进行中……）。

回应头里有两个额外信息：
- `Content-Disposition`：文件名，形如 `投递记录_20260908_143000.xlsx`
- `X-Row-Count`：导出了几行

**可能出错**：
- 400：`fields` 里有不认识的列名 / `stage` `status` 不合法 / `format` 不是 xlsx 或 csv

**小知识**：csv 用的是 utf-8-sig 编码（开头带一个隐形标记），这样用 Excel 直接打开中文不会乱码。
"""
    # ---- 检查参数 ----
    fmt = body.format.lower()
    if fmt not in ("xlsx", "csv"):
        raise HTTPException(status_code=400, detail="format 只能是 xlsx 或 csv")
    mode = (body.mode or "records").lower()
    if mode not in ("records", "matrix", "report"):
        raise HTTPException(status_code=400, detail="mode 只能是 records、matrix 或 report")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # 文件名里带时间，多次导出不会覆盖

    # ---- 模式三：招聘周报（两个工作表：阶段岗位汇总 + 进行中候选人）----
    if mode == "report":
        if body.range == "custom" and body.filters.start_date and body.filters.end_date \
                and body.filters.start_date > body.filters.end_date:
            raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")
        start, end, range_label = summary.resolve_range(body.range, body.filters.start_date, body.filters.end_date)
        matrix = summary.build_matrix(db, start, end)
        progress = summary.build_in_progress(db, start, end, settings_svc.get_stage_notes(db, user.id))
        mh, mr = summary.matrix_to_table(matrix)
        ph, pr = summary.in_progress_to_table(progress)
        if fmt == "csv":
            # csv 一个文件只能装一张表，这里退化为只导第一张（阶段岗位汇总）
            content = svc.to_csv(mh, mr)
            media = "text/csv; charset=utf-8"
        else:
            content = svc.to_xlsx_sheets([("阶段岗位汇总", mh, mr), ("进行中候选人", ph, pr)])
            media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"招聘周报_{range_label}_{stamp}.{fmt}"
        return Response(
            content=content,
            media_type=media,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
                "X-Row-Count": str(len(mr) + len(pr)),
            },
        )

    # ---- 模式二：导出「阶段 × 岗位」交叉汇总表（周报那种表）----
    if mode == "matrix":
        if body.range == "custom" and body.filters.start_date and body.filters.end_date \
                and body.filters.start_date > body.filters.end_date:
            raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")
        start, end, range_label = summary.resolve_range(body.range, body.filters.start_date, body.filters.end_date)
        matrix = summary.build_matrix(db, start, end)
        headers, rows = summary.matrix_to_table(matrix)
        if fmt == "xlsx":
            content = svc.to_xlsx(headers, rows, title="阶段岗位汇总")
            media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            content = svc.to_csv(headers, rows)
            media = "text/csv; charset=utf-8"
        filename = f"阶段岗位汇总_{range_label}_{stamp}.{fmt}"
        return Response(
            content=content,
            media_type=media,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
                "X-Row-Count": str(len(rows)),
            },
        )

    # ---- 模式一（默认）：逐条投递记录 ----
    fields = body.fields or list(svc.EXPORT_FIELDS)  # 没勾选 = 全部列
    unknown = [k for k in fields if k not in svc.EXPORT_FIELDS]  # 有没有乱传的列名
    if unknown:
        raise HTTPException(status_code=400, detail=f"不支持的导出字段：{', '.join(unknown)}")
    if body.filters.stage and body.filters.stage not in STAGES:
        raise HTTPException(status_code=400, detail="stage 不是合法阶段值")
    if body.filters.status and body.filters.status not in STATUSES:
        raise HTTPException(status_code=400, detail="status 不是合法状态值")

    # ---- 查数据、整理成表、生成文件 ----
    apps = svc.query_applications(db, body.filters)
    headers, rows = svc.build_rows(apps, fields)
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
