import shutil
from pathlib import Path
from typing import List, Optional
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from backend.app.config import PAPERS_DIR
from backend.app.models import Paper
from backend.app.resources import get_resource_limits
from backend.app.services.pdf_service import PdfService


class PaperService:
    @staticmethod
    def list_papers(db: Session, search: Optional[str] = None) -> List[Paper]:
        query = db.query(Paper)
        if search and search.strip():
            keyword = f"%{search.strip()}%"
            query = query.filter(Paper.title.ilike(keyword) | Paper.original_filename.ilike(keyword))
        return query.order_by(Paper.id.desc()).all()

    @staticmethod
    def get_paper(db: Session, paper_id: int) -> Paper:
        paper = db.query(Paper).filter(Paper.id == paper_id).first()
        if not paper:
            raise HTTPException(status_code=404, detail=f"未找到 ID 为 {paper_id} 的论文")
        return paper

    @staticmethod
    async def create_paper(db: Session, file: UploadFile) -> Paper:
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="仅支持上传 PDF 格式文件")
        limits = get_resource_limits()
        max_bytes = limits.max_upload_mb * 1024 * 1024
        if file.size is not None and file.size > max_bytes:
            raise HTTPException(status_code=413, detail=f"PDF 不能超过 {limits.max_upload_mb} MB")

        # 1. 先在数据库创建记录以获取唯一自增 ID
        paper = Paper(
            title="Processing...",
            original_filename=file.filename,
            original_pdf_path="",
            translation_status="pending",
            translation_progress=0,
            last_read_page=1,
        )
        db.add(paper)
        db.commit()
        db.refresh(paper)

        paper_id = paper.id
        # 2. 建立本地专用存储目录 data/papers/{id}/
        paper_dir = PAPERS_DIR / str(paper_id)
        paper_dir.mkdir(parents=True, exist_ok=True)
        original_pdf_path = paper_dir / "original.pdf"

        # 3. 流式写入文件，避免大文件一次性进内存
        try:
            written = 0
            with open(original_pdf_path, "wb") as buffer:
                while content := await file.read(1024 * 1024):  # 1MB 块
                    written += len(content)
                    if written > max_bytes:
                        raise HTTPException(status_code=413, detail=f"PDF 不能超过 {limits.max_upload_mb} MB")
                    buffer.write(content)
            # Reject oversized documents before they can enter the worker queue.
            title, page_count = PdfService.extract_pdf_info(original_pdf_path, file.filename)
            if page_count > limits.max_pdf_pages:
                raise HTTPException(status_code=413, detail=f"PDF 不能超过 {limits.max_pdf_pages} 页")
        except Exception as e:
            shutil.rmtree(paper_dir, ignore_errors=True)
            db.delete(paper)
            db.commit()
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=f"保存 PDF 文件失败: {str(e)}")
        finally:
            await file.close()

        paper.title = title
        paper.original_pdf_path = str(original_pdf_path)
        paper.page_count = page_count
        db.commit()
        db.refresh(paper)

        return paper

    @staticmethod
    def delete_paper(db: Session, paper_id: int) -> None:
        paper = db.query(Paper).filter(Paper.id == paper_id).first()
        if not paper:
            raise HTTPException(status_code=404, detail="论文不存在")
        if paper.translation_status in ("queued", "translating"):
            raise HTTPException(status_code=409, detail="请等待翻译任务完成后再删除论文")

        # 1. 删除文件目录
        paper_dir = PAPERS_DIR / str(paper_id)
        if paper_dir.exists():
            shutil.rmtree(paper_dir, ignore_errors=True)

        # 2. 删除数据库记录
        db.delete(paper)
        db.commit()

    @staticmethod
    def update_reading_position(db: Session, paper_id: int, page: int) -> Paper:
        paper = db.query(Paper).filter(Paper.id == paper_id).first()
        if not paper:
            raise HTTPException(status_code=404, detail="论文不存在")

        paper.last_read_page = max(1, page)
        db.commit()
        db.refresh(paper)
        return paper
