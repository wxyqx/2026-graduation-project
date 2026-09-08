from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import AiApiConfig, User
from app.services.ai_screen import run_intake

router = APIRouter(prefix="/api/ai-screen", tags=["ai-screen"])

MAX_FILE_BYTES = 20 * 1024 * 1024


@router.post("/intake")
async def intake(
    files: list[UploadFile] = File(default=[]),
    texts: list[str] = Form(default=[]),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """AI 智能录入：上传 PDF（files[]）或粘贴纯文本（texts[]）→ 提取文本 → AI 识别姓名、匹配岗位、评估通过与否并自动建档。逐条返回结果。PDF 与文本都不保存。"""
    if not files and not texts:
        raise HTTPException(status_code=400, detail="请至少上传一个 PDF 或粘贴一段简历文本")
    configs = db.scalars(
        select(AiApiConfig)
        .where(AiApiConfig.user_id == user.id, AiApiConfig.is_enabled == 1)
        .order_by(AiApiConfig.id)
    ).all()
    if not configs:
        raise HTTPException(status_code=400, detail="没有已启用的 AI 配置，请先在系统设置中添加并启用")

    payload: list[tuple[str, bytes]] = []
    for f in files:
        data = await f.read()
        if len(data) > MAX_FILE_BYTES:
            raise HTTPException(status_code=413, detail=f"文件 {f.filename} 超过 20MB")
        payload.append((f.filename or "resume.pdf", data))
    return await run_intake(db, payload, texts, configs)
