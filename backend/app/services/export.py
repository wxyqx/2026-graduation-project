import csv
import io
from datetime import datetime, time, timedelta

from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application
from app.schemas.export import ExportFilters
from app.services.state_machine import STAGE_LABELS

# 字段 key → 中文表头（顺序即导出顺序）
EXPORT_FIELDS: dict[str, str] = {
    "id": "投递编号",
    "candidate_name": "候选人姓名",
    "position_name": "岗位名称",
    "current_stage": "当前阶段",
    "overall_status": "全局状态",
    "ai_result": "AI筛选结果",
    "ai_comment": "AI筛选理由",
    "resume_submit_time": "简历提交时间",
    "resume_result": "简历筛选结果",
    "phone_time": "电话沟通时间",
    "phone_result": "电话沟通结果",
    "test_time": "笔试时间",
    "test_result": "笔试结果",
    "pro_time": "专业面时间",
    "pro_result": "专业面结果",
    "hr_time": "HR面时间",
    "hr_result": "HR面结果",
    "final_time": "终面时间",
    "final_result": "终面结果",
    "create_time": "投递创建时间",
    "update_time": "更新时间",
}

STATUS_LABELS = {"pending": "进行中", "pass": "已录用", "fail": "已淘汰"}
RESULT_LABELS = {"pass": "通过", "fail": "淘汰"}


def query_applications(db: Session, f: ExportFilters) -> list[Application]:
    stmt = select(Application).order_by(Application.id)
    if f.start_date:
        stmt = stmt.where(Application.create_time >= datetime.combine(f.start_date, time.min))
    if f.end_date:
        stmt = stmt.where(Application.create_time < datetime.combine(f.end_date + timedelta(days=1), time.min))
    if f.pos_id:
        stmt = stmt.where(Application.pos_id == f.pos_id)
    if f.stage:
        stmt = stmt.where(Application.current_stage == f.stage)
    if f.status:
        stmt = stmt.where(Application.overall_status == f.status)
    return db.scalars(stmt).all()


def _cell(app: Application, key: str):
    if key == "candidate_name":
        return app.candidate.name if app.candidate else None
    if key == "position_name":
        return app.position.position_name if app.position else None
    val = getattr(app, key)
    if key == "current_stage":
        return STAGE_LABELS.get(val, val)
    if key == "overall_status":
        return STATUS_LABELS.get(val, val)
    if key.endswith("_result"):
        return RESULT_LABELS.get(val, val)
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    return val


def build_rows(apps: list[Application], fields: list[str]) -> tuple[list[str], list[list]]:
    headers = [EXPORT_FIELDS[k] for k in fields]
    rows = [[_cell(a, k) for k in fields] for a in apps]
    return headers, rows


def to_xlsx(headers: list[str], rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "投递记录"
    ws.append(headers)
    for r in rows:
        ws.append(r)
    for i, h in enumerate(headers, start=1):
        width = max([len(str(h))] + [len(str(r[i - 1])) for r in rows if r[i - 1] is not None] or [8])
        ws.column_dimensions[get_column_letter(i)].width = min(max(width * 1.6, 10), 60)
    ws.freeze_panes = "A2"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def to_csv(headers: list[str], rows: list[list]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    for r in rows:
        w.writerow(["" if v is None else v for v in r])
    return buf.getvalue().encode("utf-8-sig")
