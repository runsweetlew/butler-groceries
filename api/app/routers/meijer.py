"""Meijer integration — product matching, shopping list sync."""

import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import MeijerToken, User, Recipe, RecipeIngredient, Ingredient
from app.services.meijer import meijer_client
from app.config import get_settings

logger = logging.getLogger("butlergroceries.meijer")
router = APIRouter(prefix="/api/meijer", tags=["meijer"])
settings = get_settings()


# ── Connection Status ──

@router.get("/status")
async def meijer_status(user_id: int = Query(1), db: AsyncSession = Depends(get_db)):
    """Check if Meijer is configured and connected."""
    result = await db.execute(select(MeijerToken).where(MeijerToken.user_id == user_id))
    token = result.scalar_one_or_none()

    if token:
        expired = datetime.utcnow() > token.expires_at if token.expires_at else False
        return {
            "connected": True,
            "expired": expired,
            "store_id": token.store_id or settings.meijer_store_id,
        }

    # Fall back to env config
    return {
        "connected": meijer_client.is_configured,
        "expired": False,
        "store_id": settings.meijer_store_id,
    }


# ── Save Token (from mitmproxy capture) ──

@router.post("/token")
async def save_meijer_token(
    user_id: int = Query(1),
    auth_token: str = Query(...),
    refresh_token: str = Query(""),
    db: AsyncSession = Depends(get_db),
):
    """Save a Meijer bearer token captured via mitmproxy."""
    result = await db.execute(select(MeijerToken).where(MeijerToken.user_id == user_id))
    existing = result.scalar_one_or_none()

    expires_at = datetime.utcnow() + timedelta(hours=24)

    if existing:
        existing.access_token = auth_token
        existing.refresh_token = refresh_token
        existing.expires_at = expires_at
    else:
        db.add(MeijerToken(
            user_id=user_id,
            access_token=auth_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        ))

    await db.commit()
    logger.info(f"Meijer token saved for user {user_id}")
    return {"status": "ok", "message": "Meijer token saved"}


# ── Product Matching ──

@router.get("/match/{recipe_id}")
async def match_recipe_ingredients(
    recipe_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Match all recipe ingredients to Meijer products."""
    result = await db.execute(
        select(RecipeIngredient)
        .where(RecipeIngredient.recipe_id == recipe_id)
        .order_by(RecipeIngredient.sort_order)
    )
    recipe_ings = result.scalars().all()

    if not recipe_ings:
        raise HTTPException(404, "Recipe not found or has no ingredients")

    # Get ingredient names
    ing_ids = [ri.ingredient_id for ri in recipe_ings if ri.ingredient_id]
    if ing_ids:
        result = await db.execute(select(Ingredient).where(Ingredient.id.in_(ing_ids)))
        ing_map = {i.id: i.name for i in result.scalars().all()}
    else:
        ing_map = {}

    # Build search terms
    search_items = []
    for ri in recipe_ings:
        name = ing_map.get(ri.ingredient_id, "") or ri.raw_text or ""
        if not ing_map.get(ri.ingredient_id) and ri.raw_text:
            name = ri.raw_text
        search_items.append({
            "name": name,
            "quantity": ri.quantity,
            "unit": ri.unit or "",
        })

    store_id = settings.meijer_store_id
    matches = await meijer_client.match_ingredients(
        [s["name"] for s in search_items], store_id
    )

    # Merge back with quantities
    for i, m in enumerate(matches):
        if i < len(search_items):
            m["needed_quantity"] = search_items[i]["quantity"]
            m["needed_unit"] = search_items[i]["unit"]

    total_price = sum(m.get("price", 0) or 0 for m in matches if m.get("matched"))
    matched_count = sum(1 for m in matches if m.get("matched"))

    return {
        "recipe_id": recipe_id,
        "store_id": store_id,
        "matched": matched_count,
        "total": len(matches),
        "estimated_cost": round(total_price, 2),
        "items": matches,
    }


# ── Add to Shopping List ──

@router.post("/list/add/{recipe_id}")
async def add_recipe_to_list(
    recipe_id: int,
    user_id: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """Match ingredients and add them to Meijer shopping list."""
    match_data = await match_recipe_ingredients(recipe_id, db)
    items = match_data["items"]

    # Build list items from matched products
    list_items = []
    skipped = []
    for item in items:
        if item.get("matched"):
            list_items.append({
                "name": item.get("description") or item["ingredient"],
                "quantity": 1,
            })
        else:
            skipped.append(item["ingredient"])

    if not list_items:
        raise HTTPException(400, "No products matched — nothing to add")

    result = await meijer_client.add_to_shopping_list(list_items)

    return {
        "success": result.get("success", False),
        "added": result.get("added", 0),
        "skipped": skipped,
        "estimated_cost": match_data["estimated_cost"],
        "message": f"Added {result.get('added', 0)} items to Meijer list",
        "items": items,
    }


# ── Product Search ──

@router.get("/search")
async def search_products(
    q: str = Query(..., description="Search term"),
    limit: int = Query(5, ge=1, le=50),
):
    """Search Meijer products."""
    products = await meijer_client.search_products(
        q, settings.meijer_store_id, limit
    )
    results = []
    for p in products:
        price_info = p.get("price", {})
        results.append({
            "upc": p.get("upc", ""),
            "description": p.get("description", p.get("name", "")),
            "brand": p.get("brand", ""),
            "size": p.get("size", p.get("packageSize", "")),
            "price": price_info.get("salePrice") or price_info.get("basePrice"),
            "on_sale": bool(price_info.get("salePrice")),
        })
    return results
