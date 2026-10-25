"""
【候选人接口】
  GET    /api/candidates?name=张   列表，可按姓名模糊搜（含名下投递数）
  POST   /api/candidates           新建
  GET    /api/candidates/{id}      详情
  PUT    /api/candidates/{id}      改备注
  DELETE /api/candidates/{id}      删除（级联删除其名下投递，不可恢复）
"""
from datetime import datetime

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_hr
from app.models import Application, Candidate, User
from app.schemas.candidate import CandidateIn, CandidateOut, CandidateUpdate
from app.services import accounts, ownership
from app.services.phone import is_valid_phone, normalize_phone

router = APIRouter(prefix="/api/candidates", tags=["candidates"], dependencies=[Depends(get_current_hr)])


def _out(c: Candidate, count: int = 0, has_account: bool = False) -> CandidateOut:
    return CandidateOut(
        id=c.id,
        owner_id=c.owner_id,
        owner_name=_hr_display(c.owner),
        name=c.name,
        phone=c.phone,
        email=c.email,
        remark=c.remark,
        onboard_date=c.onboard_date,
        school=c.school,
        degree=c.degree,
        major=c.major,
        expected_salary=c.expected_salary,
        work_location=c.work_location,
        hire_type=c.hire_type,
        work_experience=c.work_experience,
        create_time=c.create_time,
        application_count=count,
        has_account=has_account,
    )


def _hr_display(u) -> str | None:
    """HR 显示名：实名优先。"""
    return None if u is None else (u.real_name or u.username)


def _account_ids(db: Session) -> set[int]:
    """一次查出「哪些候选人已经开通账号」，列表页不用每人查一次。"""
    rows = db.execute(
        select(User.candidate_id).where(User.role == "candidate", User.candidate_id.isnot(None))
    ).all()
    return {r[0] for r in rows}


def _count_map(db: Session) -> dict[int, int]:
    """一次查出「每个候选人名下有几条投递」，返回 {候选人编号: 数量}。暂不招岗位的投递不计入。"""
    from app.services import positions as positions_svc

    stmt = select(Application.can_id, func.count()).group_by(Application.can_id)
    stmt = positions_svc.exclude_hidden_apps(stmt, db)
    rows = db.execute(stmt).all()
    return {can_id: n for can_id, n in rows}


def _get_or_404(db: Session, can_id: int) -> Candidate:
    c = db.get(Candidate, can_id)
    if c is None:
        raise HTTPException(status_code=404, detail="候选人不存在")
    return c


@router.get("", response_model=list[CandidateOut])
def list_candidates(
    name: str | None = Query(default=None, description="姓名关键字，模糊搜索。传「张」能搜到张三、小张；不传 = 全部"),
    remark: str | None = Query(default=None, description="备注关键字，模糊搜索。例：内推 / 二批 / AI录入"),
    has_application: str | None = Query(
        default=None,
        description="按有没有投递筛选：yes=只看有投递的；no=只看还没投递的；不传=全部",
    ),
    phone: str | None = Query(default=None, description="手机号关键字，模糊搜索"),
    has_account: str | None = Query(
        default=None,
        description="按有没有开通候选人端账号筛选：yes=已开通（有手机号）；no=未开通/待补手机号；不传=全部",
    ),
    db: Session = Depends(get_db),
):
    """候选人列表（可按姓名 / 备注 / 手机号 / 账号状态 / 有无投递筛选）

**干什么用**：前端「候选人管理」页的表格与搜索栏。

**怎么填**（都可组合，是「且」的关系）：
- `name`：姓名里含这几个字（模糊）
- `remark`：备注里含这几个字（模糊）
- `phone`：手机号里含这几位（模糊）
- `has_account`：`yes` 只看已开通账号的；`no` 只看还没开通的（通常是待补手机号）
- `has_application`：`yes` 只看有投递记录的；`no` 只看一条投递都没有的
"""
    # Query(default=None)：这些参数写在网址问号后面（?name=张&remark=内推），不传也行
    stmt = select(Candidate).order_by(Candidate.id.desc())
    if name:
        stmt = stmt.where(Candidate.name.like(f"%{name}%"))  # % 是通配符：「张」能搜到「张三」「小张」
    if remark:
        stmt = stmt.where(Candidate.remark.like(f"%{remark}%"))
    if phone:
        stmt = stmt.where(Candidate.phone.like(f"%{phone}%"))
    if has_account not in (None, "", "yes", "no"):
        raise HTTPException(status_code=400, detail="has_account 只能是 yes 或 no")
    account_ids = select(User.candidate_id).where(
        User.role == "candidate", User.candidate_id.isnot(None)
    )
    if has_account == "yes":
        stmt = stmt.where(Candidate.id.in_(account_ids))
    elif has_account == "no":
        stmt = stmt.where(Candidate.id.notin_(account_ids))
    counts = _count_map(db)
    acct = _account_ids(db)
    if has_application == "yes":
        stmt = stmt.where(Candidate.id.in_(select(Application.can_id).distinct()))
    elif has_application == "no":
        stmt = stmt.where(Candidate.id.notin_(select(Application.can_id).distinct()))
    return [_out(c, counts.get(c.id, 0), c.id in acct) for c in db.scalars(stmt).all()]


