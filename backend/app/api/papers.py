from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Query, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from backend.app.auth import get_current_user
from backend.app.database import get_db
from backend.app.schemas import PaperResponse, ReadingPositionUpdate, TranslateResponse
from backend.app.services.paper_service import PaperService
from backend.app.services.translation_updates import stream_translation_updates
from backend.app.workers.translation_worker import enqueue_translation, TranslationQueueFull

router = APIRouter(
    prefix="/papers",
    tags=["papers"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=List[PaperResponse])
def get_papers(
    search: Optional[str] = Query(None, description="搜索关键词"),
    db: Session = Depends(get_db),
):
    """获取论文列表，支持按标题或文件名搜索"""
    return PaperService.list_papers(db=db, search=search)


@router.post("", response_model=PaperResponse)
async def upload_paper(
    file: UploadFile = File(..., description="上传的英文论文 PDF 文件"),
    db: Session = Depends(get_db),
):
    """导入新的论文 PDF"""
    return await PaperService.create_paper(db=db, file=file)


@router.get("/events")
async def translation_events(request: Request, ids: List[int] = Query(...)):
    """订阅指定论文的翻译进度，避免前端反复请求完整论文列表。"""
    return StreamingResponse(
        stream_translation_updates(request, sorted(set(ids))),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{paper_id}", response_model=PaperResponse)
def get_paper(paper_id: int, db: Session = Depends(get_db)):
    """获取指定论文的详情"""
    return PaperService.get_paper(db=db, paper_id=paper_id)


@router.delete("/{paper_id}")
def delete_paper(paper_id: int, db: Session = Depends(get_db)):
    """删除论文及其本地文件"""
    PaperService.delete_paper(db=db, paper_id=paper_id)
    return {"status": "success", "message": f"论文 {paper_id} 已删除"}


@router.post("/{paper_id}/translate", response_model=TranslateResponse)
def start_translate(paper_id: int, db: Session = Depends(get_db)):
    """触发论文翻译任务"""
    paper = PaperService.get_paper(db=db, paper_id=paper_id)
    if paper.translation_status in ["queued", "translating"]:
        return TranslateResponse(status="already_running", message="该论文已在翻译中或等待队列中")

    try:
        success = enqueue_translation(paper_id)
    except TranslationQueueFull as exc:
        raise HTTPException(status_code=429, detail=str(exc), headers={"Retry-After": "30"})
    if not success:
        return TranslateResponse(status="already_running", message="任务已在处理队列中")

    return TranslateResponse(status="started", message="翻译任务已启动")


@router.get("/{paper_id}/original")
def get_original_pdf(paper_id: int, db: Session = Depends(get_db)):
    """获取原始 PDF 文件"""
    paper = PaperService.get_paper(db=db, paper_id=paper_id)
    path = Path(paper.original_pdf_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="原始 PDF 文件不存在")
    return FileResponse(
        path=path,
        media_type="application/pdf",
        filename=f"{paper.title}_original.pdf",
    )


@router.get("/{paper_id}/translated")
def get_translated_pdf(paper_id: int, db: Session = Depends(get_db)):
    """获取翻译后的中文 PDF 文件"""
    paper = PaperService.get_paper(db=db, paper_id=paper_id)
    if not paper.translated_pdf_path:
        raise HTTPException(status_code=404, detail="该论文尚未生成翻译 PDF")

    path = Path(paper.translated_pdf_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="翻译 PDF 文件不存在或已被移除")

    return FileResponse(
        path=path,
        media_type="application/pdf",
        filename=f"{paper.title}_translated.pdf",
    )


@router.put("/{paper_id}/reading-position", response_model=PaperResponse)
def update_reading_position(
    paper_id: int,
    body: ReadingPositionUpdate,
    db: Session = Depends(get_db),
):
    """更新论文最后阅读页码"""
    return PaperService.update_reading_position(db=db, paper_id=paper_id, page=body.page)
