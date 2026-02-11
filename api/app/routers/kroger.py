"""Kroger integration — OAuth callback, product matching, cart add."""

import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import KrogerToken, User, Recipe, RecipeIngredient, Ingredient
from app.services.kroger import kroger_client
from app.config import get_settings

logger = logging.getLogger("dukecook.kroger")
router = APIRouter(prefix="/api/kroger", tags=["kroger"])
settings = get_settings()

REDIRECT_URI = "https://cook.trevorduke.com/api/kroger/callback"


# ── OAuth Flow ──

@router.get("/connect")
async def kroger_connect(user_id: int = Query(...)):
    """Redirect user to Kroger OAuth login. One-time setup."""
    url = kroger_client.get_authorize_url(
        redirect_uri=REDIRECT_URI,
        state=str(user_id),
    )
    return RedirectResponse(url)


@router.get("/callback")
async def kroger_callback(
    code: str = Query(None),
    state: str = Query(""),
    error: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Handle Kroger OAuth callback — store tokens."""
    if error:
        logger.error(f"Kroger OAuth error: {error}")
        return RedirectResponse(f"/?kroger_error={error}")

    if not code:
        raise HTTPException(400, "Missing authorization code")

    user_id = int(state) if state.isdigit() else 1

    # Exchange code for tokens
    token_data = await kroger_client.exchange_code(code, REDIRECT_URI)

    expires_at = datetime.utcnow() + timedelta(seconds=token_data.get("expires_in", 1800))

    # Upsert token
    result = await db.execute(select(KrogerToken).where(KrogerToken.user_id == user_id))
    existing = result.scalar_one_or_none()

    if existing:
        existing.access_token = token_data["access_token"]
        existing.refresh_token = token_data["refresh_token"]
        existing.expires_at = expires_at
    else:
        db.add(KrogerToken(
            user_id=user_id,
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            expires_at=expires_at,
        ))

    await db.commit()
    logger.info(f"Kroger connected for user {user_id}")

    # Redirect back to the app with success
    return RedirectResponse("/?kroger_connected=1")


@router.get("/status")
async def kroger_status(user_id: int = Query(1), db: AsyncSession = Depends(get_db)):
    """Check if user has a valid Kroger connection."""
    result = await db.execute(select(KrogerToken).where(KrogerToken.user_id == user_id))
    token = result.scalar_one_or_none()

    if not token:
        return {"connected": False}

    expired = datetime.utcnow() > token.expires_at
    resp = {
        "connected": True,
        "expired": expired,
        "store_id": token.store_id,
    }

    # Try to get profile email if token is valid
    if not expired:
        import httpx as httpx_mod
        try:
            async with httpx_mod.AsyncClient() as client:
                profile_resp = await client.get(
                    "https://api.kroger.com/v1/identity/profile",
                    headers={"Authorization": f"Bearer {token.access_token}", "Accept": "application/json"},
                )
                if profile_resp.status_code == 200:
                    profile = profile_resp.json().get("data", {})
                    resp["email"] = profile.get("email", "")
                    resp["first_name"] = profile.get("firstName", "")
        except Exception:
            pass

    return resp


# ── Ensure valid user token ──

async def _get_user_token(user_id: int, db: AsyncSession) -> str:
    """Get a valid user access token, refreshing if needed."""
    result = await db.execute(select(KrogerToken).where(KrogerToken.user_id == user_id))
    token = result.scalar_one_or_none()
    if not token:
        raise HTTPException(401, "Kroger not connected. Please connect first.")

    # Refresh if expired
    if datetime.utcnow() > token.expires_at - timedelta(minutes=2):
        try:
            new_data = await kroger_client.refresh_user_token(token.refresh_token)
            token.access_token = new_data["access_token"]
            token.refresh_token = new_data.get("refresh_token", token.refresh_token)
            token.expires_at = datetime.utcnow() + timedelta(seconds=new_data.get("expires_in", 1800))
            await db.commit()
            logger.info(f"Refreshed Kroger token for user {user_id}")
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            raise HTTPException(401, "Kroger session expired. Please reconnect.")

    return token.access_token


# ── Product Matching ──

@router.get("/match/{recipe_id}")
async def match_recipe_ingredients(
    recipe_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Match all recipe ingredients to Kroger products. No user auth needed."""
    # Get recipe ingredients
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
    names = []
    if ing_ids:
        result = await db.execute(select(Ingredient).where(Ingredient.id.in_(ing_ids)))
        ing_map = {i.id: i.name for i in result.scalars().all()}
    else:
        ing_map = {}

    # Build search terms — prefer ingredient name over raw_text
    search_items = []
    for ri in recipe_ings:
        name = ing_map.get(ri.ingredient_id, "") or ri.raw_text or ""
        # Clean up: strip quantities/measurements from raw_text if no ingredient name
        if not ing_map.get(ri.ingredient_id) and ri.raw_text:
            name = ri.raw_text
        search_items.append({
            "name": name,
            "quantity": ri.quantity,
            "unit": ri.unit or "",
        })

    store_id = settings.kroger_store_id
    matches = await kroger_client.match_ingredients(
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


# ── Add to Cart ──

@router.post("/cart/add/{recipe_id}")
async def add_recipe_to_cart(
    recipe_id: int,
    user_id: int = Query(1),
    db: AsyncSession = Depends(get_db),
):
    """One-click: match ingredients + add all to Kroger cart."""
    # Get user token
    user_token = await _get_user_token(user_id, db)

    # Match ingredients
    match_data = await match_recipe_ingredients(recipe_id, db)
    items = match_data["items"]

    # Build cart items from matched products
    cart_items = []
    skipped = []
    for item in items:
        if item.get("matched") and item.get("upc"):
            cart_items.append({"upc": item["upc"], "quantity": 1})
        else:
            skipped.append(item["ingredient"])

    if not cart_items:
        raise HTTPException(400, "No products matched — nothing to add to cart")

    # Try to add to cart via API (may or may not show up depending on fulfillment session)
    cart_result = await kroger_client.add_to_cart(user_token, cart_items)

    return {
        "success": True,
        "added": len(cart_items),
        "skipped": skipped,
        "estimated_cost": match_data["estimated_cost"],
        "message": f"Matched {len(cart_items)} items at Kroger!",
        "api_cart_added": cart_result.get("success", False),
        "items": items,  # Include full match data with product_url
    }


# ── Product Search (for manual lookups) ──

@router.get("/debug")
async def kroger_debug(user_id: int = Query(1), db: AsyncSession = Depends(get_db)):
    """Debug endpoint: show Kroger account info and test cart add."""
    import httpx as httpx_mod

    user_token = await _get_user_token(user_id, db)

    # Get profile
    profile = None
    async with httpx_mod.AsyncClient() as client:
        resp = await client.get(
            "https://api.kroger.com/v1/identity/profile",
            headers={"Authorization": f"Bearer {user_token}", "Accept": "application/json"},
        )
        if resp.status_code == 200:
            profile = resp.json().get("data", {})
        else:
            profile = {"error": resp.status_code, "body": resp.text[:500]}

    # Try adding a single test item (Kroger brand milk)
    cart_test = None
    async with httpx_mod.AsyncClient() as client:
        resp = await client.put(
            "https://api.kroger.com/v1/cart/add",
            json={"items": [{"upc": "0001111089305", "quantity": 1}]},
            headers={
                "Authorization": f"Bearer {user_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        cart_test = {
            "status": resp.status_code,
            "headers": dict(resp.headers),
            "body": resp.text[:500] if resp.text else "(empty)",
        }

    return {
        "profile": profile,
        "cart_test": cart_test,
        "token_scopes": "cart.basic:write product.compact",
    }


@router.get("/search")
async def search_products(
    q: str = Query(..., description="Search term"),
    limit: int = Query(5, ge=1, le=50),
):
    """Search Kroger products."""
    products = await kroger_client.search_products(
        q, settings.kroger_store_id, limit
    )
    results = []
    for p in products:
        item = p.get("items", [{}])[0] if p.get("items") else {}
        price = item.get("price", {})
        results.append({
            "upc": p["upc"],
            "description": p.get("description", ""),
            "brand": p.get("brand", ""),
            "size": item.get("size", ""),
            "price": price.get("promo") if price.get("promo", 0) > 0 else price.get("regular"),
            "on_sale": bool(price.get("promo", 0) > 0),
        })
    return results
