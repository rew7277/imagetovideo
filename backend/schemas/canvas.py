"""
Pydantic schemas for Canvas endpoints.
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class CanvasCreate(BaseModel):
    title: str = "Untitled Canvas"
    drawing_data: str = "[]"  # JSON string of strokes
    thumbnail: Optional[str] = None
    is_public: bool = False


class CanvasUpdate(BaseModel):
    title: Optional[str] = None
    drawing_data: Optional[str] = None
    thumbnail: Optional[str] = None
    is_public: Optional[bool] = None


class CanvasOut(BaseModel):
    id: int
    title: str
    drawing_data: str
    thumbnail: Optional[str]
    is_public: bool
    owner_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CanvasSummary(BaseModel):
    """Used in dashboard listings — excludes heavy drawing_data."""
    id: int
    title: str
    thumbnail: Optional[str]
    is_public: bool
    owner_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
