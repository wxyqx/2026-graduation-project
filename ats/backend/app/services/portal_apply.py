"""
【候选人投递的 AI 首筛】

与管理端「AI 智能录入」的区别：
  · 岗位是候选人自己选的，固定不变，不用 AI 挑岗位
  · 候选人是登录账号绑定的，不靠 AI 认名字
  · 解析失败 / 没配置 / AI 报错 → 一律降级为「待人工筛选」，投递不丢

返回 screening 三种值（前端文案用）：
  ai_pass        AI 初筛通过 → 自动进入简历筛选
  ai_fail        AI 初筛未通过 → 标记已淘汰
  pending_review 转人工 → 停在 AI 筛选关，等 HR 处理
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AiApiConfig, Position
from app.services import llm, prompt
from app.services import settings as settings_svc
from app.services.pdf import PdfExtractError, extract_text

MESSAGES = {
    "ai_pass": "简历已通过初筛，进入简历筛选阶段",
    "ai_fail": "很遗憾，本次初筛未通过",
    "pending_review": "简历已提交，HR 会尽快查看",
}


def enabled_configs(db: Session) -> list[AiApiConfig]:
    """所有启用中的 AI 配置（v3.15 起是系统级，不按人隔离）。"""
    return db.scalars(select(AiApiConfig).where(AiApiConfig.is_enabled == 1).order_by(AiApiConfig.id)).all()


async def screen_resume(db: Session, position: Position, data: bytes) -> dict:
    """对一份简历做首筛。任何异常都不抛，统一返回降级结果。"""
    try:
        text = extract_text(data)
    except PdfExtractError:
        return {"result": None, "comment": None, "screening": "pending_review", "reason": "extract_failed"}

    configs = enabled_configs(db)
    if not configs:
        return {"result": None, "comment": None, "screening": "pending_review", "reason": "no_config"}

    # 系统级的筛选规则（技术管理员维护；没有就用默认规则）
    rules = settings_svc.get_system_prompt(db)
    block = prompt.positions_block([position])
    last_err = ""
    for cfg in configs[:3]:
        try:
            content = await llm.chat(
                cfg,
                prompt.build_system_prompt(rules),
                prompt.build_user_prompt(block, text, fixed_position=position),
            )
            parsed = prompt.parse_answer(content, {position.id: position}, position)
        except Exception as e:
            last_err = str(e)
            continue
        if parsed["result"] in ("pass", "fail"):
            result = parsed["result"]
            comment = (parsed.get("reason") or "").strip()[:500] or None
            return {
                "result": result,
                "comment": comment,
                "screening": "ai_pass" if result == "pass" else "ai_fail",
                "reason": "ok",
                "config_used": cfg.name,
            }
        last_err = "AI 回答里没有可识别的结论"
    return {"result": None, "comment": None, "screening": "pending_review", "reason": last_err or "unknown"}
