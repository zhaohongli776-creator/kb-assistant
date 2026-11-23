"""请求/响应模型（M1 的 D3：校验与状态码都从这里长出来）。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DocumentIn(BaseModel):
    filename: str = Field(min_length=1, max_length=255, pattern=r"\.(pdf|docx|txt|md)$")
    size_bytes: int = Field(ge=0, le=50 * 1024 * 1024, description="文件大小，上限 50MB")


class DocumentOut(BaseModel):
    id: int
    filename: str
    size_bytes: int
    status: str
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class HealthOut(BaseModel):
    status: str
    db: str
