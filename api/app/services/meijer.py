"""Meijer API integration — product search, shopping list, aisle lookup.

Uses the python_Meijer library (https://github.com/dapperfu/python_Meijer).
Auth requires a bearer token captured via mitmproxy from the Meijer mobile app.
"""

import logging
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger("butlergroceries.meijer")

settings = get_settings()

MEIJER_API_BASE = "https://gw.meijer.com"
MEIJER_SEARCH_URL = "https://www.meijer.com/shopping/search.html"


class MeijerClient:
    """Handles Meijer API requests for product search and shopping list."""

    def __init__(self):
        self._auth_token: Optional[str] = settings.meijer_auth_token or None
        self._refresh_token: Optional[str] = settings.meijer_refresh_token or None
        self._store_id: str = settings.meijer_store_id

    @property
    def is_configured(self) -> bool:
        """Check if Meijer auth token is configured."""
        return bool(self._auth_token)

    def _headers(self) -> dict:
        """Build auth headers for Meijer API requests."""
        return {
            "Authorization": f"Bearer {self._auth_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Meijer/8.71.0 (Android)",
        }

    # ── Product Search ──

    async def search_products(
        self, term: str, store_id: Optional[str] = None, limit: int = 5
    ) -> list[dict]:
        """Search for products at a Meijer store."""
        if not self.is_configured:
            logger.warning("Meijer not configured — skipping product search")
            return []

        sid = store_id or self._store_id
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{MEIJER_API_BASE}/product/api/v1/search",
                    params={
                        "query": term,
                        "storeId": sid,
                        "offset": "0",
                        "limit": str(limit),
                    },
                    headers=self._headers(),
                )
                if resp.status_code == 401:
                    logger.error("Meijer auth token expired — needs refresh")
                    return []
                resp.raise_for_status()
                data = resp.json()
                return data.get("products", [])
        except Exception as e:
            logger.error(f"Meijer product search failed: {e}")
            return []

    async def search_best_match(
        self, ingredient_name: str, store_id: Optional[str] = None
    ) -> Optional[dict]:
        """Search for the single best product match for an ingredient."""
        products = await self.search_products(ingredient_name, store_id, limit=1)
        if not products:
            return None

        p = products[0]
        upc = p.get("upc", "")
        desc = p.get("description", p.get("name", ""))
        price_info = p.get("price", {})
        price = price_info.get("salePrice") or price_info.get("basePrice") or price_info.get("price")
        regular_price = price_info.get("basePrice") or price_info.get("price")
        on_sale = bool(price_info.get("salePrice"))

        # Build Meijer product search URL
        search_url = f"{MEIJER_SEARCH_URL}?s={ingredient_name.replace(' ', '+')}"

        # Aisle location
        aisle = ""
        aisle_info = p.get("aisleLocation") or p.get("aisle", {})
        if isinstance(aisle_info, dict):
            aisle = f"Aisle {aisle_info.get('aisle', '')} {aisle_info.get('side', '')}".strip()
        elif isinstance(aisle_info, str):
            aisle = aisle_info

        return {
            "upc": upc,
            "description": desc,
            "brand": p.get("brand", ""),
            "size": p.get("size", p.get("packageSize", "")),
            "price": float(price) if price else None,
            "price_regular": float(regular_price) if regular_price else None,
            "on_sale": on_sale,
            "in_stock": p.get("inStock", True),
            "aisle": aisle,
            "image_url": p.get("imageUrl", p.get("image", "")),
            "search_url": search_url,
        }

    async def match_ingredients(
        self, ingredients: list[str], store_id: Optional[str] = None
    ) -> list[dict]:
        """Match a list of ingredient names to Meijer products."""
        results = []
        for name in ingredients:
            match = await self.search_best_match(name, store_id)
            results.append({
                "ingredient": name,
                "matched": match is not None,
                **(match or {}),
            })
        return results

    # ── Shopping List Operations ──

    async def get_shopping_list(self) -> list[dict]:
        """Get the user's Meijer shopping list."""
        if not self.is_configured:
            return []

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{MEIJER_API_BASE}/loyalty/shoppinglist/GetList",
                    headers=self._headers(),
                )
                if resp.status_code == 401:
                    logger.error("Meijer auth token expired")
                    return []
                resp.raise_for_status()
                return resp.json().get("items", [])
        except Exception as e:
            logger.error(f"Failed to get Meijer shopping list: {e}")
            return []

    async def add_to_shopping_list(self, items: list[dict]) -> dict:
        """Add items to the user's Meijer shopping list.

        items: [{"name": "Chicken Breast", "quantity": 1}, ...]
        """
        if not self.is_configured:
            return {"success": False, "error": "Meijer not configured"}

        added = 0
        errors = []
        for item in items:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        f"{MEIJER_API_BASE}/loyalty/shoppinglist/AddListItem",
                        json={
                            "itemName": item.get("name", ""),
                            "quantity": item.get("quantity", 1),
                        },
                        headers=self._headers(),
                    )
                    if resp.status_code in (200, 201, 204):
                        added += 1
                    else:
                        errors.append(f"{item.get('name')}: {resp.status_code}")
            except Exception as e:
                errors.append(f"{item.get('name')}: {e}")

        logger.info(f"Added {added}/{len(items)} items to Meijer shopping list")
        return {
            "success": added > 0,
            "added": added,
            "total": len(items),
            "errors": errors,
        }


# Singleton
meijer_client = MeijerClient()
