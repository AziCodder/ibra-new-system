from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.user import User
from app.routers.auth import get_current_user
from app.schemas.product import ProductCreate, ProductOut, ProductShipmentOut, ProductUpdate
from app.services.logistics_validation import get_product_already_shipped
from app.services.order_access import get_order_for_read as _get_order_for_read
from app.services.order_access import get_order_for_write as _get_order_for_write
from app.services.payment_request_validation import get_product_already_requested
from app.services.product_dependencies import count_product_dependencies
from app.services.product_logistics_summary import (
    ProductLogisticsTotals,
    get_products_logistics_totals,
)
from app.services.product_payment_summary import get_products_payment_totals

router = APIRouter(prefix="/api/orders/{order_id}/products", tags=["products"])


def _to_product_out(
    product: Product,
    supplier_name: str,
    payment_totals: tuple[Decimal, Decimal] | None = None,
    logistics_totals: ProductLogisticsTotals | None = None,
) -> ProductOut:
    requested_amount, paid_amount = payment_totals if payment_totals else (None, None)
    logistics = logistics_totals or ProductLogisticsTotals()
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
        exchange_rate=product.exchange_rate,
        photo_key=product.photo_key,
        created_at=product.created_at,
        requested_amount=requested_amount,
        paid_amount=paid_amount,
        shipped_quantity=logistics.shipped_quantity,
        accepted_quantity=logistics.accepted_quantity,
        shipments=[
            ProductShipmentOut(
                id=shipment.id,
                tracking=shipment.tracking,
                quantity=shipment.quantity,
                status=shipment.status,
            )
            for shipment in logistics.shipments
        ],
    )


def _resolve_exchange_rate(currency: str, order_currency: str, rate: Decimal | None) -> Decimal:
    """Normalise a product's rate to the order's currency, or raise 422.

    The rate reads "units of the product's currency per 1 unit of the order's"
    ("1 CNY = 11.5 RUB" -> 11.5), so converting a product total into the order's
    currency divides by it.

    A product priced in the order's own currency is always rate 1 — accepting
    anything else there would silently distort the profit calculation. A product
    priced in another currency has no sensible default, so the rate is required.
    """
    if currency == order_currency:
        if rate is not None and rate != Decimal("1"):
            raise HTTPException(
                status_code=422,
                detail=f"Exchange rate must be 1 when the product is priced in the order's currency ({order_currency})",
            )
        return Decimal("1")

    if rate is None:
        raise HTTPException(
            status_code=422,
            detail=f"Exchange rate is required: product currency {currency} differs from the order's {order_currency}",
        )
    return rate


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
    rows = result.all()
    product_ids = [product.id for product, _ in rows]
    payment_totals = await get_products_payment_totals(session, product_ids)
    logistics_totals = await get_products_logistics_totals(session, product_ids)
    return [
        _to_product_out(
            product,
            supplier_name,
            payment_totals.get(product.id),
            logistics_totals.get(product.id),
        )
        for product, supplier_name in rows
    ]


@router.post("/", response_model=ProductOut, status_code=201)
async def create_product(
    order_id: int,
    body: ProductCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    order = await _get_order_for_write(order_id, user, session)
    supplier = await _get_supplier_or_404(body.supplier_id, session)

    currency = body.currency or order.currency
    exchange_rate = _resolve_exchange_rate(currency, order.currency, body.exchange_rate)

    product = Product(
        order_id=order_id,
        supplier_id=body.supplier_id,
        name=body.name,
        details=body.details,
        quantity=body.quantity,
        price=body.price,
        currency=currency,
        exchange_rate=exchange_rate,
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
    order = await _get_order_for_write(order_id, user, session)

    result = await session.execute(select(Product).where(Product.id == product_id, Product.order_id == order_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    updates = body.model_dump(exclude_unset=True)
    if "supplier_id" in updates:
        await _get_supplier_or_404(updates["supplier_id"], session)

    if "quantity" in updates:
        already_shipped = await get_product_already_shipped(session, product_id)
        if updates["quantity"] < already_shipped:
            raise HTTPException(
                status_code=422,
                detail=f"Cannot lower quantity below already-shipped amount ({already_shipped})",
            )

    if "quantity" in updates or "price" in updates:
        already_requested = await get_product_already_requested(session, product_id)
        new_quantity = updates.get("quantity", product.quantity)
        new_price = updates.get("price", product.price)
        if new_quantity * new_price < already_requested:
            raise HTTPException(
                status_code=422,
                detail=f"Cannot lower total value below already-requested amount ({already_requested})",
            )

    if "currency" in updates and updates["currency"] != product.currency:
        # Item amounts on existing requests are denominated in the old currency —
        # re-labelling the product would silently reinterpret every one of them.
        already_requested = await get_product_already_requested(session, product_id)
        if already_requested > 0:
            raise HTTPException(
                status_code=422,
                detail="Cannot change currency: product has existing payment requests",
            )

    if "currency" in updates or "exchange_rate" in updates:
        new_currency = updates.get("currency", product.currency)
        if "exchange_rate" in updates:
            new_rate = updates["exchange_rate"]
        elif new_currency != product.currency:
            # The stored rate described the *old* currency and says nothing about
            # the new one — so the caller has to supply one (or be switching back
            # to the order's currency, where _resolve_exchange_rate settles on 1).
            new_rate = None
        else:
            new_rate = product.exchange_rate
        updates["exchange_rate"] = _resolve_exchange_rate(new_currency, order.currency, new_rate)

    for field, value in updates.items():
        setattr(product, field, value)

    await session.commit()
    await session.refresh(product)

    supplier = await _get_supplier_or_404(product.supplier_id, session)
    payment_totals = await get_products_payment_totals(session, [product.id])
    logistics_totals = await get_products_logistics_totals(session, [product.id])
    return _to_product_out(
        product, supplier.name, payment_totals.get(product.id), logistics_totals.get(product.id)
    )


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

    dependency_count = await count_product_dependencies(session, product_id)
    if dependency_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Product has {dependency_count} related record(s) and cannot be deleted",
        )

    await session.delete(product)
    await session.commit()
