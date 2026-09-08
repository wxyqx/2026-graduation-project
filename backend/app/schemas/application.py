from pydantic import BaseModel, Field


class ApplicationCreate(BaseModel):
    can_id: int
    pos_id: int


class AdvanceIn(BaseModel):
    from_stage: str = Field(alias="fromStage")
    result: str

    model_config = {"populate_by_name": True}


class RevertIn(BaseModel):
    to_stage: str | None = Field(default=None, alias="toStage")

    model_config = {"populate_by_name": True}
