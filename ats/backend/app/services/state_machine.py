"""
【这个文件是干什么的？】——招聘流程的「闯关规则」
一条投递要过 7 关。这个文件规定：关卡顺序是什么、每一关的成绩记在表的哪一格、
过关怎么往前走、被淘汰怎么办、想撤回一步怎么退。

所有名字（ai / resume / pass / fail / pending …）都照抄数据字典，不自己发明。
"""
from datetime import datetime

from app.models import Application

# 7 关的顺序，从左到右
STAGES = ["ai", "resume", "phone", "test", "pro", "hr", "final"]

# 每一关的中文名，给前端展示用
STAGE_LABELS = {
    "ai": "AI筛选",
    "resume": "简历筛选",
    "phone": "电话沟通",
    "test": "笔试",
    "pro": "专业面",
    "hr": "HR面",
    "final": "终面",
}

# 每一关的成绩记在 Application 表的哪两格：(结果列名, 时间列名)
#   ai   ：只有结果，没有时间列（表里就没设计）
#   其余 ：一个结果列 + 一个时间列
STAGE_FIELDS: dict[str, tuple[str | None, str | None]] = {
    "ai": ("ai_result", None),
    "resume": ("resume_result", "resume_submit_time"),
    "phone": ("phone_result", "phone_time"),
    "test": ("test_result", "test_time"),
    "pro": ("pro_result", "pro_time"),
    "hr": ("hr_result", "hr_time"),
    "final": ("final_result", "final_time"),
}

RESULTS = {"pass", "fail"}  # 每一关只有两种成绩：通过 / 淘汰
STATUSES = {"pending", "pass", "fail"}  # 整体只有三种状态：进行中 / 已录用 / 已淘汰


def next_stage(stage: str) -> str | None:
    """下一关是哪一关？最后一关（final）之后没有了，返回 None。"""
    idx = STAGES.index(stage)
    return STAGES[idx + 1] if idx + 1 < len(STAGES) else None


def write_stage(app: Application, stage: str, result: str, now: datetime) -> None:
    """把某一关的成绩和时间填进对应的格子。没有时间列的（ai）就只填结果。

    setattr(app, "phone_result", "pass") 等价于 app.phone_result = "pass"，
    只是列名是从字典里查出来的变量，所以要用 setattr。
    """
    result_field, time_field = STAGE_FIELDS[stage]
    if result_field:
        setattr(app, result_field, result)
    if time_field:
        setattr(app, time_field, now)


def clear_stage(app: Application, stage: str) -> None:
    """把某一关的成绩和时间擦掉（撤回时用）。ai 这关顺便把 AI 理由也擦掉。"""
    result_field, time_field = STAGE_FIELDS[stage]
    if result_field:
        setattr(app, result_field, None)
    if time_field:
        setattr(app, time_field, None)
    if stage == "ai":
        app.ai_comment = None


def apply_result(app: Application, stage: str, result: str, now: datetime) -> None:
    """给当前这一关打分，并决定接下来怎么走。「手动推进」和「AI 录入」都调用它。

    - 打了 fail ：整体状态变成 fail（已淘汰），停在这一关不动
    - 打了 pass 且这是最后一关（final）：整体状态变成 pass（已录用！）
    - 打了 pass 且后面还有关：走到下一关，整体状态保持 pending
    """
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

    举例：走到 phone 关被打了 fail → 撤回 → 擦掉 phone 的成绩，还在 phone 关，状态回到进行中。
         走到 test 关还没打分（上一步是 phone 打了 pass）→ 撤回 → 擦掉 phone 的成绩，回到 phone 关。
    """
    current = app.current_stage
    cur_idx = STAGES.index(current)  # 当前是第几关（从 0 数）
    if to_stage is None:
        # 没指定退到哪，就撤销「上一步」
        if app.overall_status != "pending":
            # 已经结束（淘汰/录用）：上一步就是在当前关打的分，擦掉它、原地不动
            clear_stage(app, current)
            target = current
        else:
            # 还在进行中：当前关还没打分，上一步是「上一关打了 pass」
            if cur_idx == 0:
                raise ValueError("第一阶段（AI筛选）不可再撤回")  # 已经在第一关且没打分，没有上一步可撤
            target = STAGES[cur_idx - 1]
            clear_stage(app, target)
    else:
        # 指定退到某一关
        if to_stage not in STAGES:
            raise ValueError("toStage 不是合法阶段值")
        target_idx = STAGES.index(to_stage)
        # 不能「退」到比现在还靠后的关；进行中时也不能退到当前关自己（那等于没退）
        if target_idx > cur_idx or (target_idx == cur_idx and app.overall_status == "pending"):
            raise ValueError("toStage 必须早于当前阶段")
        # 从目标关到当前关，全部擦干净，重头再来
        for s in STAGES[target_idx : cur_idx + 1]:
            clear_stage(app, s)
        target = to_stage
    app.current_stage = target
    app.overall_status = "pending"  # 不管之前是什么状态，撤回后一律回到进行中
    app.update_time = now


def stage_timeline(app: Application) -> list[dict]:
    """把 7 关的情况整理成一个列表，给详情页画「时间线」用。每一项：关名、中文名、成绩、时间、是否当前关。"""
    items = []
    for s in STAGES:
        result_field, time_field = STAGE_FIELDS[s]
        items.append(
            {
                "stage": s,
                "label": STAGE_LABELS[s],
                "result": getattr(app, result_field) if result_field else None,  # getattr 是「按名字取属性」
                "time": getattr(app, time_field) if time_field else None,
                "is_current": s == app.current_stage,
            }
        )
    return items
