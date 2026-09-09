"""
【这个文件是干什么的？】
它是「门卫」——负责检查每个请求是不是已经登录的用户发来的。

流程像进小区：
  1. 浏览器发请求时，在「请求头」里带一张通行证：Authorization: Bearer <一长串token>
  2. 门卫（这个文件里的 get_current_user）把 token 拿出来验章（有没有被改过？过期了没？）
  3. 验过后，从 token 里读出用户编号，去数据库把这个用户找出来，交给接口函数使用
  4. 任何一步不对，就回 401（意思是「你没登录」），前端收到 401 会跳回登录页

除了注册、登录、健康检查这几个接口，其余所有接口都要过这个门卫。
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import User
from app.services.security import decode_token

# HTTPBearer 会帮我们从请求头里把「Bearer xxx」那串东西取出来。
# auto_error=False 表示：没带也别急着报错，交给下面自己判断、自己写中文提示
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """检查通行证，返回当前登录用户；检查不通过就抛 401。"""

    # 先准备好「拒绝进入」的回复，下面几种情况都用它
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未登录或登录已过期",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 情况一：根本没带通行证，或者带的不是 Bearer 类型
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized

    # 情况二：通行证是假的、被改过、或者过期了（decode_token 会返回 None）
    user_id = decode_token(credentials.credentials)
    if user_id is None:
        raise unauthorized

    # 情况三：通行证是真的，但这个用户在数据库里已经不存在了
    user = db.get(User, user_id)
    if user is None:
        raise unauthorized

    # 全部通过，把用户对象交出去，接口函数就知道「现在是谁在操作」
    return user
