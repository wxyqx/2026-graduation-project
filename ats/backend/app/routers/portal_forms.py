"""
【候选人端表单接口】
  GET /api/portal/forms?application_id=      我能填哪些表（个人资料表 + 该投递的岗位表）
  GET /api/portal/forms/{template_id}        模板字段 + 我的答案
  PUT /api/portal/forms/{template_id}        保存草稿 / 提交

规则：
  · 个人资料表全局一份，填写时不要传 application_id
  · 岗位申请表必须传 application_id，而且这次投递必须属于自己、岗位要对得上
  · 只能填启用中的模板；停用的模板候选人看不到
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_candidate
from app.models import User
from app.schemas.form import FormAnswersIn
from app.services import form_service

router = APIRouter(prefix="/api/portal/forms", tags=["portal-forms"])

TemplateId = Annotated[int, Path(description="表单模板编号")]


def _candidate_id(user: User) -> int:
    if user.candidate_id is None:
        raise HTTPException(status_code=401, detail="账号未关联候选人档案，请联系 HR")
    return user.candidate_id


@router.get("")
def list_my_forms(
    application_id: int | None = Query(default=None, description="看某次投递的岗位申请表时传"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_candidate),
):
    """我能填的表

**返回什么**：数组。个人资料表总有（如果 HR 配了）；传了 `application_id` 时再加上该岗位的申请表。
每条带 `my_status`：none=还没填 / draft=草稿 / submitted=已提交。
"""
    return form_service.available_templates(db, _candidate_id(user), application_id)


@router.get("/{template_id}")
def get_my_form(
    template_id: TemplateId,
    application_id: int | None = Query(default=None, description="岗位申请表必须传；个人资料表不传"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_candidate),
):
    """模板字段 + 我的答案（没填过时 submission 为 null）"""
    cid = _candidate_id(user)
    try:
        t = form_service.get_template_or_404(db, template_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    try:
        form_service.ensure_template_applicable(db, t, cid, application_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except form_service.FormError as e:
        raise HTTPException(status_code=400, detail=str(e))

    sub = form_service.get_submission(db, t.id, cid, application_id)
    data = form_service.template_out(db, t, detail=True)
    # 候选人只看到启用中的字段（停用/删除的字段不展示）
    data["fields"] = [f for f in data["fields"] if f["is_active"]]
    return {
        "template": data,
        "submission": form_service.submission_out(db, sub, active_only=True) if sub else None,
    }


@router.put("/{template_id}")
def save_my_form(
    template_id: TemplateId,
    body: FormAnswersIn,
    application_id: int | None = Query(default=None, description="岗位申请表必须传；个人资料表不传"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_candidate),
):
    """保存草稿或提交答卷

**怎么填**：
- `answers`：键是字段的 `field_key`，值是答案；多选传数组
- `submit`：`false` 存草稿，`true` 提交

**校验**：必填、数字、日期、邮箱、手机号、选项、长度都会在服务端检查，不通过返回 400 和具体字段名。

**返回什么**：保存后的答卷（含状态、答案、带中文标签的 items）。
"""
    cid = _candidate_id(user)
    try:
        t = form_service.get_template_or_404(db, template_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    try:
        form_service.ensure_template_applicable(db, t, cid, application_id)
        sub = form_service.save_submission(
            db,
            t=t,
            candidate_id=cid,
            application_id=application_id,
            answers=body.answers,
            submit=body.submit,
        )
        db.commit()
        db.refresh(sub)
        return form_service.submission_out(db, sub, active_only=True)
    except LookupError as e:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    except form_service.FormError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
