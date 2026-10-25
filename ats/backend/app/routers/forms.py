"""
【HR 端表单接口】
  GET    /api/form-templates                 模板列表
  POST   /api/form-templates                 新建模板（可带字段）
  GET    /api/form-templates/{id}            模板详情（含字段）
  PUT    /api/form-templates/{id}            改模板名/说明/启停
  PUT    /api/form-templates/{id}/fields     批量保存字段
  DELETE /api/form-templates/{id}            停用模板（软删除）；?purge=true 物理删除（仅限已停用且无答卷）
  GET    /api/candidates/{can_id}/forms      某候选人的全部答卷
  GET    /api/applications/{app_id}/forms    某次投递的岗位答卷

模板规则：
  · 个人资料表全局只能有一个启用中的；每个岗位同时只能有一个启用中的申请表
  · 改字段时版本 +1；未出现在新列表里的字段会软删除，历史答案保留
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_hr
from app.models import Application, Candidate, User
from app.schemas.form import FormFieldsIn, FormTemplateIn, FormTemplateUpdate
from app.services import form_service

router = APIRouter(prefix="/api", tags=["forms"])

TemplateId = Annotated[int, Path(description="模板编号")]
CanId = Annotated[int, Path(description="候选人编号")]
AppId = Annotated[int, Path(description="投递编号")]


def _template_or_404(db: Session, template_id: int):
    try:
        return form_service.get_template_or_404(db, template_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/form-templates")
def list_templates(
    scope: str | None = Query(default=None, description="profile=个人资料表 / position=岗位申请表"),
    position_id: int | None = Query(default=None, description="只看某个岗位的申请表"),
    include_inactive: bool = Query(default=True, description="是否包含已停用的模板"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_hr),
):
    """表单模板列表

**干什么用**：HR「表单模板」页。每个模板带字段数和启停状态。
"""
    try:
        return form_service.list_templates(db, scope=scope, position_id=position_id, include_inactive=include_inactive)
    except form_service.FormError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/form-templates", status_code=status.HTTP_201_CREATED)
def create_template(body: FormTemplateIn, db: Session = Depends(get_db), user: User = Depends(get_current_hr)):
    """新建表单模板（可同时带字段）

**怎么填**：
- `scope=profile`：个人资料表，`position_id` 必须为空
- `scope=position`：岗位申请表，`position_id` 必填
- `fields`：字段列表；`field_type` 支持 text/textarea/number/date/select/radio/checkbox/email/phone

**可能出错**：
- 400：字段键重复 / 选项缺失 / 该范围已有启用中的模板
"""
    try:
        t = form_service.create_template(db, body, user.id)
        db.commit()
        db.refresh(t)
        return form_service.template_out(db, t, detail=True)
    except form_service.FormError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/form-templates/{template_id}")
def get_template(template_id: TemplateId, db: Session = Depends(get_db), user: User = Depends(get_current_hr)):
    """模板详情（含全部字段，包括已停用的）"""
    t = _template_or_404(db, template_id)
    return form_service.template_out(db, t, detail=True)


@router.put("/form-templates/{template_id}")
def update_template(
    template_id: TemplateId,
    body: FormTemplateUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_hr),
):
    """修改模板元信息（名称 / 说明 / 启停）

**注意**：启用模板时，如果同范围已有其他启用中的模板，会返回 400。
"""
    t = _template_or_404(db, template_id)
    try:
        form_service.update_template_meta(db, t, body)
        db.commit()
        db.refresh(t)
        return form_service.template_out(db, t, detail=True)
    except form_service.FormError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/form-templates/{template_id}/fields")
def save_fields(
    template_id: TemplateId,
    body: FormFieldsIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_hr),
):
    """批量保存字段（传完整列表）

**怎么填**：`{"fields": [...]}`。未出现在列表里的旧字段会被软删除（历史答案保留）。
字段有任何变化，模板 `version` 会 +1。
"""
    t = _template_or_404(db, template_id)
    try:
        form_service.apply_fields(db, t, body.fields)
        db.commit()
        db.refresh(t)
        return form_service.template_out(db, t, detail=True)
    except form_service.FormError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/form-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    template_id: TemplateId,
    purge: bool = Query(default=False, description="true=物理删除（仅限已停用且无答卷）"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_hr),
):
    """停用模板（软删除）；`?purge=true` 时物理删除

**注意**：物理删除仅限已停用且没有任何答卷的模板；有答卷的会返回 409，历史答卷保留。
"""
    t = _template_or_404(db, template_id)
    if not purge:
        t.is_active = 0
        db.commit()
        return
    try:
        form_service.purge_template(db, t)
        db.commit()
    except form_service.FormError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/candidates/{can_id}/forms")
def list_candidate_forms(can_id: CanId, db: Session = Depends(get_db), user: User = Depends(get_current_hr)):
    """某候选人的全部答卷（个人资料表 + 各投递的岗位表）

**返回什么**：数组，每条带模板名、状态、答案（field_key → 值）和带中文标签的 items。
"""
    if db.get(Candidate, can_id) is None:
        raise HTTPException(status_code=404, detail="候选人不存在")
    subs = form_service.list_submissions(db, candidate_id=can_id)
    return [form_service.submission_out(db, s, with_candidate=True) for s in subs]


@router.get("/applications/{app_id}/forms")
def list_application_forms(app_id: AppId, db: Session = Depends(get_db), user: User = Depends(get_current_hr)):
    """某次投递的岗位答卷"""
    if db.get(Application, app_id) is None:
        raise HTTPException(status_code=404, detail="投递记录不存在")
    subs = form_service.list_submissions(db, application_id=app_id)
    return [form_service.submission_out(db, s, with_candidate=True) for s in subs]
