from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.note import Note
from app.models.order import Order
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.schemas.note import NoteCreate, NoteOut

router = APIRouter(prefix="/api/orders/{order_id}/notes", tags=["notes"])


async def _get_visible_order(order_id: int, user: User, session: AsyncSession) -> Order:
    result = await session.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if user.role == UserRole.manager and order.manager_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


async def _get_order_for_write(order_id: int, user: User, session: AsyncSession) -> Order:
    if user.role == UserRole.observer:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return await _get_visible_order(order_id, user, session)


@router.get("/", response_model=list[NoteOut])
async def list_notes(
    order_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_visible_order(order_id, user, session)

    result = await session.execute(
        select(Note, User.full_name)
        .join(User, Note.author_id == User.id)
        .where(Note.order_id == order_id)
        .order_by(Note.created_at)
    )
    return [
        NoteOut(
            id=note.id,
            order_id=note.order_id,
            author_id=note.author_id,
            author_name=author_name,
            text=note.text,
            created_at=note.created_at,
        )
        for note, author_name in result.all()
    ]


@router.post("/", response_model=NoteOut, status_code=201)
async def create_note(
    order_id: int,
    body: NoteCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_order_for_write(order_id, user, session)

    note = Note(order_id=order_id, author_id=user.id, text=body.text)
    session.add(note)
    await session.commit()
    await session.refresh(note)
    return NoteOut(
        id=note.id,
        order_id=note.order_id,
        author_id=note.author_id,
        author_name=user.full_name,
        text=note.text,
        created_at=note.created_at,
    )
