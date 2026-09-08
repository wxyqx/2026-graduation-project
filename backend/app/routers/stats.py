from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import Application, Position
from app.services.state_machine import STAGE_LABELS, STAGES

router = APIRouter(prefix="/api/stats", tags=["stats"], dependencies=[Depends(get_current_user)])


def _week_start(d: datetime) -> datetime:
    monday = d - timedelta(days=d.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    """统计总览：各状态/阶段计数、本月录用、本周进行、上周完成、按岗位分组（顶部状态栏与汇总页共用）。"""
    now = datetime.now()
    this_week = _week_start(now)
    last_week = this_week - timedelta(days=7)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    position_count = db.scalar(select(func.count()).select_from(Position)) or 0

    status_rows = db.execute(select(Application.overall_status, func.count()).group_by(Application.overall_status)).all()
    status_counts = {"pending": 0, "pass": 0, "fail": 0}
    for s, n in status_rows:
        status_counts[s] = n

    stage_rows = db.execute(
        select(Application.current_stage, func.count())
        .where(Application.overall_status == "pending")
        .group_by(Application.current_stage)
    ).all()
    stage_map = {s: n for s, n in stage_rows}
    stage_counts = [{"stage": s, "label": STAGE_LABELS[s], "count": stage_map.get(s, 0)} for s in STAGES]

    ai_pending = stage_map.get("ai", 0)

    month_hired = db.scalar(
        select(func.count())
        .select_from(Application)
        .where(Application.overall_status == "pass", Application.update_time >= month_start)
    ) or 0
    week_in_progress = db.scalar(
        select(func.count())
        .select_from(Application)
        .where(Application.overall_status == "pending", Application.create_time >= this_week)
    ) or 0
    last_week_completed = db.scalar(
        select(func.count())
        .select_from(Application)
        .where(
            Application.overall_status.in_(["pass", "fail"]),
            Application.update_time >= last_week,
            Application.update_time < this_week,
        )
    ) or 0

    by_pos_rows = db.execute(
        select(Position.id, Position.position_name, Application.overall_status, func.count())
        .join(Application, Application.pos_id == Position.id, isouter=True)
        .group_by(Position.id, Position.position_name, Application.overall_status)
        .order_by(Position.id)
    ).all()
    by_position: dict[int, dict] = {}
    for pid, pname, status, n in by_pos_rows:
        entry = by_position.setdefault(
            pid, {"pos_id": pid, "position_name": pname, "total": 0, "pending": 0, "pass": 0, "fail": 0}
        )
        if status is not None:
            entry[status] = n
            entry["total"] += n

    return {
        "position_count": position_count,
        "application_total": sum(status_counts.values()),
        "pending_count": status_counts["pending"],
        "pass_count": status_counts["pass"],
        "fail_count": status_counts["fail"],
        "ai_pending_count": ai_pending,
        "week_in_progress": week_in_progress,
        "last_week_completed": last_week_completed,
        "month_hired": month_hired,
        "stage_counts": stage_counts,
        "by_position": list(by_position.values()),
    }
