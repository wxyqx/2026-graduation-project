"""
【可配置表单服务】

两种模板：
  profile  个人资料表：全局一份，每个候选人一份答卷
  position 岗位申请表：绑定某个岗位，每次投递一份答卷

规则：
  · 同一范围（个人资料表 / 同一个岗位）同时只能有一个启用中的模板
  · 改字段时 Version +1；已提交的答卷保留当时的版本号，不会因为改模板丢答案
  · 字段只软删除（Is_Active=0），历史答案仍能显示
  · 答案统一存文本；多选/复选存 JSON 数组
"""
import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Application,
    Candidate,
    FormAnswer,
    FormField,
    FormSubmission,
    FormTemplate,
    Position,
)
from app.services.phone import is_valid_phone, normalize_phone
from app.services.state_machine import STAGES as ALL_STAGES

FIELD_TYPES = {"text", "textarea", "number", "date", "daterange", "select", "radio", "checkbox", "email", "phone", "section", "color"}
SCOPES = {"profile", "position", "assessment"}
KEY_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{0,49}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class FormError(ValueError):
    """表单配置或答案不合规。"""


# ======================================================================
# 模板 / 字段
# ======================================================================
def _options_of(field: FormField) -> list[str]:
    try:
        value = json.loads(field.options_json or "[]")
        return [str(x) for x in value] if isinstance(value, list) else []
    except (ValueError, TypeError):
        return []


def _field_out(f: FormField) -> dict:
    return {
        "id": f.id,
        "field_key": f.field_key,
        "label": f.label,
        "field_type": f.field_type,
        "required": bool(f.required),
        "options": _options_of(f) or None,
        "placeholder": f.placeholder,
        "help_text": f.help_text,
        "max_length": f.max_length,
        "sort_order": f.sort_order,
        "is_active": bool(f.is_active),
    }


def _normalize_fields(fields) -> list[dict]:
    """把前端传来的字段列表校验并整理成字典；重复 key 或类型不对直接报错。"""
    out: list[dict] = []
    seen: set[str] = set()
    for i, f in enumerate(fields):
        key = (getattr(f, "field_key", "") or "").strip()
        label = (getattr(f, "label", "") or "").strip()
        ftype = (getattr(f, "field_type", "") or "").strip()
        if not KEY_RE.match(key):
            raise FormError(f"字段键「{key}」不合法：只能用字母开头，包含字母、数字、下划线，最长 50")
        if key in seen:
            raise FormError(f"字段键「{key}」重复")
        seen.add(key)
        if not label:
            raise FormError(f"字段「{key}」缺少显示名")
        if ftype not in FIELD_TYPES:
            raise FormError(f"字段「{label}」的类型「{ftype}」不支持")
        options = [str(x).strip() for x in (getattr(f, "options", None) or []) if str(x).strip()]
        if ftype in {"select", "radio", "checkbox", "color"} and not options:
            raise FormError(f"字段「{label}」需要至少一个选项")
        max_length = getattr(f, "max_length", None)
        out.append(
            {
                "field_key": key,
                "label": label[:100],
                "field_type": ftype,
                "required": 0 if ftype == "section" else (1 if getattr(f, "required", False) else 0),
                "options_json": json.dumps(options, ensure_ascii=False) if options else None,
                "placeholder": (getattr(f, "placeholder", None) or None),
                "help_text": (getattr(f, "help_text", None) or None),
                "max_length": max_length,
                "sort_order": getattr(f, "sort_order", i) or i,
                "is_active": 0 if getattr(f, "is_active", True) is False else 1,
            }
        )
    return out


def _active_conflict(db: Session, scope: str, position_id: int | None, exclude_id: int | None = None) -> FormTemplate | None:
    stmt = select(FormTemplate).where(FormTemplate.scope == scope, FormTemplate.is_active == 1)
    if position_id is None:
        stmt = stmt.where(FormTemplate.position_id.is_(None))
    else:
        stmt = stmt.where(FormTemplate.position_id == position_id)
    if exclude_id is not None:
        stmt = stmt.where(FormTemplate.id != exclude_id)
    return db.scalar(stmt)


