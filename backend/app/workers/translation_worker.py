import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from backend.app.database import SessionLocal
from backend.app.models import Paper
from backend.app.services.translation_service import TranslationService

# 本地单用户推荐 max_workers=1，避免 CPU/GPU/网络资源过载
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="translation_worker")
translation_service = TranslationService()

# 保护线程安全的排队与状态跟踪
_lock = threading.Lock()
_active_paper_ids = set()


def _run_translation_job(paper_id: int):
    db = SessionLocal()
    try:
        paper = db.query(Paper).filter(Paper.id == paper_id).first()
        if not paper:
            return

        paper.translation_status = "translating"
        paper.translation_progress = 10
        paper.translation_error = None
        db.commit()

        source_pdf = Path(paper.original_pdf_path)
        output_dir = source_pdf.parent

        def on_progress(percent: int, message: str = ""):
            nonlocal paper_id
            # 100% 与 completed、译文路径一起提交，避免先显示完成再发布文件。
            if percent >= 100:
                return
            job_db = SessionLocal()
            try:
                p = job_db.query(Paper).filter(Paper.id == paper_id).first()
                if p and p.translation_status == "translating":
                    p.translation_progress = max(p.translation_progress, min(99, max(0, percent)))
                    job_db.commit()
            finally:
                job_db.close()

        # 调用翻译服务
        final_pdf = translation_service.translate(
            source_pdf=source_pdf,
            output_dir=output_dir,
            progress_callback=on_progress,
        )

        paper = db.query(Paper).filter(Paper.id == paper_id).first()
        if paper:
            paper.translated_pdf_path = str(final_pdf)
            paper.translation_status = "completed"
            paper.translation_progress = 100
            paper.translation_error = None
            db.commit()

    except Exception as e:
        paper = db.query(Paper).filter(Paper.id == paper_id).first()
        if paper:
            paper.translation_status = "failed"
            paper.translation_error = str(e)
            paper.translation_progress = 0
            db.commit()
    finally:
        with _lock:
            _active_paper_ids.discard(paper_id)
        db.close()


def enqueue_translation(paper_id: int) -> bool:
    """
    将论文翻译任务提交至后台线程池
    """
    with _lock:
        if paper_id in _active_paper_ids:
            return False  # 已在队列或正在执行中
        _active_paper_ids.add(paper_id)

    db = SessionLocal()
    try:
        paper = db.query(Paper).filter(Paper.id == paper_id).first()
        if paper:
            paper.translation_status = "queued"
            paper.translation_progress = 0
            paper.translation_error = None
            db.commit()
    finally:
        db.close()

    executor.submit(_run_translation_job, paper_id)
    return True
