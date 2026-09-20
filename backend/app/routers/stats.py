"""
【统计接口】
  GET /api/stats/overview

一次算出一大堆数字，给两个地方用：
  · 页面顶部的状态栏：在招岗位数、进行中投递数、待 AI 筛选数、本周进行数、上周完成数
  · 汇总导出页的统计卡：进行中/已录用/已淘汰、各关卡人数分布、本月录用数、按岗位分组

全部是「数数」——用数据库的 count 和 group by（分组计数）来做，不把数据都读出来再数（那样慢）。
"""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import Application, Position, User
from app.services import positions as positions_svc
from app.services import settings as settings_svc
from app.services import summary
from app.services.state_machine import STAGE_LABELS, STAGES

router = APIRouter(prefix="/api/stats", tags=["stats"], dependencies=[Depends(get_current_user)])


def _week_start(d: datetime) -> datetime:
    """算出某一天所在那周的「周一 0 点」。weekday() 周一是 0、周日是 6，往前退这么多天就是周一。"""
    monday = d - timedelta(days=d.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    """统计总览：一次拿到所有数字

**干什么用**：页面顶部状态栏和「汇总导出」页的统计卡都用它，一次请求全拿到。

**怎么填**：不用填。

**返回什么**：
```json
{
  "position_count": 3,          // 在招岗位数
  "application_total": 12,      // 投递总数
  "pending_count": 7,           // 进行中
  "pass_count": 2,              // 已录用
  "fail_count": 3,              // 已淘汰
  "ai_pending_count": 4,        // 卡在第一关等 AI 筛的（顶部「待 AI 筛选」）
  "week_in_progress": 5,        // 本周新建且还在进行中的
  "last_week_completed": 3,     // 上周结束的（录用 + 淘汰）
  "month_hired": 2,             // 本月录用
  "stage_counts": [             // 进行中的投递，每一关各有几个人（固定 8 项，顺序固定）
    {"stage": "ai", "label": "AI筛选", "count": 4},
    {"stage": "resume", "label": "简历筛选", "count": 2},
    "……"
  ],
  "by_position": [              // 每个岗位下各状态几条（没投递的岗位也在，全是 0）
    {"pos_id": 1, "position_name": "Java高级工程师", "total": 8, "pending": 5, "pass": 1, "fail": 2}
  ]
}
```

**时间口径**：「周」从周一 0 点算；「本月」从 1 号 0 点算；「完成 / 录用」看的是投递的最后更新时间。
"""
    # ---- 先算几个时间点 ----
    now = datetime.now()
    this_week = _week_start(now)  # 本周一 0 点
    last_week = this_week - timedelta(days=7)  # 上周一 0 点
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)  # 本月 1 号 0 点

    # ---- 岗位总数 ----
    hidden = positions_svc.hidden_ids(db)
    position_count = db.scalar(select(func.count()).select_from(Position).where(Position.is_hidden == 0)) or 0  # or 0：万一是 None 就当 0

    # 除岗位数以外的所有统计都只看「非隐藏岗位」的投递（暂不招岗位的投递不计入）
    vis = [] if not hidden else [Application.pos_id.notin_(hidden)]

    # ---- 按整体状态分组数数：pending 几条、pass 几条、fail 几条 ----
    status_rows = db.execute(
        select(Application.overall_status, func.count()).where(*vis).group_by(Application.overall_status)
    ).all()
    status_counts = {"pending": 0, "pass": 0, "fail": 0}  # 先全填 0，防止某个状态一条都没有时缺 key
    for s, n in status_rows:
        status_counts[s] = n

    # ---- 进行中的投递，按当前关卡分组数数 ----
    stage_rows = db.execute(
        select(Application.current_stage, func.count())
        .where(Application.overall_status == "pending", *vis)
        .group_by(Application.current_stage)
    ).all()
    stage_map = {s: n for s, n in stage_rows}
    # 按 8 关的固定顺序输出，没人的关卡也要有一项（数量 0），前端画图才整齐
    stage_counts = [{"stage": s, "label": STAGE_LABELS[s], "count": stage_map.get(s, 0)} for s in STAGES]

    ai_pending = stage_map.get("ai", 0)  # 卡在第一关等 AI 筛的有几个

    # ---- 三个跟时间有关的数 ----
    month_hired = db.scalar(  # 本月录用：状态 pass 且最后更新在本月
        select(func.count())
        .select_from(Application)
        .where(Application.overall_status == "pass", Application.update_time >= month_start, *vis)
    ) or 0
    week_in_progress = db.scalar(  # 本周进行：本周新建且还在进行中
        select(func.count())
        .select_from(Application)
        .where(Application.overall_status == "pending", Application.create_time >= this_week, *vis)
    ) or 0
    last_week_completed = db.scalar(  # 上周完成：上周一到本周一之间结束的（录用或淘汰）
        select(func.count())
        .select_from(Application)
        .where(
            Application.overall_status.in_(["pass", "fail"]),
            Application.update_time >= last_week,
            Application.update_time < this_week,
            *vis,
        )
    ) or 0

    # ---- 按岗位分组：每个岗位下 pending / pass / fail 各几条 ----
    # isouter=True（左外连接）：一条投递都没有的岗位也要出现在结果里，不能漏
    # 额外条件 Position.is_hidden == 0：暂不招的岗位不出现
    by_pos_rows = db.execute(
        select(Position.id, Position.position_name, Application.overall_status, func.count())
        .join(
            Application,
            (Application.pos_id == Position.id) & (Application.pos_id.notin_(hidden) if hidden else True),
            isouter=True,
        )
        .where(Position.is_hidden == 0)
        .group_by(Position.id, Position.position_name, Application.overall_status)
        .order_by(Position.id)
    ).all()
    by_position: dict[int, dict] = {}
    for pid, pname, status, n in by_pos_rows:
        # setdefault：这个岗位第一次出现就先建一个全 0 的条目，之后直接拿已有的
        entry = by_position.setdefault(
            pid, {"pos_id": pid, "position_name": pname, "total": 0, "pending": 0, "pass": 0, "fail": 0}
        )
        if status is not None:  # 没有投递的岗位 status 是 None，跳过，保留全 0
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


