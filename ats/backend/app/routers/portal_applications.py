"""
【候选人端投递接口】
  POST /api/portal/applications      投递（用当前简历 + AI 首筛）
  GET  /api/portal/applications      我的投递列表
  GET  /api/portal/applications/{id} 我的投递详情

投递前置条件：
  1. 岗位在招（is_hidden=0）
  2. 有当前版本简历
  3. 如果 HR 配了「个人资料表」，必须已提交（草稿不行）
  4. 同一岗位只能投一次
  5. 24 小时内投递次数不超过配置上限

岗位申请表不阻塞投递：投递成功后再补填，HR 能看到「待补充」状态。
"""
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.core.database import get_db
from app.core.deps import get_current_candidate
from app.models import Application, Position, User
from app.schemas.portal import PortalApplyIn
from app.services import (
    file_service,
    form_service,
    portal_apply,
    portal_views,
    ratelimit,
)
from app.services import state_machine as sm
from app.services.log_service import log_action

router = APIRouter(prefix="/api/portal/applications", tags=["portal-applications"])

AppId = Annotated[int, Path(description="投递编号")]


def _candidate_id(user: User) -> int:
    if user.candidate_id is None:
        raise HTTPException(status_code=401, detail="账号未关联候选人档案，请联系 HR")
    return user.candidate_id


def _own_or_404(db: Session, app_id: int, candidate_id: int) -> Application:
    a = db.get(Application, app_id)
    if a is None or a.can_id != candidate_id:
        # 不暴露「别人的投递存在」这件事
        raise HTTPException(status_code=404, detail="投递记录不存在")
    return a


@router.post("", status_code=status.HTTP_201_CREATED)
async def apply(
    body: PortalApplyIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_candidate),
):
    """投递一个岗位（自动触发 AI 首筛）

**怎么填**：`{"pos_id": 1}`。简历用 HR 上传的「当前版本简历」，候选人不需要自己上传。

**会发生什么**：
- AI 可用：根据岗位要求判断 pass/fail，通过则进入简历筛选，不通过则标记淘汰
- AI 不可用 / 简历无法解析：仍建档，转「待人工筛选」，不丢简历
- 成功后 `source=portal`，HR 能在投递列表看到来源

**返回什么**：
```json
{
  "application": {"id": 12, "position": {...}, "current_stage": "resume", "timeline": [...]},
  "screening": "ai_pass",
  "message": "简历已通过初筛，进入简历筛选阶段"
}
```

**可能出错**：
- 400：HR 还没上传简历 / 个人资料表未提交
- 404：岗位不存在或已停招
- 409：已经投过这个岗位
- 429：24 小时内投递次数过多
"""
    cid = _candidate_id(user)
    position = db.get(Position, body.pos_id)
    if position is None or position.is_hidden:
        raise HTTPException(status_code=404, detail="岗位不存在或已停止招聘")

    if db.scalar(select(Application.id).where(Application.can_id == cid, Application.pos_id == position.id)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="你已经投递过这个岗位")

    resume = file_service.current_resume(db, cid)
    if resume is None:
        raise HTTPException(status_code=400, detail="HR 尚未上传你的简历，请联系 HR 上传后再投递")

    profile_t = form_service.get_active_template(db, "profile")
    if profile_t is not None:
        sub = form_service.get_submission(db, profile_t.id, cid, None)
        if sub is None or sub.status != "submitted":
            raise HTTPException(status_code=400, detail="请先填写并提交个人资料表")

    window = 24 * 3600
    key = f"portal_apply:{cid}"
    if ratelimit.too_many(key, app_settings.portal_apply_daily_limit, window):
        wait = ratelimit.remaining_seconds(key, window)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"24 小时内投递次数过多，请 {max(1, wait // 3600)} 小时后再试",
        )

    now = datetime.now()
    app = Application(
        can_id=cid,
        pos_id=position.id,
        current_stage="ai",
        overall_status="pending",
        source="portal",
        create_time=now,
        update_time=now,
    )
    db.add(app)
    try:
        db.flush()  # 先拿到投递编号
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="你已经投递过这个岗位")

    outcome = await portal_apply.screen_resume(db, position, resume.content)
    if outcome["result"] in sm.RESULTS:
        app.ai_comment = outcome["comment"]
        sm.apply_result(app, "ai", outcome["result"], now)
    else:
        # 降级：停在 AI 筛选关，等 HR 人工处理；理由只给 HR 看
        app.ai_comment = "候选人自主投递，AI 初筛未完成（未配置 / 简历无法解析 / 调用失败），请人工筛选"[:500]
        app.update_time = now

    log_action(
        db,
        user,
        "create",
        target_type="application",
        target_id=app.id,
        detail={"pos_id": position.id, "screening": outcome["screening"]},
    )
    db.commit()
    db.refresh(app)
    ratelimit.record_event(key, window)

    return {
        "application": portal_views.application_detail(db, app),
        "screening": outcome["screening"],
        "message": portal_apply.MESSAGES[outcome["screening"]],
    }


@router.get("")
def list_my_applications(db: Session = Depends(get_db), user: User = Depends(get_current_candidate)):
    """我的投递列表

**返回什么**：岗位、当前阶段、整体状态、AI 首筛结果、时间。
岗位后来被设为「暂不招」时仍会显示，并带 `position_closed=true`。
"""
    cid = _candidate_id(user)
    rows = db.scalars(
        select(Application).where(Application.can_id == cid).order_by(Application.update_time.desc(), Application.id.desc())
    ).all()
    return [portal_views.application_summary(db, a) for a in rows]


@router.get("/{app_id}")
def get_my_application(
    app_id: AppId,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_candidate),
):
    """我的投递详情（7 关时间线 + 简历 + 表单状态）

**不返回**：各关原因、面试评价、AI 理由等内部信息。
"""
    cid = _candidate_id(user)
    a = _own_or_404(db, app_id, cid)
    return portal_views.application_detail(db, a)
