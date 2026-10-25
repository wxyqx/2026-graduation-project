"""
【Form_Template / Form_Field：可配置表单的模板与字段】

HR 在后台定义「要问候选人什么」，候选人端按模板渲染成表单填写。
两种用途（Scope）：
    profile  ：个人资料表，全局一份，每个候选人一份答卷
    position ：岗位申请表，绑定某个岗位，每次投递一份答卷

模板字段改动时 Version +1；已提交的答卷保留当时的 Template_Version，不会因为改模板而丢答案。
字段用软删除（Is_Active=0），历史答案仍能显示。
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class FormTemplate(Base):
    __tablename__ = "form_template"  # Windows MySQL 表名统一小写存储，模型直接用小写保持与 alembic/库一致

    id: Mapped[int] = mapped_column("ID", Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column("Name", String(100), nullable=False)
    scope: Mapped[str] = mapped_column("Scope", String(20), nullable=False)  # profile / position
    position_id: Mapped[int | None] = mapped_column(
        "Position_ID", Integer, ForeignKey("position.ID", ondelete="CASCADE"), nullable=True
    )
    description: Mapped[str | None] = mapped_column("Description", String(500))
    version: Mapped[int] = mapped_column("Version", Integer, nullable=False, default=1)
    is_active: Mapped[int] = mapped_column("Is_Active", SmallInteger, nullable=False, default=1)
    created_by: Mapped[int | None] = mapped_column("Created_By", Integer)
    create_time: Mapped[datetime] = mapped_column("Create_Time", DateTime, nullable=False)
    update_time: Mapped[datetime] = mapped_column("Update_Time", DateTime, nullable=False)

    fields = relationship(
        "FormField",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="FormField.sort_order",
        lazy="selectin",
    )


class FormField(Base):
    __tablename__ = "form_field"  # 小写化，见本目录其他模型注释

    id: Mapped[int] = mapped_column("ID", Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(
        "Template_ID", Integer, ForeignKey("form_template.ID", ondelete="CASCADE"), nullable=False
    )
    field_key: Mapped[str] = mapped_column("Field_Key", String(50), nullable=False)  # 英文键，同模板内唯一
    label: Mapped[str] = mapped_column("Label", String(100), nullable=False)  # 显示名
    field_type: Mapped[str] = mapped_column("Field_Type", String(20), nullable=False)
    required: Mapped[int] = mapped_column("Required", SmallInteger, nullable=False, default=0)
    options_json: Mapped[str | None] = mapped_column("Options_JSON", Text)  # select/radio/checkbox 的选项
    placeholder: Mapped[str | None] = mapped_column("Placeholder", String(200))
    help_text: Mapped[str | None] = mapped_column("Help_Text", String(500))
    max_length: Mapped[int | None] = mapped_column("Max_Length", Integer)
    sort_order: Mapped[int] = mapped_column("Sort_Order", Integer, nullable=False, default=0)
    is_active: Mapped[int] = mapped_column("Is_Active", SmallInteger, nullable=False, default=1)

    template = relationship("FormTemplate", back_populates="fields")
