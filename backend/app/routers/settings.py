"""
【系统设置接口】
  GET /api/settings/ai-prompt   读取当前的 AI 筛选提示词（规则部分）
  PUT /api/settings/ai-prompt   保存 AI 筛选提示词（规则部分）

注意：这里能改的只是「筛选规则」（比如「只要 985」「必须有医疗行业项目经验」）。
回答格式（必须输出 JSON、result 只能是 pass/fail）由系统锁定，不在这里也不允许改——
因为格式一乱，程序就读不懂 AI 的回答了。
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User
from app.services import prompt as prompt_svc
from app.services.settings import get_setting, set_setting

router = APIRouter(prefix="/api/settings", tags=["settings"])


class AiPromptIn(BaseModel):
    """保存提示词请求体。rules 就是你在设置页写的那段筛选规则；传空 = 恢复默认。"""

    rules: str | None = Field(default=None, max_length=8000, description="AI 筛选规则（人设/筛选标准）。留空表示用系统默认规则")


class AiPromptOut(BaseModel):
    """返回给前端的提示词信息。"""

    rules: str = Field(description="当前生效的筛选规则（你写的；没写过则返回默认规则）")
    is_custom: bool = Field(description="是你自定义的规则（true）还是系统默认规则（false）")
    default_rules: str = Field(description="系统默认规则，方便你一键恢复")
    format_rules: str = Field(description="系统锁定的回答格式说明（只读，不可修改）")


@router.get("/ai-prompt", response_model=AiPromptOut)
def read_ai_prompt(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """读取 AI 筛选提示词

**干什么用**：前端「系统设置 → AI 筛选提示词」卡片打开时调用，把当前规则填进输入框。

**返回什么**：
- `rules`：当前生效的筛选规则（你没写过时，返回的就是系统默认规则的内容）
- `is_custom`：true = 你自定义过；false = 正在用系统默认
- `default_rules`：系统默认规则原文，供「恢复默认」用
- `format_rules`：系统锁定的回答格式说明（只读展示）
"""
    saved = get_setting(db, user.id, "ai_prompt")
    return AiPromptOut(
        rules=(saved or "").strip() or prompt_svc.DEFAULT_RULES,
        is_custom=bool((saved or "").strip()),
        default_rules=prompt_svc.DEFAULT_RULES,
        format_rules=prompt_svc.FORMAT_RULES,
    )


@router.put("/ai-prompt", response_model=AiPromptOut)
def save_ai_prompt(body: AiPromptIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """保存 AI 筛选提示词

**干什么用**：改了筛选规则后点保存。

**怎么填**：`{"rules": "只要 985/211；必须有医疗行业项目经验；不接收外包背景"}`。
传空字符串表示恢复默认规则（等于删掉你的自定义）。

**注意**：只能改筛选规则，回答格式由系统锁定，传什么都不影响格式。
"""
    set_setting(db, user.id, "ai_prompt", body.rules)
    saved = get_setting(db, user.id, "ai_prompt")
    return AiPromptOut(
        rules=(saved or "").strip() or prompt_svc.DEFAULT_RULES,
        is_custom=bool((saved or "").strip()),
        default_rules=prompt_svc.DEFAULT_RULES,
        format_rules=prompt_svc.FORMAT_RULES,
    )