@router.post("", response_model=CandidateOut, status_code=status.HTTP_201_CREATED)
def create_candidate(
    body: CandidateIn, db: Session = Depends(get_db), user: User = Depends(get_current_hr)
):
    """手动新建一个候选人

**干什么用**：来了个应聘的人，先把他录进系统。（用「AI 录入」传简历的话不用手动建，AI 会自动建。）

**怎么填**：`name` 必填，`remark` 随意。

**返回什么**：新建好的候选人，带 `id`。建投递时 `can_id` 填它。

**注意**：系统按姓名认人，同名会被当成同一个人。手动建重名不拦你，但 AI 录入遇到同名会直接复用旧的。
"""
    phone = normalize_phone(body.phone)
    if body.phone and not is_valid_phone(phone):
        raise HTTPException(status_code=400, detail="手机号格式不正确")
    if phone:
        dup = db.scalar(select(Candidate).where(Candidate.phone == phone))
        if dup is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"手机号 {phone} 已被候选人「{dup.name or dup.id}」使用",
            )
    now = datetime.now()
    c = Candidate(
        name=body.name,
        phone=phone,
        email=(body.email or "").strip() or None,
        remark=body.remark,
        owner_id=user.id,  # 默认负责人 = 建档的 HR
        create_time=now,
        update_time=now,
    )
    try:
        db.add(c)
        db.flush()  # 先拿到候选人 ID，才能建账号
        accounts.ensure_candidate_account(db, c)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="手机号已被其他候选人使用")
    db.refresh(c)
    return _out(c, 0, accounts.get_candidate_user(db, c.id) is not None)


@router.get("/{can_id}", response_model=CandidateOut)
def get_candidate(can_id: Annotated[int, Path(description="候选人编号")], db: Session = Depends(get_db)):
    """看一个候选人的详情

**怎么填**：网址里换候选人编号，比如 `/api/candidates/3`。

**可能出错**：
- 404：没有这个编号的候选人
"""
    c = _get_or_404(db, can_id)
    from app.services import positions as positions_svc
    stmt = positions_svc.exclude_hidden_apps(
        select(func.count()).select_from(Application).where(Application.can_id == can_id), db
    )
    count = db.scalar(stmt) or 0
    return _out(c, count, accounts.get_candidate_user(db, can_id) is not None)


