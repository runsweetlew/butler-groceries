"""Recipe import pipeline.

1. Fetch URL
2. Try structured data extraction (recipe-scrapers)
3. Fall back to AI extraction (Claude)
4. Normalize and save to database
"""

import logging
import time
from typing import Optional
import httpx
from bs4 import BeautifulSoup
from recipe_scrapers import scrape_html
from recipe_scrapers._exceptions import SchemaOrgException, WebsiteNotImplementedError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Recipe, RecipeIngredient, RecipeStep, Tag, RecipeTag, Ingredient, ImportLog
from app.services.ai_extractor import extract_recipe_from_html, enrich_recipe_tags

logger = logging.getLogger("dukecook.services.recipe_importer")

# Common user agent to avoid blocks
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


async def fetch_url(url: str) -> Optional[str]:
    """Fetch a URL and return the HTML content."""
    logger.info(f"Fetching URL: {url}")
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            logger.info(f"Fetched URL successfully: {url} ({len(resp.text)} bytes, status {resp.status_code})")
            return resp.text
    except httpx.TimeoutException:
        logger.error(f"Timeout fetching URL: {url}")
        return None
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching URL: {url} — {e.response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Failed to fetch URL: {url} — {e}", exc_info=True)
        return None


def try_structured_extraction(html: str, url: str) -> Optional[dict]:
    """Try to extract recipe using recipe-scrapers (schema.org/microdata)."""
    logger.info(f"Attempting structured extraction for: {url}")
    try:
        scraper = scrape_html(html, org_url=url)

        recipe_data = {
            "title": scraper.title(),
            "description": "",
            "image_url": scraper.image() or "",
            "prep_time_min": None,
            "cook_time_min": None,
            "total_time_min": scraper.total_time() if scraper.total_time() else None,
            "servings": _parse_servings(scraper.yields()),
            "cuisine": scraper.cuisine() if hasattr(scraper, 'cuisine') and scraper.cuisine() else "",
            "difficulty": "medium",
            "ingredients": [],
            "steps": [],
            "tags": [],
        }

        # Parse ingredients
        for i, ing_text in enumerate(scraper.ingredients()):
            recipe_data["ingredients"].append({
                "raw_text": ing_text,
                "quantity": None,
                "unit": "",
                "name": ing_text,
                "preparation": "",
                "group": "",
            })

        # Parse steps
        instructions = scraper.instructions_list() if hasattr(scraper, 'instructions_list') else []
        if not instructions and scraper.instructions():
            instructions = [s.strip() for s in scraper.instructions().split("\n") if s.strip()]

        for i, step_text in enumerate(instructions):
            recipe_data["steps"].append({
                "instruction": step_text,
                "duration_minutes": None,
                "timer_label": "",
            })

        # Try to get description
        try:
            recipe_data["description"] = scraper.description() or ""
        except Exception:
            pass

        # Try to parse prep/cook times
        try:
            recipe_data["prep_time_min"] = scraper.prep_time() if scraper.prep_time() else None
        except Exception:
            pass
        try:
            recipe_data["cook_time_min"] = scraper.cook_time() if scraper.cook_time() else None
        except Exception:
            pass

        logger.info(
            f"Structured extraction successful: {recipe_data['title']}",
            extra={
                "extra_data": {
                    "url": url,
                    "title": recipe_data["title"],
                    "ingredient_count": len(recipe_data["ingredients"]),
                    "step_count": len(recipe_data["steps"]),
                }
            },
        )
        return recipe_data

    except (SchemaOrgException, WebsiteNotImplementedError) as e:
        logger.info(f"No structured data found for {url}: {e}")
        return None
    except Exception as e:
        logger.warning(f"Structured extraction failed for {url}: {e}", exc_info=True)
        return None


def _parse_servings(yields_str: str) -> int:
    """Parse servings from a string like '4 servings' or '6'."""
    if not yields_str:
        return 4
    import re
    match = re.search(r'(\d+)', str(yields_str))
    return int(match.group(1)) if match else 4


async def download_image(image_url: str, recipe_id: int) -> Optional[str]:
    """Download recipe hero image and save locally."""
    if not image_url:
        return None

    from app.config import get_settings
    import os
    from pathlib import Path

    settings = get_settings()
    image_dir = Path(settings.image_dir)
    image_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Downloading image for recipe {recipe_id}: {image_url}")

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            resp = await client.get(image_url)
            resp.raise_for_status()

            # Determine extension from content type
            content_type = resp.headers.get("content-type", "image/jpeg")
            ext = ".jpg"
            if "png" in content_type:
                ext = ".png"
            elif "webp" in content_type:
                ext = ".webp"

            filename = f"recipe_{recipe_id}{ext}"
            filepath = image_dir / filename

            filepath.write_bytes(resp.content)
            logger.info(f"Saved image: {filepath} ({len(resp.content)} bytes)")
            return f"/images/{filename}"

    except Exception as e:
        logger.warning(f"Failed to download image: {e}", exc_info=True)
        return None


async def get_or_create_tag(db: AsyncSession, name: str, tag_type: str = "custom") -> Tag:
    """Find or create a tag."""
    name = name.lower().strip()
    result = await db.execute(
        select(Tag).where(Tag.name == name, Tag.type == tag_type)
    )
    tag = result.scalar_one_or_none()
    if not tag:
        tag = Tag(name=name, type=tag_type)
        db.add(tag)
        await db.flush()
        logger.debug(f"Created tag: {name} ({tag_type})")
    return tag


async def get_or_create_ingredient(db: AsyncSession, name: str, category: str = "other") -> Ingredient:
    """Find or create a normalized ingredient."""
    name = name.lower().strip()
    result = await db.execute(select(Ingredient).where(Ingredient.name == name))
    ingredient = result.scalar_one_or_none()
    if not ingredient:
        ingredient = Ingredient(name=name, category=category)
        db.add(ingredient)
        await db.flush()
    return ingredient


async def save_recipe_data(
    db: AsyncSession,
    recipe_data: dict,
    source_url: str,
    extraction_method: str,
    user_id: Optional[int] = None,
    start_time: Optional[float] = None,
    source_image_path: Optional[str] = None,
) -> dict:
    """Save extracted recipe data to the database.

    Shared by URL import, photo import, and any other import method.
    Returns {"status": "success", "recipe_id": N, ...} or {"status": "failed", ...}
    """
    if start_time is None:
        start_time = time.time()

    # Build original_text from the full extraction for reference
    original_parts = []
    if recipe_data.get("title"):
        original_parts.append(recipe_data["title"])
    if recipe_data.get("description"):
        original_parts.append(f"\n{recipe_data['description']}")
    if recipe_data.get("ingredients"):
        original_parts.append("\n\nIngredients:")
        for ing in recipe_data["ingredients"]:
            original_parts.append(f"  • {ing.get('raw_text', '')}")
    if recipe_data.get("steps"):
        original_parts.append("\n\nInstructions:")
        for i, step in enumerate(recipe_data["steps"], 1):
            original_parts.append(f"  {i}. {step.get('instruction', '')}")
    if recipe_data.get("notes"):
        original_parts.append(f"\n\nNotes:\n{recipe_data['notes']}")
    original_text = "\n".join(original_parts)

    try:
        recipe = Recipe(
            title=recipe_data.get("title", "Untitled"),
            description=recipe_data.get("description", ""),
            source_url=source_url,
            image_url=recipe_data.get("image_url", ""),
            prep_time_min=recipe_data.get("prep_time_min"),
            cook_time_min=recipe_data.get("cook_time_min"),
            total_time_min=recipe_data.get("total_time_min"),
            servings=recipe_data.get("servings", 4),
            cuisine=recipe_data.get("cuisine", ""),
            difficulty=recipe_data.get("difficulty", "medium"),
            notes=recipe_data.get("notes", ""),
            original_text=original_text,
            created_by=user_id,
        )
        db.add(recipe)
        await db.flush()

        logger.info(f"Created recipe record: id={recipe.id}, title={recipe.title}")

        # Save ingredients
        for i, ing in enumerate(recipe_data.get("ingredients", [])):
            ing_name = ing.get("name", ing.get("raw_text", ""))
            normalized_ing = await get_or_create_ingredient(db, ing_name)

            ri = RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_id=normalized_ing.id,
                raw_text=ing.get("raw_text", ing_name),
                quantity=ing.get("quantity"),
                unit=ing.get("unit", ""),
                preparation=ing.get("preparation", ""),
                group_name=ing.get("group", ""),
                sort_order=i,
            )
            db.add(ri)

        # Save steps
        for i, step in enumerate(recipe_data.get("steps", [])):
            rs = RecipeStep(
                recipe_id=recipe.id,
                step_number=i + 1,
                instruction=step.get("instruction", ""),
                duration_minutes=step.get("duration_minutes"),
                timer_label=step.get("timer_label", ""),
            )
            db.add(rs)

        # Save tags
        tag_type_map = {
            "chicken": "protein", "beef": "protein", "pork": "protein",
            "salmon": "protein", "shrimp": "protein", "fish": "protein",
            "tofu": "protein", "vegetarian": "dietary", "vegan": "dietary",
            "gluten-free": "dietary", "dairy-free": "dietary", "low-carb": "dietary",
            "easy": "effort", "medium": "effort", "hard": "effort",
            "weeknight": "meal_type", "weekend": "meal_type",
            "date-night": "meal_type", "meal-prep": "meal_type",
            "summer": "season", "winter": "season", "fall": "season", "spring": "season",
        }

        for tag_name in recipe_data.get("tags", []):
            tag_type = tag_type_map.get(tag_name.lower(), "cuisine")
            tag = await get_or_create_tag(db, tag_name, tag_type)
            rt = RecipeTag(recipe_id=recipe.id, tag_id=tag.id)
            db.add(rt)

        await db.flush()

        # Download image if URL provided, or use saved source image (photo imports)
        image_path = await download_image(recipe_data.get("image_url", ""), recipe.id)
        if image_path:
            recipe.image_path = image_path
        elif source_image_path:
            # For photo imports: use the uploaded photo as the recipe image
            recipe.image_path = source_image_path
            logger.info(f"Using source photo as recipe image: {source_image_path}")
        if recipe.image_path:
            await db.flush()

        duration_ms = int((time.time() - start_time) * 1000)

        # Log the import
        log_entry = ImportLog(
            url=source_url,
            status="success",
            recipe_id=recipe.id,
            extraction_method=extraction_method,
            raw_data=recipe_data,
            duration_ms=duration_ms,
        )
        db.add(log_entry)
        await db.flush()

        logger.info(
            f"Recipe imported successfully: {recipe.title} (id={recipe.id})",
            extra={
                "extra_data": {
                    "recipe_id": recipe.id,
                    "title": recipe.title,
                    "source": source_url,
                    "method": extraction_method,
                    "duration_ms": duration_ms,
                    "ingredients": len(recipe_data.get("ingredients", [])),
                    "steps": len(recipe_data.get("steps", [])),
                    "tags": recipe_data.get("tags", []),
                }
            },
        )

        return {
            "status": "success",
            "recipe_id": recipe.id,
            "recipe_title": recipe.title,
            "url": source_url,
            "extraction_method": extraction_method,
            "duration_ms": duration_ms,
        }

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Failed to save recipe: {e}", exc_info=True, extra={
            "extra_data": {"source": source_url, "duration_ms": duration_ms}
        })
        log_entry = ImportLog(url=source_url, status="failed", error=str(e), duration_ms=duration_ms)
        db.add(log_entry)
        await db.flush()
        return {"status": "failed", "error": str(e), "url": source_url, "duration_ms": duration_ms}


