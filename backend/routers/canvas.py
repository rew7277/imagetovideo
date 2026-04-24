"""
Canvas Router — CRUD endpoints for saving and loading drawings.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from backend.core.database import get_db
from backend.core.security import get_current_user
from backend.models.user import User
from backend.models.canvas import Canvas
from backend.schemas.canvas import CanvasCreate, CanvasUpdate, CanvasOut, CanvasSummary

router = APIRouter()


@router.post("/", response_model=CanvasOut, status_code=status.HTTP_201_CREATED)
def create_canvas(
    canvas_data: CanvasCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new canvas for the authenticated user."""
    canvas = Canvas(
        title=canvas_data.title,
        drawing_data=canvas_data.drawing_data,
        thumbnail=canvas_data.thumbnail,
        is_public=canvas_data.is_public,
        owner_id=current_user.id,
    )
    db.add(canvas)
    db.commit()
    db.refresh(canvas)
    return canvas


@router.get("/", response_model=List[CanvasSummary])
def list_canvases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all canvases belonging to the current user (summary, no drawing data)."""
    return (
        db.query(Canvas)
        .filter(Canvas.owner_id == current_user.id)
        .order_by(Canvas.updated_at.desc())
        .all()
    )


@router.get("/{canvas_id}", response_model=CanvasOut)
def get_canvas(
    canvas_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Load a specific canvas by ID (includes full drawing data)."""
    canvas = db.query(Canvas).filter(Canvas.id == canvas_id).first()
    if not canvas:
        raise HTTPException(status_code=404, detail="Canvas not found")
    # Allow owner or public canvases
    if canvas.owner_id != current_user.id and not canvas.is_public:
        raise HTTPException(status_code=403, detail="Access denied")
    return canvas


@router.put("/{canvas_id}", response_model=CanvasOut)
def update_canvas(
    canvas_id: int,
    canvas_data: CanvasUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update drawing data, title, or settings for a canvas."""
    canvas = db.query(Canvas).filter(Canvas.id == canvas_id).first()
    if not canvas:
        raise HTTPException(status_code=404, detail="Canvas not found")
    if canvas.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your canvas")

    # Update only provided fields
    if canvas_data.title is not None:
        canvas.title = canvas_data.title
    if canvas_data.drawing_data is not None:
        canvas.drawing_data = canvas_data.drawing_data
    if canvas_data.thumbnail is not None:
        canvas.thumbnail = canvas_data.thumbnail
    if canvas_data.is_public is not None:
        canvas.is_public = canvas_data.is_public

    db.commit()
    db.refresh(canvas)
    return canvas


@router.delete("/{canvas_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_canvas(
    canvas_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a canvas permanently."""
    canvas = db.query(Canvas).filter(Canvas.id == canvas_id).first()
    if not canvas:
        raise HTTPException(status_code=404, detail="Canvas not found")
    if canvas.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your canvas")

    db.delete(canvas)
    db.commit()
