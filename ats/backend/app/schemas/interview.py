"""【面试评价的请求 / 返回模板】"""
from pydantic import BaseModel, Field

_EXAMPLE = {
    "transcript": "xyq 02:18\n喂，你能听到吗？……\n候选人 02:20\n能听到，我在惠州。"
}


class EvaluateIn(BaseModel):
    """生成面试评价的请求：把逐字稿整段贴进来。"""

    transcript: str = Field(
        min_length=1,
        max_length=30000,
        description="面试对话逐字稿全文。直接粘贴即可，带不带时间戳、说话人怎么标都行。最长 3 万字，超了请分段",
    )

    model_config = {"json_schema_extra": {"examples": [_EXAMPLE]}}


class EvaluateOut(BaseModel):
    """生成的面试评价。text 是完整的评价正文，直接显示/复制。"""

    text: str = Field(description="面试评价正文，按固定 7 项模板排版好的文字")
    config_used: str = Field(description="这次实际用的 AI 配置名（配了多个时轮着用）")
