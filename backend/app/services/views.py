"""
【这个文件是干什么的？】
把「投递记录」这个数据库对象整理成前端好用的字典（JSON）。

为什么单独放一个文件？因为好几个接口（列表、详情、创建、推进、撤回）都要返回投递数据，
统一在这里拼，格式就不会各处不一样。

两种「视图」：
  application_summary：列表页用的简版——一行能显示的那些字段
  application_detail ：详情页用的完整版——多了候选人、岗位的完整信息和 8 关时间线
"""
from app.models import Application
from app.services.state_machine import STAGE_LABELS, stage_timeline


def application_summary(app: Application) -> dict:
    """简版：列表里一行显示的内容。"""
    return {
        "id": app.id,
        "can_id": app.can_id,
        "pos_id": app.pos_id,
        # 顺着 relationship 拿名字。if app.candidate 是防御：万一关联对象取不到，别让整个接口崩掉
        "candidate_name": app.candidate.name if app.candidate else None,
        "position_name": app.position.position_name if app.position else None,
        "current_stage": app.current_stage,
        "current_stage_label": STAGE_LABELS.get(app.current_stage or "", app.current_stage),  # 中文名，前端直接显示
        "overall_status": app.overall_status,
        "ai_result": app.ai_result,
        "ai_comment": app.ai_comment,
        "create_time": app.create_time,
        "update_time": app.update_time,
    }


def application_detail(app: Application) -> dict:
    """完整版：先拿简版，再补上候选人、岗位、时间线。"""
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
    data["stages"] = stage_timeline(app)  # 8 关每关的成绩和时间，详情页画时间线
    return data
