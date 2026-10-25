"""
【这个文件是干什么的？】
它是「门卫」——负责检查每个请求是不是已经登录、是什么角色。

三个端共用一套 token，但角色不同：
    candidate → /api/portal/**
    hr        → /api/**（招聘业务）
    admin     → /api/tech/**（技术管理）

流程像进小区：
  1. 浏览器在请求头带通行证：Authorization: Bearer <token>
  2. 门卫验章（有没有被改？过期没？），从 token 读出用户编号
  3. 去数据库把用户找出来（数据库里的 role 才是准的，token 里的 role 只作参考）
  4. 账号被停用 → 403；角色不对 → 403；没登录 → 401
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import User
from app.services.security import decode_token

# HTTPBearer 会帮我们从请求头里把「Bearer xxx」取出来。
# auto_error=False：没带也别急着报错，交给下面自己判断、自己写中文提示
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """检查通行证，返回当前登录用户；检查不通过就抛 401/403。"""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未登录或登录已过期",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized

    user_id = decode_token(credentials.credentials)
    if user_id is None:
        raise unauthorized

    user = db.get(User, user_id)
    if user is None:
        raise unauthorized

    # 停用账号：即使 token 还没过期也不让继续用
    if getattr(user, "is_active", 1) == 0:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已停用，请联系管理员")

    return user


def require_role(*roles: str):
    """角色门卫工厂：require_role("hr") 返回一个只放行 HR 的依赖函数。

    用法：router = APIRouter(..., dependencies=[Depends(get_current_hr)])
    或者：user: User = Depends(get_current_hr)
    """

    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            # 403 而不是 401：已经登录了，只是没有这个端的权限
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该功能")
        return user

    return dependency


# 三个端各一个，名字短、写起来清楚
get_current_hr = require_role("hr")
get_current_admin = require_role("admin")


def get_current_candidate(
    user: User = Depends(require_role("candidate")),
    db: Session = Depends(get_db),
) -> User:
    """候选人门卫：角色检查之外，还执行「淘汰 2 天销号」。

    被淘汰的候选人保留期一过，即使 token 还没过期（有效期 30 天），这里也拦下——
    拦截信息用淘汰通知模板渲染，候选人在登录页/接口报错里都能看到被淘汰的说明。
    """
    if user.candidate_id:
        from app.services import notice_service

        blocked = notice_service.elimination_block(db, user.candidate_id, deactivate=True)
        if blocked:
            db.commit()
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=blocked)
    return user