@router.get("/matrix")
def matrix(
    range: str = Query(default="week", description="时间范围：week=本周（默认）/ last_week=上周 / month=本月 / all=全部 / custom=自定义（需配 start_date、end_date）"),
    start_date: date | None = Query(default=None, description="自定义范围的开始日期（仅 range=custom 时用），格式 2026-09-01"),
    end_date: date | None = Query(default=None, description="自定义范围的结束日期（仅 range=custom 时用），格式 2026-09-30"),
    db: Session = Depends(get_db),
):
    """阶段 × 岗位 交叉汇总表（周报那种表）

**干什么用**：一眼看清「本周各岗位分别走到哪一步了」。前端「汇总导出」页的那张交叉表就是它。

**表格长什么样**：
- 每一行是一个阶段：简历筛选数 / 电话沟通人数 / 笔试人数 / 面试人数
- **面试人数**：专业面 / HR面 / 终面 **三关中任一关**在所选时间范围内就计入（不要求是专业面），
  且**在这三关被淘汰的也算**（面过就计入）；同一个人三关都命中只算一次
- 每一列是一个在招岗位（岗位名长，自动缩写成短标签；若两个岗位缩写后重名，自动补负责人区分）
- 最后一列是「总计」，最后一行也是「总计」

**格子里的数字**：在所选时间范围内「**通过了这一关**」或「**正停在这一关**」的人数；
面试行额外包含「在这一关被淘汰」的人。

**怎么填**：`range` 可选
- `week` 本周（默认，从本周一 0 点起）
- `last_week` 上周（上周一到本周一之间）
- `month` 本月（本月 1 号起）
- `all` 全部（不按时间筛，即历史累计）
- `custom` 自定义，配合 `start_date` / `end_date`（含当天）

**返回什么**：
```json
{
  "range": "week",
  "range_label": "本周",
  "start": "2026-09-14T00:00:00",
  "end": "2026-09-17T23:59:59.999999",
  "positions": [{"id": 10, "name": "web前端开发工程师（中级）", "label": "web前端(中级)", "owner": "胡倞"}],
  "rows": [{"key": "resume", "label": "简历筛选数", "cells": [3, 1, 0], "total": 4}],
  "col_totals": [4, 2, 0],
  "row_totals": [4],
  "grand_total": 6
}
```
"""
    if range == "custom" and start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")
    start, end, label = summary.resolve_range(range, start_date, end_date)
    data = summary.build_matrix(db, start, end)
    return {
        "range": range if range in summary.RANGE_LABELS else "all",
        "range_label": label,
        "start": start,
        "end": end,
        **data,
    }


