"""SSE 回归测试；使用独立内存数据库，不修改本地论文或调用翻译服务。"""
import json
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base
from backend.app.main import app
from backend.app.models import Paper
from backend.app.services.translation_updates import get_translation_snapshot, stream_translation_updates


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


class StreamTests(unittest.IsolatedAsyncioTestCase):
    async def collect(self, snapshots):
        request = AsyncMock()
        request.is_disconnected.return_value = False
        with patch("backend.app.services.translation_updates.get_translation_snapshot", side_effect=snapshots), \
                patch("backend.app.services.translation_updates.asyncio.sleep", new_callable=AsyncMock):
            return [event async for event in stream_translation_updates(request, [1, 2])]

    async def test_emits_changes_only_and_closes_after_completion(self):
        queued = snapshot(("queued", 0))
        translating = snapshot(("translating", 35))
        completed = snapshot(("completed", 100))
        events = await self.collect([queued, queued, translating, translating, completed])
        updates = [event for event in events if event.startswith("event: papers")]
        self.assertEqual(len(updates), 3)
        self.assertIn('"translation_progress": 100', updates[-1])
        self.assertTrue(events[-1].startswith("event: done"))

    async def test_waits_for_all_selected_tasks(self):
        events = await self.collect([
            snapshot(("completed", 100), ("queued", 0)),
            snapshot(("completed", 100), ("translating", 35)),
            snapshot(("completed", 100), ("completed", 100)),
        ])
        self.assertEqual(sum(event.startswith("event: papers") for event in events), 3)
        self.assertTrue(events[-1].startswith("event: done"))

    async def test_failure_is_delivered_before_close(self):
        failed = snapshot(("failed", 0))
        failed["papers"][0]["translation_error"] = "翻译服务错误"
        events = await self.collect([snapshot(("translating", 35)), failed])
        self.assertIn("翻译服务错误", events[-2])
        self.assertTrue(events[-1].startswith("event: done"))

    async def test_deleted_task_is_delivered_before_close(self):
        events = await self.collect([snapshot(("queued", 0)), snapshot(removed_ids=[1])])
        self.assertIn('"removed_ids": [1]', events[-2])
        self.assertTrue(events[-1].startswith("event: done"))

    async def test_client_disconnect_stops_database_reads(self):
        request = AsyncMock()
        request.is_disconnected.side_effect = [False, True]
        with patch("backend.app.services.translation_updates.get_translation_snapshot",
                   return_value=snapshot(("translating", 35))) as read, \
                patch("backend.app.services.translation_updates.asyncio.sleep", new_callable=AsyncMock):
            events = [event async for event in stream_translation_updates(request, [1])]
        self.assertEqual(read.call_count, 1)
        self.assertEqual(len(events), 2)


from backend.app.auth import create_access_token

class RouteTests(unittest.TestCase):
    def setUp(self):
        self.token = create_access_token()

    def test_sse_route_headers_and_final_snapshot(self):
        final = snapshot(("completed", 100))
        with patch("backend.app.services.translation_updates.get_translation_snapshot", return_value=final) as read:
            response = TestClient(app).get(f"/api/papers/events?ids=1&ids=1&ids=2&token={self.token}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers["content-type"])
        self.assertEqual(response.headers["cache-control"], "no-cache")
        self.assertEqual(response.headers["x-accel-buffering"], "no")
        read.assert_called_once_with([1, 2])
        self.assertIn("event: done", response.text)
        data = next(line[6:] for line in response.text.splitlines() if line.startswith("data: "))
        self.assertEqual(json.loads(data), final)

    def test_missing_ids_is_rejected_without_opening_stream(self):
        response = TestClient(app).get(f"/api/papers/events?token={self.token}")
        self.assertEqual(response.status_code, 422)

    def test_unauthorized_sse_request_rejected(self):
        response = TestClient(app).get("/api/papers/events?ids=1")
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
