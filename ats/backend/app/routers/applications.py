"""
【投递接口】——系统的主战场
  GET  /api/applications?stage=&status=&pos_id=   列表（三种筛选都可选）
  POST /api/applications                          手动新建一条投递
  GET  /api/applications/{id}                     详情（含 7 关时间线）
  POST /api/applications/{id}/advance             推进：给当前关打分（pass / fail）
  POST /api/applications/{id}/revert              撤回上一步
  PUT  /api/applications/{id}/stage-note          给某一关补写原因 / 面试评价（不改流程）

推进、撤回的具体规则不在这里，在 services/state_machine.py。这里只做检查和调用。
"""
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import Application, Candidate, Position
from app.schemas.application import AdvanceIn, ApplicationCreate, RevertIn, StageNoteIn
from app.services import positions as positions_svc
from app.services import state_machine as sm
from app.services.views import application_detail, application_summary

router = APIRouter(prefix="/api/applications", tags=["applications"], dependencies=[Depends(get_current_user)])

AppId = Annotated[int, Path(description="投递记录编号（列表里每一行的 id）")]


def _get_or_404(db: Session, app_id: int) -> Application:
    a = db.get(Application, app_id)
    if a is None:
        raise HTTPException(status_code=404, detail="投递记录不存在")
    # 岗位已设为暂不招时，这条投递也当作不存在
    if positions_svc.is_hidden(db, a.pos_id):
        raise HTTPException(status_code=404, detail="投递记录不存在")
    return a


@router.get("")
def list_applications(
    stage: str | None = Query(
        default=None,
        description="只看当前在这一关的：ai=AI筛选 / resume=简历筛选 / phone=电话沟通 / test=笔试 / pro=专业面 / hr=HR面 / final=终面",
    ),
    status_: str | None = Query(
        default=None, alias="status", description="只看这个状态的：pending=进行中 / pass=已录用 / fail=已淘汰"
    ),  # 网址里叫 status，但 status 这个名字已经被上面 import 的模块占了，所以 Python 里叫 status_
    pos_id: int | None = Query(default=None, description="只看这个岗位的（岗位编号）"),
    can_id: int | None = Query(default=None, description="只看这个候选人的（候选人编号）。用于候选人详情里列他投了哪些岗位"),
    db: Session = Depends(get_db),
):
    """投递列表（可按关卡 / 状态 / 岗位筛选）

**干什么用**：前端「投递列表」页的表格。三个筛选条件都可不填，填了就是「且」的关系（同时满足）。

**举例**：
- 什么都不填 → 全部投递
- `status=pending` → 所有还在进行中的
- `stage=ai&status=pending` → 卡在第一关等 AI 筛选的
- `pos_id=1` → 投了 1 号岗位的所有人

**返回什么**：数组，每条是精简信息（详情要另外调 GET /{id}）：
```json
[{
  "id": 7, "can_id": 3, "pos_id": 1,
  "candidate_name": "张三", "position_name": "Java高级工程师",
  "current_stage": "phone", "current_stage_label": "电话沟通",
  "overall_status": "pending",
  "ai_result": "pass", "ai_comment": "5年Java经验，符合要求",
  "create_time": "...", "update_time": "..."
}]
```

**可能出错**：
- 400：`stage` 或 `status` 传了不在可选值里的东西
"""
    # 先把乱传的值挡在门外（枚举值以数据字典为准）
    if stage is not None and stage not in sm.STAGES:
        raise HTTPException(status_code=400, detail="stage 不是合法阶段值")
    if status_ is not None and status_ not in sm.STATUSES:
        raise HTTPException(status_code=400, detail="status 不是合法状态值")
    # 像搭积木一样拼查询：先「查全部、倒序」，传了哪个条件就再加一块 where
    stmt = select(Application).order_by(Application.id.desc())
    if stage:
        stmt = stmt.where(Application.current_stage == stage)
    if status_:
        stmt = stmt.where(Application.overall_status == status_)
    if pos_id:
        stmt = stmt.where(Application.pos_id == pos_id)
    if can_id:
        stmt = stmt.where(Application.can_id == can_id)
    stmt = positions_svc.exclude_hidden_apps(stmt, db)  # 暂不招岗位的投递不显示
    return [application_summary(a) for a in db.scalars(stmt).all()]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_application(body: ApplicationCreate, db: Session = Depends(get_db)):
    """手动新建一条投递（某人投了某岗位）

**干什么用**：不走 AI 录入、手动把「张三投了 Java 岗」记进系统。新投递永远从第一关 `ai` 开始、状态 `pending`。

**怎么填**：`can_id` 候选人编号 + `pos_id` 岗位编号，两个都得先存在。

**返回什么**：完整详情（和 GET /{id} 一样，含 7 关时间线）。

**可能出错**：
- 404：候选人或岗位编号不存在
- 409：这个人已经投过这个岗位了（同一人同一岗只能一条）

**小知识**：手动建的投递第一关 `ai` 也可以人工打分——调 advance 传 `{"fromStage": "ai", "result": "pass"}` 就跳过 AI 直接进第二关。
"""
    # 先确认「人」和「岗位」都真实存在
    if db.get(Candidate, body.can_id) is None:
        raise HTTPException(status_code=404, detail="候选人不存在")
    pos = db.get(Position, body.pos_id)
    if pos is None:
        raise HTTPException(status_code=404, detail="岗位不存在")
    if pos.is_hidden:
        raise HTTPException(status_code=400, detail=f"「{pos.position_name}」已设为暂不招，不能建投递")
    # 再查重：同一个人投同一个岗位只能有一条
    dup = db.scalar(
        select(Application).where(Application.can_id == body.can_id, Application.pos_id == body.pos_id)
    )
    if dup:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该候选人已投递过此岗位")
    now = datetime.now()
    a = Application(
        can_id=body.can_id,
        pos_id=body.pos_id,
        current_stage="ai",  # 新投递永远从第一关开始
        overall_status="pending",
        create_time=now,
        update_time=now,
    )
    db.add(a)
    try:
        db.commit()
    except IntegrityError:
        # 双保险：万一两个请求同一瞬间都通过了上面的查重，数据库的唯一约束会拦住第二个，这里接住它
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该候选人已投递过此岗位")
    db.refresh(a)
    return application_detail(a)


