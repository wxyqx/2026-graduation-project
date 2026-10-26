"""
【HR 端系统设置】——只保留「周报阶段文案」这一项

AI 配置与 AI 筛选提示词已经迁到技术管理端（/api/tech/ai-configs、/api/tech/ai-prompt），
HR 不再有修改入口，避免业务侧误改系统配置。
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_hr
from app.models import User
from app.services import settings as settings_svc

router = APIRouter(prefix="/api/settings", tags=["settings"])


class PortalFormStageIn(BaseModel):
    """候选人表单可见阶段配置。"""

    position: str | None = Field(default=None, description="岗位申请表从哪关起可见，如 pro")
    assessment: str | None = Field(default=None, description="职业底色图从哪关起可见，如 pro")


class PortalFormStageOut(BaseModel):
    """表单可见阶段配置。"""

    position: str = Field(description="岗位申请表可见阶段")
    assessment: str = Field(description="职业底色图可见阶段")


class StageNoteIn(BaseModel):
    """保存手动改写的阶段文案。"""

    app_id: int = Field(description="投递编号（清单里每行的 app_id）")
    note: str | None = Field(
        default=None, max_length=50, description="你写的阶段文案，如「待offer回传」「待入职 1.11」。传空 = 恢复自动生成"
    )


class StageNoteOut(BaseModel):
    """返回保存后的全部手动文案映射（键是投递编号的字符串）。"""

    notes: dict[str, str] = Field(description="当前所有手动改写的阶段文案，形如 {\"82\": \"待offer回传\"}")


@router.put("/stage-note", response_model=StageNoteOut)
def save_stage_note(body: StageNoteIn, db: Session = Depends(get_db), user: User = Depends(get_current_hr)):
    """手动改写某条投递的「阶段」文案（周报清单里那一列）

**干什么用**：系统只能自动说「待笔试/待专业面/待终面」这些。想写系统没有的说法（比如「待offer回传」「待入职 1.11」）时用它。

**怎么填**：
- `app_id`：清单里那一行的投递编号
- `note`：你想显示的文字；**传空字符串 = 恢复到系统自动生成**

**存在哪**：存进 App_Setting 表（键 stage_notes，一段 JSON），按登录用户隔离，不改任何表结构、不影响投递本身的数据。
"""
    notes = settings_svc.set_stage_note(db, user.id, body.app_id, body.note)
    return StageNoteOut(notes=notes)


@router.get("/portal-form-stage", response_model=PortalFormStageOut)
def get_portal_form_stage(db: Session = Depends(get_db), user: User = Depends(get_current_hr)):
    """候选人从哪一关起能看到岗位申请表 / 职业底色图（系统级配置）"""
    cfg = settings_svc.get_portal_form_stage(db)
    return PortalFormStageOut(**cfg)


@router.put("/portal-form-stage", response_model=PortalFormStageOut)
def set_portal_form_stage(body: PortalFormStageIn, db: Session = Depends(get_db), user: User = Depends(get_current_hr)):
    """调整候选人表单可见阶段

**干什么用**：控制候选人在招聘流程走到哪一关后，才能看到并填写岗位申请表、职业底色图（个人资料表不受影响，投递前始终要填）。

**怎么填**：两个字段都传 7 关代号之一（ai/resume/phone/test/pro/hr/final），如 {"position":"pro","assessment":"pro"} 表示专业面起可见。传空字符串 = 恢复默认（专业面）。
"""
    cfg = settings_svc.set_portal_form_stage(db, body.model_dump())
    return PortalFormStageOut(**cfg)


class StageNoticeEntry(BaseModel):
    """单关通过通知模板。"""

    enabled: bool = Field(default=True, description="是否在该关通过时给候选人发通知")
    title: str = Field(default="", max_length=100, description="通知标题，占位符 {候选人} {岗位} {关卡} {负责人} {时间}")
    body: str = Field(default="", max_length=5000, description="通知正文，占位符 {候选人} {岗位} {关卡} {负责人} {时间}")


class StageNoticeIn(BaseModel):
    """保存通过通知模板（笔试/专业面/HR面/终面）。"""

    phone: StageNoticeEntry = Field(default_factory=StageNoticeEntry, description='电话沟通通过通知')
    test: StageNoticeEntry = Field(default_factory=StageNoticeEntry)
    pro: StageNoticeEntry = Field(default_factory=StageNoticeEntry)
    hr: StageNoticeEntry = Field(default_factory=StageNoticeEntry)
    final: StageNoticeEntry = Field(default_factory=StageNoticeEntry)
    onboard: StageNoticeEntry = Field(default_factory=StageNoticeEntry, description='入职通知（HR 回传盖章文件时生成草稿）')
    eliminated: StageNoticeEntry = Field(default_factory=StageNoticeEntry, description='淘汰通知（打 fail 淘汰时立即发送）')


@router.get("/stage-notice")
def get_stage_notice(db: Session = Depends(get_db), user: User = Depends(get_current_hr)):
    """各关通过通知的开关与模板（默认为占位模板，HR 可自行修改）"""
    return settings_svc.get_stage_notice(db)


@router.put("/stage-notice")
def set_stage_notice(body: StageNoticeIn, db: Session = Depends(get_db), user: User = Depends(get_current_hr)):
    """保存各关通过通知模板

**干什么用**：候选人通过笔试/专业面/HR面/终面时，若该关开关开启，系统按模板渲染后给候选人发一条通知，
候选人下次登录时弹窗展示。占位符：`{候选人}` `{岗位}` `{关卡}` `{负责人}` `{时间}`；某关不想发就把它的开关关掉。
"""
    # exclude_unset：只取客户端真正发了的关卡（配合 service 层合并式保存，
    # 部分保存不再把没传的关抹成默认——这里曾两次丢过 HR 自己保存的模板）
    return settings_svc.set_stage_notice(db, body.model_dump(exclude_unset=True))
