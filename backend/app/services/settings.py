"""
【这个文件是干什么的？】
读写 App_Setting 表里那些「键值对」式的系统设置。目前只用到一项：AI 筛选提示词。

为什么单独一个文件？因为读写设置的地方不止一处（AI 录入要读提示词、设置接口要读写提示词），
集中在这里，逻辑不会两处写得不一样。
"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AppSetting


def get_setting(db: Session, user_id: int, key: str) -> str | None:
    """取某个用户的某项设置；没有就返回 None。"""
    row = db.scalar(select(AppSetting).where(AppSetting.user_id == user_id, AppSetting.setting_key == key))
    return row.setting_value if row else None


def set_setting(db: Session, user_id: int, key: str, value: str | None) -> None:
    """保存某项设置。值传空（None 或空字符串）等于删掉这项设置。"""
    row = db.scalar(select(AppSetting).where(AppSetting.user_id == user_id, AppSetting.setting_key == key))
    text = (value or "").strip()
    if not text:
        # 清空设置 = 删掉记录，之后读出来就是 None（走默认逻辑）
        if row:
            db.delete(row)
            db.commit()
        return
    if row:
        row.setting_value = text
        row.update_time = datetime.now()
    else:
        db.add(AppSetting(user_id=user_id, setting_key=key, setting_value=text, update_time=datetime.now()))
    db.commit()
