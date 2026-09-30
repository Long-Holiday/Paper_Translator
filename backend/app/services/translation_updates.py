from backend.app.database import SessionLocal
from backend.app.models import Paper
from backend.app.schemas import PaperResponse


def get_translation_snapshot(paper_ids: list[int]) -> dict:
    # 每次检查使用短会话，确保轮询读取最新状态且及时释放连接。
    with SessionLocal() as db:
        papers = db.query(Paper).filter(Paper.id.in_(paper_ids)).order_by(Paper.id).all()
        existing_ids = {paper.id for paper in papers}
        return {
            "papers": [PaperResponse.model_validate(paper).model_dump(mode="json") for paper in papers],
            "removed_ids": [paper_id for paper_id in paper_ids if paper_id not in existing_ids],
        }
