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

格子里的数字是「在指定时间范围内**通过了这一关** 或 **正停在这一关**的人数」：
  · 通过了这一关（含已进入下一关的）→ 算；用该关自己的时间戳判断是否落在范围内
  · 正停在这一关、还没打分 → 算；用 update_time（进入这一关的时间）判断
  · 在这一关被淘汰 → 不算
这样既包含「已经过了这关的人」，也包含「正在进行到这关的人」，不会漏人。

面试那一行只判**专业面**：过了专业面就计入（含后来过了 HR 面、终面的人）。
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

# 表格的行定义：key（程序用）、label（显示用）、判定用哪个阶段
# 「面试人数」只判专业面这一关：过了专业面就计入（含后来过了 HR 面/终面的人）
ROW_DEFS = [
    ("resume", "简历筛选数", "resume"),
    ("phone", "电话沟通人数", "phone"),
    ("test", "笔试人数", "test"),
    ("interview", "面试人数", "pro"),
]

# 各阶段的时间戳字段（与 state_machine.STAGE_FIELDS 一致）
STAGE_TIME_FIELD = {
    "ai": None,  # AI 筛选没有时间字段
    "resume": "resume_submit_time",
    "contact": None,  # 联系候选人没有结果也没有时间
    "phone": "phone_time",
    "test": "test_time",
    "pro": "pro_time",
    "hr": "hr_time",
    "final": "final_time",
}

STAGE_ORDER = ["ai", "resume", "contact", "phone", "test", "pro", "hr", "final"]


RESULT_FIELD = {
    "ai": "ai_result",
    "resume": "resume_result",
    "contact": None,
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


def stage_hit(app: Application, stage: str, start: datetime | None, end: datetime | None) -> tuple[bool, bool]:
    """判断某个人算不算在「这一关」里。

    返回 (算不算, 是否已通过这一关)：
      · 已通过这一关（该关 result = pass）→ 算，且 passed=True；用该关时间戳判范围
      · 正停在这一关还没打分（current_stage=该关、该关无结果、仍进行中）→ 算，passed=False；用 update_time 判范围
      · 在这一关被淘汰 / 还没走到这一关 → 不算
    没有结果字段的阶段（contact）只能靠「正停在这一关」判断。
    """
    result_field = RESULT_FIELD.get(stage)
    time_field = STAGE_TIME_FIELD.get(stage)
    result = getattr(app, result_field, None) if result_field else None

    # 情况一：已经通过了这一关（包括后来走到了更后面的阶段）
    if result == "pass":
        if time_field:
            t = getattr(app, time_field, None)
            if t is None:
                # 时间戳缺失（理论上不会有）：只在不限时间时计入
                return (start is None and end is None), True
            return _in_range(t, start, end), True
        return True, True

    # 情况二：正停在这一关、还没打分（进行中）
    if app.current_stage == stage and result is None and app.overall_status == "pending":
        return _in_range(app.update_time, start, end), False

    # 其余：在这一关被淘汰，或根本没走到这一关
    return False, False


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
    positions = db.scalars(select(Position).order_by(Position.id)).all()
    cols = position_columns(positions)
    pos_index = {c.id: i for i, c in enumerate(cols)}  # 岗位编号 → 第几列

    apps = db.scalars(select(Application)).all()

    counts = {row_key: [0] * len(cols) for row_key, _, _ in ROW_DEFS}

    for app in apps:
        col = pos_index.get(app.pos_id)
        if col is None:
            continue  # 岗位可能已被删（外键限制下一般不会），跳过更安全
        for row_key, _label, stage in ROW_DEFS:
            hit, _passed = stage_hit(app, stage, start, end)
            if hit:
                counts[row_key][col] += 1

    rows = []
    for row_key, label, _stage in ROW_DEFS:
        cells = counts[row_key]
        rows.append({"key": row_key, "label": label, "cells": cells, "total": sum(cells)})

    col_totals = [sum(counts[k][i] for k, _, _ in ROW_DEFS) for i in range(len(cols))]
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
    people 每项：{app_id, candidate_id, name, stage_text, passed, is_custom}
    passed=True 表示这个人已经通过了这一关（否则是正停在这一关）。
    """
    row_def = next((r for r in ROW_DEFS if r[0] == row_key), None)
    if row_def is None:
        raise ValueError("row 不是合法的行（可选：resume / phone / test / interview）")
    _, row_label, stage = row_def

    notes = notes or {}
    position = db.get(Position, pos_id)
    if position is None:
        raise ValueError("岗位不存在")

    pos_cols = position_columns([position])
    label = pos_cols[0].label

    people = []
    apps = db.scalars(select(Application).where(Application.pos_id == pos_id)).all()
    for app in apps:
        hit, passed = stage_hit(app, stage, start, end)
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
                "passed": passed,
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
    "contact": "待联系候选人",
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
    positions = db.scalars(select(Position).order_by(Position.id)).all()
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
