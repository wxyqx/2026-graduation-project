"""
【这个文件是干什么的？】
它负责读取「配置」——程序运行时需要知道的一些设置，比如数据库在哪里、登录密钥是什么。

这些设置写在 backend/.env 文件里（一行一条，形如 KEY=值）。
密码这类东西不能随代码分享，所以放 .env（已 gitignore）。

v3.15 新增候选人端相关配置，全部有默认值：.env 里不写也能跑。
"""
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """所有配置项都列在这里。等号右边是「默认值」——.env 里没写时就用它。"""

    # 数据库连接地址。格式：数据库类型+驱动://用户名:密码@地址:端口/库名?字符集
    database_url: str = "mysql+pymysql://root@127.0.0.1:3306/ats?charset=utf8mb4"

    # 给登录凭证（token）盖章用的「印章」，谁拿到它谁就能伪造登录，所以要保密、要随机
    secret_key: str = "change-me-to-a-random-hex-string"

    # 登录一次能用几天，过了要重新登录
    token_expire_days: int = 7

    # ---------------- 候选人端 ----------------
    # 默认密码：手机号开通账号、HR/技术管理员重置密码时都用它
    default_candidate_password: str = "admin"
    # 候选人 login 有效期（候选人用手机，放宽到 30 天少登录几次）
    portal_token_expire_days: int = 30
    # 短信验证码总开关：本期 false，接口不开放，后期接真实通道再打开
    portal_sms_enabled: bool = False
    sms_provider: str = "mock"  # mock / aliyun
    sms_code_ttl_seconds: int = 300
    sms_resend_seconds: int = 60
    # 防刷：同一候选人 24 小时最多投递几次
    portal_apply_daily_limit: int = 10
    # 单个文件最大 MB，以及单个候选人文件总量上限
    portal_upload_max_mb: int = 10
    portal_file_total_mb: int = 50

    # ---------------- 技术管理端 ----------------
    # 是否允许通过 /api/auth/register 自助注册 HR 账号；首个管理员请用 scripts/create_user.py 创建
    allow_hr_register: bool = True
    # 登录失败几次锁定、锁多久（分钟）
    login_max_failures: int = 5
    login_lock_minutes: int = 10

    # 告诉 pydantic：去上上级目录找 .env 文件，用 utf-8 编码读
    model_config = {
        "env_file": Path(__file__).resolve().parents[2] / ".env",
        "env_file_encoding": "utf-8",
    }


# 整个程序只需要一份配置，在这里造好，别的文件直接 import 来用
settings = Settings()
