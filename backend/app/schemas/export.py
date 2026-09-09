"""【导出相关的表格模板】"""
from datetime import date

from pydantic import BaseModel, Field


class ExportFilters(BaseModel):
    """导出时的「筛选条件」：想导哪段时间、哪个岗位、哪一关、什么状态的记录。全都可不填 = 全部导出。"""

    start_date: date | None = None  # 只要这一天（含）之后创建的投递
    end_date: date | None = None  # 只要这一天（含）之前创建的投递
    pos_id: int | None = None
    stage: str | None = None
    status: str | None = None


class ExportIn(BaseModel):
    """导出请求：条件 + 想要哪几列 + 文件格式。"""

    # default_factory=ExportFilters：不传 filters 时自动造一个「什么都不筛」的空条件
    filters: ExportFilters = Field(default_factory=ExportFilters)
    fields: list[str] = Field(default_factory=list)  # 空列表 = 全部字段都导
    format: str = "xlsx"  # xlsx（Excel）或 csv
