"""
【认证接口：注册 / 登录 / 我是谁】
这是整个系统唯一「不用先登录」就能访问的一组接口（不然怎么登录呢）。

四个网址：
  POST /api/auth/register  注册（成功顺便帮你登录，直接发 token）
  POST /api/auth/login     登录
  GET  /api/auth/me        拿着 token 问「我是谁」——前端刷新页面后用它确认还在登录状态
  PUT  /api/auth/profile   修改个人信息（用户名 / 密码），改密码需先验当前密码

每个函数下面那段三引号里的文字，会原样显示在 /docs 网页上（支持 markdown）。
"""
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_hr
from app.models import User
from app.schemas.auth import LoginIn, ProfileUpdateIn, RegisterIn, TokenOut, UserOut
from app.services import avatar_service, ratelimit
from app.services.phone import is_valid_phone, normalize_phone
from app.services.security import create_access_token, hash_password, verify_password

# prefix：这个文件里所有网址都以 /api/auth 开头；tags：在 /docs 文档页里归到「auth」这一组
router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_out(user: User) -> UserOut:
    """把数据库里的用户对象变成回给前端的样子（去掉密码哈希）。"""
    return UserOut(
        id=user.id,
        username=user.username,
        phone=user.phone,
        real_name=user.real_name,
        role=user.role,
        candidate_id=user.candidate_id,
        is_active=bool(getattr(user, "is_active", 1)),
        create_time=user.create_time,
    )


def _validated_phone(db: Session, raw: str, exclude_user_id: int | None = None) -> str:
    """HR/管理员的手机号：洗成标准 11 位、验格式、查重（排除自己）。不合格直接 4xx。"""
    phone = normalize_phone(raw)
    if not is_valid_phone(phone):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="手机号格式不正确（11 位，1 开头）")
    dup = select(User.id).where(User.phone == phone)
    if exclude_user_id is not None:
        dup = dup.where(User.id != exclude_user_id)
    if db.scalar(dup):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="手机号已被其他账号使用")
    return phone


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    """注册新用户，成功后直接登录（返回 token）

**干什么用**：第一次用系统先在这里注册一个账号。

**怎么填**：
- `username`：2～50 个字，以后登录用它
- `password`：至少 6 位
- `phone`：11 位手机号，必填（个人信息强制要求有联系方式）
- `real_name`：实名，必填

**返回什么**：
```json
{
  "token": "eyJhbGciOi...（一长串）",
  "token_type": "bearer",
  "user": {"id": 1, "username": "xiaoming", "phone": "13800138000", "create_time": "2026-09-08T10:00:00"}
}
```
把 `token` 那一串复制下来，点页面右上角 **Authorize** 粘进去，之后所有接口就能用了。

**可能出错**：
- 409：这个用户名或手机号已经有人用了，换一个
- 422：用户名太短 / 密码太短 / 手机号没填
- 400：手机号格式不对

**注意**：密码不会原样存进数据库，存的是搅碎后的哈希，谁也看不到原文。
"""
    # body 是浏览器发来的 JSON，已经按 RegisterIn 模板检查过了（用户名长度、密码长度）
    if not settings.allow_hr_register:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="未开放自助注册，请联系技术管理员开通账号")
    exists = db.scalar(select(User).where(User.username == body.username))  # 查一下这个用户名有没有人用
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")  # 409 = 冲突
    phone = _validated_phone(db, body.phone)
    user = User(
        username=body.username,
        phone=phone,
        real_name=body.real_name.strip(),
        password_hash=hash_password(body.password),
        role="hr",  # 这个入口只注册 HR；技术管理员用脚本创建
        create_time=datetime.now(),
    )
    db.add(user)  # 放进小推车
    db.commit()  # 结账，真正写入数据库
    db.refresh(user)  # 重新读一遍，拿到数据库分配的 ID
    return TokenOut(token=create_access_token(user.id, user.role), user=_user_out(user))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    """登录，换一张新的 token

**干什么用**：已经注册过，token 过期了（7 天）或换了浏览器，来这里重新拿一张。

**怎么填**：注册时的用户名和密码。

**返回什么**：和注册一样——`token` + 用户信息。复制 token 去右上角 Authorize。

**可能出错**：
- 401：用户名或密码错了。故意不区分是「用户名不存在」还是「密码错」，防止别人试探哪些用户名存在。
"""
    # 限流：同一用户名 10 分钟内最多失败 5 次（与候选人端同一套规则）
    window = settings.login_lock_minutes * 60
    key = f"hr_login:{body.username}"
    if ratelimit.too_many(key, settings.login_max_failures, window):
        wait = ratelimit.remaining_seconds(key, window)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"登录失败次数过多，请 {max(1, wait // 60)} 分钟后再试",
        )

    user = db.scalar(select(User).where(User.username == body.username))
    # 用户不存在、或密码对不上，都回同一句话——不告诉攻击者「用户名是对的，只是密码错了」
    if user is None or not verify_password(body.password, user.password_hash):
        ratelimit.record_failure(key, window)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    # 这里只允许 HR 登录；候选人和技术管理员走各自的入口
    if user.role != "hr":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="请从对应入口登录：候选人用 /portal/login，技术管理员用 /tech/login",
        )
    if getattr(user, "is_active", 1) == 0:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已停用，请联系管理员")
    ratelimit.reset(key)  # 登录成功：清空失败记录
    return TokenOut(token=create_access_token(user.id, user.role), user=_user_out(user))


