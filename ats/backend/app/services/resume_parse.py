"""
【简历字段识别】从简历文本里抽姓名 / 电话 / 邮箱 / 出生年月，供手动建档时自动填充。

与 AI 录入（ai_screen：认人 + 配岗 + 筛选 + 建档）是两回事：这里只识别、不建任何数据，
也不做筛选判断。电话 / 邮箱用正则（稳定、不花 AI 额度）；姓名 / 出生年月优先问 AI，
AI 不可用或没识别到时回退——姓名用文件名，出生年月用「出生」字样的正则。
"""
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AiApiConfig
from app.services import llm
from app.services.phone import is_valid_phone
from app.services.prompt import _first_key, extract_json

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# 手机号允许分隔符穿插（138 0013 8000 / 138-0013-8000）：11 位数字、每位之间最多一个空格或横线
_PHONE_RE = re.compile(r"(?<!\d)1[3-9](?:[ \-]?\d){9}(?!\d)")
# 出生年月只认带「出生 / 生日」字样的，避免把「2020.06 入职」这类工作年份误当生日
_BIRTH_RE = re.compile(r"(?:出生|生日)[^\d]{0,8}((?:19|20)\d{2})\s*[年./\-]\s*(\d{1,2})")

_NAME_KEYS = ("name", "姓名", "候选人姓名", "candidate_name")
_BIRTH_KEYS = ("birth", "出生年月", "出生日期", "生日", "birth_date", "birth_year_month")

_EXTRACT_SYSTEM_PROMPT = (
    "你是简历信息抽取助手。从简历文本里找出候选人的姓名和出生年月，"
    '只输出一个 JSON 对象：{"name": "姓名", "birth": "YYYY-MM"}。'
    "出生年月统一成 YYYY-MM（只有年份就填 YYYY）；找不到的字段填空字符串，"
    "不要输出任何解释或代码块标记。"
)


def extract_email(text: str) -> str | None:
    m = _EMAIL_RE.search(text)
    return m.group(0).strip(".").lower() if m else None


def extract_phone(text: str) -> str | None:
    for m in _PHONE_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if is_valid_phone(digits):
            return digits
    return None


def _normalize_birth(raw: str) -> str | None:
    """各种写法归一成 YYYY-MM：1999-06 / 1999.6 / 1999年6月 / 1999年6月15日 / 1999/06/15。"""
    m = re.search(r"((?:19|20)\d{2})\s*[年./\-]\s*(\d{1,2})", str(raw))
    if not m:
        m = re.search(r"((?:19|20)\d{2})", str(raw))
        if not m:
            return None
        year, month = m.group(1), None
    else:
        year, month = m.group(1), m.group(2)
    if month is not None and not 1 <= int(month) <= 12:
        return None
    return f"{year}-{int(month):02d}" if month else year


def extract_birth(text: str) -> str | None:
    m = _BIRTH_RE.search(text)
    return _normalize_birth(f"{m.group(1)}-{m.group(2)}") if m else None


def _fallback_name(filename: str) -> str | None:
    """AI 没认出姓名时用文件名兜底：「张三简历.pdf」→「张三简历」（与 AI 录入同口径）。"""
    stem = filename.rsplit(".", 1)[0].strip() if "." in filename else filename.strip()
    return stem or None


async def _ai_name_birth(text: str, configs: list[AiApiConfig]) -> tuple[str | None, str | None]:
    """问 AI 要姓名和出生年月；一个配置失败换下一个，全失败就返回 (None, None)。"""
    for cfg in configs:
        try:
            content = await llm.chat(cfg, _EXTRACT_SYSTEM_PROMPT, text)
            obj = extract_json(content)
            name, birth = _first_key(obj, _NAME_KEYS), _first_key(obj, _BIRTH_KEYS)
            name = (str(name[1]).strip() if name and name[1] else "") or None
            birth = _normalize_birth(birth[1]) if birth and birth[1] else None
            if name or birth:
                return name, birth
        except (llm.LlmError, ValueError):
            continue  # 网络失败 / 回答格式不对，换下一个配置
    return None, None


async def parse_resume(db: Session, text: str, filename: str) -> dict:
    """识别入口：返回 {name, phone, email, birth, used_ai}。调用方负责先抽出文本。"""
    configs = db.scalars(
        select(AiApiConfig).where(AiApiConfig.is_enabled == 1).order_by(AiApiConfig.id)
    ).all()
    name = birth = None
    if configs:
        name, birth = await _ai_name_birth(text[:4000], configs)
    if not birth:
        birth = extract_birth(text)
    if not name:
        name = _fallback_name(filename)
    return {
        "name": name,
        "phone": extract_phone(text),
        "email": extract_email(text),
        "birth": birth,
        "used_ai": bool(configs),
    }
