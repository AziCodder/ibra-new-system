from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import User, UserRole
from app.routers.auth import get_current_user, require_role
from app.schemas.supplier import SupplierCreate, SupplierOut, SupplierUpdate

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


@router.get("/", response_model=list[SupplierOut])
async def list_suppliers(
    _user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Supplier).order_by(Supplier.name))
    return result.scalars().all()


@router.post("/", response_model=SupplierOut, status_code=201)
async def create_supplier(
    body: SupplierCreate,
    _admin: User = require_role(UserRole.admin),
    session: AsyncSession = Depends(get_session),
):
    existing = await session.execute(select(Supplier).where(Supplier.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Supplier name already exists")

    supplier = Supplier(name=body.name, contacts=body.contacts, details=body.details)
    session.add(supplier)
    await session.commit()
    await session.refresh(supplier)
    return supplier


@router.patch("/{supplier_id}", response_model=SupplierOut)
async def update_supplier(
    supplier_id: int,
    body: SupplierUpdate,
    _admin: User = require_role(UserRole.admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    if body.name is not None:
        supplier.name = body.name
    if body.contacts is not None:
        supplier.contacts = body.contacts
    if body.details is not None:
        supplier.details = body.details

    await session.commit()
    await session.refresh(supplier)
    return supplier


@router.delete("/{supplier_id}", status_code=204)
async def delete_supplier(
    supplier_id: int,
    _admin: User = require_role(UserRole.admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    product_count = (await session.execute(
        select(func.count()).select_from(Product).where(Product.supplier_id == supplier_id)
    )).scalar_one()
    if product_count > 0:
        product_names = (await session.execute(
            select(Product.name).where(Product.supplier_id == supplier_id).order_by(Product.id).limit(20)
        )).scalars().all()
        raise HTTPException(
            status_code=409,
            detail={
                "message": f"Cannot delete supplier: {product_count} product(s) reference this supplier",
                "product_count": product_count,
                "product_names": product_names,
            },
        )

    await session.delete(supplier)
    await session.commit()
