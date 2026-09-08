from datetime import date

from pydantic import BaseModel, Field


class ExportFilters(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    pos_id: int | None = None
    stage: str | None = None
    status: str | None = None


class ExportIn(BaseModel):
    filters: ExportFilters = Field(default_factory=ExportFilters)
    fields: list[str] = Field(default_factory=list)
    format: str = "xlsx"
