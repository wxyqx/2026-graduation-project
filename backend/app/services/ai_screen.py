"""AI 智能录入编排：PDF 提取 → 并发调 LLM（多配置轮询、失败换配置重试一次）→ 顺序写库。

简历原文与 PDF 全程只在内存中，不落库不落盘。
"""
import asyncio
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AiApiConfig, Application, Candidate, Position
from app.services import llm
from app.services import state_machine as sm
from app.services.pdf import PdfExtractError, extract_text

MAX_RESUME_CHARS = 8000
CONCURRENCY = 4

SYSTEM_PROMPT = (
    "你是一名专业的招聘助理，负责阅读候选人简历、匹配应聘岗位并做初步筛选。"
    "你必须只输出一个 JSON 对象，不要输出任何解释、markdown 或多余文字。"
)


@dataclass
class IntakeItem:
    index: int
    source: str  # file / text
    filename: str | None
    status: str = "pending"  # ok / duplicate / no_position / extract_failed / error
    message: str | None = None
    candidate_id: int | None = None
    candidate_name: str | None = None
    position_id: int | None = None
    position_name: str | None = None
    application_id: int | None = None
    ai_result: str | None = None
    ai_comment: str | None = None
    config_used: str | None = None
    text: str | None = field(default=None, repr=False)
    llm_obj: dict | None = field(default=None, repr=False)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("text", None)
        d.pop("llm_obj", None)
        return d


def _positions_block(positions: list[Position]) -> str:
    rows = [
        {"id": p.id, "name": p.position_name or "", "requirements": (p.position_requirements or "")[:1500]}
        for p in positions
    ]
    return json.dumps(rows, ensure_ascii=False, indent=1)


def _user_prompt(positions_block: str, resume_text: str) -> str:
    return (
        "## 在招岗位列表（JSON）\n"
        f"{positions_block}\n\n"
        "## 简历内容\n"
        f"{resume_text[:MAX_RESUME_CHARS]}\n\n"
        "## 任务\n"
        "1. 识别候选人姓名，填入 name；确实无法识别时填空字符串。\n"
        "2. 从岗位列表中选出该简历最可能应聘的一个岗位，把其 id 填入 position_id；"
        "若简历方向与所有岗位都不相关，position_id 填 null。\n"
        "3. 若匹配到岗位，严格依据该岗位的 requirements 判断 result 为 \"pass\" 或 \"fail\"，"
        "并在 reason 中用不超过 120 字说明理由（未匹配岗位时 reason 说明原因）。\n\n"
        "输出格式（仅此 JSON）：\n"
        '{"name": "张三", "position_id": 1, "result": "pass", "reason": "..."}'
    )


async def _screen_one(idx: int, item: IntakeItem, configs: list[AiApiConfig], positions_block: str, sem: asyncio.Semaphore):
    n = len(configs)
    first = configs[idx % n]
    second = configs[(idx + 1) % n]
    last_err: Exception | None = None
    async with sem:
        for cfg in (first, second):
            try:
                content = await llm.chat(cfg, SYSTEM_PROMPT, _user_prompt(positions_block, item.text or ""))
                item.llm_obj = llm.parse_json_object(content)
                item.config_used = cfg.name
                return
            except llm.LlmError as e:
                last_err = e
    item.status = "error"
    item.message = f"AI 调用失败（已重试）：{last_err}"


def _fallback_name(item: IntakeItem) -> str | None:
    if item.filename:
        stem = Path(item.filename).stem.strip()
        return stem[:255] if stem else None
    return None


def _persist(db: Session, item: IntakeItem, pos_map: dict[int, Position], now: datetime) -> None:
    obj = item.llm_obj or {}
    name = str(obj.get("name") or "").strip()[:255] or _fallback_name(item)
    reason = str(obj.get("reason") or "").strip()[:500]
    result = str(obj.get("result") or "").strip().lower()
    raw_pos = obj.get("position_id")
    try:
        pos_id = int(raw_pos) if raw_pos is not None and str(raw_pos).strip() != "" else None
    except (TypeError, ValueError):
        pos_id = None

    item.candidate_name = name
    item.ai_comment = reason or None

    if pos_id is None or pos_id not in pos_map:
        item.status = "no_position"
        item.message = reason or "未匹配到相关在招岗位，未建档"
        return
    position = pos_map[pos_id]
    item.position_id = position.id
    item.position_name = position.position_name

    if not name:
        item.status = "error"
        item.message = "未能识别候选人姓名，未建档"
        return
    if result not in sm.RESULTS:
        item.status = "error"
        item.message = f"模型返回的 result 不是 pass/fail：{result or '空'}"
        return
    item.ai_result = result

    candidate = db.scalar(select(Candidate).where(Candidate.name == name))
    if candidate is None:
        candidate = Candidate(name=name, remark="AI录入", create_time=now)
        db.add(candidate)
        db.flush()
    item.candidate_id = candidate.id

    existing = db.scalar(
        select(Application).where(Application.can_id == candidate.id, Application.pos_id == position.id)
    )
    if existing:
        item.status = "duplicate"
        item.application_id = existing.id
        item.message = f"「{name}」已投递过「{position.position_name}」，未重复建档"
        db.commit()
        return

    app = Application(
        can_id=candidate.id,
        pos_id=position.id,
        current_stage="ai",
        overall_status="pending",
        ai_comment=item.ai_comment,
        create_time=now,
        update_time=now,
    )
    sm.apply_result(app, "ai", result, now)
    db.add(app)
    db.commit()
    db.refresh(app)
    item.application_id = app.id
    item.status = "ok"
    item.message = "AI 筛选通过，已进入简历筛选阶段" if result == "pass" else "AI 筛选未通过，已标记淘汰"


async def run_intake(
    db: Session,
    files: list[tuple[str, bytes]],
    texts: list[str],
    configs: list[AiApiConfig],
) -> dict:
    positions = db.scalars(select(Position).order_by(Position.id)).all()
    pos_map = {p.id: p for p in positions}
    positions_block = _positions_block(positions)

    items: list[IntakeItem] = []
    for filename, data in files:
        item = IntakeItem(index=len(items), source="file", filename=filename)
        if not filename.lower().endswith(".pdf"):
            item.status, item.message = "extract_failed", "仅支持 PDF 文件"
        else:
            try:
                item.text = extract_text(data)
            except PdfExtractError as e:
                item.status, item.message = "extract_failed", str(e)
        items.append(item)
    for text in texts:
        item = IntakeItem(index=len(items), source="text", filename=None)
        t = (text or "").strip()
        if len(t) < 30:
            item.status, item.message = "extract_failed", "文本过短，无法作为简历"
        else:
            item.text = t
        items.append(item)

    pending = [it for it in items if it.status == "pending"]
    if pending and not positions:
        for it in pending:
            it.status, it.message = "no_position", "系统内暂无岗位，无法匹配，未建档"
        pending = []

    if pending:
        sem = asyncio.Semaphore(CONCURRENCY)
        await asyncio.gather(*(_screen_one(i, it, configs, positions_block, sem) for i, it in enumerate(pending)))
        now = datetime.now()
        for it in pending:
            if it.status != "pending":
                continue
            try:
                _persist(db, it, pos_map, now)
            except Exception as e:  # 单条落库异常不影响其他条目
                db.rollback()
                it.status, it.message = "error", f"写入数据库失败：{e.__class__.__name__}"

    summary: dict[str, int] = {}
    for it in items:
        summary[it.status] = summary.get(it.status, 0) + 1
    return {"total": len(items), "summary": summary, "results": [it.to_dict() for it in items]}
