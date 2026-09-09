"""
【AI 智能录入接口】
  POST /api/ai-screen/intake

这是一个「上传文件」类型的接口，跟别的接口传 JSON 不一样——用的是 multipart/form-data 格式
（就是网页上传文件用的那种）。可以同时传多个 PDF（files）和多段文字（texts）。

这个文件只做门口的活：检查登录、检查有没有启用的 AI 配置、把文件读进内存，
然后交给 services/ai_screen.py 的 run_intake 去跑三步流水线。
"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import AiApiConfig, User
from app.services.ai_screen import run_intake

router = APIRouter(prefix="/api/ai-screen", tags=["ai-screen"])

MAX_FILE_BYTES = 20 * 1024 * 1024  # 单个文件最大 20MB（1024 字节 = 1KB，1024KB = 1MB）


# async def：这个接口是异步的，因为里面要「等」——等文件读完、等 AI 回话
@router.post("/intake")
async def intake(
    files: list[UploadFile] = File(default=[]),  # 上传的 PDF 们，可以一个都不传
    texts: list[str] = Form(default=[]),  # 粘贴的文字们，可以一个都不传
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """AI 智能录入：上传 PDF（files[]）或粘贴纯文本（texts[]）→ 提取文本 → AI 识别姓名、匹配岗位、评估通过与否并自动建档。逐条返回结果。PDF 与文本都不保存。"""
    if not files and not texts:
        raise HTTPException(status_code=400, detail="请至少上传一个 PDF 或粘贴一段简历文本")
    # 找出「我的」并且「已启用」的 AI 配置，一个都没有就没法干活
    configs = db.scalars(
        select(AiApiConfig)
        .where(AiApiConfig.user_id == user.id, AiApiConfig.is_enabled == 1)
        .order_by(AiApiConfig.id)
    ).all()
    if not configs:
        raise HTTPException(status_code=400, detail="没有已启用的 AI 配置，请先在系统设置中添加并启用")

    # 把每个上传的文件读成字节，放进列表 [(文件名, 字节), ...]
    payload: list[tuple[str, bytes]] = []
    for f in files:
        data = await f.read()  # await = 等这个读取动作完成
        if len(data) > MAX_FILE_BYTES:
            raise HTTPException(status_code=413, detail=f"文件 {f.filename} 超过 20MB")  # 413 = 太大了
        payload.append((f.filename or "resume.pdf", data))
    return await run_intake(db, payload, texts, configs)
