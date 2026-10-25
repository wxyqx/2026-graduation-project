"""
【Form_Submission / Form_Answer：候选人填写的答卷与答案】

一份答卷（Submission）对应一个候选人 + 一个模板：
    profile 表：Application_ID 为 NULL，同一候选人同一模板只有一份
    position 表：Application_ID 指向某次投递

答案（Answer）一个字段一行；多选/复选的值统一存 JSON 数组字符串，读的时候再解析。
Field_Key 存快照：即使字段后来被删掉，历史答案仍然能看出问的是什么。
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class FormSubmission(Base):
    __tablename__ = "form_submission"  # Windows MySQL 表名统一小写存储，模型直接用小写保持与 alembic/库一致

    id: Mapped[int] = mapped_column("ID", Integer, primary_key=True, autoincrement=True)
    template_id: Mapped[int] = mapped_column(
        "Template_ID", Integer, ForeignKey("form_template.ID", ondelete="RESTRICT"), nullable=False
    )
    candidate_id: Mapped[int] = mapped_column(
        "Candidate_ID", Integer, ForeignKey("candidate.ID", ondelete="CASCADE"), nullable=False
    )
    application_id: Mapped[int | None] = mapped_column(
        "Application_ID", Integer, ForeignKey("application.ID", ondelete="CASCADE"), nullable=True
    )
    template_version: Mapped[int] = mapped_column("Template_Version", Integer, nullable=False)
    status: Mapped[str] = mapped_column("Status", String(20), nullable=False, default="draft")  # draft / submitted
    submit_time: Mapped[datetime | None] = mapped_column("Submit_Time", DateTime)
    update_time: Mapped[datetime] = mapped_column("Update_Time", DateTime, nullable=False)

    answers = relationship(
        "FormAnswer", back_populates="submission", cascade="all, delete-orphan", lazy="selectin"
    )


class FormAnswer(Base):
    __tablename__ = "form_answer"  # 小写化，见本目录其他模型注释

    id: Mapped[int] = mapped_column("ID", Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[int] = mapped_column(
        "Submission_ID", Integer, ForeignKey("form_submission.ID", ondelete="CASCADE"), nullable=False
    )
    field_id: Mapped[int] = mapped_column(
        "Field_ID", Integer, ForeignKey("form_field.ID", ondelete="CASCADE"), nullable=False
    )
    field_key: Mapped[str] = mapped_column("Field_Key", String(50), nullable=False)
    value_text: Mapped[str | None] = mapped_column("Value_Text", Text)

    submission = relationship("FormSubmission", back_populates="answers")
