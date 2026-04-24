"""
Canvas database model.
Stores drawing data as JSON (strokes + metadata).
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime

from backend.core.database import Base


class Canvas(Base):
    __tablename__ = "canvases"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), nullable=False, default="Untitled Canvas")
    # Drawing data stored as JSON string: list of stroke objects
    drawing_data = Column(Text, nullable=True, default="[]")
    # Thumbnail as base64 PNG (optional, for dashboard previews)
    thumbnail = Column(Text, nullable=True)
    is_public = Column(Boolean, default=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship back to user
    owner = relationship("User", back_populates="canvases")

    def __repr__(self):
        return f"<Canvas id={self.id} title={self.title} owner={self.owner_id}>"
