"""
【HR 端文件接口】
  GET    /api/candidates/{can_id}/files       某候选人的文件列表
  POST   /api/candidates/{can_id}/files       代传文件（线下收到的简历等）
  DELETE /api/files/{file_id}                 删除文件
  GET    /api/files/{file_id}/download        下载文件

HR 可以看/下载所有候选人的文件；候选人端只能看自己的（见 portal_files.py）。
"""
from datetime import datetime
from typing import Annotated
from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    UploadFile,
    status,
)
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_hr
from app.models import Application, Candidate, CandidateFile, User
from app.schemas.file import CandidateFileOut
from app.services import file_service, notice_service, ownership
from app.services.log_service import log_action

router = APIRouter(prefix="/api", tags=["files"])

CanId = Annotated[int, Path(description="候选人编号")]
FileId = Annotated[int, Path(description="文件编号")]


def _candidate_or_404(db: Session, can_id: int) -> Candidate:
    c = db.get(Candidate, can_id)
    if c is None:
        raise HTTPException(status_code=404, detail="候选人不存在")
    return c


def _file_or_404(db: Session, file_id: int) -> CandidateFile:
    f = db.get(CandidateFile, file_id)
    if f is None:
        raise HTTPException(status_code=404, detail="文件不存在")
    return f


@router.get("/candidates/{can_id}/files", response_model=list[CandidateFileOut])
def list_candidate_files(can_id: CanId, db: Session = Depends(get_db), user: User = Depends(get_current_hr)):
    """某候选人的全部文件（简历、证书、作品）

**干什么用**：HR 候选人详情页「文件」分区。按上传时间倒序，简历会标出当前版本。

**权限**：主要负责人（候选人负责人）能看全部；协助负责人（非主要负责人）只能看到简历，
证书 / 作品 / 其他 / Offer 三件套属于私密附件，不可见。
"""
    c = _candidate_or_404(db, can_id)
    rows = db.scalars(
        select(CandidateFile)
        .where(CandidateFile.candidate_id == can_id)
        .order_by(CandidateFile.upload_time.desc())
    ).all()
    rows = ownership.filter_private_files(rows, c, user)
    return [file_service.serialize(f, for_candidate=False) for f in rows]


@router.post("/candidates/{can_id}/files", response_model=CandidateFileOut, status_code=status.HTTP_201_CREATED)
async def upload_candidate_file(
    can_id: CanId,
    file: UploadFile = File(description="PDF / DOC / DOCX / JPG / PNG，单文件 ≤10MB"),
    category: str = Form(default="resume", description="resume / certificate / portfolio / other"),
    application_id: int | None = Form(default=None, description="绑定到某次投递；个人文件不填"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_hr),
):
    """HR 上传候选人文件（简历 / 证书等）

**规则**：候选人端只读，所有上传/替换都由 HR 完成；上传简历同样会成为当前版本。
"""
    _candidate_or_404(db, can_id)
    if application_id is not None:
        app = db.get(Application, application_id)
        if app is None or app.can_id != can_id:
            raise HTTPException(status_code=404, detail="投递记录不存在")
    data = await file.read()
    try:
        saved = file_service.save_file(
            db,
            candidate_id=can_id,
            data=data,
            filename=file.filename,
            category=category,
            application_id=application_id,
            uploaded_by_role="hr",
        )
    except file_service.FileTooLarge as e:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(e))
    except file_service.FileError as e:
        raise HTTPException(status_code=400, detail=str(e))
    log_action(db, user, "create", target_type="file", target_id=saved.id, detail={"candidate_id": can_id})
    db.commit()
    db.refresh(saved)
    # HR 回传盖章文件（三类 Offer 文件）后，按模板生成「入职通知」草稿（候选人不可见，待 HR 编辑发送）
    if saved.category in file_service.OFFER_CATEGORIES and saved.application_id:
        try:
            app = db.get(Application, saved.application_id)
            if app is not None:
                notice_service.send_stage_notice(db, app, "onboard")
                db.commit()
        except Exception:
            db.rollback()  # 通知生成失败不影响文件上传本身
    return file_service.serialize(saved, for_candidate=False)


