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

格子里的数字是「在指定时间范围内**到达**过这一关的人数」：
  · 能查时间戳的阶段（简历筛选/电话沟通/笔试/专业面/HR面/终面）→ 看该关的时间戳是否落在范围内
  · 没有时间戳的阶段（AI筛选、联系候选人）→ 用「当前阶段」的位置推算
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

# 表格的行定义：key（程序用）、label（显示用）、涉及哪些阶段
# 「面试人数」把 专业面/HR面/终面 三关合并成一行，同一个人只算一次
ROW_DEFS = [
    ("resume", "简历筛选数", ("resume",)),
    ("phone", "电话沟通人数", ("phone",)),
    ("test", "笔试人数", ("test",)),
    ("interview", "面试人数", ("pro", "hr", "final")),
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


def _reached_by_time(app: Application, stage: str, start: datetime | None, end: datetime | None) -> bool:
    """这个人「在时间范围内到达过某一关」吗？

    有该关时间戳的：直接看时间戳是否落在范围内。
    """
    field = STAGE_TIME_FIELD.get(stage)
    if not field:
        return False
    t = getattr(app, field, None)
    if t is None:
        return False
    if start is not None and t < start:
        return False
    if end is not None and t > end:
        return False
    return True


def build_matrix(
    db: Session,
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict:
    """算出整张交叉表。

    start/end 为 None 时表示「全部时间」，不按时间筛。
    返回：{positions, rows, col_totals, grand_total, row_totals}
    """
    positions = db.scalars(select(Position).order_by(Position.id)).all()
    cols = position_columns(positions)
    pos_index = {c.id: i for i, c in enumerate(cols)}  # 岗位编号 → 第几列

    # 一次把投递都取出来（自用系统数据量小，在内存里算最直观）
    apps = db.scalars(select(Application)).all()

    pos_ids = list(pos_index.keys())
    # 行 × 列 的计数表
    counts = {row_key: [0] * len(cols) for row_key, _, _ in ROW_DEFS}

    for app in apps:
        col = pos_index.get(app.pos_id)
        if col is None:
            continue  # 岗位可能已被删（外键限制下一般不会），跳过更安全
        for row_key, _label, stages in ROW_DEFS:
            for st in stages:
                if _reached_by_time(app, st, start, end):
                    counts[row_key][col] += 1
                    break  # 面试行有三关，同一个人只算一次

    rows = []
    for row_key, label, _stages in ROW_DEFS:
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


def matrix_to_table(matrix: dict) -> tuple[list[str], list[list]]:
    """把交叉表转成「表头 + 数据行」，交给导出模块生成 Excel。"""
    headers = ["阶段"] + [p["label"] for p in matrix["positions"]] + ["总计"]
    rows = []
    for r in matrix["rows"]:
        rows.append([r["label"]] + list(r["cells"]) + [r["total"]])
    rows.append(["总计"] + list(matrix["col_totals"]) + [matrix["grand_total"]])
    return headers, rows