async def import_recipe_from_url(db: AsyncSession, url: str, user_id: Optional[int] = None) -> dict:
    """Full import pipeline: fetch → extract → save.

    Returns {"status": "success", "recipe_id": N, ...} or {"status": "failed", "error": "..."}
    """
    start_time = time.time()
    logger.info(f"Starting recipe import from URL: {url}", extra={
        "extra_data": {"url": url, "user_id": user_id}
    })

    # 1. Fetch
    html = await fetch_url(url)
    if not html:
        duration_ms = int((time.time() - start_time) * 1000)
        log_entry = ImportLog(url=url, status="failed", error="Failed to fetch URL", duration_ms=duration_ms)
        db.add(log_entry)
        await db.flush()
        return {"status": "failed", "error": "Failed to fetch URL", "url": url, "duration_ms": duration_ms}

    # 2. Try structured extraction first
    recipe_data = try_structured_extraction(html, url)
    extraction_method = "schema" if recipe_data else ""

    # 3. Fall back to AI extraction
    if not recipe_data:
        logger.info(f"Falling back to AI extraction for: {url}")
        recipe_data = await extract_recipe_from_html(html, url)
        extraction_method = "ai" if recipe_data else ""

    if not recipe_data:
        duration_ms = int((time.time() - start_time) * 1000)
        log_entry = ImportLog(url=url, status="failed", error="Could not extract recipe data", duration_ms=duration_ms)
        db.add(log_entry)
        await db.flush()
        logger.error(f"Failed to extract recipe from: {url}")
        return {"status": "failed", "error": "Could not extract recipe data", "url": url, "duration_ms": duration_ms}

    # 4. Enrich tags via AI if we used structured extraction (which doesn't get tags)
    if extraction_method == "schema":
        recipe_data["tags"] = await enrich_recipe_tags(recipe_data)

    # 5. For schema extraction, try to grab any notes/tips from the page
    if extraction_method == "schema" and not recipe_data.get("notes"):
        try:
            soup = BeautifulSoup(html, "html.parser")
            # Look for common notes/tips sections
            notes_parts = []
            for selector in ["[class*='note']", "[class*='tip']", "[class*='variation']",
                             "[class*='make-ahead']", "[class*='storage']"]:
                for el in soup.select(selector):
                    text = el.get_text(strip=True)
                    if text and len(text) > 20 and len(text) < 2000:
                        notes_parts.append(text)
            if notes_parts:
                recipe_data["notes"] = "\n\n".join(notes_parts[:5])
        except Exception:
            pass

    # 6. Save to database
    return await save_recipe_data(db, recipe_data, url, extraction_method, user_id, start_time)
