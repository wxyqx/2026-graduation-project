"""
【这个文件是干什么的？】
读写 App_Setting 表里那些「键值对」式的系统设置。目前只用到一项：AI 筛选提示词。

为什么单独一个文件？因为读写设置的地方不止一处（AI 录入要读提示词、设置接口要读写提示词），
集中在这里，逻辑不会两处写得不一样。
"""
import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AiApiConfig, AppSetting, User


def get_setting(db: Session, user_id: int, key: str) -> str | None:
    """取某个用户的某项设置；没有就返回 None。"""
    row = db.scalar(select(AppSetting).where(AppSetting.user_id == user_id, AppSetting.setting_key == key))
    return row.setting_value if row else None


def get_system_admin(db: Session) -> User | None:
    """系统级设置挂在哪个技术管理员名下：取编号最小的 admin。"""
    return db.scalar(select(User).where(User.role == "admin").order_by(User.id))


def get_system_prompt(db: Session) -> str | None:
    """系统级的 AI 筛选规则。

    优先取技术管理员（编号最小的 admin）的设置；没有就退回第一个 AI 配置所属用户的旧设置，
    再没有就返回 None（AI 服务层会用默认规则）。
    """
    admin = get_system_admin(db)
    if admin is not None:
        value = get_setting(db, admin.id, "ai_prompt")
        if value:
            return value
    cfg = db.scalar(select(AiApiConfig).order_by(AiApiConfig.id))
    if cfg is not None:
        return get_setting(db, cfg.user_id, "ai_prompt")
    return None


def set_setting(db: Session, user_id: int, key: str, value: str | None) -> None:
    """保存某项设置。值传空（None 或空字符串）等于删掉这项设置。"""
    row = db.scalar(select(AppSetting).where(AppSetting.user_id == user_id, AppSetting.setting_key == key))
    text = (value or "").strip()
    if not text:
        # 清空设置 = 删掉记录，之后读出来就是 None（走默认逻辑）
        if row:
            db.delete(row)
            db.commit()
        return
    if row:
        row.setting_value = text
        row.update_time = datetime.now()
    else:
        db.add(AppSetting(user_id=user_id, setting_key=key, setting_value=text, update_time=datetime.now()))
    db.commit()


# ---------- 阶段文案的手动改写（存成一条 JSON 设置）----------

STAGE_NOTES_KEY = "stage_notes"


def get_stage_notes(db: Session, user_id: int) -> dict[str, str]:
    """取手动改写的阶段文案，形如 {"82": "待offer回传"}。没有或格式坏了都返回空字典。"""
    raw = get_setting(db, user_id, STAGE_NOTES_KEY)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items() if str(v).strip()}
    except (ValueError, TypeError):
        pass
    return {}


def set_stage_note(db: Session, user_id: int, app_id: int, note: str | None) -> dict[str, str]:
    """保存某条投递的手动阶段文案；note 传空 = 恢复自动（从记录里删掉）。返回保存后的全量映射。"""
    notes = get_stage_notes(db, user_id)
    key = str(app_id)
    text = (note or "").strip()
    if text:
        notes[key] = text
    else:
        notes.pop(key, None)
    # 全空就把整条设置删掉，保持干净
    set_setting(db, user_id, STAGE_NOTES_KEY, json.dumps(notes, ensure_ascii=False) if notes else "")
    return notes

# ---------- 候选人表单可见阶段（系统级设置，挂技术管理员名下）----------

PORTAL_FORM_STAGE_KEY = "portal_form_stage"
PORTAL_FORM_TYPES = ("position", "assessment")  # 岗位申请表 / 职业底色图
DEFAULT_FORM_STAGE = "pro"  # 默认专业面起可见


def get_portal_form_stage(db: Session) -> dict[str, str]:
    """候选人能从哪一关起看到岗位申请表/职业底色图。没有配置或格式坏了都返回默认值。"""
    admin = get_system_admin(db)
    raw = get_setting(db, admin.id, PORTAL_FORM_STAGE_KEY) if admin else None
    cfg: dict[str, str] = {}
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                cfg = {k: v for k, v in data.items() if k in PORTAL_FORM_TYPES and v}
        except (ValueError, TypeError):
            pass
    return {k: cfg.get(k, DEFAULT_FORM_STAGE) for k in PORTAL_FORM_TYPES}


