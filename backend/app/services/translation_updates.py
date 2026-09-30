import asyncio
import json
import time

from fastapi import Request
from starlette.concurrency import run_in_threadpool

from backend.app.database import SessionLocal
from backend.app.models import Paper
from backend.app.schemas import PaperResponse


def get_translation_snapshot(paper_ids: list[int]) -> dict:
    # 每次检查使用短会话，避免长连接占用数据库连接或读取旧状态。
    with SessionLocal() as db:
        papers = db.query(Paper).filter(Paper.id.in_(paper_ids)).order_by(Paper.id).all()
        existing_ids = {paper.id for paper in papers}
        return {
            "papers": [PaperResponse.model_validate(paper).model_dump(mode="json") for paper in papers],
            "removed_ids": [paper_id for paper_id in paper_ids if paper_id not in existing_ids],
        }


async def stream_translation_updates(request: Request, paper_ids: list[int]):
    """复用一个 SSE 连接，只在状态变化时发送数据，任务结束后关闭。"""
    previous = None
    last_sent = time.monotonic()
    yield "retry: 5000\n\n"

    while not await request.is_disconnected():
        snapshot = await run_in_threadpool(get_translation_snapshot, paper_ids)
        serialized = json.dumps(snapshot, ensure_ascii=False)
        if serialized != previous:
            yield f"event: papers\ndata: {serialized}\n\n"
            previous = serialized
            last_sent = time.monotonic()

        if not any(paper["translation_status"] in ("queued", "translating") for paper in snapshot["papers"]):
            yield "event: done\ndata: {}\n\n"
            return

        if time.monotonic() - last_sent >= 15:
            yield ": keep-alive\n\n"
            last_sent = time.monotonic()

        await asyncio.sleep(1)
