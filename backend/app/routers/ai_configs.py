"""
【AI 接口配置：增删改查 + 启用/停用】
  GET    /api/ai-configs               我的配置列表
  POST   /api/ai-configs               新建
  PUT    /api/ai-configs/{id}          编辑
  DELETE /api/ai-configs/{id}          删除
  PUT    /api/ai-configs/{id}/enable   启用
  PUT    /api/ai-configs/{id}/disable  停用

重点：每个人只能看到、改动「自己」添加的配置。所有查询都带上 user_id == 当前用户 这个条件，
别人的配置对你来说就像不存在（回 404 而不是 403，连「有这么一条」都不告诉你）。
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import AiApiConfig, User
from app.schemas.ai_config import AiConfigIn, AiConfigOut, AiConfigUpdate

# 这里没在 router 上统一挂门卫，因为每个函数都要拿到 user 本人（要用 user.id 过滤），所以各自写 Depends
router = APIRouter(prefix="/api/ai-configs", tags=["ai-configs"])


def _out(c: AiApiConfig) -> AiConfigOut:
    # 数据库存 1/0，回给前端变成 True/False
    return AiConfigOut(
        id=c.id, name=c.name, base_url=c.base_url, api_key=c.api_key, model=c.model, is_enabled=bool(c.is_enabled)
    )


def _get_own_or_404(db: Session, cfg_id: int, user: User) -> AiApiConfig:
    """按编号找配置，而且必须是「我的」。不是我的或不存在，一律 404。"""
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
        base_url=body.base_url.strip(),  # strip 去掉用户复制粘贴时多带的空格
        api_key=body.api_key.strip(),
        model=body.model.strip(),
        is_enabled=1 if body.is_enabled else 0,  # True/False → 1/0
        user_id=user.id,  # 记下是谁建的
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
    data = body.model_dump(exclude_unset=True)  # 只取前端真正传了的字段
    if "is_enabled" in data:
        data["is_enabled"] = 1 if data["is_enabled"] else 0
    for k, v in data.items():
        setattr(c, k, v.strip() if isinstance(v, str) else v)  # 文字类的字段顺手去空格
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
