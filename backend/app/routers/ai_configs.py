from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import AiApiConfig, User
from app.schemas.ai_config import AiConfigIn, AiConfigOut, AiConfigUpdate

router = APIRouter(prefix="/api/ai-configs", tags=["ai-configs"])


def _out(c: AiApiConfig) -> AiConfigOut:
    return AiConfigOut(
        id=c.id, name=c.name, base_url=c.base_url, api_key=c.api_key, model=c.model, is_enabled=bool(c.is_enabled)
    )


def _get_own_or_404(db: Session, cfg_id: int, user: User) -> AiApiConfig:
    c = db.scalar(select(AiApiConfig).where(AiApiConfig.id == cfg_id, AiApiConfig.user_id == user.id))
    if c is None:
        raise HTTPException(status_code=404, detail="AI 配置不存在")
    return c


@router.get("", response_model=list[AiConfigOut])
def list_configs(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """我的 AI 配置列表（只看到自己添加的）。"""
    rows = db.scalars(select(AiApiConfig).where(AiApiConfig.user_id == user.id).order_by(AiApiConfig.id)).all()
    return [_out(c) for c in rows]


@router.post("", response_model=AiConfigOut, status_code=status.HTTP_201_CREATED)
def create_config(body: AiConfigIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """新建 AI 配置（OpenAI 兼容接口：GLM / Qwen / DeepSeek 等）。"""
    c = AiApiConfig(
        name=body.name,
        base_url=body.base_url.strip(),
        api_key=body.api_key.strip(),
        model=body.model.strip(),
        is_enabled=1 if body.is_enabled else 0,
        user_id=user.id,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return _out(c)


@router.put("/{cfg_id}", response_model=AiConfigOut)
def update_config(
    cfg_id: int, body: AiConfigUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """编辑 AI 配置（只更新传入的字段）。"""
    c = _get_own_or_404(db, cfg_id, user)
    data = body.model_dump(exclude_unset=True)
    if "is_enabled" in data:
        data["is_enabled"] = 1 if data["is_enabled"] else 0
    for k, v in data.items():
        setattr(c, k, v.strip() if isinstance(v, str) else v)
    db.commit()
    db.refresh(c)
    return _out(c)


@router.delete("/{cfg_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_config(cfg_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """删除 AI 配置。"""
    c = _get_own_or_404(db, cfg_id, user)
    db.delete(c)
    db.commit()


@router.put("/{cfg_id}/enable", response_model=AiConfigOut)
def enable_config(cfg_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """启用该配置（可多个同时启用，AI 录入时在启用的配置间轮询）。"""
    c = _get_own_or_404(db, cfg_id, user)
    c.is_enabled = 1
    db.commit()
    db.refresh(c)
    return _out(c)


@router.put("/{cfg_id}/disable", response_model=AiConfigOut)
def disable_config(cfg_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """停用该配置。"""
    c = _get_own_or_404(db, cfg_id, user)
    c.is_enabled = 0
    db.commit()
    db.refresh(c)
    return _out(c)