def set_portal_form_stage(db: Session, cfg: dict[str, str]) -> dict[str, str]:
    """保存表单可见阶段。值必须合法；传空字符串等于恢复默认。返回保存后的完整配置。"""
    from app.services.state_machine import STAGES

    admin = get_system_admin(db)
    if admin is None:
        raise ValueError("系统里还没有技术管理员账号")
    clean = {k: v for k, v in cfg.items() if k in PORTAL_FORM_TYPES and v in STAGES}
    text = json.dumps(clean, ensure_ascii=False) if clean else ""
    set_setting(db, admin.id, PORTAL_FORM_STAGE_KEY, text)
    return get_portal_form_stage(db)

# ---------- 通过/淘汰通知模板（关卡通过时、以及被淘汰时发给候选人）----------

STAGE_NOTICE_KEY = "stage_notice"
# onboard（入职）不在 7 关流程里：触发条件是 HR 回传盖章文件，模板体系与其他关一致
# eliminated（淘汰）：触发条件是投递被打 fail 且就此淘汰（overall_status 变 fail），模板体系一致
STAGE_NOTICE_STAGES = ("phone", "test", "pro", "hr", "final", "onboard", "eliminated")

# 默认模板（占位）：可用的占位符 {候选人} {岗位} {关卡}；淘汰为正式版，其余 HR 可在设置页自行修改
DEFAULT_STAGE_NOTICE = {
    "phone": {
        "enabled": True,
        "title": "【占位】恭喜通过电话沟通",
        "body": "（通知模板占位）亲爱的 {候选人}：恭喜您通过「{岗位}」的{关卡}，请留意后续安排。",
    },
    "test": {
        "enabled": True,
        "title": "【占位】恭喜通过笔试",
        "body": "（通知模板占位）亲爱的 {候选人}：恭喜您通过「{岗位}」的{关卡}，请留意后续安排。",
    },
    "pro": {
        "enabled": True,
        "title": "【占位】恭喜通过专业面",
        "body": "（通知模板占位）亲爱的 {候选人}：恭喜您通过「{岗位}」的{关卡}，请留意后续安排。",
    },
    "hr": {
        "enabled": True,
        "title": "【占位】恭喜通过 HR 面",
        "body": "（通知模板占位）亲爱的 {候选人}：恭喜您通过「{岗位}」的{关卡}，请留意后续安排。",
    },
    "final": {
        "enabled": True,
        "title": "【占位】恭喜通过终面",
        "body": "（通知模板占位）亲爱的 {候选人}：恭喜您通过「{岗位}」的{关卡}，请留意后续安排。",
    },
    "onboard": {
        "enabled": True,
        "title": "【占位】入职通知",
        "body": "（通知模板占位）亲爱的 {候选人}：恭喜您正式加入「{岗位}」！盖章文件已回传，请到「文件」页查看下载，并按约定时间办理入职。",
    },
    "eliminated": {
        "enabled": True,
        "title": "【应聘结果】感谢参与，期待再会",
        "body": "亲爱的 <b>{候选人}</b>：<br><br>感谢您应聘「<b>{岗位}</b>」并参与我们的招聘流程。经综合评估，很遗憾此次未能通过<b>{关卡}</b>。这更多是岗位匹配度的考量，并非对您能力的否定，希望您早日找到更合适的舞台。<br><br>温馨提醒：本通知发出后，您的登录账号将保留 <b>2 天</b>，期间可登录查看历史消息与文件，逾期登录通道将关闭。再次感谢您的时间与信任！",
    },
}


def get_stage_notice(db: Session) -> dict[str, dict]:
    """各关通过通知的模板与开关。没有配置的关用默认占位模板。"""
    admin = get_system_admin(db)
    raw = get_setting(db, admin.id, STAGE_NOTICE_KEY) if admin else None
    saved: dict[str, dict] = {}
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                saved = {k: v for k, v in data.items() if k in STAGE_NOTICE_STAGES and isinstance(v, dict)}
        except (ValueError, TypeError):
            pass
    out = {}
    for stage in STAGE_NOTICE_STAGES:
        entry = dict(DEFAULT_STAGE_NOTICE[stage])
        entry.update(saved.get(stage, {}))
        entry["enabled"] = bool(entry.get("enabled", True))
        out[stage] = entry
    return out


