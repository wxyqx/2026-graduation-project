"""【文件相关的表格模板】"""
from datetime import datetime

from pydantic import BaseModel, Field


class CandidateFileOut(BaseModel):
    """文件元数据（不含内容）。"""

    id: int
    candidate_id: int
    application_id: int | None = Field(default=None, description="绑定的投递编号；个人文件为 null")
    category: str = Field(description="resume / certificate / portfolio / other")
    original_name: str
    mime_type: str
    size_bytes: int
    is_current: bool = Field(description="是否为当前版本（简历替换后旧版本为 false）")
    uploaded_by_role: str = Field(description="candidate / hr")
    send_time: datetime | None = Field(default=None, description="发送给候选人的时间；仅 Offer 文件使用，NULL=未发送")
    upload_time: datetime
    download_url: str = Field(description="下载地址")