@router.put("/files/{file_id}/send", response_model=CandidateFileOut)
def send_offer_file(file_id: FileId, db: Session = Depends(get_db), user: User = Depends(get_current_hr)):
    """发送 Offer 文件给候选人（仅限 offer 分类）

**干什么用**：录用协议 / offer / 背景调查这类文档上传后先不发给候选人，HR 预览确认后再点发送；
发送后候选人端「文件」页立即可见、可下载填写。发送时间记录在文件上，并写入操作日志供技术管理端查看。

**可能出错**：404 文件不存在；400 该文件不是 Offer 文件（其他分类本来就对候选人可见）。
"""
    f = _file_or_404(db, file_id)
    if f.category not in file_service.OFFER_CATEGORIES:
        raise HTTPException(status_code=400, detail="只有录用协议 / Offer / 背景调查需要发送；其他分类上传后即对候选人可见")
    c = db.get(Candidate, f.candidate_id)
    if c is not None and not ownership.is_primary_owner(c, user):
        raise HTTPException(status_code=403, detail="Offer 文件仅候选人负责人可以发送")
    if f.send_time is None:
        f.send_time = datetime.now()
        log_action(
            db,
            user,
            "update",
            target_type="file",
            target_id=f.id,
            detail={"candidate_id": f.candidate_id, "application_id": f.application_id, "file": f.original_name, "sent": True},
        )
        db.commit()
    db.refresh(f)
    return file_service.serialize(f, for_candidate=False)


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(file_id: FileId, db: Session = Depends(get_db), user: User = Depends(get_current_hr)):
    """删除文件（HR；私密附件仅候选人负责人可删，简历类任意 HR 可删）"""
    f = _file_or_404(db, file_id)
    c = db.get(Candidate, f.candidate_id)
    if c is not None and f.category != "resume" and not ownership.is_primary_owner(c, user):
        raise HTTPException(status_code=403, detail="该附件仅候选人负责人可以删除")
    log_action(db, user, "delete", target_type="file", target_id=f.id, detail={"name": f.original_name})
    db.delete(f)
    db.commit()


@router.get("/files/{file_id}/download")
def download_file(file_id: FileId, db: Session = Depends(get_db), user: User = Depends(get_current_hr)):
    """下载文件（HR）

返回文件流。中文文件名用 RFC 5987 的 `filename*` 编码，浏览器能正确还原。
"""
    f = _file_or_404(db, file_id)
    # 私密附件：非主要负责人（协助负责人）连下载/预览也不行，简历除外
    c = db.get(Candidate, f.candidate_id)
    if c is not None and f.category != "resume" and not ownership.is_primary_owner(c, user):
        raise HTTPException(status_code=403, detail="该附件仅候选人负责人可见，你只能查看简历与面试相关材料")
    return Response(
        content=f.content,
        media_type=f.mime_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(f.original_name)}"},
    )


@router.put("/files/{file_id}/promote-resume", response_model=CandidateFileOut)
def promote_resume(file_id: FileId, db: Session = Depends(get_db), user: User = Depends(get_current_hr)):
    """把候选人自助上传的简历转正为当前简历（v3.17 P1-7）

**干什么用**：候选人端上传的新版简历先挂起（is_current=0），HR 核对后调本接口转正：
原当前简历自动降为历史版本，被转正的文件变成「当前简历」。
"""
    f = _file_or_404(db, file_id)
    if f.category != "resume" or f.uploaded_by_role != "candidate":
        raise HTTPException(status_code=400, detail="只能转正「候选人上传」的简历")
    if f.is_current:
        raise HTTPException(status_code=400, detail="该文件已是当前简历")
    # 行锁 + 降级旧当前版本（与 save_file 同一套并发口径）
    db.execute(select(Candidate.id).where(Candidate.id == f.candidate_id).with_for_update())
    for old in db.scalars(
        select(CandidateFile).where(
            CandidateFile.candidate_id == f.candidate_id,
            CandidateFile.category == "resume",
            CandidateFile.is_current == 1,
        )
    ).all():
        old.is_current = 0
    f.is_current = 1
    log_action(db, user, "update", target_type="file", target_id=f.id,
               detail={"promote_resume": True, "candidate_id": f.candidate_id, "name": f.original_name})
    db.commit()
    db.refresh(f)
    return file_service.serialize(f, for_candidate=False)
