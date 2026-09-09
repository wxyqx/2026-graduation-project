"""【AI 接口配置的表格模板】"""
from pydantic import BaseModel, Field


class AiConfigIn(BaseModel):
    """新建配置：四个必填 + 是否立刻启用（默认不启用）。"""

    name: str = Field(min_length=1, max_length=50)
    base_url: str = Field(min_length=1, max_length=255)
    api_key: str = Field(min_length=1, max_length=255)
    model: str = Field(min_length=1, max_length=100)
    is_enabled: bool = False  # 前端用 true/false，数据库里存 1/0，转换在 routers/ai_configs.py 里做


class AiConfigUpdate(BaseModel):
    """编辑配置：都可不填，没填的保持原样。"""

    name: str | None = Field(default=None, min_length=1, max_length=50)
    base_url: str | None = Field(default=None, min_length=1, max_length=255)
    api_key: str | None = Field(default=None, min_length=1, max_length=255)
    model: str | None = Field(default=None, min_length=1, max_length=100)
    is_enabled: bool | None = None


class AiConfigOut(BaseModel):
    """回给前端的配置。api_key 也回传——自用系统，方便在设置页直接看和改。"""

    id: int
    name: str
    base_url: str
    api_key: str
    model: str
    is_enabled: bool
