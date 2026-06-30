from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.order import Order
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import User, UserRole
from app.routers.auth import get_current_user
from app.schemas.product import ProductCreate, ProductOut, ProductUpdate

router = APIRouter(prefix="/api/orders/{order_id}/products", tags=["products"])


async def _get_order_for_read(order_id: int, user: User, session: AsyncSession) -> Order:
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
    return await _get_order_for_read(order_id, user, session)


def _to_product_out(product: Product, supplier_name: str) -> ProductOut:
    return ProductOut(
        id=product.id,
        order_id=product.order_id,
        supplier_id=product.supplier_id,
        supplier_name=supplier_name,
        name=product.name,
        details=product.details,
        quantity=product.quantity,
        price=product.price,
        currency=product.currency,
        photo_key=product.photo_key,
        created_at=product.created_at,
    )


async def _get_supplier_or_404(supplier_id: int, session: AsyncSession) -> Supplier:
    result = await session.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


@router.get("/", response_model=list[ProductOut])
async def list_products(
    order_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_order_for_read(order_id, user, session)

    result = await session.execute(
        select(Product, Supplier.name)
        .join(Supplier, Product.supplier_id == Supplier.id)
        .where(Product.order_id == order_id)
        .order_by(Product.created_at)
    )
    return [_to_product_out(product, supplier_name) for product, supplier_name in result.all()]


@router.post("/", response_model=ProductOut, status_code=201)
async def create_product(
    order_id: int,
    body: ProductCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_order_for_write(order_id, user, session)
    supplier = await _get_supplier_or_404(body.supplier_id, session)

    product = Product(
        order_id=order_id,
        supplier_id=body.supplier_id,
        name=body.name,
        details=body.details,
        quantity=body.quantity,
        price=body.price,
        currency=body.currency,
        photo_key=body.photo_key,
    )
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return _to_product_out(product, supplier.name)


@router.patch("/{product_id}", response_model=ProductOut)
async def update_product(
    order_id: int,
    product_id: int,
    body: ProductUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_order_for_write(order_id, user, session)

    result = await session.execute(select(Product).where(Product.id == product_id, Product.order_id == order_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    updates = body.model_dump(exclude_unset=True)
    if "supplier_id" in updates:
        await _get_supplier_or_404(updates["supplier_id"], session)
    for field, value in updates.items():
        setattr(product, field, value)

    await session.commit()
    await session.refresh(product)

    supplier = await _get_supplier_or_404(product.supplier_id, session)
    return _to_product_out(product, supplier.name)


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    order_id: int,
    product_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _get_order_for_write(order_id, user, session)

    result = await session.execute(select(Product).where(Product.id == product_id, Product.order_id == order_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    await session.delete(product)
    await session.commit()
