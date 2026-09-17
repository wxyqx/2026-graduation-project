"""
【这个文件是干什么的？】——「AI 智能录入」的总指挥
用户一次上传好几份 PDF 简历（或者粘贴几段文字），这个文件负责把它们变成系统里的投递记录。

整个过程是一条三步流水线：
  第 1 步（顺序做）：每份 PDF 抠出文字。抠不出来的（扫描件）当场标记失败，不影响别人。
  第 2 步（同时做）：把每份简历发给 AI，让它回答：这人叫什么？合不合格（按岗位要求）？
                    好几份一起发（异步并发），多个 AI 配置轮着用，某个 AI 出错自动换一个再试一次。
  第 3 步（顺序做）：根据 AI 的回答写数据库——找/建候选人、建投递、填 AI 成绩、自动推进。
                    一条一条写，不同时写，避免两条同时建同一个人产生冲突。

岗位怎么定？
  · 你在界面上选了具体岗位 → 只把这一个岗位给 AI，让它判断「符不符合这个岗位」，它挑不了别的岗位。
  · 你选了「自动识别」   → 把全部岗位给 AI，让它挑一个（提示词里已要求宁可不匹配也别硬凑）。

为什么第 2 步同时做、第 3 步顺序做？——等 AI 回话很慢（几秒），一起等省时间；
写数据库很快（几毫秒），排队写更安全。

隐私：简历原文和 PDF 全程只在内存里，不存数据库、不存硬盘。只有「结果」（pass/fail + 理由）会被记下来。
"""
import asyncio
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AiApiConfig, Application, Candidate, Position
from app.services import llm, prompt as prompt_svc
from app.services import state_machine as sm
from app.services.pdf import PdfExtractError, extract_text

MAX_RESUME_CHARS = 8000  # 简历太长就截到 8000 字，够 AI 判断了，还省钱（AI 按字数收费）
CONCURRENCY = 4  # 最多同时问 4 个 AI 请求，太多容易被对方限流


@dataclass
class IntakeItem:
    """流水线上的「一份简历」。从头到尾跟着它走，各步骤往里填结果，最后整个交给前端。

    @dataclass 是 Python 的省事写法：只列属性，自动生成 __init__ 等方法。
    """

    index: int  # 第几份（从 0 数）
    source: str  # 来源：file（上传的 PDF）/ text（粘贴的文字）
    filename: str | None  # 文件名（粘贴文字的没有）
    status: str = "pending"  # 处理状态，最终会变成下面 5 种之一：
    #   ok            ：成功建档
    #   duplicate     ：这个人已经投过这个岗位，没重复建
    #   no_position   ：没匹配到岗位（自动模式下 AI 说都不搭），没建档
    #   extract_failed：PDF 抠不出文字 / 不是 PDF / 文字太短
    #   error         ：AI 调用失败、或它回的格式实在看不懂
    message: str | None = None  # 给用户看的一句话说明
    candidate_id: int | None = None
    candidate_name: str | None = None
    position_id: int | None = None
    position_name: str | None = None
    application_id: int | None = None
    ai_result: str | None = None  # AI 打的分：pass / fail
    ai_comment: str | None = None  # AI 给的理由
    config_used: str | None = None  # 最终是哪个 AI 配置回答的
    # 下面几个是中间数据，repr=False 表示打印时不显示（简历原文太长）
    text: str | None = field(default=None, repr=False)  # 简历原文（只在内存里）
    parsed: dict | None = field(default=None, repr=False)  # 解析后的 AI 回答

    def to_dict(self) -> dict:
        """转成字典回给前端。把简历原文和 AI 原始回答去掉，只留结果。"""
        d = asdict(self)
        d.pop("text", None)
        d.pop("parsed", None)
        return d


