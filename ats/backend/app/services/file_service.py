"""
【候选人文件服务】——简历、证书、作品等，内容直接存 MySQL（LONGBLOB）

规则：
  · 单文件 ≤ PORTAL_UPLOAD_MAX_MB（默认 10MB）
  · 单候选人文件总量 ≤ PORTAL_FILE_TOTAL_MB（默认 50MB）
  · 只允许 PDF / DOC / DOCX / JPG / PNG
  · 简历（resume）保留历史：新上传的把旧的 Is_Current 置 0，新的置 1
  · 文件内容不落磁盘，下载时才从数据库读 Content
"""
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import CandidateFile

# 扩展名 → MIME 类型（白名单）
ALLOWED_TYPES: dict[str, str] = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}

CATEGORIES = ("resume", "certificate", "portfolio", "other", "offer", "offer_agreement", "background_check")
# 这三类是要「发送」后才对候选人可见的 Offer 类文档
OFFER_CATEGORIES = ("offer", "offer_agreement", "background_check")


class FileError(ValueError):
    """文件不合规（类型 / 大小 / 分类）。"""


class FileTooLarge(FileError):
    """单个文件或总量超限。"""


def clean_filename(name: str | None) -> str:
    """去掉路径、控制字符，只留文件名；空名字给个默认值。"""
    raw = Path(name or "").name
    safe = "".join(ch for ch in raw if ch.isprintable() and ch not in '\\/:*?"<>|').strip()
    return (safe or "file")[:255]


def validate_file(filename: str | None, data: bytes) -> tuple[str, str]:
    """校验并返回 (MIME 类型, 清洗后的文件名)。不合规抛 FileError。"""
    if not data:
        raise FileError("文件是空的")
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_TYPES:
        raise FileError("只支持 PDF / DOC / DOCX / JPG / PNG 文件")
    limit = settings.portal_upload_max_mb * 1024 * 1024
    if len(data) > limit:
        raise FileTooLarge(f"单个文件不能超过 {settings.portal_upload_max_mb}MB")
    return ALLOWED_TYPES[suffix], clean_filename(filename)


def total_size(db: Session, candidate_id: int) -> int:
    """某个候选人已上传文件的总字节数。"""
    return int(
        db.scalar(select(func.coalesce(func.sum(CandidateFile.size_bytes), 0)).where(CandidateFile.candidate_id == candidate_id))
        or 0
    )


def save_file(
    db: Session,
    *,
    candidate_id: int,
    data: bytes,
    filename: str | None,
    category: str,
    application_id: int | None,
    uploaded_by_role: str,
) -> CandidateFile:
    """保存一个文件。调用方负责校验候选人/投递归属，并 commit。"""
    if category not in CATEGORIES:
        raise FileError("文件分类不合法")
    mime, name = validate_file(filename, data)
    limit = settings.portal_file_total_mb * 1024 * 1024
    if total_size(db, candidate_id) + len(data) > limit:
        raise FileTooLarge(f"每位候选人的文件总量不能超过 {settings.portal_file_total_mb}MB")

    # 简历换新版本：旧版本保留但不再是 current
    if category == "resume":
        old = db.scalars(
            select(CandidateFile).where(
                CandidateFile.candidate_id == candidate_id,
                CandidateFile.category == "resume",
                CandidateFile.is_current == 1,
            )
        ).all()
        for f in old:
            f.is_current = 0

    f = CandidateFile(
        candidate_id=candidate_id,
        application_id=application_id,
        category=category,
        original_name=name,
        mime_type=mime,
        size_bytes=len(data),
        content=data,
        is_current=1,
        uploaded_by_role=uploaded_by_role,
        upload_time=datetime.now(),
    )
    db.add(f)
    db.flush()
    return f


def current_resume(db: Session, candidate_id: int) -> CandidateFile | None:
    """取当前版本简历。"""
    return db.scalar(
        select(CandidateFile)
        .where(
            CandidateFile.candidate_id == candidate_id,
            CandidateFile.category == "resume",
            CandidateFile.is_current == 1,
        )
        .order_by(CandidateFile.upload_time.desc())
    )


def serialize(f: CandidateFile, *, for_candidate: bool) -> dict:
    """文件元数据（不含内容）。"""
    base = "/api/portal/files" if for_candidate else "/api/files"
    return {
        "id": f.id,
        "candidate_id": f.candidate_id,
        "application_id": f.application_id,
        "category": f.category,
        "original_name": f.original_name,
        "mime_type": f.mime_type,
        "size_bytes": f.size_bytes,
        "send_time": f.send_time,
        "is_current": bool(f.is_current),
        "uploaded_by_role": f.uploaded_by_role,
        "upload_time": f.upload_time,
        "download_url": f"{base}/{f.id}/download",
    }
