"""招聘流程状态机：阶段顺序与字段映射均以数据字典为准。"""
from datetime import datetime

from app.models import Application

STAGES = ["ai", "resume", "contact", "phone", "test", "pro", "hr", "final"]

STAGE_LABELS = {
    "ai": "AI筛选",
    "resume": "简历筛选",
    "contact": "联系候选人",
    "phone": "电话沟通",
    "test": "笔试",
    "pro": "专业面",
    "hr": "HR面",
    "final": "终面",
}

# (结果字段, 时间字段)；contact 阶段在数据字典中没有对应字段，仅作为流程节点
STAGE_FIELDS: dict[str, tuple[str | None, str | None]] = {
    "ai": ("ai_result", None),
    "resume": ("resume_result", "resume_submit_time"),
    "contact": (None, None),
    "phone": ("phone_result", "phone_time"),
    "test": ("test_result", "test_time"),
    "pro": ("pro_result", "pro_time"),
    "hr": ("hr_result", "hr_time"),
    "final": ("final_result", "final_time"),
}

RESULTS = {"pass", "fail"}
STATUSES = {"pending", "pass", "fail"}


def next_stage(stage: str) -> str | None:
    idx = STAGES.index(stage)
    return STAGES[idx + 1] if idx + 1 < len(STAGES) else None


def write_stage(app: Application, stage: str, result: str, now: datetime) -> None:
    result_field, time_field = STAGE_FIELDS[stage]
    if result_field:
        setattr(app, result_field, result)
    if time_field:
        setattr(app, time_field, now)


def clear_stage(app: Application, stage: str) -> None:
    result_field, time_field = STAGE_FIELDS[stage]
    if result_field:
        setattr(app, result_field, None)
    if time_field:
        setattr(app, time_field, None)
    if stage == "ai":
        app.ai_comment = None


def apply_result(app: Application, stage: str, result: str, now: datetime) -> None:
    """写入某阶段结果并推进/终止，advance 与 AI 录入共用。"""
    write_stage(app, stage, result, now)
    if result == "fail":
        app.overall_status = "fail"
    elif stage == "final":
        app.overall_status = "pass"
    else:
        app.current_stage = next_stage(stage)
        app.overall_status = "pending"
    app.update_time = now


def revert(app: Application, to_stage: str | None, now: datetime) -> None:
    """撤回上一步决定。

    - 已淘汰/已录用：终局结果写在当前阶段，撤回即清掉该结果、停留原阶段、恢复 pending
    - 进行中：当前阶段尚无结果，撤回回到上一阶段并清掉上一阶段结果（那才是上一步决定）
    - 指定 toStage：回到该阶段，清掉 toStage 及其后所有阶段数据，重新从 toStage 开始
    """
    current = app.current_stage
    cur_idx = STAGES.index(current)
    if to_stage is None:
        if app.overall_status != "pending":
            clear_stage(app, current)
            target = current
        else:
            if cur_idx == 0:
                raise ValueError("第一阶段（AI筛选）不可再撤回")
            target = STAGES[cur_idx - 1]
            clear_stage(app, target)
    else:
        if to_stage not in STAGES:
            raise ValueError("toStage 不是合法阶段值")
        target_idx = STAGES.index(to_stage)
        if target_idx > cur_idx or (target_idx == cur_idx and app.overall_status == "pending"):
            raise ValueError("toStage 必须早于当前阶段")
        for s in STAGES[target_idx : cur_idx + 1]:
            clear_stage(app, s)
        target = to_stage
    app.current_stage = target
    app.overall_status = "pending"
    app.update_time = now


def stage_timeline(app: Application) -> list[dict]:
    items = []
    for s in STAGES:
        result_field, time_field = STAGE_FIELDS[s]
        items.append(
            {
                "stage": s,
                "label": STAGE_LABELS[s],
                "result": getattr(app, result_field) if result_field else None,
                "time": getattr(app, time_field) if time_field else None,
                "is_current": s == app.current_stage,
            }
        )
    return items
