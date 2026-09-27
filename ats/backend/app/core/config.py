"""
【这个文件是干什么的？】
它负责读取「配置」——也就是程序运行时需要知道的一些"设置"，
比如：数据库在哪里？用什么密码连？登录用的密钥是什么？

打个比方：这就像你出门前看一眼冰箱上贴的便利贴——
「今天去哪个超市」「带多少钱」。程序启动时也要先看一眼这些设置。

这些设置写在 backend/.env 文件里（一行一条，形如 KEY=值）。
之所以不直接写在代码里，是因为密码这类东西不能随代码一起分享给别人。
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

    # 告诉 pydantic：去上上级目录找 .env 文件，用 utf-8 编码读
    model_config = {
        "env_file": Path(__file__).resolve().parents[2] / ".env",
        "env_file_encoding": "utf-8",
    }


# 整个程序只需要一份配置，在这里造好，别的文件直接 import 来用
settings = Settings()
