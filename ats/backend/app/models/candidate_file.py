"""
【Candidate_File 表：候选人文件（HR 上传，候选人只读）】——简历、证书、作品等

文件内容直接存数据库（LONGBLOB），不落磁盘，符合「全部使用最开始那个数据库」的要求。
列表查询时不要把 Content 查出来（模型里设了 deferred=True），只有下载时才读它。

替换简历不删旧文件：旧记录 Is_Current 置 0，新记录置 1，保留历史。
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, SmallInteger, String
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class CandidateFile(Base):
    __tablename__ = "Candidate_File"

    id: Mapped[int] = mapped_column("ID", Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        "Candidate_ID", Integer, ForeignKey("Candidate.ID", ondelete="CASCADE"), nullable=False
    )
    # 绑定到某次投递（岗位表专用附件）；个人简历/证书为空
    application_id: Mapped[int | None] = mapped_column(
        "Application_ID", Integer, ForeignKey("Application.ID", ondelete="SET NULL"), nullable=True
    )
    category: Mapped[str] = mapped_column(String(20), nullable=False)  # resume / certificate / portfolio / other
    original_name: Mapped[str] = mapped_column("Original_Name", String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column("Mime_Type", String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column("Size_Bytes", Integer, nullable=False)
    # deferred=True：查询列表时不把几 MB 的内容一起读出来
    content: Mapped[bytes] = mapped_column(LONGBLOB, nullable=False, deferred=True)
    is_current: Mapped[int] = mapped_column("Is_Current", SmallInteger, nullable=False, default=1)
    uploaded_by_role: Mapped[str] = mapped_column("Uploaded_By_Role", String(20), nullable=False)  # candidate / hr
    upload_time: Mapped[datetime] = mapped_column("Upload_Time", DateTime, nullable=False)
    send_time: Mapped[datetime | None] = mapped_column("Send_Time", DateTime)  # 发送给候选人的时间；NULL=未发送