def template_out(db: Session, t: FormTemplate, *, detail: bool = False) -> dict:
    position_name = None
    if t.position_id is not None:
        p = db.get(Position, t.position_id)
        position_name = p.position_name if p else None
    active_fields = [f for f in t.fields if f.is_active]
    data = {
        "id": t.id,
        "name": t.name,
        "scope": t.scope,
        "position_id": t.position_id,
        "position_name": position_name,
        "description": t.description,
        "version": t.version,
        "is_active": bool(t.is_active),
        "field_count": len(active_fields),
        "create_time": t.create_time,
        "update_time": t.update_time,
    }
    if detail:
        data["fields"] = [_field_out(f) for f in t.fields]
    return data


def get_active_template(db: Session, scope: str, position_id: int | None = None) -> FormTemplate | None:
    """取某个范围当前启用中的模板（个人资料表 / 某岗位的申请表）。"""
    stmt = select(FormTemplate).where(FormTemplate.scope == scope, FormTemplate.is_active == 1)
    if position_id is None:
        stmt = stmt.where(FormTemplate.position_id.is_(None))
    else:
        stmt = stmt.where(FormTemplate.position_id == position_id)
    return db.scalar(stmt.order_by(FormTemplate.id.desc()))


def list_templates(db: Session, scope: str | None = None, position_id: int | None = None, include_inactive: bool = True) -> list[dict]:
    stmt = select(FormTemplate).order_by(FormTemplate.id.desc())
    if scope:
        if scope not in SCOPES:
            raise FormError("scope 只能是 profile、position 或 assessment")
        stmt = stmt.where(FormTemplate.scope == scope)
    if position_id is not None:
        stmt = stmt.where(FormTemplate.position_id == position_id)
    if not include_inactive:
        stmt = stmt.where(FormTemplate.is_active == 1)
    return [template_out(db, t) for t in db.scalars(stmt).all()]


def get_template_or_404(db: Session, template_id: int) -> FormTemplate:
    t = db.get(FormTemplate, template_id)
    if t is None:
        raise LookupError("表单模板不存在")
    return t


def purge_template(db: Session, t: FormTemplate) -> None:
    """物理删除模板（仅限已停用且没有任何答卷的；有答卷的保留历史，不允许删）。"""
    if t.is_active:
        raise FormError("启用中的模板请先停用再删除")
    has_submission = db.scalar(
        select(func.count()).select_from(FormSubmission).where(FormSubmission.template_id == t.id)
    )
    if has_submission:
        raise FormError("该模板已有答卷，为保留历史记录不能删除")
    for f in db.scalars(select(FormField).where(FormField.template_id == t.id)).all():
        db.delete(f)
    db.delete(t)


def create_template(db: Session, body, user_id: int | None) -> FormTemplate:
    name = (body.name or "").strip()
    if not name:
        raise FormError("模板名不能为空")
    if body.scope not in SCOPES:
        raise FormError("scope 只能是 profile、position 或 assessment")
    position_id = body.position_id
    if body.scope == "position":
        # position_id 为空 = 通用岗位申请表，对全部岗位生效；指定岗位则只对该岗位生效
        if position_id is not None and db.get(Position, position_id) is None:
            raise FormError("岗位不存在")
    elif position_id is not None:
        raise FormError("个人资料表 / 职业底色图不能绑定岗位")
    if _active_conflict(db, body.scope, position_id) is not None:
        raise FormError("该范围已有启用中的表单模板，请先停用旧模板")

    now = datetime.now()
    t = FormTemplate(
        name=name[:100],
        scope=body.scope,
        position_id=position_id,
        description=(body.description or None),
        version=1,
        is_active=1,
        created_by=user_id,
        create_time=now,
        update_time=now,
    )
    db.add(t)
    db.flush()
    apply_fields(db, t, body.fields, bump_version=False)
    return t


def update_template_meta(db: Session, t: FormTemplate, body) -> FormTemplate:
    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise FormError("模板名不能为空")
        t.name = name[:100]
    if "description" in getattr(body, "model_fields_set", set()):
        t.description = body.description or None
    if body.is_active is not None:
        if body.is_active:
            other = _active_conflict(db, t.scope, t.position_id, exclude_id=t.id)
            if other is not None:
                raise FormError(f"已有启用中的模板「{other.name}」，请先停用它")
        t.is_active = 1 if body.is_active else 0
    t.update_time = datetime.now()
    return t