@router.get("/matrix/cell")
def matrix_cell(
    row: str = Query(description="哪一行：resume=简历筛选数 / phone=电话沟通人数 / test=笔试人数 / interview=面试人数"),
    pos_id: int = Query(description="哪个岗位（岗位编号）"),
    range: str = Query(default="week", description="时间范围，同 /stats/matrix"),
    start_date: date | None = Query(default=None, description="自定义范围的开始日期（仅 range=custom 用）"),
    end_date: date | None = Query(default=None, description="自定义范围的结束日期（仅 range=custom 用）"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """看交叉表某个格子里具体是哪些人（点数字时调它）

**干什么用**：前端点「阶段 × 岗位汇总」里某个数字，弹出这些人是谁。

**怎么填**：`row`（哪一行）+ `pos_id`（哪个岗位）+ `range`（时间范围，同交叉表）。

**返回什么**：
```json
{
  "row": "test", "row_label": "笔试人数",
  "position_id": 9, "position_label": "Go后端(中级)",
  "count": 3,
  "people": [
    {"app_id": 78, "candidate_id": 74, "name": "乔从旺", "stage_text": "待专业面",
     "is_custom": false, "passed": true, "overall_status": "pending", "current_stage": "pro"}
  ]
}
```
`passed=true` 表示这个人**已经通过**了这一关（现在在更后面的环节）；`false` 表示他**正停在这一关**等着。
名单口径与格子数字完全一致。

**可能出错**：400 row 不合法 / 岗位不存在；404 不需要（用 400 统一提示）。
"""
    if range == "custom" and start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")
    start, end, _label = summary.resolve_range(range, start_date, end_date)
    notes = settings_svc.get_stage_notes(db, user.id)
    try:
        return summary.matrix_cell_people(db, row, pos_id, start, end, notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/in-progress")
def in_progress(
    range: str = Query(default="week", description="时间范围：week 本周（默认）/ last_week 上周 / month 本月 / all 全部 / custom 自定义"),
    start_date: date | None = Query(default=None, description="自定义范围的开始日期（仅 range=custom 时用）"),
    end_date: date | None = Query(default=None, description="自定义范围的结束日期（仅 range=custom 时用）"),
    stages: list[str] | None = Query(
        default=None,
        description="只显示当前处于这些阶段的人，可传多个（如 stages=test&stages=pro）；不传 = 全部阶段。可选值同 stage 过滤：ai/resume/contact/phone/test/pro/hr/final",
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """进行中的候选人所处阶段清单（周报第二张表）

**干什么用**：列出「还在推进中」的候选人，按岗位分组，看每个人现在卡在哪一步。前端「汇总导出」页下半部分那张表就是它。

**筛选口径**：
- 只看**进行中**（还没淘汰也没录用）的投递；
- 且在所选时间范围内**有动作**（创建时间或最后更新时间落在范围内）——「以前投的、这周才面到下一关」的人也会出现在本周里。

**阶段文案**：按当前阶段自动生成（待AI筛选/待简历筛选/待联系候选人/待电话沟通/待笔试/待专业面/待HR面/待终面）；已淘汰→「已淘汰」、已录用→「已录用」。你可以对某一条手动改写成自己的说法（如「待offer回传」「待入职 1.11」），用 PUT /api/settings/stage-note 保存；改过的行 `is_custom` 为 true。

**返回什么**：
```json
{
  "range": "week", "range_label": "本周",
  "start": "2026-09-14T00:00:00", "end": "2026-09-17T23:59:59",
  "groups": [
    {"position_id": 1, "position_label": "C++客户端(初级)—朱力伟", "position_name": "C++客户端开发工程师（初级）", "owner": "朱力伟",
     "candidates": [{"app_id": 81, "candidate_id": 77, "name": "高辉圳", "stage_key": "final", "stage_text": "待终面", "auto_text": "待终面", "is_custom": false, "update_time": "..."}]}
  ],
  "total": 12
}
```
"""
    if range == "custom" and start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")
    if stages:
        bad = [x for x in stages if x not in STAGES]
        if bad:
            raise HTTPException(status_code=400, detail=f"stages 里有不合法阶段值：{', '.join(bad)}")
    start, end, label = summary.resolve_range(range, start_date, end_date)
    notes = settings_svc.get_stage_notes(db, user.id)
    data = summary.build_in_progress(db, start, end, notes, stages)
    return {
        "range": range if range in summary.RANGE_LABELS else "all",
        "range_label": label,
        "start": start,
        "end": end,
        **data,
    }
