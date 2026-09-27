"""
【User 表：用户】
谁能登录这个系统？就是这张表里的人。

注意：这里存的不是密码本身，而是密码「搅碎后的乱码」（哈希）。
就算有人偷看了数据库，也看不出原密码是什么。怎么搅碎的见 services/security.py。
"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class User(Base):
    __tablename__ = "User"  # 对应数据库里的表名

    # Mapped[int] 是告诉 Python「这一列是整数」；mapped_column 里写数据库的细节
    # "ID" 是数据库里的列名（大写），左边的 id 是我们在 Python 里用的名字（小写）
    id: Mapped[int] = mapped_column("ID", Integer, primary_key=True, autoincrement=True)  # 主键，自动 1、2、3 往上编号

    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)  # 用户名，不能重复、不能为空
    password_hash: Mapped[str] = mapped_column(String(100), nullable=False)  # 密码的哈希值
    create_time: Mapped[datetime | None] = mapped_column(DateTime)  # 什么时候注册的
