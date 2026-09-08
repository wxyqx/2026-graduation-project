from app.models import Application
from app.services.state_machine import STAGE_LABELS, stage_timeline


def application_summary(app: Application) -> dict:
    return {
        "id": app.id,
        "can_id": app.can_id,
        "pos_id": app.pos_id,
        "candidate_name": app.candidate.name if app.candidate else None,
        "position_name": app.position.position_name if app.position else None,
        "current_stage": app.current_stage,
        "current_stage_label": STAGE_LABELS.get(app.current_stage or "", app.current_stage),
        "overall_status": app.overall_status,
        "ai_result": app.ai_result,
        "ai_comment": app.ai_comment,
        "create_time": app.create_time,
        "update_time": app.update_time,
    }


def application_detail(app: Application) -> dict:
    data = application_summary(app)
    data["candidate"] = (
        {
            "id": app.candidate.id,
            "name": app.candidate.name,
            "remark": app.candidate.remark,
            "create_time": app.candidate.create_time,
        }
        if app.candidate
        else None
    )
    data["position"] = (
        {
            "id": app.position.id,
            "position_name": app.position.position_name,
            "owner": app.position.owner,
            "position_requirements": app.position.position_requirements,
        }
        if app.position
        else None
    )
    data["stages"] = stage_timeline(app)
    return data
