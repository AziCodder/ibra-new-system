import mimetypes

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.logistics import Logistics
from app.models.order import Order
from app.models.payment import Payment
from app.models.payment_request import PaymentRequest
from app.models.product import Product
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.services.storage import CONTEXT_MAX_SIZES, MAX_FILE_SIZE, StorageError, storage

router = APIRouter(prefix="/api/files", tags=["files"])


async def _find_file_order_id(file_key: str, session: AsyncSession) -> int | None:
    """Best-effort lookup of the order a file is attached to, across every entity that can reference a file key."""
    result = await session.execute(select(Order.id).where(Order.file_keys.any(file_key)))
    order_id = result.scalar_one_or_none()
    if order_id is not None:
        return order_id

    result = await session.execute(select(Product.order_id).where(Product.photo_key == file_key))
    order_id = result.scalar_one_or_none()
    if order_id is not None:
        return order_id

    result = await session.execute(select(Logistics.order_id).where(Logistics.invoice_file_key == file_key))
    order_id = result.scalar_one_or_none()
    if order_id is not None:
        return order_id

    result = await session.execute(select(PaymentRequest.order_id).where(PaymentRequest.file_keys.any(file_key)))
    order_id = result.scalar_one_or_none()
    if order_id is not None:
        return order_id

    result = await session.execute(
        select(PaymentRequest.order_id)
        .join(Payment, Payment.payment_request_id == PaymentRequest.id)
        .where(Payment.file_key == file_key)
    )
    return result.scalar_one_or_none()


@router.post("/upload")
async def upload_file(
    file: UploadFile,
    context: str | None = None,
    _user: User = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    data = await file.read()
    max_size = CONTEXT_MAX_SIZES.get(context, MAX_FILE_SIZE) if context else MAX_FILE_SIZE
    try:
        key = await storage.save(file.filename, data, max_size=max_size)
    except StorageError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    return {"key": key, "filename": file.filename, "size": len(data)}


@router.get("/{file_key}")
async def download_file(
    file_key: str,
    _user: User = Depends(get_current_user),
):
    try:
        data = await storage.get(file_key)
    except StorageError:
        raise HTTPException(status_code=404, detail="File not found") from None

    media_type, _ = mimetypes.guess_type(file_key)
    media_type = media_type or "application/octet-stream"
    # Images render inline (e.g. product photo previews); other files force a download.
    disposition = "inline" if media_type.startswith("image/") else "attachment"

    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'{disposition}; filename="{file_key}"'},
    )


@router.delete("/{file_key}", status_code=204)
async def delete_file(
    file_key: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if user.role == UserRole.observer:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    order_id = await _find_file_order_id(file_key, session)
    if order_id is not None:
        if user.role == UserRole.manager:
            order = (await session.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
            if order is None or order.manager_id != user.id:
                raise HTTPException(status_code=404, detail="File not found")
    elif user.role != UserRole.admin:
        # File isn't attached to anything we can check ownership against (e.g. a freshly
        # uploaded, not-yet-attached file) — only admins may delete blind.
        raise HTTPException(status_code=404, detail="File not found")

    try:
        await storage.delete(file_key)
    except StorageError:
        raise HTTPException(status_code=404, detail="File not found") from None