@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_hr)):
    """我是谁（检查 token 还有没有效）

**干什么用**：拿着 token 问后端「我是谁」。前端刷新页面后用它确认还在登录状态；你也可以用它测试 Authorize 有没有贴对。

**怎么填**：不用填任何参数，只要 Authorize 过。

**返回什么**：`{"id": 1, "username": "xiaoming", "create_time": "..."}`

**可能出错**：
- 401：没 Authorize、token 贴错了、或者过了 7 天。重新 login 拿新的。
"""
    # Depends(get_current_hr)：门卫先验 token，验过了把用户对象塞给 current 参数
    return _user_out(current)


@router.put("/profile", response_model=TokenOut)
def update_profile(body: ProfileUpdateIn, db: Session = Depends(get_db), current: User = Depends(get_current_hr)):
    """修改个人信息（用户名 / 手机号 / 密码）

**干什么用**：登录后想换个用户名、补手机号，或者想改密码，都来这里。点页面右上角用户名 →「个人信息」。

**怎么填**：
- `username`：必填，2～50 个字。和别人重名会被拒。
- `phone`：必填，11 位手机号。和别人重复会被拒。
- `real_name`：必填，实名。
- 要**改密码**时，把三项都填上：`current_password`（当前密码，用来验证是你本人）、`new_password`（至少 6 位）。
  不改密码就只填 `username`、`phone`、`real_name`，密码三项留空即可。

**返回什么**：和登录一样，会重新发一张 `token` + 用户信息。前端拿到后替换本地保存的登录状态，顶栏用户名立刻更新。

**可能出错**：
- 400：要改密码但「当前密码」填错了 / 手机号格式不对
- 409：新用户名或手机号已经被别人用了
- 422：用户名长度不对 / 新密码太短 / 手机号没填
"""
    # 改密码：必须先验当前密码。否则只要 token 泄露，别人就能直接把密码改掉、把你锁在门外
    if body.new_password:
        if not body.current_password or not verify_password(body.current_password, current.password_hash):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前密码不正确")
        current.password_hash = hash_password(body.new_password)

    # 改用户名：查重时排除自己（新名字和自己的旧名字相同不算冲突）
    if body.username != current.username:
        exists = db.scalar(select(User).where(User.username == body.username, User.id != current.id))
        if exists:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")
        current.username = body.username

    # 手机号：个人信息强制要求有，必填且不能和别人重复
    phone = _validated_phone(db, body.phone, exclude_user_id=current.id)
    current.phone = phone

    # 实名：个人信息强制要求有
    current.real_name = body.real_name.strip()

    db.commit()
    db.refresh(current)
    return TokenOut(token=create_access_token(current.id, current.role), user=_user_out(current))


@router.put("/avatar")
async def upload_avatar(
    file: UploadFile = File(description="图片：jpg / png / webp / gif，≤5MB"),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_hr),
):
    """上传我的头像（当前登录用户）

**干什么用**：三个端通用——HR、候选人、技术管理员都给当前账号设置头像；再次上传即替换。
"""
    try:
        await avatar_service.save_avatar(db, current, file)
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@router.get("/avatar")
def get_avatar(db: Session = Depends(get_db), current: User = Depends(get_current_hr)):
    """获取我的头像图片（没设置时返回 404，前端用用户名首字占位）"""
    return avatar_service.avatar_response(current)
