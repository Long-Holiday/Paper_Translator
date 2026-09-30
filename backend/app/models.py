from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from backend.app.database import Base


class Paper(Base):
    __tablename__ = "papers"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    title = Column(String, nullable=False, index=True)
    original_filename = Column(String, nullable=False)
    original_pdf_path = Column(String, nullable=False)
    translated_pdf_path = Column(String, nullable=True)
    page_count = Column(Integer, nullable=True)

    # 翻译状态: pending, queued, translating, completed, failed
    translation_status = Column(String, nullable=False, default="pending", index=True)
    translation_progress = Column(Integer, nullable=False, default=0)
    translation_error = Column(Text, nullable=True)

    # 最后阅读页码
    last_read_page = Column(Integer, nullable=False, default=1)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