async def _screen_one(
    idx: int,
    item: IntakeItem,
    configs: list[AiApiConfig],
    positions_block: str,
    fixed_position: Position | None,
    user_rules: str | None,
    pos_map: dict[int, Position],
    sem: asyncio.Semaphore,
):
    """第 2 步：把一份简历发给 AI。这是「并发」执行的——好几份同时跑这个函数。

    轮询 + 重试的规则：
      第 idx 份简历先用第 idx % n 个配置（n 个配置轮着排队，像发牌）；
      失败了就换下一个配置再试一次；两次都失败就标记 error。
      只有 1 个配置时，两次用的是同一个（相当于简单重试）。

    「失败」不只看网络错误——AI 答得看不懂（没认出通过/淘汰、JSON 不合规）也算失败，会重试一次。
    重试时会追加更严厉的格式要求，往往第二次就正常了。

    sem（信号量）像停车场的车位：只有 CONCURRENCY 个位，满了就在门口等，防止一次发太多请求。
    """
    n = len(configs)
    first = configs[idx % n]
    second = configs[(idx + 1) % n]
    last_err: str | None = None

    async with sem:  # 占一个车位
        for attempt, cfg in enumerate((first, second)):
            try:
                user_prompt = prompt_svc.build_user_prompt(
                    positions_block,
                    item.text or "",
                    fixed_position=fixed_position,
                    resume_chars=MAX_RESUME_CHARS,
                    strict=(attempt > 0),  # 第二次重试时措辞更严厉
                )
                content = await llm.chat(cfg, prompt_svc.build_system_prompt(user_rules), user_prompt)
                parsed = prompt_svc.parse_answer(content, pos_map, fixed_position)
                # 答非所问也算失败：必须能认出「通过/淘汰」；自动模式下还必须有匹配的岗位
                if parsed["result"] is None:
                    last_err = f"没能理解 AI 的结论（它回的是：{str(parsed['obj'])[:120]}）"
                    continue
                if fixed_position is None and parsed["position"] is None:
                    # 自动模式下没匹配到岗位是正常结果，不是错误，直接采用
                    pass
                item.parsed = parsed
                item.config_used = cfg.name
                return
            except (llm.LlmError, ValueError) as e:
                # LlmError：网络/接口出错；ValueError：回答里找不到合法 JSON
                last_err = str(e)
    item.status = "error"
    item.message = f"AI 回答无法识别（已重试）：{last_err}"


def _fallback_name(item: IntakeItem) -> str | None:
    """AI 没认出姓名时的备用方案：用文件名（去掉 .pdf）当姓名。粘贴的文字没有文件名，返回 None。"""
    if item.filename:
        stem = Path(item.filename).stem.strip()  # stem = 文件名去掉扩展名，"张三简历.pdf" → "张三简历"
        return stem[:255] if stem else None
    return None


