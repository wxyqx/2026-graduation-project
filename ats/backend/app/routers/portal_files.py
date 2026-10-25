"""
【候选人端文件接口】

  GET /api/portal/files                 我的文件列表（HR 上传的 + 我回传的）
  GET /api/portal/files/{id}/download   下载自己的文件
  POST /api/portal/files                回传文件（签署的录用协议 / Offer / 背景调查 / 其他附件）

简历仍然只读（HR 上传、候选人不能动）；回传是 v3.16 新增：
收到 Offer 类文件后，候选人按类型把签署好的文件传回来（绑定对应投递），
HR 端在投递详情「Offer 文件」页签能看到「已回传」标记并下载。
"""
from typing import Annotated
from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_candidate
from app.models import CandidateFile, CandidateNotice, User
from app.schemas.file import CandidateFileOut
from app.services import file_service

router = APIRouter(prefix="/api/portal/files", tags=["portal-files"])

FileId = Annotated[int, Path(description="文件编号")]


def _own_file(db: Session, file_id: int, user: User) -> CandidateFile:
    f = db.get(CandidateFile, file_id)
    if f is None or user.candidate_id is None or f.candidate_id != user.candidate_id:
        raise HTTPException(status_code=404, detail="文件不存在")
    return f


@router.get("", response_model=list[CandidateFileOut])
def list_my_files(
    category: str | None = Query(default=None, description="只看某一类：resume / certificate / portfolio / other"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_candidate),
):
    """我的文件列表（只读）

**干什么用**：候选人端「我的简历/附件」页。HR 上传的简历与附件会出现在这里，按上传时间倒序。

**返回什么**：文件元数据数组（不含文件内容），带 `download_url`。简历会标出当前版本。
"""
    if user.candidate_id is None:
        raise HTTPException(status_code=401, detail="账号未关联候选人档案，请联系 HR")
    stmt = (
        select(CandidateFile)
        .where(
            CandidateFile.candidate_id == user.candidate_id,
            # 三类 Offer 文件要 HR 发送「通过通知」后才可见（旧数据按文件级 Send_Time 兼容）；其余分类不受影响
            CandidateFile.category.notin_(file_service.OFFER_CATEGORIES)
            | CandidateFile.send_time.isnot(None)
            | (
                CandidateFile.application_id.in_(
                    select(CandidateNotice.application_id).where(
                        CandidateNotice.candidate_id == user.candidate_id,
                        CandidateNotice.send_time.isnot(None),
                    )
                )
            ),
        )
        .order_by(CandidateFile.upload_time.desc())
    )
    if category:
        stmt = stmt.where(CandidateFile.category == category)
    return [file_service.serialize(f, for_candidate=True) for f in db.scalars(stmt).all()]


@router.get("/{file_id}/download")
def download_my_file(
    file_id: FileId,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_candidate),
):
    """下载自己的文件（只读）

返回文件流，文件名按原始中文名返回。
"""
    f = _own_file(db, file_id, user)
    return Response(
        content=f.content,
        media_type=f.mime_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(f.original_name)}"},
    )


# 候选人可回传的分类：三类 Offer 文件 + 其他附件
RETURN_CATEGORIES = (*file_service.OFFER_CATEGORIES, "other")


@router.post("", response_model=CandidateFileOut, status_code=status.HTTP_201_CREATED)
async def upload_return_file(
    file: UploadFile = File(description="回传的文件：jpg / png / pdf / doc(x) 等，≤10MB"),
    category: str = Form(description="offer_agreement / offer / background_check / other"),
    application_id: int = Form(description="回传对应的投递编号"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_candidate),
):
    """回传文件给 HR（签署件 / 附件）

**干什么用**：收到 Offer 文件并签署后，按类型把签署件传回来（不同文件用不同按钮）；
传回的文件 HR 在投递详情「Offer 文件」页签会看到「已回传」标记。同一类型可以重新上传，
以最新一次为准，历史版本保留。

**怎么填**：
- `category`：offer_agreement=签署的录用协议 / offer=签署的 Offer / background_check=签署的背景调查 / other=其他附件
- `application_id`：这条回传对应哪次投递

**可能出错**：400 分类不合法 / 投递不属于你 / 文件超限。
"""
    if user.candidate_id is None:
        raise HTTPException(status_code=401, detail="账号未关联候选人档案，请联系 HR")
    if category not in RETURN_CATEGORIES:
        raise HTTPException(status_code=400, detail="回传分类不合法")
    from app.models import Application

    app = db.get(Application, application_id)
    if app is None or app.can_id != user.candidate_id:
        raise HTTPException(status_code=404, detail="投递记录不存在")
    data = await file.read()
    try:
        saved = file_service.save_file(
            db,
            candidate_id=user.candidate_id,
            data=data,
            filename=file.filename,
            category=category,
            application_id=application_id,
            uploaded_by_role="candidate",
        )
    except file_service.FileTooLarge as e:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(e))
    except file_service.FileError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    db.refresh(saved)
    return file_service.serialize(saved, for_candidate=True)
