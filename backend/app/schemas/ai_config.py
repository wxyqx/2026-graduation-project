from pydantic import BaseModel, Field


class AiConfigIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    base_url: str = Field(min_length=1, max_length=255)
    api_key: str = Field(min_length=1, max_length=255)
    model: str = Field(min_length=1, max_length=100)
    is_enabled: bool = False


class AiConfigUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    base_url: str | None = Field(default=None, min_length=1, max_length=255)
    api_key: str | None = Field(default=None, min_length=1, max_length=255)
    model: str | None = Field(default=None, min_length=1, max_length=100)
    is_enabled: bool | None = None


class AiConfigOut(BaseModel):
    id: int
    name: str
    base_url: str
    api_key: str
    model: str
    is_enabled: bool
