"""【AI 接口配置的表格模板】"""
from pydantic import BaseModel, Field

_EXAMPLE = {
    "name": "GLM免费版",
    "base_url": "https://open.bigmodel.cn/api/paas/v4",
    "api_key": "把你在智谱/通义等平台申请的密钥粘这里",
    "model": "glm-4-flash",
    "is_enabled": True,
}


class AiConfigIn(BaseModel):
    """新建配置：四个必填 + 是否立刻启用（默认不启用）。"""

    name: str = Field(min_length=1, max_length=50, description="给这个配置起个名字，自己认得就行。例：GLM免费版")
    base_url: str = Field(
        min_length=1,
        max_length=255,
        description="AI 接口的网址。填到 /v4 或 /v1 就行，后面的 /chat/completions 系统自动补。例：https://open.bigmodel.cn/api/paas/v4",
    )
    api_key: str = Field(min_length=1, max_length=255, description="密钥（相当于门票），在 AI 平台的「API Key」页面申请")
    model: str = Field(min_length=1, max_length=100, description="模型名字，看平台文档。例：glm-4-flash（免费）/ qwen-plus / deepseek-chat")
    is_enabled: bool = Field(default=False, description="建好就启用？true=马上能用；false=先存着。可以同时启用多个，AI 录入时轮着用")

    model_config = {"json_schema_extra": {"examples": [_EXAMPLE]}}


class AiConfigUpdate(BaseModel):
    """编辑配置：都可不填，没填的保持原样。"""

    name: str | None = Field(default=None, min_length=1, max_length=50, description="新名字，不改就别传")
    base_url: str | None = Field(default=None, min_length=1, max_length=255, description="新网址，不改就别传")
    api_key: str | None = Field(default=None, min_length=1, max_length=255, description="新密钥，不改就别传")
    model: str | None = Field(default=None, min_length=1, max_length=100, description="新模型名，不改就别传")
    is_enabled: bool | None = Field(default=None, description="改启用状态，不改就别传（也可以用 enable/disable 接口）")

    model_config = {"json_schema_extra": {"examples": [{"model": "glm-4-plus"}]}}


class AiConfigOut(BaseModel):
    """回给前端的配置。api_key 也回传——自用系统，方便在设置页直接看和改。"""

    id: int = Field(description="配置编号，启用/停用/编辑/删除时用")
    name: str = Field(description="配置名")
    base_url: str = Field(description="接口网址")
    api_key: str = Field(description="密钥（自用系统直接回传，方便查看）")
    model: str = Field(description="模型名")
    is_enabled: bool = Field(description="是否启用")
