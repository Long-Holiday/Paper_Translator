"""Resource regressions; isolated databases/files, no paid API calls."""

import asyncio
import io
import multiprocessing
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import time
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.models import Paper
from backend.app.resources import ResourceLimits, get_resource_limits
from backend.app.services.paper_service import PaperService
from backend.app.services.translation_process import _run_process, translate_isolated
from backend.app.workers import translation_worker as worker


def child_success(connection):
    connection.send(("progress", 50, "half"))
    connection.send(("result", "/tmp/translated.pdf"))
    connection.close()


def child_error(connection):
    connection.send(("error", "engine failed"))
    connection.close()


def child_crash(connection):
    os._exit(7)


def child_hang(connection):
    time.sleep(60)


class ProcessTests(unittest.TestCase):
    def test_real_child_error_is_forwarded_and_staging_removed(self):
        with TemporaryDirectory() as directory:
            output = Path(directory)
            with self.assertRaisesRegex(RuntimeError, "源 PDF 文件不存在"):
                translate_isolated(output / "missing.pdf", output)
            self.assertEqual(list(output.iterdir()), [])

    def test_progress_success_and_process_reaped(self):
        progress = Mock()
        before = {p.pid for p in multiprocessing.active_children()}
        self.assertEqual(_run_process(child_success, (), progress, 15), Path("/tmp/translated.pdf"))
        progress.assert_called_once_with(50, "half")
        self.assertEqual({p.pid for p in multiprocessing.active_children()}, before)

    def test_error_crash_timeout_and_shutdown_release_process(self):
        stop = threading.Event()
        stop.set()
        for target, timeout, event, pattern in (
            (child_error, 15, None, "engine failed"),
            (child_crash, 15, None, "异常退出"),
            (child_hang, 0.5, None, "超过"),
            (child_hang, 15, stop, "正在停止"),
        ):
            with self.subTest(target=target.__name__, stop=event is not None):
                before = {p.pid for p in multiprocessing.active_children()}
                with self.assertRaisesRegex(RuntimeError, pattern):
                    _run_process(target, (), None, timeout, event)
                self.assertEqual({p.pid for p in multiprocessing.active_children()}, before)

    def test_parent_removes_staging_directory_after_child_failure(self):
        with TemporaryDirectory() as directory, \
                patch("backend.app.services.translation_process._run_process", side_effect=RuntimeError("OOM")):
            output = Path(directory)
            (output / "original.pdf").write_bytes(b"original")
            with self.assertRaisesRegex(RuntimeError, "OOM"):
                translate_isolated(output / "original.pdf", output)
            self.assertEqual([p.name for p in output.iterdir()], ["original.pdf"])