@router.put("/{can_id}", response_model=CandidateOut)
def update_candidate(
    can_id: Annotated[int, Path(description="候选人编号")],
    body: CandidateUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_hr),
):
    """改候选人：可以改备注，也可以改姓名

**干什么用**：
- 记备注，比如「已电话确认到岗时间」「期望薪资 20k」；
- **纠正姓名**——AI 识别简历有时会认错名字（最典型的是把 PDF 文件名当成了姓名），人工改过来即可。

**怎么填**：
- 只改备注：`{"remark": "新备注"}`，传空字符串可清空；
- 改姓名：`{"name": "樊浩"}`，姓名不能传空；
- 改名不影响任何投递记录（投递按候选人编号关联），历史进度与时间线原样保留。

**重名怎么办**：如果新姓名与**另一个**候选人完全相同，第一次会返回 409 并告诉你是哪个候选人、他名下有几条投递；
你确认「确实是另一个同名的不同人」后，带上 `{"name": "...", "confirm_duplicate": true}` 再提交一次即可改成同名。

**可能出错**：
- 400：姓名传了空字符串
- 404：没有这个候选人
- 409：新姓名与已有候选人重名（需带 confirm_duplicate=true 确认）
"""
    c = _get_or_404(db, can_id)
    # 资料编辑权限：负责人本人；暂无负责人的候选人任意 HR 可改
    try:
        ownership.ensure_can_edit_candidate(db, c, user)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    # model_fields_set = 前端真正传了的字段集合。这样能区分「没传某个字段」和「传了但值是空」
    if "remark" in body.model_fields_set:
        c.remark = body.remark

    # 手机号：改了立刻影响登录；清空 = 保留账号但再也登录不了
    if "phone" in body.model_fields_set:
        raw = (body.phone or "").strip()
        if raw:
            new_phone = normalize_phone(raw)
            if not is_valid_phone(new_phone):
                raise HTTPException(status_code=400, detail="手机号格式不正确")
            other = db.scalar(
                select(Candidate).where(Candidate.phone == new_phone, Candidate.id != c.id)
            )
            if other is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"手机号 {new_phone} 已被候选人「{other.name or other.id}」使用",
                )
            c.phone = new_phone
        else:
            c.phone = None
        c.update_time = datetime.now()

    if "email" in body.model_fields_set:
        c.email = (body.email or "").strip() or None
        c.update_time = datetime.now()

    # HR 从简历摘录的个人信息：文本字段，填什么存什么，传空即清空
    for f in ("onboard_date", "school", "degree", "major", "expected_salary", "work_location", "hire_type", "work_experience"):
        if f in body.model_fields_set:
            setattr(c, f, (getattr(body, f) or "").strip() or None)
            c.update_time = datetime.now()

    if "name" in body.model_fields_set or body.name is not None:
        new_name = (body.name or "").strip()
        if not new_name:
            raise HTTPException(status_code=400, detail="姓名不能为空")
        # 只有真的要改名时才查重（改成一样的名字不算改）
        if new_name != c.name and not body.confirm_duplicate:
            other = db.scalar(
                select(Candidate).where(Candidate.name == new_name, Candidate.id != c.id)
            )
            if other is not None:
                n = db.scalar(
                    select(func.count()).select_from(Application).where(Application.can_id == other.id)
                ) or 0
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"已有同名候选人「{new_name}」（名下 {n} 条投递）。"
                        "如果是两个同名的人、确实要改成一样的名字，请确认后重试。"
                    ),
                )
        c.name = new_name

    # 有手机号就确保账号存在（首次填手机号时自动开通，默认密码 admin）
    if c.phone:
        accounts.ensure_candidate_account(db, c)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="手机号已被其他候选人使用")
    db.refresh(c)
    from app.services import positions as positions_svc
    stmt = positions_svc.exclude_hidden_apps(
        select(func.count()).select_from(Application).where(Application.can_id == can_id), db
    )
    count = db.scalar(stmt) or 0
    return _out(c, count, accounts.get_candidate_user(db, can_id) is not None)


@router.delete("/{can_id}", status_code=status.HTTP_200_OK)
def delete_candidate(can_id: Annotated[int, Path(description="候选人编号")], db: Session = Depends(get_db)):
    """删除候选人（连带删除他名下的所有投递）

**干什么用**：录错了人、或想彻底清掉某位候选人的所有记录。

**怎么填**：网址里换候选人编号。

**会发生什么**：先删除该候选人名下的全部投递记录，再删除候选人本人，一步完成（应用层实现级联，
数据库外键本身不允许直接删人，所以这里自己先清投递）。删除后不可恢复。

**返回什么**：`{"deleted_applications": 2}`（连带删了几条投递）——注意不是 204，是 200 + 这个数字，
方便前端提示「已删除张三及其 2 条投递记录」。

**可能出错**：
- 404：没有这个候选人
- 409：意外删不掉（一般不会出现）
"""
    c = _get_or_404(db, can_id)
    # 先删候选人账号，再删投递，最后删候选人
    linked_user = accounts.get_candidate_user(db, can_id)
    if linked_user is not None:
        db.delete(linked_user)
        db.flush()
    # 先删投递，再删候选人——同一个事务里，要么全成功要么全不成功（rollback）
    count = db.scalar(select(func.count()).select_from(Application).where(Application.can_id == can_id)) or 0
    if count:
        db.query(Application).filter(Application.can_id == can_id).delete(synchronize_session=False)
    db.delete(c)
    try:
        db.commit()
    except IntegrityError:
        # 兜底：万一还有别的东西引用这个候选人（数据库外键挡住），回滚并给个中文提示
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该候选人仍被其他记录引用，无法删除")
    return {"deleted_applications": count}

