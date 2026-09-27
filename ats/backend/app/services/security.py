"""
【这个文件是干什么的？】
两件跟「安全」有关的事：① 密码怎么存  ② 登录凭证（token）怎么发、怎么验。

① 密码：绝对不能把「123456」这样的原文存进数据库。
   我们用 bcrypt 算法把它「搅碎」成一串乱码（叫哈希），比如 $2b$12$N9qo8uLO...
   特点：同一个密码每次搅出来的乱码都不一样（因为加了随机「盐」），但都能验证回去；
   反过来，从乱码推不出原密码。就像把鸡蛋打成蛋液——你能确认这是鸡蛋做的，但拼不回鸡蛋。

② token（JWT）：登录成功后发给浏览器的一张「盖了章的通行证」。
   上面写着「用户编号 = 7，有效期到 X 日」，然后用 secret_key 盖个章（签名）。
   以后浏览器每次请求都带着它；我们只要验章，不用每次都查密码。
   有人想篡改「用户编号」？改了内容，章就对不上了——立刻识破。
"""
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

ALGORITHM = "HS256"  # 盖章用的算法名（一种带密钥的摘要算法）

# 「搅碎机」：指定用 bcrypt。deprecated="auto" 表示以后换新算法时旧密码还能验、并自动升级
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """把明文密码搅成哈希，注册时用。"""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """检查用户输的密码（plain）和库里存的哈希（hashed）是否匹配，登录时用。"""
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: int) -> str:
    """给某个用户发一张通行证。

    sub（subject）：这张证是谁的——放用户编号（JWT 规定 sub 必须是字符串，所以转成 str）
    exp（expire） ：过期时间——现在 + 7 天（天数在 .env 里配）
    """
    expire = datetime.now(timezone.utc) + timedelta(days=settings.token_expire_days)
    return jwt.encode({"sub": str(user_id), "exp": expire}, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> int | None:
    """验证通行证。合格就返回里面的用户编号；假的 / 改过的 / 过期的一律返回 None。"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])  # 验章 + 检查过期，不合格直接抛异常
        return int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        # JWTError：章不对或过期；KeyError：里面没有 sub；ValueError：sub 不是数字
        return None
