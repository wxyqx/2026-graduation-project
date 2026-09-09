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
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import AiApiConfig, User
from app.schemas.ai_config import AiConfigIn, AiConfigOut, AiConfigUpdate

# 这里没在 router 上统一挂门卫，因为每个函数都要拿到 user 本人（要用 user.id 过滤），所以各自写 Depends
router = APIRouter(prefix="/api/ai-configs", tags=["ai-configs"])

CfgId = Annotated[int, Path(description="配置编号（列表里的 id）")]


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
    """我的 AI 配置列表

**干什么用**：前端「系统设置」页的 AI 配置表格。只显示你自己添加的，别人的看不到。

**返回什么**：
```json
[{"id": 1, "name": "GLM免费版", "base_url": "https://open.bigmodel.cn/api/paas/v4", "api_key": "…", "model": "glm-4-flash", "is_enabled": true}]
```
"""
    rows = db.scalars(select(AiApiConfig).where(AiApiConfig.user_id == user.id).order_by(AiApiConfig.id)).all()
    return [_out(c) for c in rows]


@router.post("", response_model=AiConfigOut, status_code=status.HTTP_201_CREATED)
def create_config(body: AiConfigIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """添加一个 AI 配置（告诉系统去哪找 AI、凭什么用）

**干什么用**：系统自己不会「思考」，筛简历要请外面的大模型帮忙。这里填大模型的地址、密钥、模型名。
支持所有「OpenAI 兼容格式」的服务：智谱 GLM、通义千问、DeepSeek、Kimi、OpenAI……

**怎么填**（以智谱为例）：
- `name`：随便起，如「GLM免费版」
- `base_url`：`https://open.bigmodel.cn/api/paas/v4`（填到 /v4 就行，后面的路径系统自动补）
- `api_key`：去 https://open.bigmodel.cn 注册 → 右上角 API Keys → 创建 → 复制
- `model`：`glm-4-flash`（免费）
- `is_enabled`：`true` 立刻可用

**返回什么**：新建的配置，带 `id`。

**注意**：可以添加多个、同时启用多个。AI 录入时会在启用的配置间轮流用，某个出错自动换另一个重试。
"""
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
    cfg_id: CfgId, body: AiConfigUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """编辑配置（只改你传的字段）

**干什么用**：换模型、换密钥。想改哪个传哪个，没传的不动。例：`{"model": "glm-4-plus"}`。

**可能出错**：
- 404：没有这个配置，或者它不是你的
"""
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
def delete_config(cfg_id: CfgId, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """删除配置

**返回什么**：204，无内容。

**可能出错**：
- 404：没有这个配置，或者它不是你的
"""
    c = _get_own_or_404(db, cfg_id, user)
    db.delete(c)
    db.commit()


@router.put("/{cfg_id}/enable", response_model=AiConfigOut)
def enable_config(cfg_id: CfgId, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """启用一个配置（开关拨到「开」）

**干什么用**：前端设置页每行的开关。只有启用的配置才会被 AI 录入使用。可以同时开好几个。

**怎么填**：网址里换配置编号，不用传 body。
"""
    c = _get_own_or_404(db, cfg_id, user)
    c.is_enabled = 1
    db.commit()
    db.refresh(c)
    return _out(c)


@router.put("/{cfg_id}/disable", response_model=AiConfigOut)
def disable_config(cfg_id: CfgId, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """停用一个配置（开关拨到「关」）

**干什么用**：某个 AI 额度用完了、或者想暂时不用它，关掉但不删。
"""
    c = _get_own_or_404(db, cfg_id, user)
    c.is_enabled = 0
    db.commit()
    db.refresh(c)
    return _out(c)
