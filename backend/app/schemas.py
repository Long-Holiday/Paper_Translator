from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class PaperBase(BaseModel):
    title: str
    original_filename: str
    page_count: Optional[int] = None
    translation_status: str
    translation_progress: int
    translation_error: Optional[str] = None
    last_read_page: int


class PaperResponse(PaperBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ReadingPositionUpdate(BaseModel):
    page: int = Field(..., ge=1, description="阅读页码，从1开始")


class TranslateResponse(BaseModel):
    status: str
    message: Optional[str] = None


class ConfigModel(BaseModel):
    translation: Dict[str, Any]
    server: Dict[str, Any]
