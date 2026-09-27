"""
【这个文件是干什么的？】——「阶段 × 岗位」交叉汇总表

就是周报里那种表格：每一行是一个招聘阶段，每一列是一个岗位，格子里是人数，最后有总计。

    行：简历筛选数 / 电话沟通人数 / 笔试人数 / 面试人数
    列：各在招岗位 + 总计

两件主要的事：
  1. position_label()：把很长的岗位名缩成表格能放下的短标签
     「C++客户端开发工程师（初级）」 → 「C++客户端(初级)」
     如果缩完有两个岗位重名（库里有两条同名的 C++ 客户端岗位），后面自动补负责人区分：
     「C++客户端(初级)—朱力伟」 / 「C++客户端(初级)—丘春辉」
  2. build_matrix()：算出每个格子里的人数

格子里的数字，默认是「在指定时间范围内**通过了这一关** 或 **正停在这一关**的人数」：
  · 通过了这一关（含已进入下一关的）→ 算；用该关自己的时间戳判断是否落在范围内
  · 正停在这一关、还没打分 → 算；用 update_time（进入这一关的时间）判断
  · 在这一关被淘汰 → 不算
这样既包含「已经过了这关的人」，也包含「正在进行到这关的人」，不会漏人。

**面试那一行是特例**（见 ROW_DEFS 的 include_rejected 开关）：
  · 涉及「专业面 / HR面 / 终面」三关，**任一关命中时间范围就计入**（不要求是专业面）；
  · 在这三关里**被淘汰的也算**（面过就计入，所以这一行统计的是"进入面试环节的人数"）；
  · 同一个人三关都命中，也只计一次。
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, Position

# ======================================================================
# 一、岗位名缩写
# ======================================================================

# 缩写时要扔掉的冗余词（从长到短替换，避免误伤）
_NOISE_WORDS = ("开发工程师", "研发工程师", "工程师", "开发")


def _shorten(name: str) -> str:
    """把一个岗位名缩成短标签。"""
    s = (name or "").strip()
    # 全角括号 → 半角，视觉上更整齐
    s = s.replace("（", "(").replace("）", ")")
    for w in _NOISE_WORDS:
        s = s.replace(w, "")
    return s.strip() or (name or "").strip()


@dataclass
class PositionCol:
    """交叉表里的一列（一个岗位）。"""

    id: int
    name: str  # 数据库里的完整岗位名
    label: str  # 表头显示的短标签（可能带负责人后缀）
    owner: str | None


def position_columns(positions: list[Position]) -> list[PositionCol]:
    """把岗位列表整理成交叉表的列。

    缩写后如果出现重名（比如两个岗位都叫「C++客户端(初级)」），
    就给这些列补上负责人：`C++客户端(初级)—朱力伟`、`C++客户端(初级)—丘春辉`。
    """
    short_list = [_shorten(p.position_name or "") for p in positions]
    # 统计每个短名出现了几次
    counts: dict[str, int] = {}
    for s in short_list:
        counts[s] = counts.get(s, 0) + 1

    cols: list[PositionCol] = []
    for p, short in zip(positions, short_list):
        label = short
        if counts[short] > 1 and (p.owner or "").strip():
            # 重名了，补负责人区分
            label = f"{short}—{p.owner.strip()}"
        cols.append(PositionCol(id=p.id, name=p.position_name or "", label=label, owner=p.owner))
    return cols


# ======================================================================
# 二、时间范围
# ======================================================================

RANGE_LABELS = {
    "week": "本周",
    "last_week": "上周",
    "month": "本月",
    "all": "全部",
    "custom": "自定义",
}


def week_start(d: datetime) -> datetime:
    """算某天所在那周的周一 0 点。"""
    monday = d - timedelta(days=d.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def resolve_range(
    range_key: str,
    start_date: date | None = None,
    end_date: date | None = None,
    now: datetime | None = None,
) -> tuple[datetime | None, datetime | None, str]:
    """把「本周/上周/本月/全部/自定义」翻译成具体的起止时间。

    返回 (开始时间, 结束时间, 范围中文名)；「全部」时起止都是 None。
    结束时间是「包含当天」的，所以用当天 23:59:59.999999。
    """
    now = now or datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    if range_key == "week":
        return week_start(now), today_end, RANGE_LABELS["week"]
    if range_key == "last_week":
        this_monday = week_start(now)
        return this_monday - timedelta(days=7), this_monday - timedelta(microseconds=1), RANGE_LABELS["last_week"]
    if range_key == "month":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0), today_end, RANGE_LABELS["month"]
    if range_key == "custom":
        start = datetime.combine(start_date, time.min) if start_date else None
        end = datetime.combine(end_date, time.max) if end_date else today_end
        return start, end, RANGE_LABELS["custom"]
    # all（或不认识的键，按全部处理）
    return None, None, RANGE_LABELS["all"]


# ======================================================================
# 三、交叉表
# ======================================================================

@dataclass
class RowDef:
    """交叉表的一行。

    - key / label：程序用 / 显示用
    - stages：这一行判定涉及哪几关（一般是 1 关；面试行是 3 关）
    - include_rejected：在这一关**被淘汰**的人算不算进来
        · False（默认）：不算——「通过该关」或「正停在该关等待」才计入（简历/电话/笔试行的口径）
        · True：算——只要**在该关面过**就计入（面试行的口径，面过就计入）
    """

    key: str
    label: str
    stages: tuple[str, ...]
    include_rejected: bool = False


# 表格的行定义（口径见 RowDef 注释）
ROW_DEFS = [
    RowDef("resume", "简历筛选数", ("resume",)),
    RowDef("phone", "电话沟通人数", ("phone",)),
    RowDef("test", "笔试人数", ("test",)),
    # 面试行：专业面 / HR面 / 终面 任一关在范围内就计入；在这三关被淘汰的也算
    RowDef("interview", "面试人数", ("pro", "hr", "final"), include_rejected=True),
]

ROW_BY_KEY = {r.key: r for r in ROW_DEFS}

# 各阶段的时间戳字段（与 state_machine.STAGE_FIELDS 一致）
STAGE_TIME_FIELD = {
    "ai": None,  # AI 筛选没有时间字段
    "resume": "resume_submit_time",
    "phone": "phone_time",
    "test": "test_time",
    "pro": "pro_time",
    "hr": "hr_time",
    "final": "final_time",
}

STAGE_ORDER = ["ai", "resume", "phone", "test", "pro", "hr", "final"]


RESULT_FIELD = {
    "ai": "ai_result",
    "resume": "resume_result",
    "phone": "phone_result",
    "test": "test_result",
    "pro": "pro_result",
    "hr": "hr_result",
    "final": "final_result",
}


def _in_range(t: datetime | None, start: datetime | None, end: datetime | None) -> bool:
    """这个时间点落在范围内吗？（start/end 为 None 表示不限）"""
    if t is None:
        return False
    if start is not None and t < start:
        return False
    if end is not None and t > end:
        return False
    return True


# 单关判定的结果
VISIT_NONE = "none"  # 没走到这一关 / 时间不在范围内
VISIT_WAITING = "waiting"  # 正停在这一关、还没打分（且在范围内）
VISIT_PASSED = "passed"  # 已经通过了这一关（且时间在范围内）
VISIT_REJECTED = "rejected"  # 在这一关被打成淘汰（且时间在范围内）


def _stage_visit(app: Application, stage: str, start: datetime | None, end: datetime | None) -> str:
    """看这个人在某一关的「到访情况」，返回 VISIT_* 之一。

    · 已通过（result=pass）：看该关时间戳是否在范围内
    · 正停在这一关没打分（进行中）：看 update_time 是否在范围内
    · 在这一关被淘汰（result=fail）：看该关时间戳是否在范围内
    没有时间字段的阶段（ai）只能靠「正停在这一关」判断。
    """
    result_field = RESULT_FIELD.get(stage)
    time_field = STAGE_TIME_FIELD.get(stage)
    result = getattr(app, result_field, None) if result_field else None

    # 已经打过分的（通过 / 淘汰）：用该关自己的时间戳判范围
    if result in ("pass", "fail"):
        t = getattr(app, time_field, None) if time_field else None
        if time_field and t is None:
            # 时间戳缺失（理论上不会有）：只在不限时间时算在范围内
            in_range = start is None and end is None
        elif time_field:
            in_range = _in_range(t, start, end)
        else:
            in_range = True  # 没有时间字段的阶段（ai）
        if not in_range:
            return VISIT_NONE
        return VISIT_PASSED if result == "pass" else VISIT_REJECTED

    # 还没打分、正停在这一关等着（进行中）
    if app.current_stage == stage and result is None and app.overall_status == "pending":
        return VISIT_WAITING if _in_range(app.update_time, start, end) else VISIT_NONE

    # 其余：还没走到这一关
    return VISIT_NONE


def row_membership(app: Application, row: RowDef, start: datetime | None, end: datetime | None) -> tuple[bool, str]:
    """判断某个人算不算在交叉表的「这一行」里。

    返回 (算不算, 状态)：
      · 不算 → (False, "")
      · 算   → (True, "passed" / "waiting" / "rejected")
        状态优先级：**淘汰 > 通过 > 等待**。
        · 淘汰最优先：一个人在专业面通过、后来 HR面被淘汰，应该显示「已淘汰」——
          因为流程已终止，标成「已通过」会与投递列表的状态自相矛盾；
        · 其次是"通过过任一场就标已通过"（正等第一场才算等待）。
      · include_rejected=False 的行（简历/电话/笔试）：被淘汰的不算
      · include_rejected=True 的行（面试）：被淘汰的也算

    这是**唯一**的判定入口——交叉表计数（build_matrix）和点开看名单（matrix_cell_people）都用它，
    保证「格子里的数字」和「点开看到的名单」永远一致。
    """
    states = [_stage_visit(app, st, start, end) for st in row.stages]
    hits = [s for s in states if s != VISIT_NONE]
    if not hits:
        return False, ""

    # 状态优先级：淘汰 > 通过 > 等待（淘汰是终态，信息量最大，放最前）
    if VISIT_REJECTED in hits:
        if not row.include_rejected:
            return False, ""  # 该行不算被淘汰的人
        state = "rejected"
    elif VISIT_PASSED in hits:
        state = "passed"
    else:
        state = "waiting"
    return True, state


def build_matrix(
    db: Session,
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict:
    """算出整张交叉表。

    格子口径见 stage_hit()：范围内「通过了这一关」或「正停在这一关」的人数。
    start/end 为 None 表示「全部时间」，不按时间筛。
    返回：{positions, rows, col_totals, grand_total, row_totals}
    """
    # 暂不招的岗位不生成列
    positions = db.scalars(select(Position).where(Position.is_hidden == 0).order_by(Position.id)).all()
    cols = position_columns(positions)
    pos_index = {c.id: i for i, c in enumerate(cols)}  # 岗位编号 → 第几列

    apps = db.scalars(select(Application)).all()

    counts = {r.key: [0] * len(cols) for r in ROW_DEFS}

    for app in apps:
        col = pos_index.get(app.pos_id)
        if col is None:
            continue  # 岗位可能已被删（外键限制下一般不会），跳过更安全
        for row in ROW_DEFS:
            hit, _state = row_membership(app, row, start, end)
            if hit:
                counts[row.key][col] += 1  # 每行每人只加一次（三关都命中也不会重复计）

    rows = []
    for row in ROW_DEFS:
        cells = counts[row.key]
        rows.append({"key": row.key, "label": row.label, "cells": cells, "total": sum(cells)})

    col_totals = [sum(counts[r.key][i] for r in ROW_DEFS) for i in range(len(cols))]
    grand_total = sum(col_totals)

    return {
        "positions": [{"id": c.id, "name": c.name, "label": c.label, "owner": c.owner} for c in cols],
        "rows": rows,
        "col_totals": col_totals,
        "row_totals": [r["total"] for r in rows],
        "grand_total": grand_total,
    }


def matrix_cell_people(
    db: Session,
    row_key: str,
    pos_id: int,
    start: datetime | None = None,
    end: datetime | None = None,
    notes: dict[str, str] | None = None,
) -> dict:
    """列出某个格子里具体是哪些人（点数字时用）。

    返回 {row, row_label, position_id, position_label, count, people:[...]}
    people 每项：{app_id, candidate_id, name, stage_text, is_custom, state, passed}
    state 取值：passed=已通过该环节 / waiting=正停在该环节等待 / rejected=在该环节被淘汰
    （面试行的 rejected 表示"面过但没过"；passed 字段为旧兼容保留，等价于 state=='passed'）
    """
    row_def = ROW_BY_KEY.get(row_key)
    if row_def is None:
        raise ValueError("row 不是合法的行（可选：resume / phone / test / interview）")
    row_label = row_def.label

    notes = notes or {}
    position = db.get(Position, pos_id)
    if position is None or position.is_hidden:
        raise ValueError("岗位不存在（或已设为暂不招）")

    pos_cols = position_columns([position])
    label = pos_cols[0].label

    people = []
    apps = db.scalars(select(Application).where(Application.pos_id == pos_id)).all()
    for app in apps:
        hit, state = row_membership(app, row_def, start, end)
        if not hit:
            continue
        note = (notes.get(str(app.id)) or "").strip()
        people.append(
            {
                "app_id": app.id,
                "candidate_id": app.can_id,
                "name": app.candidate.name if app.candidate else "",
                "stage_text": note or auto_stage_text(app),
                "is_custom": bool(note),
                # state：passed=已通过该环节 / waiting=正等待 / rejected=该环节被淘汰
                "state": state,
                # passed 保留（旧字段）：只有 passed 状态才算 true，rejected/waiting 都是 false
                "passed": state == "passed",
                "overall_status": app.overall_status,
                "current_stage": app.current_stage,
            }
        )
    people.sort(key=lambda x: (x["name"] or "", x["app_id"]))
    return {
        "row": row_key,
        "row_label": row_label,
        "position_id": pos_id,
        "position_label": label,
        "count": len(people),
        "people": people,
    }


def matrix_to_table(matrix: dict) -> tuple[list[str], list[list]]:
    """把交叉表转成「表头 + 数据行」，交给导出模块生成 Excel。"""
    headers = ["阶段"] + [p["label"] for p in matrix["positions"]] + ["总计"]
    rows = []
    for r in matrix["rows"]:
        rows.append([r["label"]] + list(r["cells"]) + [r["total"]])
    rows.append(["总计"] + list(matrix["col_totals"]) + [matrix["grand_total"]])
    return headers, rows


# ======================================================================
# 四、本周进行中的候选人所处阶段（周报里的第二张表）
# ======================================================================

# 各阶段自动生成的文案：站在「候选人现在处于什么状态」的角度说
AUTO_STAGE_TEXT = {
    "ai": "待AI筛选",
    "resume": "待简历筛选",
    "phone": "待电话沟通",
    "test": "待笔试",
    "pro": "待专业面",
    "hr": "待HR面",
    "final": "待终面",
}


def auto_stage_text(app: Application) -> str:
    """按投递的当前状态自动生成一句「所处阶段」文案。

    进行中 → 「待X」（如 待笔试）
    已淘汰 → 「已淘汰」；已录用 → 「已录用」
    认不出的阶段 → 原样返回阶段代号，免得显示空白
    """
    if app.overall_status == "fail":
        return "已淘汰"
    if app.overall_status == "pass":
        return "已录用"
    stage = app.current_stage or ""
    return AUTO_STAGE_TEXT.get(stage, stage or "—")


def build_in_progress(
    db: Session,
    start: datetime | None = None,
    end: datetime | None = None,
    notes: dict[str, str] | None = None,
    stages: list[str] | None = None,
) -> dict:
    """算出「进行中的候选人所处阶段」清单，按岗位分组。

    只收两类人：
      · overall_status == 'pending'（还在推进的）
      · 且在时间范围内「有动作」——创建时间或最后更新时间落在范围内
        （只看创建时间会漏掉「以前投的、这周才面到下一关」的人，所以两个时间都要看）

    notes ：手动改写的阶段文案，形如 {"82": "待offer回传"}（键是投递编号的字符串）。
            命中就用你写的，并在返回里标 is_custom=True。
    stages：只保留当前阶段在这些阶段里的人（如 ["test","pro"]）；不传 = 全部阶段。
    """
    notes = notes or {}
    # 暂不招的岗位不出现
    positions = db.scalars(select(Position).where(Position.is_hidden == 0).order_by(Position.id)).all()
    cols = position_columns(positions)
    col_by_id = {c.id: c for c in cols}

    apps = db.scalars(select(Application)).all()

    # 按岗位编号归组
    grouped: dict[int, list[dict]] = {}
    for app in apps:
        if app.overall_status != "pending":
            continue  # 只看进行中的
        if not _moved_within(app, start, end):
            continue
        if stages and (app.current_stage not in stages):
            continue  # 用户只勾选了这几个阶段
        col = col_by_id.get(app.pos_id)
        if col is None:
            continue  # 岗位已不存在（理论上不会有），跳过
        note = (notes.get(str(app.id)) or "").strip()
        row = {
            "app_id": app.id,
            "candidate_id": app.can_id,
            "name": app.candidate.name if app.candidate else "",
            "stage_key": app.current_stage,
            "stage_text": note or auto_stage_text(app),
            "auto_text": auto_stage_text(app),  # 自动文案，供前端「恢复自动」用
            "is_custom": bool(note),
            "update_time": app.update_time,
        }
        grouped.setdefault(app.pos_id, []).append(row)

    groups = []
    for c in cols:
        rows = grouped.get(c.id)
        if not rows:
            continue  # 这个岗位本周没有人，不显示空组
        rows.sort(key=lambda r: (r["name"] or "", r["app_id"]))
        groups.append(
            {
                "position_id": c.id,
                "position_label": c.label,
                "position_name": c.name,
                "owner": c.owner,
                "candidates": rows,
            }
        )

    total = sum(len(g["candidates"]) for g in groups)
    return {"groups": groups, "total": total}


def _moved_within(app: Application, start: datetime | None, end: datetime | None) -> bool:
    """这个人在这段时间里「有动作」吗？（创建时间或更新时间任一落在范围内）"""
    if start is None and end is None:
        return True  # 全部范围，不筛时间
    for t in (app.create_time, app.update_time):
        if t is None:
            continue
        if start is not None and t < start:
            continue
        if end is not None and t > end:
            continue
        return True
    return False


def in_progress_to_table(data: dict) -> tuple[list[str], list[list]]:
    """把清单转成「表头 + 数据行」，供导出用（岗位 / 候选人 / 阶段）。"""
    headers = ["岗位", "候选人", "阶段"]
    rows = []
    for g in data["groups"]:
        for c in g["candidates"]:
            rows.append([g["position_label"], c["name"], c["stage_text"]])
    return headers, rows
