"""
【这个文件是干什么的？】
两件跟「安全」有关的事：① 密码怎么存  ② 登录凭证（token）怎么发、怎么验。

① 密码：绝对不能把「123456」这样的原文存进数据库。
   我们用 bcrypt 算法把它「搅碎」成一串乱码（叫哈希）。
   特点：同一个密码每次搅出来的乱码都不一样（因为加了随机「盐」），但都能验证回去；
   反过来，从乱码推不出原密码。

② token（JWT）：登录成功后发给浏览器的一张「盖了章的通行证」。
   上面写着「用户编号 = 7，角色 = hr，有效期到 X 日」，然后用 secret_key 盖个章。
   以后浏览器每次请求都带着它；我们只要验章，不用每次都查密码。

   role 写进 token 只是方便排查；真正鉴权时以数据库里的 User.role 为准，
   这样管理员改了某个人的角色，旧 token 也立刻按新角色受限。
"""
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

ALGORITHM = "HS256"  # 盖章用的算法名（一种带密钥的摘要算法）

# 「搅碎机」：指定用 bcrypt。deprecated="auto" 表示以后换新算法时旧密码还能验、并自动升级
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """把明文密码搅成哈希，注册/重置密码时用。"""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """检查用户输的密码（plain）和库里存的哈希（hashed）是否匹配，登录时用。"""
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: int, role: str | None = None) -> str:
    """给某个用户发一张通行证。

    sub（subject）：这张证是谁的——放用户编号（JWT 规定 sub 必须是字符串）
    role          ：角色，方便日志与快速判断
    exp（expire） ：过期时间——候选人 30 天，其余 7 天（都在 .env 里配）
    """
    days = settings.portal_token_expire_days if role == "candidate" else settings.token_expire_days
    now = datetime.now(UTC)
    expire = now + timedelta(days=days)
    # iat（issued at）：签发时间。配 User.token_valid_after 可让改密/重置后旧 token 全部失效（强制下线）。
    # 另存 iat_ms（毫秒精度）：秒级 iat 无法区分「同一秒内先签的旧票」和「改密响应里刚签发的新票」，
    # 会导致用户改完密码立刻被自己踢下线——强制下线判定一律用 iat_ms。
    payload = {"sub": str(user_id), "exp": expire, "iat": now, "iat_ms": int(now.timestamp() * 1000)}
    if role:
        payload["role"] = role
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> tuple[int, int | None] | None:
    """验证通行证。合格返回 (用户编号, 签发时间毫秒)；假的 / 改过的 / 过期的一律返回 None。

    签发时间优先取 iat_ms（毫秒）；旧票只有秒级 iat，按「该秒末尾」折算，宁可放过 1 秒也不误杀。
    都缺返回 None，调用方按「不校验」处理。
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])  # 验章 + 检查过期
        iat_ms = payload.get("iat_ms")
        if iat_ms is None:
            iat = payload.get("iat")
            iat_ms = (int(iat) + 1) * 1000 if iat is not None else None  # 旧票：按该秒末尾算
        return int(payload["sub"]), (int(iat_ms) if iat_ms is not None else None)
    except (JWTError, KeyError, ValueError):
        # JWTError：章不对或过期；KeyError：里面没有 sub；ValueError：sub 不是数字
        return None
