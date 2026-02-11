"""Kroger API integration — OAuth, product search, cart management."""

import base64
import time
import logging
from typing import Optional
import httpx

from app.config import get_settings

logger = logging.getLogger("dukecook.kroger")

API_BASE = "https://api.kroger.com/v1"
DEFAULT_STORE = "01800661"  # Kroger Middlebelt, Farmington Hills MI

settings = get_settings()


class KrogerClient:
    """Handles Kroger API auth and requests."""

    def __init__(self):
        self.client_id = settings.kroger_client_id
        self.client_secret = settings.kroger_client_secret
        self._client_token: Optional[str] = None
        self._client_token_expires: float = 0

    # ── Client Credentials (product search, no user needed) ──

    async def _get_client_token(self) -> str:
        """Get or refresh client_credentials token for product search."""
        if self._client_token and time.time() < self._client_token_expires - 60:
            return self._client_token

        auth = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{API_BASE}/connect/oauth2/token",
                data={"grant_type": "client_credentials", "scope": "product.compact"},
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {auth}",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        self._client_token = data["access_token"]
        self._client_token_expires = time.time() + data.get("expires_in", 1800)
        return self._client_token

    # ── User OAuth (for cart operations) ──

    def get_authorize_url(self, redirect_uri: str, state: str = "") -> str:
        """Build the Kroger OAuth authorize URL."""
        params = {
            "scope": "cart.basic:write product.compact profile.compact",
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
        }
        if state:
            params["state"] = state
        qs = "&".join(f"{k}={httpx.URL('', params={k: v}).params}" for k, v in params.items())
        # Build manually to avoid double-encoding
        from urllib.parse import urlencode
        return f"{API_BASE}/connect/oauth2/authorize?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> dict:
        """Exchange authorization code for access + refresh tokens."""
        auth = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{API_BASE}/connect/oauth2/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {auth}",
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def refresh_user_token(self, refresh_token: str) -> dict:
        """Refresh a user's access token."""
        auth = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{API_BASE}/connect/oauth2/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {auth}",
                },
            )
            resp.raise_for_status()
            return resp.json()

    # ── Product Search ──

    async def search_products(
        self, term: str, location_id: str = DEFAULT_STORE, limit: int = 5
    ) -> list[dict]:
        """Search for products at a store."""
        token = await self._get_client_token()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{API_BASE}/products",
                params={
                    "filter.term": term,
                    "filter.locationId": location_id,
                    "filter.limit": str(limit),
                },
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
            resp.raise_for_status()
            return resp.json().get("data", [])

    async def search_best_match(
        self, ingredient_name: str, location_id: str = DEFAULT_STORE
    ) -> Optional[dict]:
        """Search for the single best product match for an ingredient."""
        products = await self.search_products(ingredient_name, location_id, limit=1)
        if not products:
            return None
        p = products[0]
        item = p.get("items", [{}])[0] if p.get("items") else {}
        price = item.get("price", {})
        upc = p["upc"]
        desc = p.get("description", "")
        # Build a Kroger product page URL (slug from description)
        slug = desc.lower().replace("®", "").replace("™", "")
        slug = "".join(c if c.isalnum() or c == " " else "" for c in slug)
        slug = "-".join(slug.split())
        product_url = f"https://www.kroger.com/p/{slug}/{upc}"

        return {
            "upc": upc,
            "description": desc,
            "brand": p.get("brand", ""),
            "size": item.get("size", ""),
            "price": price.get("promo") if price.get("promo", 0) > 0 else price.get("regular"),
            "price_regular": price.get("regular"),
            "on_sale": bool(price.get("promo", 0) > 0),
            "in_stock": item.get("fulfillment", {}).get("inStore", False),
            "aisle": _format_aisle(p.get("aisleLocations", [])),
            "image_url": _get_image_url(p),
            "product_url": product_url,
            "search_url": f"https://www.kroger.com/search?query={ingredient_name.replace(' ', '+')}&searchType=default_search",
        }

    async def match_ingredients(
        self, ingredients: list[str], location_id: str = DEFAULT_STORE
    ) -> list[dict]:
        """Match a list of ingredient names to Kroger products."""
        results = []
        for name in ingredients:
            match = await self.search_best_match(name, location_id)
            results.append({
                "ingredient": name,
                "matched": match is not None,
                **(match or {}),
            })
        return results

    # ── Cart Operations (requires user token) ──

    async def add_to_cart(self, user_token: str, items: list[dict]) -> dict:
        """Add items to user's Kroger cart.

        items: [{"upc": "0001111004965", "quantity": 1}, ...]
        Returns dict with success status and raw response details.
        """
        logger.info(f"Cart add: sending {len(items)} items, first 3: {items[:3]}")
        async with httpx.AsyncClient() as client:
            resp = await client.put(
                f"{API_BASE}/cart/add",
                json={"items": items},
                headers={
                    "Authorization": f"Bearer {user_token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
            body = resp.text[:1000] if resp.text else "(empty)"
            logger.info(f"Cart add response: status={resp.status_code} headers={dict(resp.headers)} body={body}")

            if resp.status_code in (200, 201, 204):
                logger.info(f"Added {len(items)} items to Kroger cart")
                return {"success": True, "status": resp.status_code, "body": body}
            logger.error(f"Cart add failed: {resp.status_code} {body}")
            return {"success": False, "status": resp.status_code, "body": body}


# ── Helpers ──

def _format_aisle(aisle_locations: list) -> str:
    if not aisle_locations:
        return ""
    a = aisle_locations[0]
    return f"{a.get('description', '')} #{a.get('number', '')}".strip()


def _get_image_url(product: dict) -> str:
    for img in product.get("images", []):
        if img.get("perspective") == "front":
            for size in img.get("sizes", []):
                if size.get("size") == "medium":
                    return size.get("url", "")
    return ""


# Singleton
kroger_client = KrogerClient()
