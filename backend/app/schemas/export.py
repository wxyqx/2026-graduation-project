"""【导出相关的表格模板】"""
from datetime import date

from pydantic import BaseModel, Field


class ExportFilters(BaseModel):
    """导出时的「筛选条件」：想导哪段时间、哪个岗位、哪一关、什么状态的记录。全都可不填 = 全部导出。"""

    start_date: date | None = Field(default=None, description="只要这一天（含）之后创建的投递。格式 2026-09-01")
    end_date: date | None = Field(default=None, description="只要这一天（含）之前创建的投递。格式 2026-09-30")
    pos_id: int | None = Field(default=None, description="只要这个岗位的投递（岗位编号）")
    stage: str | None = Field(default=None, description="只要当前在这一关的投递。ai/resume/contact/phone/test/pro/hr/final")
    status: str | None = Field(default=None, description="只要这个状态的投递。pending=进行中 / pass=已录用 / fail=已淘汰")


class ExportIn(BaseModel):
    """导出请求：条件 + 想要哪几列 + 文件格式。"""

    # default_factory=ExportFilters：不传 filters 时自动造一个「什么都不筛」的空条件
    filters: ExportFilters = Field(default_factory=ExportFilters, description="筛选条件，不传 = 全部")
    fields: list[str] = Field(
        default_factory=list,
        description="想导出哪几列，填列的英文名（先调 GET /api/export/fields 看有哪些）。空列表 = 全部 21 列都导。mode=matrix 时本字段忽略",
    )
    format: str = Field(default="xlsx", description="文件格式：xlsx（Excel，推荐）或 csv")
    mode: str = Field(
        default="records",
        description=(
            "导出内容：records=逐条投递记录（默认）；"
            "matrix=「阶段 × 岗位」交叉汇总表（周报那种表，行=阶段、列=岗位+总计）"
        ),
    )
    range: str = Field(
        default="week",
        description="仅 mode=matrix 时使用：week 本周 / last_week 上周 / month 本月 / all 全部 / custom 自定义（自定义用 filters 里的 start_date、end_date）",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "filters": {"status": "pending"},
                    "fields": ["id", "candidate_name", "position_name", "current_stage", "overall_status"],
                    "format": "xlsx",
                    "mode": "records",
                },
                {"mode": "matrix", "range": "week", "format": "xlsx"},
            ]
        }
    }