def apply_fields(db: Session, t: FormTemplate, fields, *, bump_version: bool = True) -> FormTemplate:
    """批量保存字段：按 field_key 增量更新；未出现的字段软删除。"""
    specs = _normalize_fields(fields)
    existing = {f.field_key: f for f in t.fields}
    changed = False

    for spec in specs:
        f = existing.get(spec["field_key"])
        if f is None:
            f = FormField(template_id=t.id, **spec)
            db.add(f)
            changed = True
        else:
            for attr, value in spec.items():
                if getattr(f, attr) != value:
                    setattr(f, attr, value)
                    changed = True

    incoming = {s["field_key"] for s in specs}
    for key, f in existing.items():
        if key not in incoming and f.is_active:
            f.is_active = 0
            changed = True

    if changed:
        if bump_version:
            t.version += 1
        t.update_time = datetime.now()
    db.flush()
    return t


# ======================================================================
# 答卷
# ======================================================================
def _active_fields(t: FormTemplate) -> list[FormField]:
    return sorted([f for f in t.fields if f.is_active], key=lambda f: (f.sort_order, f.id))


def validate_answers(t: FormTemplate, answers: dict, *, enforce_required: bool = True) -> dict[str, str | None]:
    """校验答案并返回 {field_key: 存储值}；不合规抛 FormError。

    enforce_required=False 用于「保存草稿」：允许必填项暂时为空，但填了的内容仍要合法。
    """
    stored: dict[str, str | None] = {}
    for f in _active_fields(t):
        if f.field_type == "section":
            # 分组标题只用于展示，不收集答案
            continue
        raw = answers.get(f.field_key)
        options = _options_of(f)

        if f.field_type in {"checkbox", "daterange"}:
            if raw is None or raw == "":
                values: list[str] = []
            elif isinstance(raw, list):
                values = [str(x).strip() for x in raw if str(x).strip()]
            elif isinstance(raw, str):
                s = raw.strip()
                if s.startswith("["):
                    try:
                        parsed = json.loads(s)
                        values = [str(x).strip() for x in parsed] if isinstance(parsed, list) else []
                    except ValueError:
                        values = []
                else:
                    values = [x.strip() for x in s.split(",") if x.strip()]
            else:
                values = [str(raw)]
            if f.required and not values and enforce_required:
                raise FormError(f"「{f.label}」是必填项")
            if f.field_type == "checkbox":
                bad = [v for v in values if options and v not in options]
                if bad:
                    raise FormError(f"「{f.label}」包含无效选项：{bad[0]}")
            else:
                # daterange：恰好是「开始, 结束」两个 YYYY-MM-DD
                bad = [v for v in values if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v)]
                if bad:
                    raise FormError(f"「{f.label}」的日期格式应为 YYYY-MM-DD")
                if f.required and enforce_required and len(values) != 2:
                    raise FormError(f"「{f.label}」需要开始和结束两个日期")
            stored[f.field_key] = json.dumps(values, ensure_ascii=False) if values else None
            continue

        s = "" if raw is None else str(raw).strip()
        if not s:
            if f.required and enforce_required:
                raise FormError(f"「{f.label}」是必填项")
            stored[f.field_key] = None
            continue

        if f.field_type in {"select", "radio", "color"} and options and s not in options:
            raise FormError(f"「{f.label}」的选项不合法")
        if f.field_type == "number":
            try:
                Decimal(s)
            except InvalidOperation:
                raise FormError(f"「{f.label}」必须是数字")
        if f.field_type == "date":
            try:
                datetime.strptime(s[:10], "%Y-%m-%d")
            except ValueError:
                raise FormError(f"「{f.label}」日期格式应为 YYYY-MM-DD")
            s = s[:10]
        if f.field_type == "email" and not EMAIL_RE.match(s):
            raise FormError(f"「{f.label}」不是合法邮箱")
        if f.field_type == "phone":
            s = normalize_phone(s) or ""
            if not is_valid_phone(s):
                raise FormError(f"「{f.label}」不是合法手机号")
        if f.max_length and len(s) > f.max_length:
            raise FormError(f"「{f.label}」不能超过 {f.max_length} 个字")
        stored[f.field_key] = s
    return stored


