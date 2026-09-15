"""
【这个文件夹（models）是干什么的？】
这里定义「数据长什么样」。

数据库里有 5 张表（5 个货架）：用户、岗位、候选人、投递记录、AI 接口配置。
每张表在这里对应一个 Python「类」（class），类里的每个属性对应表里的一列。
这样我们就能像操作普通 Python 对象一样操作数据库，不用手写 SQL 语句——
这种技术叫 ORM（对象关系映射），SQLAlchemy 是帮我们干这活的工具。

规矩：表名、列名、类型全部照抄 crebas.sql 建表脚本和数据字典，不自己发明。
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """所有表的「爸爸类」。每张表都继承它，SQLAlchemy 才认得这是一张表。"""

    pass


# 下面这几行必须放在 Base 定义之后（因为它们都要用到 Base），所以加了 noqa 告诉检查工具别报「import 不在开头」
from app.models.user import User  # noqa: E402
from app.models.position import Position  # noqa: E402
from app.models.candidate import Candidate  # noqa: E402
from app.models.application import Application  # noqa: E402
from app.models.ai_api_config import AiApiConfig  # noqa: E402
from app.models.app_setting import AppSetting  # noqa: E402

# 别的文件写 from app.models import User 就能拿到这些类
__all__ = ["Base", "User", "Position", "Candidate", "Application", "AiApiConfig", "AppSetting"]
