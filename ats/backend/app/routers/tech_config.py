"""
【技术管理端系统配置】
  GET/POST/PUT/DELETE /api/tech/ai-configs        AI 接口配置（系统级，所有启用的轮流使用）
  PUT  /api/tech/ai-configs/{id}/enable|disable
  GET/PUT /api/tech/ai-prompt                    AI 筛选提示词（系统级）

这些配置原来在 HR 的「系统设置」里，v3.15 起收归技术管理端。
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.models import AiApiConfig, User
from app.schemas.ai_config import AiConfigIn, AiConfigOut, AiConfigUpdate
from app.services import email_service
from app.services import prompt as prompt_svc
from app.services import settings as settings_svc
from app.services.log_service import log_action

router = APIRouter(prefix="/api/tech", tags=["tech-config"])


def _out(c: AiApiConfig) -> AiConfigOut:
    return AiConfigOut(
        id=c.id, name=c.name, base_url=c.base_url, api_key=c.api_key, model=c.model, is_enabled=bool(c.is_enabled)
    )


def _get_or_404(db: Session, cfg_id: int) -> AiApiConfig:
    c = db.get(AiApiConfig, cfg_id)
    if c is None:
        raise HTTPException(status_code=404, detail="AI 配置不存在")
    return c


@router.get("/ai-configs", response_model=list[AiConfigOut])
def list_configs(db: Session = Depends(get_db), current: User = Depends(get_current_admin)):
    """所有 AI 配置（系统级）"""
    rows = db.scalars(select(AiApiConfig).order_by(AiApiConfig.id)).all()
    return [_out(c) for c in rows]


@router.post("/ai-configs", response_model=AiConfigOut, status_code=status.HTTP_201_CREATED)
def create_config(body: AiConfigIn, db: Session = Depends(get_db), current: User = Depends(get_current_admin)):
    """新增 AI 配置（OpenAI 兼容接口）"""
    c = AiApiConfig(
        name=body.name.strip(),
        base_url=body.base_url.strip(),
        api_key=body.api_key.strip(),
        model=body.model.strip(),
        is_enabled=1 if body.is_enabled else 0,
        user_id=current.id,
    )
    db.add(c)
    db.flush()
    log_action(db, current, "config_change", target_type="ai_config", target_id=c.id, detail={"action": "create"})
    db.commit()
    db.refresh(c)
    return _out(c)


@router.put("/ai-configs/{cfg_id}", response_model=AiConfigOut)
def update_config(
    cfg_id: int, body: AiConfigUpdate, db: Session = Depends(get_db), current: User = Depends(get_current_admin)
):
    """编辑 AI 配置（只改传入的字段）"""
    c = _get_or_404(db, cfg_id)
    data = body.model_dump(exclude_unset=True)
    if "is_enabled" in data:
        data["is_enabled"] = 1 if data["is_enabled"] else 0
    for k, v in data.items():
        setattr(c, k, v.strip() if isinstance(v, str) else v)
    log_action(db, current, "config_change", target_type="ai_config", target_id=c.id, detail={"action": "update"})
    db.commit()
    db.refresh(c)
    return _out(c)


@router.delete("/ai-configs/{cfg_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_config(cfg_id: int, db: Session = Depends(get_db), current: User = Depends(get_current_admin)):
    """删除 AI 配置"""
    c = _get_or_404(db, cfg_id)
    log_action(db, current, "config_change", target_type="ai_config", target_id=c.id, detail={"action": "delete"})
    db.delete(c)
    db.commit()


@router.put("/ai-configs/{cfg_id}/enable", response_model=AiConfigOut)
def enable_config(cfg_id: int, db: Session = Depends(get_db), current: User = Depends(get_current_admin)):
    """启用 AI 配置"""
    c = _get_or_404(db, cfg_id)
    c.is_enabled = 1
    log_action(db, current, "config_change", target_type="ai_config", target_id=c.id, detail={"action": "enable"})
    db.commit()
    db.refresh(c)
    return _out(c)


@router.put("/ai-configs/{cfg_id}/disable", response_model=AiConfigOut)
def disable_config(cfg_id: int, db: Session = Depends(get_db), current: User = Depends(get_current_admin)):
    """停用 AI 配置"""
    c = _get_or_404(db, cfg_id)
    c.is_enabled = 0
    log_action(db, current, "config_change", target_type="ai_config", target_id=c.id, detail={"action": "disable"})
    db.commit()
    db.refresh(c)
    return _out(c)


class AiPromptIn(BaseModel):
    rules: str | None = Field(default=None, max_length=8000, description="筛选规则；留空 = 恢复系统默认")


class AiPromptOut(BaseModel):
    rules: str
    is_custom: bool
    default_rules: str
    format_rules: str


def _prompt_out(db: Session, current: User) -> AiPromptOut:
    admin = settings_svc.get_system_admin(db) or current
    saved = settings_svc.get_setting(db, admin.id, "ai_prompt")
    return AiPromptOut(
        rules=(saved or "").strip() or prompt_svc.DEFAULT_RULES,
        is_custom=bool((saved or "").strip()),
        default_rules=prompt_svc.DEFAULT_RULES,
        format_rules=prompt_svc.FORMAT_RULES,
    )


@router.get("/ai-prompt", response_model=AiPromptOut)
def read_prompt(db: Session = Depends(get_db), current: User = Depends(get_current_admin)):
    """读取系统级 AI 筛选提示词"""
    return _prompt_out(db, current)


@router.put("/ai-prompt", response_model=AiPromptOut)
def save_prompt(body: AiPromptIn, db: Session = Depends(get_db), current: User = Depends(get_current_admin)):
    """保存系统级 AI 筛选提示词（只改筛选规则，回答格式由系统锁定）"""
    admin = settings_svc.get_system_admin(db) or current
    settings_svc.set_setting(db, admin.id, "ai_prompt", body.rules)
    log_action(db, current, "config_change", target_type="ai_config", detail={"field": "ai_prompt"})
    db.commit()
    return _prompt_out(db, current)


# ---------- SMTP 邮件配置（通知的邮件渠道） ----------

class EmailSmtpIn(BaseModel):
    """SMTP 发件配置。password 传空 = 保持原密码不变。"""

    enabled: bool = Field(default=False, description="是否启用邮件渠道")
    host: str = Field(default="", description="SMTP 服务器，如 smtp.qq.com")
    port: int = Field(default=465, description="端口：465=SSL（推荐）/ 587=STARTTLS")
    use_ssl: bool = Field(default=True, description="true=SSL（465）/ false=STARTTLS（587）")
    username: str = Field(default="", description="发件邮箱账号")
    password: str = Field(default="", description="授权码（不是邮箱登录密码）；留空 = 保持原值")
    sender_name: str = Field(default="ATS 招聘系统", description="发件人显示名")
    site_url: str = Field(default="", description="候选人端登录地址，会附在邮件末尾")


class EmailTestIn(BaseModel):
    to: str = Field(description="收件邮箱（发一封测试邮件验证配置）")


@router.get("/email-smtp")
def get_email_smtp(db: Session = Depends(get_db), current: User = Depends(get_current_admin)):
    """读 SMTP 配置（授权码不回显，只回 has_password）"""
    cfg = email_service.get_email_config(db)
    has_password = bool(cfg.get("password"))
    cfg["password"] = ""
    cfg["has_password"] = has_password
    return cfg


@router.put("/email-smtp")
def set_email_smtp(body: EmailSmtpIn, db: Session = Depends(get_db), current: User = Depends(get_current_admin)):
    """保存 SMTP 配置（password 留空 = 保持原授权码）"""
    try:
        cfg = email_service.set_email_config(db, body.model_dump())
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    has_password = bool(cfg.get("password"))
    cfg["password"] = ""
    cfg["has_password"] = has_password
    return cfg


@router.post("/email-smtp/test")
def test_email_smtp(body: EmailTestIn, db: Session = Depends(get_db), current: User = Depends(get_current_admin)):
    """发一封测试邮件，验证 SMTP 配置；返回 error=null 即成功"""
    err = email_service.send_test_email(db, body.to)
    if err:
        raise HTTPException(status_code=400, detail=f"发送失败：{err}")
    return {"ok": True}


@router.get("/email-outbox")
def list_email_outbox(
    db: Session = Depends(get_db), current: User = Depends(get_current_admin)
):
    """邮件发件箱：每封通知邮件的投递状态（pending 重试中 / sent 已送达 / failed 放弃），新的在前。"""
    from sqlalchemy import select

    from app.models import EmailOutbox

    rows = db.scalars(select(EmailOutbox).order_by(EmailOutbox.id.desc()).limit(100)).all()
    return [
        {
            "id": r.id,
            "notice_id": r.notice_id,
            "to_email": r.to_email,
            "subject": r.subject,
            "status": r.status,
            "attempts": r.attempts,
            "last_error": r.last_error,
            "update_time": r.update_time,
        }
        for r in rows
    ]


class PrivacyPolicyIn(BaseModel):
    """政策文案更新请求。"""

    text: str = Field(min_length=1, description="《隐私政策与 AI 筛选告知书》全文（Markdown/纯文本均可）")


@router.get("/privacy-policy")
def get_privacy(db: Session = Depends(get_db), current: User = Depends(get_current_admin)):
    """当前《隐私政策与 AI 筛选告知书》文案与版本（候选人端投递/填表/回传前的同意依据）"""
    from app.services import settings as settings_svc

    return settings_svc.get_privacy_policy(db)


@router.put("/privacy-policy")
def set_privacy(body: PrivacyPolicyIn, db: Session = Depends(get_db), current: User = Depends(get_current_admin)):
    """保存政策文案（版本号自动按保存时间生成；已同意的候选人不用重签，新同意记录引用新版本）"""
    from app.services import settings as settings_svc

    try:
        return settings_svc.set_privacy_policy(db, body.text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))



class AppealContactIn(BaseModel):
    """申诉联系方式更新请求。"""

    text: str = Field(default="", max_length=500, description="申诉联系方式文案；空 = 恢复默认")


@router.get("/appeal-contact")
def get_appeal(db: Session = Depends(get_db), current: User = Depends(get_current_admin)):
    """淘汰申诉联系方式（通知模板 {申诉联系方式} 占位符的取值）"""
    from app.services import settings as settings_svc

    return {"text": settings_svc.get_appeal_contact(db)}


@router.put("/appeal-contact")
def set_appeal(body: AppealContactIn, db: Session = Depends(get_db), current: User = Depends(get_current_admin)):
    """保存淘汰申诉联系方式（留空恢复默认文案）"""
    from app.services import settings as settings_svc

    return {"text": settings_svc.set_appeal_contact(db, body.text)}