def get_submission(db: Session, template_id: int, candidate_id: int, application_id: int | None) -> FormSubmission | None:
    stmt = select(FormSubmission).where(
        FormSubmission.template_id == template_id, FormSubmission.candidate_id == candidate_id
    )
    if application_id is None:
        stmt = stmt.where(FormSubmission.application_id.is_(None))
    else:
        stmt = stmt.where(FormSubmission.application_id == application_id)
    return db.scalar(stmt)


def save_submission(
    db: Session,
    *,
    t: FormTemplate,
    candidate_id: int,
    application_id: int | None,
    answers: dict,
    submit: bool,
) -> FormSubmission:
    stored = validate_answers(t, answers or {}, enforce_required=submit)
    now = datetime.now()
    sub = get_submission(db, t.id, candidate_id, application_id)
    if sub is None:
        sub = FormSubmission(
            template_id=t.id,
            candidate_id=candidate_id,
            application_id=application_id,
            template_version=t.version,
            status="draft",
            update_time=now,
        )
        db.add(sub)
        db.flush()

    sub.template_version = t.version
    sub.update_time = now
    if submit:
        sub.status = "submitted"
        sub.submit_time = now
    elif sub.status not in ("submitted",):
        sub.status = "draft"

    existing = {a.field_id: a for a in sub.answers}
    for f in _active_fields(t):
        val = stored.get(f.field_key)
        a = existing.get(f.id)
        if a is not None:
            a.value_text = val
            a.field_key = f.field_key
        elif val is not None:
            db.add(FormAnswer(submission_id=sub.id, field_id=f.id, field_key=f.field_key, value_text=val))
    db.flush()
    return sub


def _decode(f: FormField, text: str | None):
    if text is None:
        return None
    if f.field_type in {"checkbox", "daterange"}:
        try:
            value = json.loads(text)
            return value if isinstance(value, list) else []
        except ValueError:
            return []
    return text


def submission_out(db: Session, sub: FormSubmission, *, with_candidate: bool = False, active_only: bool = False) -> dict:
    t = db.get(FormTemplate, sub.template_id)
    if t is None:
        raise FormError("表单模板不存在")
    fields = {f.id: f for f in t.fields}
    answers: dict[str, object] = {}
    items: list[dict] = []
    for a in sorted(sub.answers, key=lambda x: (fields[x.field_id].sort_order if x.field_id in fields else 0, x.id)):
        f = fields.get(a.field_id)
        if f is None:
            continue
        if active_only and not f.is_active:
            continue
        value = _decode(f, a.value_text)
        answers[f.field_key] = value
        items.append(
            {
                "field_key": f.field_key,
                "label": f.label,
                "field_type": f.field_type,
                "value": value,
                "is_active": bool(f.is_active),
            }
        )
    candidate_name = None
    if with_candidate:
        c = db.get(Candidate, sub.candidate_id)
        candidate_name = c.name if c else None
    return {
        "id": sub.id,
        "template_id": sub.template_id,
        "template_name": t.name,
        "scope": t.scope,
        "candidate_id": sub.candidate_id,
        "candidate_name": candidate_name,
        "application_id": sub.application_id,
        "template_version": sub.template_version,
        "status": sub.status,
        "submit_time": sub.submit_time,
        "update_time": sub.update_time,
        "answers": answers,
        "items": items,
    }


def list_submissions(
    db: Session, *, candidate_id: int | None = None, application_id: int | None = None
) -> list[FormSubmission]:
    stmt = select(FormSubmission).order_by(FormSubmission.update_time.desc())
    if candidate_id is not None:
        stmt = stmt.where(FormSubmission.candidate_id == candidate_id)
    if application_id is not None:
        stmt = stmt.where(FormSubmission.application_id == application_id)
    return db.scalars(stmt).all()


# ======================================================================
# 候选人端
# ======================================================================
def _form_stage_cfg(db: Session) -> dict[str, str]:
    """表单可见阶段配置；设置读不到时用默认（专业面起）。"""
    try:
        from app.services import settings as settings_svc

        return settings_svc.get_portal_form_stage(db)
    except Exception:
        return {"position": "pro", "assessment": "pro"}


