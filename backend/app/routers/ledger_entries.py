from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.ledger_entry import LedgerEntry
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.ledger_entry import LedgerEntryCreate, LedgerEntryOut
from app.services.order_access import get_order_for_read as _get_order_for_read
from app.services.order_access import get_order_for_write as _get_order_for_write

router = APIRouter(prefix="/api/orders/{order_id}/ledger-entries", tags=["ledger-entries"])


def _to_ledger_entry_out(entry: LedgerEntry, author_name: str) -> LedgerEntryOut:
    return LedgerEntryOut(
        id=entry.id,
        order_id=entry.order_id,
        author_id=entry.author_id,
        author_name=author_name,
        type=entry.type,
        amount=entry.amount,
        currency=entry.currency,
        exchange_rate=entry.exchange_rate,
        details=entry.details,
        created_at=entry.created_at,
    )


@router.get("/", response_model=list[LedgerEntryOut])
async def list_ledger_entries(
    order_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_order_for_read(order_id, user, session)

    result = await session.execute(
        select(LedgerEntry, User.full_name)
        .join(User, LedgerEntry.author_id == User.id)
        .where(LedgerEntry.order_id == order_id)
        .order_by(LedgerEntry.created_at)
    )
    return [_to_ledger_entry_out(entry, author_name) for entry, author_name in result.all()]


@router.post("/", response_model=LedgerEntryOut, status_code=201)
async def create_ledger_entry(
    order_id: int,
    body: LedgerEntryCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_order_for_write(order_id, user, session)

    entry = LedgerEntry(
        order_id=order_id,
        author_id=user.id,
        type=body.type,
        amount=body.amount,
        currency=body.currency,
        exchange_rate=body.exchange_rate,
        details=body.details,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return _to_ledger_entry_out(entry, user.full_name)


@router.delete("/{entry_id}", status_code=204)
async def delete_ledger_entry(
    order_id: int,
    entry_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_order_for_write(order_id, user, session)

    result = await session.execute(
        select(LedgerEntry).where(LedgerEntry.id == entry_id, LedgerEntry.order_id == order_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Ledger entry not found")

    await session.delete(entry)
    await session.commit()
