"""
【面试评价接口】
  POST /api/interview/evaluate

贴一段面试逐字稿进来，AI 按固定的 7 项模板写出一份面试评价，直接返回文字。
评价**不存数据库**，返回给前端显示、复制走即可。

这个文件只做门口的活：检查登录、检查逐字稿长度、检查有没有启用的 AI 配置，
然后交给 services/interview.py 去调 AI。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import AiApiConfig, User
from app.schemas.interview import EvaluateIn, EvaluateOut
from app.services import interview, llm

router = APIRouter(prefix="/api/interview", tags=["interview"])


@router.post("/evaluate", response_model=EvaluateOut)
async def evaluate(body: EvaluateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """面试评价：贴逐字稿 → AI 按固定模板写面评

**干什么用**：面试完把对话逐字稿（转写文本）整段贴进来，AI 按固定的 7 项模板
（4 项基本信息 + 3 项价值观：英雄主义 / 信任与接纳 / 严谨与高效）写出一份面试评价文字，
直接显示在页面上，你复制走即可。

**前置条件**：至少启用一个 AI 配置（去「系统设置」添加并启用，可配多个轮着用）。

**怎么填**：`transcript` 把逐字稿整段粘进去。带不带时间戳、说话人名字怎么标都可以，
系统自己分得清谁在提问（面试官）谁在回答（候选人）。

**返回什么**：
```json
{"text": "基本信息确认：\\n\\n1.籍贯……", "config_used": "GLM免费版"}
```

**可能出错**：
- 400：逐字稿为空 / 少于 30 字 / 没有已启用的 AI 配置
- 422：逐字稿超过 30000 字（请分段提交）
- 502：AI 调用失败（密钥错、额度用完、网络不通），detail 里有中文原因

**隐私**：逐字稿只在内存里过一遍，**不存数据库、不存硬盘**；生成的评价也不落库，刷新页面即失。
"""
    # 去掉首尾空白后再看长度——只贴了几个字是评不出东西的
    text = (body.transcript or "").strip()
    if len(text) < interview.MIN_TRANSCRIPT_CHARS:
        raise HTTPException(status_code=400, detail=f"逐字稿太短了，至少要 {interview.MIN_TRANSCRIPT_CHARS} 个字")

    # 找出「我的」并且「已启用」的 AI 配置，一个都没有就没法干活
    configs = db.scalars(
        select(AiApiConfig)
        .where(AiApiConfig.user_id == user.id, AiApiConfig.is_enabled == 1)
        .order_by(AiApiConfig.id)
    ).all()
    if not configs:
        raise HTTPException(status_code=400, detail="没有已启用的 AI 配置，请先在系统设置中添加并启用")

    try:
        return await interview.evaluate(configs, text)
    except llm.LlmError as e:
        # AI 那边的错（连不上 / 密钥错 / 输出空）统一翻成 502，中文提示由前端拦截器弹出
        raise HTTPException(status_code=502, detail=f"生成失败：{e}")