def _stage_reached(app: Application, threshold: str) -> bool:
    """这次投递是否已经走到 threshold 这一关（录用视为全部走完）。"""
    if threshold not in ALL_STAGES:
        return True
    if app.overall_status == "pass":
        return True
    cur = app.current_stage
    if cur not in ALL_STAGES:
        return False
    return ALL_STAGES.index(cur) >= ALL_STAGES.index(threshold)


def ensure_template_applicable(db: Session, t: FormTemplate, candidate_id: int, application_id: int | None) -> Application | None:
    """检查这个模板该不该由这个候选人在这次投递里填写。"""
    if not t.is_active:
        raise FormError("该表单已停用")
    if t.scope in {"profile", "assessment"}:
        if application_id is not None:
            raise FormError("该表单不需要 application_id")
        if t.scope == "assessment" and not _assessment_visible(db, candidate_id):
            raise FormError("还没有到可以填写这份表单的阶段")
        return None
    if application_id is None:
        raise FormError("岗位申请表需要提供 application_id")
    app = db.get(Application, application_id)
    if app is None or app.can_id != candidate_id:
        raise LookupError("投递记录不存在")
    # position_id 为空的通用申请表对所有岗位生效；绑定岗位的只对本岗位生效
    if t.position_id is not None and t.position_id != app.pos_id:
        raise FormError("该表单不属于这次投递的岗位")
    if not _stage_reached(app, _form_stage_cfg(db)["position"]):
        raise FormError("还没有到可以填写这份表单的阶段")
    return app


def _assessment_visible(db: Session, candidate_id: int) -> bool:
    """职业底色图：候选人有任意一次投递走到了配置的关卡就可见。"""
    threshold = _form_stage_cfg(db)["assessment"]
    apps = db.scalars(select(Application).where(Application.can_id == candidate_id)).all()
    return any(_stage_reached(a, threshold) for a in apps)


def available_templates(db: Session, candidate_id: int, application_id: int | None) -> list[dict]:
    items: list[dict] = []
    profile = db.scalar(
        select(FormTemplate).where(FormTemplate.scope == "profile", FormTemplate.is_active == 1).order_by(FormTemplate.id.desc())
    )
    if profile is not None:
        sub = get_submission(db, profile.id, candidate_id, None)
        items.append(
            {
                **template_out(db, profile),
                "my_status": sub.status if sub else "none",
                "submission_id": sub.id if sub else None,
                "application_id": None,
            }
        )
    assessment = db.scalar(
        select(FormTemplate)
        .where(FormTemplate.scope == "assessment", FormTemplate.is_active == 1)
        .order_by(FormTemplate.id.desc())
    )
    if assessment is not None and not _assessment_visible(db, candidate_id):
        assessment = None  # 还没到配置的关卡，候选人先看不到
    if assessment is not None:
        sub = get_submission(db, assessment.id, candidate_id, None)
        items.append(
            {
                **template_out(db, assessment),
                "my_status": sub.status if sub else "none",
                "submission_id": sub.id if sub else None,
                "application_id": None,
            }
        )
    cfg = _form_stage_cfg(db)
    if application_id is not None:
        app = db.get(Application, application_id)
        if app is not None and app.can_id == candidate_id:
            # 优先用本岗位自己的申请表；岗位没配就用通用的（position_id 为空）
            position_t = db.scalar(
                select(FormTemplate)
                .where(
                    FormTemplate.scope == "position",
                    FormTemplate.position_id == app.pos_id,
                    FormTemplate.is_active == 1,
                )
                .order_by(FormTemplate.id.desc())
            )
            if position_t is None:
                position_t = db.scalar(
                    select(FormTemplate)
                    .where(
                        FormTemplate.scope == "position",
                        FormTemplate.position_id.is_(None),
                        FormTemplate.is_active == 1,
                    )
                    .order_by(FormTemplate.id.desc())
                )
            if position_t is not None and _stage_reached(app, cfg["position"]):
                sub = get_submission(db, position_t.id, candidate_id, application_id)
                items.append(
                    {
                        **template_out(db, position_t),
                        "my_status": sub.status if sub else "none",
                        "submission_id": sub.id if sub else None,
                        "application_id": application_id,
                    }
                )
    return items