@router.get("/{app_id}")
def get_application(app_id: AppId, db: Session = Depends(get_db)):
    """投递详情（候选人 + 岗位 + 7 关时间线）

**干什么用**：前端「投递详情」页。能看到这个人每一关的成绩和时间，以及 AI 给的理由。

**返回什么**（比列表多了 `candidate`、`position`、`stages` 三块）：
```json
{
  "id": 7, "current_stage": "phone", "overall_status": "pending",
  "ai_result": "pass", "ai_comment": "5年Java经验，符合要求",
  "candidate": {"id": 3, "name": "张三", "remark": "AI录入", "create_time": "..."},
  "position": {"id": 1, "position_name": "Java高级工程师", "owner": "王HR", "position_requirements": "..."},
  "stages": [
    {"stage": "ai",      "label": "AI筛选",   "result": "pass", "time": null,  "is_current": false},
    {"stage": "resume",  "label": "简历筛选", "result": "pass", "time": "...", "is_current": false},
    {"stage": "phone",   "label": "电话沟通", "result": null,   "time": null,  "is_current": true},
    "……后面 4 关 result 和 time 都是 null，还没走到"
  ]
}
```
`stages` 里 `is_current: true` 的那一关就是现在卡的位置。`ai` 这关表里没有时间字段，`time` 永远是 null，只记结果和 AI 理由。

**可能出错**：
- 404：没有这个编号
"""
    return application_detail(_get_or_404(db, app_id))


@router.post("/{app_id}/advance")
def advance(app_id: AppId, body: AdvanceIn, db: Session = Depends(get_db)):
    """推进一关：给当前关打分（通过 / 淘汰）

**干什么用**：前端行内的「通过」「淘汰」按钮点的就是它。

**怎么填**：
- `fromStage`：你以为现在在哪一关。**必须和详情里的 `current_stage` 一样**——防止手快点两次：第一次点完阶段已经变了，第二次 fromStage 对不上就被拒绝。
- `result`：`pass` 通过 / `fail` 淘汰

**打完分会怎样**：
- `pass` 且不是最后一关 → 记下这关成绩和时间，`current_stage` 变成下一关
- `pass` 且是 `final` → `overall_status` 变 `pass`（**已录用**）
- `fail` → 记下成绩，`overall_status` 变 `fail`（**已淘汰**），停在这一关

**返回什么**：打完分后的完整详情。

**可能出错**：
- 400：`fromStage` 不是 7 关之一，或 `result` 不是 pass/fail
- 409：`fromStage` 和当前阶段不一致（刷新一下再看）；或这条投递已经结束了（要先撤回）
- 404：没有这个投递

**试一试**：新建一条投递，然后依次传 `ai→resume→phone→test→pro→hr→final` 各 pass 一次，最后看 `overall_status` 变成 pass。
"""
    a = _get_or_404(db, app_id)
    # 四道检查，一道不过就拒绝
    if body.from_stage not in sm.STAGES:
        raise HTTPException(status_code=400, detail="fromStage 不是合法阶段值")
    if body.result not in sm.RESULTS:
        raise HTTPException(status_code=400, detail="result 只能是 pass 或 fail")
    if body.from_stage != a.current_stage:
        # 前端以为在 A 关，实际已经在 B 关了——多半是手快点了两次，或者两个窗口同时操作
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"fromStage 与当前阶段不一致（当前为 {a.current_stage}），请刷新后重试",
        )
    if a.overall_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该投递已结束（已录用/已淘汰），请先撤回再操作",
        )
    sm.apply_result(a, body.from_stage, body.result, datetime.now())  # 真正的规则在状态机里
    db.commit()
    db.refresh(a)
    return application_detail(a)


