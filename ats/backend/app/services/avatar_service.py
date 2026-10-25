"""
【头像服务】三个端（HR / 候选人 / 技术管理员）共用。

头像存 User.Avatar（LONGBLOB），接口按登录用户自己上传/获取；
图片仅限 image/*，≤5MB。前端拿 blob 转 objectURL 显示。
"""
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.models import User

MAX_AVATAR_MB = 5


async def save_avatar(db: Session, user: User, file: UploadFile) -> None:
    data = await file.read()
    if len(data) > MAX_AVATAR_MB * 1024 * 1024:
        raise ValueError(f"头像不能超过 {MAX_AVATAR_MB}MB")
    mime = (file.content_type or "").lower()
    if not mime.startswith("image/"):
        raise ValueError("头像必须是图片（jpg / png / webp / gif 等）")
    user.avatar = data
    user.avatar_mime = mime


def avatar_response(user: User):
    """头像图片响应；没设置时返回 404，前端用首字占位。"""
    from fastapi import HTTPException, Response, status

    if not user.avatar:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="还没有设置头像")
    return Response(content=user.avatar, media_type=user.avatar_mime or "image/png",
                    headers={"Cache-Control": "no-store"})