def set_stage_notice(db: Session, cfg: dict[str, dict]) -> dict[str, dict]:
    """保存各关通过/淘汰通知模板。**合并式**：只更新请求里出现的关卡，没传的关保持原样。

    （整份替换曾经两次把没传的关抹成默认——部分保存必须安全。清空某关内容请显式传空值。）
    """
    admin = get_system_admin(db)
    if admin is None:
        raise ValueError("系统里还没有技术管理员账号")
    clean = get_stage_notice(db)
    for stage in STAGE_NOTICE_STAGES:
        if stage not in cfg:
            continue  # 没传的关不动
        entry = cfg.get(stage) or {}
        clean[stage] = {
            "enabled": bool(entry.get("enabled", True)),
            "title": str(entry.get("title") or "").strip()[:100],
            "body": str(entry.get("body") or "")[:5000],
        }
    set_setting(db, admin.id, STAGE_NOTICE_KEY, json.dumps(clean, ensure_ascii=False))
    return get_stage_notice(db)


# ---------- 隐私政策与 AI 筛选告知（系统级设置，挂技术管理员名下）----------

PRIVACY_KEY = "privacy_policy"
DEFAULT_PRIVACY_VERSION = "2026-10-26.1"
DEFAULT_PRIVACY_TEXT = """《候选人个人信息处理与 AI 筛选告知书》

在您使用本招聘系统前，请阅读并了解以下内容：

1. 信息收集：投递与招聘过程中，我们会收集您的姓名、手机号、邮箱、出生年月、简历内容，
   以及您填写的个人资料表、面试登记表、职业底色图等信息。

2. 使用目的：上述信息仅用于本次招聘的资格评估、面试安排、录用沟通与入职办理，
   不用于任何其他目的，不对外提供。

3. AI 辅助筛选告知：您的简历会由 AI 程序进行辅助解读与岗位匹配度评估，
   评估结果供招聘人员参考，录用决定由人工作出。

4. 保留与删除：被淘汰的候选人，账号将保留 2 天供查看历史通知，之后登录通道关闭；
   相关资料保留 90 天后不再对任何人展示。您有权要求更正或删除您的个人信息，
   可通过招聘联系人或页面上的联系方式提出。

5. 同意：勾选「同意」即表示您已阅读并理解上述内容，同意我们按所述方式处理您的个人信息。
   拒绝同意将无法使用在线投递功能。
"""


def get_privacy_policy(db: Session) -> dict:
    """当前生效的隐私政策文案与版本；技术端没改过就用内置默认。"""
    admin = get_system_admin(db)
    raw = get_setting(db, admin.id, PRIVACY_KEY) if admin else None
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and data.get("text"):
                return {"version": data.get("version") or DEFAULT_PRIVACY_VERSION, "text": data["text"]}
        except (ValueError, TypeError):
            pass
    return {"version": DEFAULT_PRIVACY_VERSION, "text": DEFAULT_PRIVACY_TEXT}


def set_privacy_policy(db: Session, text: str) -> dict:
    """技术端保存政策文案；版本号按保存时间自动生成（候选人同意记录引用它）。"""
    admin = get_system_admin(db)
    if admin is None:
        raise ValueError("系统里还没有技术管理员账号")
    clean = (text or "").strip()
    if not clean:
        raise ValueError("政策文案不能为空")
    version = datetime.now().strftime("%Y%m%d.%H%M%S")
    set_setting(db, admin.id, PRIVACY_KEY, json.dumps({"version": version, "text": clean}, ensure_ascii=False))
    return get_privacy_policy(db)


# ---------- 淘汰申诉联系方式（系统级，占位符 {申诉联系方式} 用）----------

APPEAL_CONTACT_KEY = "appeal_contact"
DEFAULT_APPEAL_CONTACT = "如对结果有异议，请通过招聘页面公示的联系方式与招聘负责人联系申诉。"


def get_appeal_contact(db: Session) -> str:
    admin = get_system_admin(db)
    raw = get_setting(db, admin.id, APPEAL_CONTACT_KEY) if admin else None
    return (raw or "").strip() or DEFAULT_APPEAL_CONTACT


def set_appeal_contact(db: Session, text: str) -> str:
    admin = get_system_admin(db)
    if admin is None:
        raise ValueError("系统里还没有技术管理员账号")
    set_setting(db, admin.id, APPEAL_CONTACT_KEY, (text or "").strip())
    return get_appeal_contact(db)