class LimitTests(unittest.TestCase):
    def test_env_overrides_yaml_and_invalid_limits_fail_early(self):
        with patch("backend.app.resources.load_config", return_value={"resources": {"cpu_threads": 2}}), \
                patch.dict(os.environ, {"PT_CPU_THREADS": "1", "PT_TRANSLATION_BATCH_PAGES": "0"}):
            limits = get_resource_limits()
            self.assertEqual(limits.cpu_threads, 1)
            self.assertEqual(limits.translation_batch_pages, 0)
            with patch.dict(os.environ, {"PT_MAX_PENDING_TASKS": "0"}):
                with self.assertRaisesRegex(ValueError, "max_pending_tasks"):
                    get_resource_limits()


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        with self.sessions() as db:
            for number in range(1, 5):
                db.add(Paper(id=number, title="Test", original_filename="test.pdf",
                             original_pdf_path="/tmp/original.pdf"))
            db.commit()

    def test_bounded_queue_duplicate_and_submission_failure(self):
        with patch.object(worker, "SessionLocal", self.sessions), \
                patch.object(worker, "executor", Mock()), \
                patch.object(worker, "_active_paper_ids", set()), \
                patch.object(worker, "_stop_event", threading.Event()), \
                patch.object(worker, "get_resource_limits", return_value=ResourceLimits(max_pending_tasks=2)):
            self.assertTrue(worker.enqueue_translation(1))
            self.assertFalse(worker.enqueue_translation(1))
            self.assertTrue(worker.enqueue_translation(2))
            with self.assertRaises(worker.TranslationQueueFull):
                worker.enqueue_translation(3)
            self.assertEqual(worker._active_paper_ids, {1, 2})
            worker._active_paper_ids.clear()
            worker.executor.submit.side_effect = RuntimeError("submit failed")
            with self.assertRaisesRegex(RuntimeError, "submit failed"):
                worker.enqueue_translation(3)
            self.assertEqual(worker._active_paper_ids, set())
            with self.sessions() as db:
                self.assertEqual(db.get(Paper, 3).translation_status, "failed")

    def test_failed_child_marks_paper_failed_and_releases_queue_slot(self):
        with patch.object(worker, "SessionLocal", self.sessions), \
                patch.object(worker, "_active_paper_ids", {1}), \
                patch.object(worker, "translate_isolated", side_effect=RuntimeError("OOM")):
            worker._run_translation_job(1)
            self.assertEqual(worker._active_paper_ids, set())
            with self.sessions() as db:
                paper = db.get(Paper, 1)
                self.assertEqual(paper.translation_status, "failed")
                self.assertEqual(paper.translation_error, "OOM")

    def test_oversize_stream_rolls_back_database_and_files(self):
        with TemporaryDirectory() as directory, \
                patch("backend.app.services.paper_service.PAPERS_DIR", Path(directory)), \
                patch("backend.app.services.paper_service.get_resource_limits", return_value=ResourceLimits(max_upload_mb=1)):
            for reported_size in (None, 2 * 1024 * 1024):
                with self.subTest(size=reported_size), self.sessions() as db:
                    upload = UploadFile(io.BytesIO(b"x" * (1024 * 1024 + 1)), filename="large.pdf", size=reported_size)
                    with self.assertRaises(HTTPException) as exc:
                        asyncio.run(PaperService.create_paper(db, upload))
                    self.assertEqual(exc.exception.status_code, 413)
                    self.assertEqual(db.query(Paper).count(), 4)
                    self.assertEqual(list(Path(directory).iterdir()), [])

    def test_page_limit_rolls_back_database_and_files(self):
        with TemporaryDirectory() as directory, \
                patch("backend.app.services.paper_service.PAPERS_DIR", Path(directory)), \
                patch("backend.app.services.paper_service.PdfService.extract_pdf_info", return_value=("test", 201)):
            with self.sessions() as db:
                upload = UploadFile(io.BytesIO(b"%PDF-test"), filename="long.pdf")
                with self.assertRaises(HTTPException) as exc:
                    asyncio.run(PaperService.create_paper(db, upload))
                self.assertEqual(exc.exception.status_code, 413)
                self.assertEqual(db.query(Paper).count(), 4)
                self.assertEqual(list(Path(directory).iterdir()), [])

    def test_queue_full_route_reports_429_and_pdf_supports_ranges(self):
        from fastapi.testclient import TestClient
        from backend.app.auth import create_access_token
        from backend.app.database import get_db
        from backend.app.main import app

        def override_db():
            with self.sessions() as db:
                yield db

        previous = dict(app.dependency_overrides)
        self.addCleanup(lambda: (app.dependency_overrides.clear(), app.dependency_overrides.update(previous)))
        app.dependency_overrides[get_db] = override_db
        client = TestClient(app)
        client.headers["Authorization"] = f"Bearer {create_access_token()}"
        with patch("backend.app.api.papers.enqueue_translation", side_effect=worker.TranslationQueueFull("queue full")):
            response = client.post("/api/papers/1/translate")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["retry-after"], "30")
        with TemporaryDirectory() as directory:
            pdf = Path(directory) / "test.pdf"
            pdf.write_bytes(b"%PDF-1.7 example content")
            with self.sessions() as db:
                db.get(Paper, 1).original_pdf_path = str(pdf)
                db.commit()
            response = client.get("/api/papers/1/original", headers={"Range": "bytes=0-7"})
            self.assertEqual(response.status_code, 206)
            self.assertEqual(response.content, b"%PDF-1.7")

    def test_lifespan_recovers_stale_jobs_and_removes_only_temporary_files(self):
        from fastapi.testclient import TestClient
        from backend.app import main

        with self.sessions() as db:
            db.get(Paper, 1).translation_status = "translating"
            db.get(Paper, 2).translation_status = "queued"
            db.commit()
        with TemporaryDirectory() as directory:
            papers = Path(directory)
            paper_dir = papers / "1"
            paper_dir.mkdir()
            (paper_dir / ".translation-job-stale").mkdir()
            (paper_dir / ".translation-stale").mkdir()
            (paper_dir / "original.pdf").write_bytes(b"original")
            with patch.object(main, "init_db"), patch.object(main, "SessionLocal", self.sessions), \
                    patch.object(main, "PAPERS_DIR", papers), patch.object(worker, "SessionLocal", self.sessions), \
                    patch.object(worker, "executor", None), patch.object(worker, "_active_paper_ids", set()), \
                    patch.object(worker, "_stop_event", threading.Event()):
                with TestClient(main.app) as client:
                    self.assertEqual(client.get("/api/health").status_code, 200)
                    self.assertEqual([p.name for p in paper_dir.iterdir()], ["original.pdf"])
                    with self.sessions() as db:
                        self.assertEqual(db.get(Paper, 1).translation_status, "failed")
                        self.assertEqual(db.get(Paper, 2).translation_status, "failed")
                self.assertIsNone(worker.executor)


if __name__ == "__main__":
    unittest.main()
