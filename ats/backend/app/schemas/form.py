"""【表单相关的表格模板】模板、字段、答卷、答案。"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FormFieldIn(BaseModel):
    """一个表单字段的定义。"""

    field_key: str = Field(min_length=1, max_length=50, description="英文键，如 education；同一模板内唯一")
    label: str = Field(min_length=1, max_length=100, description="显示名，如「最高学历」")
    field_type: str = Field(
        description="text / textarea / number / date / select / radio / checkbox / email / phone"
    )
    required: bool = Field(default=False, description="是否必填")
    options: list[str] | None = Field(default=None, description="select / radio / checkbox 的选项")
    placeholder: str | None = Field(default=None, max_length=200)
    help_text: str | None = Field(default=None, max_length=500)
    max_length: int | None = Field(default=None, ge=1, le=5000, description="文本类字段最大长度")
    sort_order: int = Field(default=0, description="排序，小的在前")
    is_active: bool = Field(default=True, description="false=停用（软删除，历史答案保留）")


class FormFieldOut(FormFieldIn):
    id: int


class FormTemplateIn(BaseModel):
    """新建表单模板。"""

    name: str = Field(min_length=1, max_length=100)
    scope: str = Field(description="profile=个人资料表 / position=岗位申请表")
    position_id: int | None = Field(default=None, description="scope=position 时必填")
    description: str | None = Field(default=None, max_length=500)
    fields: list[FormFieldIn] = Field(default_factory=list, description="可随模板一起创建字段")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "候选人资料表",
                    "scope": "profile",
                    "description": "请完善个人信息",
                    "fields": [
                        {"field_key": "education", "label": "最高学历", "field_type": "select", "required": True,
                         "options": ["大专", "本科", "硕士", "博士"], "sort_order": 1}
                    ],
                }
            ]
        }
    }


class FormTemplateUpdate(BaseModel):
    """修改模板元信息（字段用 PUT /form-templates/{id}/fields）。"""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = Field(default=None, description="启用/停用")


class FormFieldsIn(BaseModel):
    """批量保存字段：传完整列表，未出现的字段会被软删除（is_active=false）。"""

    fields: list[FormFieldIn]


class FormTemplateOut(BaseModel):
    id: int
    name: str
    scope: str
    position_id: int | None
    position_name: str | None = Field(default=None, description="岗位名（scope=position 时有值）")
    description: str | None
    version: int
    is_active: bool
    field_count: int
    create_time: datetime
    update_time: datetime


class FormTemplateDetail(FormTemplateOut):
    fields: list[FormFieldOut]


class FormAnswersIn(BaseModel):
    """候选人保存/提交答卷。"""

    answers: dict[str, Any] = Field(description="键是 field_key，值是答案；多选传数组")
    submit: bool = Field(default=False, description="true=提交；false=保存草稿")


class FormSubmissionOut(BaseModel):
    id: int
    template_id: int
    template_name: str
    candidate_id: int
    candidate_name: str | None = Field(default=None, description="HR 查看时带候选人姓名")
    application_id: int | None
    template_version: int
    status: str
    submit_time: datetime | None
    update_time: datetime
    answers: dict[str, Any] = Field(description="field_key → 答案（多选为数组）")
    items: list[dict] = Field(default_factory=list, description="带中文标签的答案列表，方便 HR 展示")
