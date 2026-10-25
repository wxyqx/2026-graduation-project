"""
【候选人端视图】——白名单序列化，绝不把内部字段带出去

候选人只能看到：
  · 自己的投递走到了第几关、通过还是淘汰、什么时候
  · 岗位名称、负责人、JD
  · 自己的简历文件与表单状态
看不到：
  · 各关原因、面试评价、AI 理由（ai_comment）
  · 候选人备注、其他候选人任何信息
"""
from sqlalchemy import select

from app.models import Application, CandidateFile, FormSubmission, Position
from app.services import file_service, form_service
from app.services import state_machine as sm


def _position_brief(p: Position) -> dict:
    return {"id": p.id, "name": p.position_name, "owner": p.owner}


def position_summary(db, p: Position, candidate_id: int) -> dict:
    """岗位列表里的一行。"""
    applied = (
        db.scalar(select(Application.id).where(Application.can_id == candidate_id, Application.pos_id == p.id))
        is not None
    )
    return {
        **_position_brief(p),
        "requirements_summary": (p.position_requirements or "")[:120],
        "applied": applied,
        "has_position_form": form_service.get_active_template(db, "position", p.id) is not None,
    }


def position_detail(db, p: Position, candidate_id: int) -> dict:
    """岗位详情：加完整 JD、表单要求、我是否已投。"""
    active_profile = form_service.get_active_template(db, "profile")
    profile_sub = (
        form_service.get_submission(db, active_profile.id, candidate_id, None) if active_profile else None
    )
    return {
        **_position_brief(p),
        "requirements": p.position_requirements,
        "applied": db.scalar(
            select(Application.id).where(Application.can_id == candidate_id, Application.pos_id == p.id)
        )
        is not None,
        "has_position_form": form_service.get_active_template(db, "position", p.id) is not None,
        "profile_form_required": active_profile is not None,
        "profile_form_submitted": bool(profile_sub and profile_sub.status == "submitted"),
    }


def _form_status(db, app: Application) -> dict:
    """这次投递的两张表填到哪一步了。"""
    profile_t = form_service.get_active_template(db, "profile")
    profile_sub = form_service.get_submission(db, profile_t.id, app.can_id, None) if profile_t else None
    position_t = form_service.get_active_template(db, "position", app.pos_id)
    position_sub = (
        form_service.get_submission(db, position_t.id, app.can_id, app.id) if position_t else None
    )
    return {
        "profile": profile_sub.status if profile_sub else ("none" if profile_t else "not_required"),
        "position": position_sub.status if position_sub else ("none" if position_t else "not_required"),
    }


def timeline(app: Application) -> list[dict]:
    """7 关时间线，带 state（passed/failed/current/waiting），前端不用自己推。"""
    current = app.current_stage
    try:
        cur_idx = sm.STAGES.index(current) if current else -1
    except ValueError:
        cur_idx = -1
    items = []
    for i, stage in enumerate(sm.STAGES):
        result_field, time_field = sm.STAGE_FIELDS[stage]
        result = getattr(app, result_field) if result_field else None
        when = getattr(app, time_field) if time_field else None
        if result == "pass":
            state = "passed"
        elif result == "fail":
            state = "failed"
        elif stage == current and app.overall_status == "pending":
            state = "current"
        elif cur_idx >= 0 and i < cur_idx:
            state = "passed"
        else:
            state = "waiting"
        items.append(
            {
                "stage": stage,
                "label": sm.STAGE_LABELS[stage],
                "state": state,
                "result": result,
                "time": when,
                "is_current": stage == current,
            }
        )
    return items


def _resume_info(db, candidate_id: int) -> dict | None:
    f: CandidateFile | None = file_service.current_resume(db, candidate_id)
    if f is None:
        return None
    return {"file_id": f.id, "name": f.original_name, "size": f.size_bytes, "upload_time": f.upload_time}


def application_summary(db, app: Application) -> dict:
    """我的投递列表里的一行。"""
    p = app.position
    return {
        "id": app.id,
        "position": _position_brief(p) if p else None,
        "position_closed": bool(p.is_hidden) if p else True,
        "current_stage": app.current_stage,
        "current_stage_label": sm.STAGE_LABELS.get(app.current_stage or "", app.current_stage),
        "overall_status": app.overall_status,
        "ai_result": app.ai_result,
        "create_time": app.create_time,
        "update_time": app.update_time,
    }


def application_detail(db, app: Application) -> dict:
    """我的投递详情：时间线 + 简历 + 表单状态，不含任何内部文字。"""
    data = application_summary(db, app)
    p = app.position
    if p is not None:
        data["position"]["requirements"] = p.position_requirements
    data["resume"] = _resume_info(db, app.can_id)
    data["form_status"] = _form_status(db, app)
    data["timeline"] = timeline(app)
    return data
