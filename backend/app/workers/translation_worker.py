import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from backend.app.database import SessionLocal
from backend.app.models import Paper
from backend.app.resources import get_resource_limits
from backend.app.services.translation_process import translate_isolated

# One lightweight coordinator; heavy imports and inference live in a child.
executor = None
_lock = threading.Lock()
_active_paper_ids = set()
_stop_event = threading.Event()


class TranslationQueueFull(Exception):
    pass


def start_worker():
    global executor
    with _lock:
        _stop_event.clear()
        if executor is None:
            executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="translation_worker")


def shutdown_worker():
    global executor
    _stop_event.set()
    with _lock:
        current, executor = executor, None
    if current is not None:
        current.shutdown(wait=True, cancel_futures=True)
    with SessionLocal() as db:
        db.query(Paper).filter(Paper.translation_status.in_(["translating", "queued"])).update({
            Paper.translation_status: "failed",
            Paper.translation_error: "服务已停止，请重新翻译",
            Paper.translation_progress: 0,
        }, synchronize_session=False)
        db.commit()
    with _lock:
        _active_paper_ids.clear()


def _update_paper(paper_id, **values):
    with SessionLocal() as db:
        paper = db.get(Paper, paper_id)
        if paper:
            for key, value in values.items():
                setattr(paper, key, value)
            db.commit()


def _run_translation_job(paper_id: int):
    try:
        # Do not hold a SQLite connection throughout a lengthy translation.
        with SessionLocal() as db:
            paper = db.get(Paper, paper_id)
            if not paper:
                return
            source_pdf = Path(paper.original_pdf_path)
            paper.translation_status = "translating"
            paper.translation_progress = 10
            paper.translation_error = None
            db.commit()

        def on_progress(percent, message=""):
            _update_paper(paper_id, translation_progress=percent)

        final_pdf = translate_isolated(source_pdf, source_pdf.parent, on_progress, _stop_event)
        _update_paper(paper_id, translated_pdf_path=str(final_pdf),
                      translation_status="completed", translation_progress=100,
                      translation_error=None)
    except Exception as exc:
        _update_paper(paper_id, translation_status="failed", translation_progress=0,
                      translation_error=str(exc))
    finally:
        with _lock:
            _active_paper_ids.discard(paper_id)


def enqueue_translation(paper_id: int) -> bool:
    global executor
    limits = get_resource_limits()
    with _lock:
        if paper_id in _active_paper_ids:
            return False
        if _stop_event.is_set():
            raise TranslationQueueFull("服务正在停止，请稍后重试")
        if len(_active_paper_ids) >= limits.max_pending_tasks:
            raise TranslationQueueFull(f"最多允许 {limits.max_pending_tasks} 个运行或排队任务，请等待完成")
        _active_paper_ids.add(paper_id)
        try:
            with SessionLocal() as db:
                paper = db.get(Paper, paper_id)
                if not paper:
                    _active_paper_ids.discard(paper_id)
                    return False
                paper.translation_status = "queued"
                paper.translation_progress = 0
                paper.translation_error = None
                db.commit()
            if executor is None:
                executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="translation_worker")
            executor.submit(_run_translation_job, paper_id)
        except Exception:
            _active_paper_ids.discard(paper_id)
            _update_paper(paper_id, translation_status="failed", translation_error="提交任务失败，请重试")
            raise
    return True