def _persist(db: Session, item: IntakeItem, now: datetime) -> None:
    """第 3 步：根据 AI 的回答写数据库。一次处理一份。

    顺序是：整理回答 → 检查岗位 → 检查姓名和成绩 → 找/建候选人 → 查重 → 建投递并推进。
    任何一步不满足就设好 status 和 message 直接 return，后面的不做。
    """
    p = item.parsed or {}
    position: Position | None = p.get("position")
    result: str | None = p.get("result")
    # 姓名的清洗：AI 给的名字优先，没有就用文件名兜底
    name = (p.get("name") or "").strip()[:255] or _fallback_name(item)
    reason = (p.get("reason") or "").strip()[:500]  # 表里 ai_comment 最多 500 字

    item.candidate_name = name
    item.ai_comment = reason or None

    # ---- 检查岗位：没匹配上就不建档 ----
    if position is None:
        item.status = "no_position"
        item.message = reason or "未匹配到相关在招岗位，未建档"
        return
    item.position_id = position.id
    item.position_name = position.position_name

    # ---- 检查姓名和成绩 ----
    if not name:
        item.status = "error"
        item.message = "未能识别候选人姓名，未建档"
        return
    if result not in sm.RESULTS:
        item.status = "error"
        item.message = f"没能识别 AI 的结论：{p.get('obj')}"
        return
    item.ai_result = result

    # ---- 找候选人：同名就复用，没有就新建 ----
    candidate = db.scalar(select(Candidate).where(Candidate.name == name))
    if candidate is None:
        candidate = Candidate(name=name, remark="AI录入", create_time=now)
        db.add(candidate)
        db.flush()  # flush = 先写进数据库拿到自动分配的 ID，但还没最终确认（commit）
    item.candidate_id = candidate.id

    # ---- 查重：这个人是不是已经投过这个岗位 ----
    existing = db.scalar(
        select(Application).where(Application.can_id == candidate.id, Application.pos_id == position.id)
    )
    if existing:
        item.status = "duplicate"
        item.application_id = existing.id
        item.message = f"「{name}」已投递过「{position.position_name}」，未重复建档"
        db.commit()  # 上面可能新建了候选人，要确认保存
        return

    # ---- 建投递，并用 AI 的成绩「过第一关」----
    app = Application(
        can_id=candidate.id,
        pos_id=position.id,
        current_stage="ai",
        overall_status="pending",
        ai_comment=item.ai_comment,
        create_time=now,
        update_time=now,
    )
    sm.apply_result(app, "ai", result, now)  # pass → 进入第 2 关 resume；fail → 整体标记已淘汰
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
    extras: dict[str, str] | None = None,
    pos_id: int | None = None,
    user_rules: str | None = None,
) -> dict:
    """总入口：接口层把文件和文字交过来，这里跑完三步流水线，返回每一份的结果。

    extras    ：各岗位的额外 AI 筛选限制（前端浏览器本地存的，不入库），形如 {"1": "只要985"}。
    pos_id    ：用户在界面上指定的岗位编号；不传 = 自动识别。
    user_rules：用户在设置页写的筛选规则；不传 = 用内置默认规则。
    """
    # 准备岗位清单（AI 要从里面选，或者只用指定的那一个）
    # 暂不招的岗位不给 AI 看，也不允许指定
    positions = db.scalars(select(Position).where(Position.is_hidden == 0).order_by(Position.id)).all()
    pos_map = {p.id: p for p in positions}  # 编号 → 岗位对象，后面按编号快速查

    # 指定岗位模式：只把这一个岗位给 AI
    fixed_position: Position | None = None
    if pos_id is not None:
        fixed_position = pos_map.get(pos_id)
        if fixed_position is None:
            raise ValueError(f"指定的岗位不存在或已设为暂不招（编号 {pos_id}）")
        positions_for_ai = [fixed_position]
    else:
        positions_for_ai = positions

    positions_block = prompt_svc.positions_block(positions_for_ai, extras)  # 附加条件一并注入给 AI

    # ---- 第 1 步：抠文字，每份简历变成一个 IntakeItem ----
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

    # 只有 status 还是 pending 的（成功抠出文字的）才需要问 AI
    pending = [it for it in items if it.status == "pending"]
    if pending and not positions_for_ai:
        # 系统里一个岗位都没有，问 AI 也白问
        for it in pending:
            it.status, it.message = "no_position", "系统内暂无岗位，无法匹配，未建档"
        pending = []

    if pending:
        # ---- 第 2 步：并发问 AI ----
        # asyncio.gather：把好几个「等 AI 回话」的任务一起启动，全部结束后再往下走
        sem = asyncio.Semaphore(CONCURRENCY)
        await asyncio.gather(
            *(
                _screen_one(i, it, configs, positions_block, fixed_position, user_rules, pos_map, sem)
                for i, it in enumerate(pending)
            )
        )

        # ---- 第 3 步：顺序写库 ----
        now = datetime.now()
        for it in pending:
            if it.status != "pending":
                continue  # 第 2 步已经标记 error 的跳过
            try:
                _persist(db, it, now)
            except Exception as e:  # 单条落库异常不影响其他条目
                db.rollback()  # 把这一条没确认的改动全撤掉，数据库回到干净状态
                it.status, it.message = "error", f"写入数据库失败：{e.__class__.__name__}"

    # 统计各状态各有几条，方便前端显示「成功 3 条，重复 1 条……」
    summary: dict[str, int] = {}
    for it in items:
        summary[it.status] = summary.get(it.status, 0) + 1
    return {"total": len(items), "summary": summary, "results": [it.to_dict() for it in items]}