@router.post("/{app_id}/revert")
def revert(app_id: AppId, body: RevertIn, db: Session = Depends(get_db)):
    """撤回：反悔上一步，或退回到指定关卡

**干什么用**：打错分了、或者想重新面试某一关。前端行内的「撤回」按钮。

**两种用法**：

1. **不传 `toStage`（传 `{}`）= 撤销上一步**
   - 已淘汰 / 已录用的：清掉当前关的成绩，停在原关，状态回到进行中。例：phone 关打了 fail → 撤回 → phone 关重新等打分
   - 进行中的：退回上一关并清掉上一关的成绩。例：现在在 test 关（说明 phone 打了 pass）→ 撤回 → 回到 phone 关重打
   - 已经在第一关 `ai` 且没打分 → 没有可撤的，回 400

2. **传 `toStage`（如 `{"toStage": "resume"}`）= 退回到那一关重来**
   - 从 `toStage` 到当前关的所有成绩全部清空，`current_stage` 变成 `toStage`，状态回到进行中
   - `toStage` 不能比现在还靠后

**返回什么**：撤回后的完整详情。

**可能出错**：
- 400：第一关无法再撤 / `toStage` 不合法 / `toStage` 晚于当前关
- 404：没有这个投递
"""
    a = _get_or_404(db, app_id)
    try:
        sm.revert(a, body.to_stage, datetime.now())
    except ValueError as e:
        # 状态机用 ValueError 表示「这样退不合规矩」（比如第一关没法再退），这里翻译成 400 给前端
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    db.refresh(a)
    return application_detail(a)


@router.put("/{app_id}/stage-note")
def save_stage_note(app_id: AppId, body: StageNoteIn, db: Session = Depends(get_db)):
    """给某一关补写「结果原因」/「面试评价」

**干什么用**：在投递详情页，给某一关补一段文字记录——为什么通过 / 为什么淘汰，
面试关还可以把面试评价写进去。纯记录，**不改流程状态**（推进 / 淘汰仍然走 advance）。

**什么时候能写**：
- 出过结果的关：随时可改（通过、淘汰都能补写）
- **正在进行的当前关：还没打分也能先写**（面试完当下就把评价记下，之后再决定通过 / 淘汰）
- 还没走到的关：不能写（写了对不上号）

**怎么填**：
- `stage`：要写哪一关（`resume` 简历筛选 / `phone` 电话沟通 / `test` 笔试 / `pro` 专业面 / `hr` HR面 / `final` 终面）。
- `reason`：结果原因（进行中的关可先记评估要点），通过或淘汰都能写。
- `evaluation`：面试评价，只有电话沟通 / 专业面 / HR面 / 终面有；简历筛选与笔试传了会被拒。
- 两个都可留空，传空字符串 = 清空该项。

**返回什么**：保存后的完整详情（和 GET /{id} 一样）。

**可能出错**：
- 400：`stage` 不是 6 个合法值之一 / `stage` 传了 `ai`（AI 理由不可手改）/
  这一关还没走到（既没结果也不是当前关）/ 给简历筛选或笔试传了面试评价
- 404：没有这个投递

**注意**：撤回这一关时，这里写的原因与面试评价会被一并清空（当作没发生过）。
"""
    a = _get_or_404(db, app_id)
    if body.stage not in sm.STAGES:
        raise HTTPException(status_code=400, detail="stage 不是合法阶段值")
    if body.stage == "ai":
        raise HTTPException(status_code=400, detail="AI 筛选的理由由 AI 生成，不能手动填写")
    reason_field, evaluation_field = sm.STAGE_NOTE_FIELDS[body.stage]
    if not reason_field:
        raise HTTPException(status_code=400, detail="该阶段没有可填写的记录项")
    # 出过结果的关、或正在进行的当前关，都能写；还没走到的关写了对不上号，拒绝
    if not sm.stage_is_writable(a, body.stage):
        raise HTTPException(status_code=400, detail="该阶段尚未进行，不能填写")
    if body.evaluation and not evaluation_field:
        raise HTTPException(status_code=400, detail="该阶段没有面试评价项（仅面试环节可填）")
    sm.save_stage_note(a, body.stage, body.reason, body.evaluation)
    db.commit()
    db.refresh(a)
    return application_detail(a)
