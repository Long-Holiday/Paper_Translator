"""轮询回归测试；使用独立内存数据库，不修改本地论文或调用翻译服务。"""
import unittest
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.main import app
from backend.app.models import Paper
from backend.app.services.translation_updates import get_translation_snapshot
from backend.app.workers.translation_worker import _run_translation_job


def snapshot(*statuses, removed_ids=None):
    return {
        "papers": [
            {"id": index, "translation_status": status, "translation_progress": progress}
            for index, (status, progress) in enumerate(statuses, 1)
        ],
        "removed_ids": removed_ids or [],
    }


class SnapshotTests(unittest.TestCase):
    def test_reads_fresh_database_state_and_reports_deleted_papers(self):
        engine = create_engine("sqlite://")
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        sessions = sessionmaker(bind=engine)
        with sessions() as db:
            db.add(Paper(id=1, title="论文", original_filename="test.pdf", original_pdf_path="/tmp/test.pdf",
                         translation_status="queued", translation_progress=0, last_read_page=1))
            db.commit()

        with patch("backend.app.services.translation_updates.SessionLocal", sessions):
            initial = get_translation_snapshot([1, 2])
            self.assertEqual(initial["removed_ids"], [2])
            self.assertEqual(initial["papers"][0]["translation_status"], "queued")
            self.assertNotIn("original_pdf_path", initial["papers"][0])

            with sessions() as db:
                paper = db.get(Paper, 1)
                paper.translation_status = "completed"
                paper.translation_progress = 100
                db.commit()
            updated = get_translation_snapshot([1])
            self.assertEqual(updated["papers"][0]["translation_progress"], 100)
            self.assertEqual(updated["papers"][0]["translation_status"], "completed")


class WorkerProgressTests(unittest.TestCase):
    def test_progress_commits_are_visible_and_completion_is_atomic(self):
        engine = create_engine("sqlite://", poolclass=StaticPool,
                               connect_args={"check_same_thread": False})
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        sessions = sessionmaker(bind=engine)
        with sessions() as db:
            db.add(Paper(id=1, title="论文", original_filename="test.pdf",
                         original_pdf_path="/tmp/test.pdf", translation_status="queued"))
            db.commit()

        def translate(**kwargs):
            progress = kwargs["progress_callback"]
            for value, expected in ((35, 35), (60, 60), (46, 60), (90, 90), (100, 90)):
                progress(value)
                current = get_translation_snapshot([1])["papers"][0]
                self.assertEqual(current["translation_progress"], expected)
                self.assertEqual(current["translation_status"], "translating")
            return "/tmp/translated.pdf"

        with patch("backend.app.workers.translation_worker.SessionLocal", sessions), \
                patch("backend.app.services.translation_updates.SessionLocal", sessions), \
                patch("backend.app.workers.translation_worker.translation_service.translate", side_effect=translate):
            _run_translation_job(1)
            current = get_translation_snapshot([1])["papers"][0]
            self.assertEqual(current["translation_status"], "completed")
            self.assertEqual(current["translation_progress"], 100)
            with sessions() as db:
                self.assertEqual(db.get(Paper, 1).translated_pdf_path, "/tmp/translated.pdf")


class RouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_poll_returns_latest_snapshot_and_deduplicates_ids(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for status, progress in (("queued", 0), ("translating", 57), ("completed", 100), ("failed", 0)):
                current = snapshot((status, progress), removed_ids=[2])
                with patch("backend.app.api.papers.get_translation_snapshot", return_value=current) as read:
                    response = await client.get("/api/papers/updates?ids=1&ids=1&ids=2")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), current)
                self.assertIn("application/json", response.headers["content-type"])
                read.assert_called_once_with([1, 2])

    async def test_missing_ids_is_rejected(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/papers/updates")
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
