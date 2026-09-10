"""
【AI 智能录入接口】
  POST /api/ai-screen/intake

这是一个「上传文件」类型的接口，跟别的接口传 JSON 不一样——用的是 multipart/form-data 格式
（就是网页上传文件用的那种）。可以同时传多个 PDF（files）和多段文字（texts）。

这个文件只做门口的活：检查登录、检查有没有启用的 AI 配置、把文件读进内存，
然后交给 services/ai_screen.py 的 run_intake 去跑三步流水线。
"""
import json

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
    files: list[UploadFile] = File(default=[], description="PDF 简历，可一次传多个。扫描件（图片型 PDF）抠不出文字会单独报错，改用 texts"),
    texts: list[str] = Form(default=[], description="粘贴的简历纯文本，可多段（每段一份简历）。没有 PDF 时的兜底方式，至少 30 个字"),
    extras: str | None = Form(default=None, description='各岗位的额外 AI 筛选限制（JSON 字符串，如 {"1":"只要985"}），前端本地存、不入库'),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """AI 智能录入：传简历 → AI 认人、配岗、打分、自动建档

**干什么用**：招聘最费时间的活——收到一堆简历，一份份看、录、筛。这个接口一次搞定：
传几份 PDF 进来，AI 自动干四件事：**① 认出候选人姓名 ② 从在招岗位里挑出他投的岗位 ③ 按岗位要求判断合不合格 ④ 建候选人 + 建投递 + 打第一关的分**。

**前置条件**：
1. 系统里得有岗位（AI 要从里面挑）
2. 至少启用一个 AI 配置（去 ai-configs 添加）

**怎么填**（Try it out 后）：
- `files`：点「选择文件」传 PDF，可多选
- `texts`：没 PDF 就把简历文字粘这里，每一格一份
- `extras`：各岗位的额外限制（JSON 字符串，如 `{"1":"只要985/211"}`），前端把岗位编辑框里填的附加条件带过来；不传则只用岗位要求判断
- 三者可以混着传，也可以只传一种

**每份简历会发生什么**：
- 抠文字 → 发给 AI → AI 回「姓名 / 岗位编号 / pass 或 fail / 理由」
- 姓名已存在 → 复用那个候选人；不存在 → 新建（备注写「AI录入」）
- 建投递：`pass` → 自动进入第 2 关 resume；`fail` → 标记已淘汰。理由存进 `ai_comment`
- 多个 AI 配置轮流用，某个出错自动换下一个再试一次

**返回什么**（逐条结果，一条失败不影响其他）：
```json
{
  "total": 3,
  "summary": {"ok": 1, "duplicate": 1, "extract_failed": 1},
  "results": [
    {"index": 0, "filename": "张三.pdf", "status": "ok",
     "candidate_name": "张三", "position_name": "Java高级工程师",
     "ai_result": "pass", "ai_comment": "5年Java经验，符合要求",
     "application_id": 7, "config_used": "GLM免费版",
     "message": "AI 筛选通过，已进入简历筛选阶段"},
    {"index": 1, "filename": "李四.pdf", "status": "duplicate", "message": "「李四」已投递过「前端工程师」，未重复建档"},
    {"index": 2, "filename": "扫描件.pdf", "status": "extract_failed", "message": "无法提取文本（可能是扫描件…）"}
  ]
}
```

**`status` 五种取值**：
| 值 | 意思 |
| :- | :--- |
| ok | 成功建档并打分 |
| duplicate | 这人已投过这个岗位，没重复建 |
| no_position | AI 觉得简历跟所有岗位都不搭，没建档 |
| extract_failed | 不是 PDF / 扫描件抠不出字 / 文字太短 |
| error | AI 调用失败（网络、密钥错、额度用完）或回答格式不对 |

**可能出错**（整个请求失败，而不是逐条）：
- 400：什么都没传；或没有已启用的 AI 配置
- 413：单个文件超过 20MB

**隐私**：PDF 和简历原文只在内存里过一遍，**不存数据库、不存硬盘**。只有结果（pass/fail + 理由）留下。
"""
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

    # 解析前端传来的岗位附加条件（JSON 字符串）。格式不对就忽略，不让整个请求失败
    extra_map: dict[str, str] = {}
    if extras:
        try:
            parsed = json.loads(extras)
            if isinstance(parsed, dict):
                extra_map = {str(k): str(v) for k, v in parsed.items() if str(v).strip()}
        except (ValueError, TypeError):
            extra_map = {}

    return await run_intake(db, payload, texts, configs, extra_map)
