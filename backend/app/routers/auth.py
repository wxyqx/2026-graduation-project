"""
【认证接口：注册 / 登录 / 我是谁】
这是整个系统唯一「不用先登录」就能访问的一组接口（不然怎么登录呢）。

三个网址：
  POST /api/auth/register  注册（成功顺便帮你登录，直接发 token）
  POST /api/auth/login     登录
  GET  /api/auth/me        拿着 token 问「我是谁」——前端刷新页面后用它确认还在登录状态

每个函数下面那段三引号里的文字，会原样显示在 /docs 网页上（支持 markdown）。
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User
from app.schemas.auth import LoginIn, RegisterIn, TokenOut, UserOut
from app.services.security import create_access_token, hash_password, verify_password

# prefix：这个文件里所有网址都以 /api/auth 开头；tags：在 /docs 文档页里归到「auth」这一组
router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_out(user: User) -> UserOut:
    """把数据库里的用户对象变成回给前端的样子（去掉密码哈希）。"""
    return UserOut(id=user.id, username=user.username, create_time=user.create_time)


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    """注册新用户，成功后直接登录（返回 token）

**干什么用**：第一次用系统先在这里注册一个账号。不需要邮箱手机号，只要用户名和密码。

**怎么填**：
- `username`：2～50 个字，以后登录用它
- `password`：至少 6 位

**返回什么**：
```json
{
  "token": "eyJhbGciOi...（一长串）",
  "token_type": "bearer",
  "user": {"id": 1, "username": "xiaoming", "create_time": "2026-09-08T10:00:00"}
}
```
把 `token` 那一串复制下来，点页面右上角 **Authorize** 粘进去，之后所有接口就能用了。

**可能出错**：
- 409：这个用户名已经有人用了，换一个
- 422：用户名太短 / 密码太短

**注意**：密码不会原样存进数据库，存的是搅碎后的哈希，谁也看不到原文。
"""
    # body 是浏览器发来的 JSON，已经按 RegisterIn 模板检查过了（用户名长度、密码长度）
    exists = db.scalar(select(User).where(User.username == body.username))  # 查一下这个用户名有没有人用
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")  # 409 = 冲突
    user = User(username=body.username, password_hash=hash_password(body.password), create_time=datetime.now())
    db.add(user)  # 放进小推车
    db.commit()  # 结账，真正写入数据库
    db.refresh(user)  # 重新读一遍，拿到数据库分配的 ID
    return TokenOut(token=create_access_token(user.id), user=_user_out(user))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    """登录，换一张新的 token

**干什么用**：已经注册过，token 过期了（7 天）或换了浏览器，来这里重新拿一张。

**怎么填**：注册时的用户名和密码。

**返回什么**：和注册一样——`token` + 用户信息。复制 token 去右上角 Authorize。

**可能出错**：
- 401：用户名或密码错了。故意不区分是「用户名不存在」还是「密码错」，防止别人试探哪些用户名存在。
"""
    user = db.scalar(select(User).where(User.username == body.username))
    # 用户不存在、或密码对不上，都回同一句话——不告诉攻击者「用户名是对的，只是密码错了」
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    return TokenOut(token=create_access_token(user.id), user=_user_out(user))


@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)):
    """我是谁（检查 token 还有没有效）

**干什么用**：拿着 token 问后端「我是谁」。前端刷新页面后用它确认还在登录状态；你也可以用它测试 Authorize 有没有贴对。

**怎么填**：不用填任何参数，只要 Authorize 过。

**返回什么**：`{"id": 1, "username": "xiaoming", "create_time": "..."}`

**可能出错**：
- 401：没 Authorize、token 贴错了、或者过了 7 天。重新 login 拿新的。
"""
    # Depends(get_current_user)：门卫先验 token，验过了把用户对象塞给 current 参数
    return _user_out(current)
