"""
Endpoints publics pour la vitrine (storefront).
Ces endpoints n'ont pas besoin d'authentification.
"""

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Product, Store, get_db
from services.promotions_service import apply_promotions_to_items, preview_product_promo_price
from services.tax_service import calculate_taxes_for_items

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/storefront", tags=["Storefront"])


class StorefrontPreviewItem(BaseModel):
    product_id: int | None = None
    name: str
    qty: int = Field(default=1, ge=1)
    unit_price: Decimal = Field(..., ge=0)
    category: str | None = None
    tax_category: str | None = None
    brand: str | None = None
    is_tax_exempt: bool = False


class StorefrontPromotionPreviewRequest(BaseModel):
    items: list[StorefrontPreviewItem]
    coupon_codes: list[str] | None = None
    country_code: str | None = Field(None, min_length=2, max_length=2)
    channel: str | None = Field(default="storefront")
    customer_email: str | None = None
    customer_phone: str | None = None
    customer_name: str | None = None
    event_context: dict | None = None


async def _resolve_store(db: AsyncSession, store_id: str):
    """
    FIX: Accept slug or numeric ID.
    Frontend generates /store/{slug} links — storefront must handle both.
    """
    try:
        result = await db.execute(
            select(Store).where(Store.id == int(store_id), Store.is_active)
        )
    except (ValueError, TypeError):
        result = await db.execute(
            select(Store).where(Store.slug == store_id, Store.is_active)
        )
    return result.scalar_one_or_none()


# ─── Get public store info by ID or slug ───────────────────────────────────────
@router.get("/{store_id}")
async def get_storefront(store_id: str, db: AsyncSession = Depends(get_db)):
    """Récupère une boutique par ID numérique ou par slug."""
    store = await _resolve_store(db, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found or inactive")

    return {
        "id": store.id,
        "name": store.name or "Ma Boutique",
        "slug": store.slug,
        "logo_url": getattr(store, "logo_url", None),
        "banner_url": getattr(store, "banner_url", None),
        "description": getattr(store, "description", "Bienvenue dans notre boutique !"),
        "whatsapp_phone": store.whatsapp_phone or "",
        "support_email": getattr(store, "support_email", None),
        "address": getattr(store, "address", None),
        "phone_display": getattr(store, "phone_display", store.whatsapp_phone),
        "website_url": getattr(store, "website_url", None),
        "category": getattr(store, "category", None),
        "opening_hours": getattr(store, "opening_hours", {}),
        "services": getattr(store, "services", []),
        "latitude": getattr(store, "latitude", None),
        "longitude": getattr(store, "longitude", None),
        "social_links": getattr(store, "social_links", {}),
        "language": store.language or "fr",
        "is_open": getattr(store, "is_open", True),
        "is_active": store.is_active,
        "created_at": store.created_at.isoformat() if store.created_at else None,
    }


# ─── Get public products ──────────────────────────────────────────────────────
@router.get("/{store_id}/products")
async def get_storefront_products(
    store_id: str,
    category: str | None = Query(None, description="Filter by category"),
    limit: int = Query(12, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """
    Récupère les produits publics d'une boutique.
    Endpoint public — aucune authentification requise.
    """
    store = await _resolve_store(db, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found or inactive")

    # FIX: always use resolved numeric store.id for product query
    stmt = select(Product).where(
        Product.store_id == store.id,
        Product.is_active,
        Product.stock_qty > 0,
    )

    if category:
        stmt = stmt.where(Product.category == category)

    # Compter le total
    count_stmt = select(func.count()).select_from(
        stmt.subquery()
    )
    total = (await db.execute(count_stmt)).scalar() or 0

    # Récupérer les produits avec pagination
    stmt = stmt.order_by(Product.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    products = result.scalars().all()

    serialized_products = []
    for p in products:
        promo_price = await preview_product_promo_price(db, store=store, product=p, channel="storefront")
        serialized_products.append(
            {
                "id": p.id,
                "name": p.name,
                "description": p.description or "",
                "price": float(p.price) if p.price else 0.0,
                "promo_price": promo_price,
                "images": p.images if getattr(p, "images", None) else [],
                "image_url": p.image_url,
                "category": p.category,
                "stock_qty": p.stock_qty or 0,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
        )

    return {
        "products": serialized_products,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < total,
    }


@router.post("/{store_id}/promotions/preview")
async def preview_storefront_promotions(
    store_id: str,
    body: StorefrontPromotionPreviewRequest,
    db: AsyncSession = Depends(get_db),
):
    store = await _resolve_store(db, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found or inactive")

    items = [item.model_dump() for item in body.items]
    promo_result = await apply_promotions_to_items(
        db,
        store=store,
        items=items,
        coupon_codes=body.coupon_codes,
        country_code=body.country_code,
        channel=body.channel,
        customer_email=body.customer_email,
        customer_phone=body.customer_phone,
        customer_name=body.customer_name,
        event_context=body.event_context,
    )
    tax_result = await calculate_taxes_for_items(
        db=db,
        store=store,
        items=promo_result.items,
        country_code=body.country_code,
        customer_email=body.customer_email,
        customer_phone=body.customer_phone,
    )
    return {
        "items": promo_result.items,
        "discount_amount": float(promo_result.discount_amount),
        "applied_promotions": promo_result.applied_promotions,
        "applied_coupon_codes": promo_result.applied_coupon_codes,
        "pricing": tax_result.as_dict(),
    }
