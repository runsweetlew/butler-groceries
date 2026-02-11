"""AI-powered meal suggestion engine.

Given available nights, dietary rules, recipe library, and cooking history,
suggests a week of meals using Claude.
"""

import json
import logging
from datetime import date, timedelta
from typing import Optional
import anthropic
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.config import get_settings
from app.models import Recipe, RecipeTag, Tag, Rating, MealPlan, CookingHistory, TasteProfile
from app.services.rules_engine import get_active_rules, evaluate_rules

logger = logging.getLogger("dukecook.services.suggestion_engine")


async def suggest_meals(
    db: AsyncSession,
    week_start: date,
    available_dates: list[date],
    context: str = "",
    user_id: Optional[int] = None,
) -> list[dict]:
    """Suggest meals for the available dates, respecting rules and taste preferences.

    Returns: [{"date": "2026-02-09", "recipe_id": 5, "recipe_title": "...", "reason": "..."}]
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        logger.error("No API key — falling back to random suggestions")
        return await _random_suggestions(db, available_dates)

    logger.info(
        f"Generating meal suggestions for week of {week_start}",
        extra={
            "extra_data": {
                "week_start": str(week_start),
                "available_dates": [str(d) for d in available_dates],
                "context": context,
            }
        },
    )

    # Gather context for the AI
    recipes = await _get_recipe_summaries(db)
    if not recipes:
        logger.warning("No recipes in library — cannot suggest meals")
        return []

    rules = await get_active_rules(db)
    recent_meals = await _get_recent_meals(db, week_start, days_back=21)
    taste_data = await _get_taste_data(db) if user_id else {}

    # Build the prompt
    prompt = _build_suggestion_prompt(
        recipes=recipes,
        rules=rules,
        available_dates=available_dates,
        recent_meals=recent_meals,
        taste_data=taste_data,
        context=context,
    )

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if "```" in text:
                text = text[:text.rfind("```")]
            text = text.strip()

        suggestions = json.loads(text)

        logger.info(
            f"AI suggested {len(suggestions)} meals",
            extra={
                "extra_data": {
                    "suggestions": suggestions,
                    "tokens_in": response.usage.input_tokens,
                    "tokens_out": response.usage.output_tokens,
                }
            },
        )

        # Validate recipe IDs exist
        recipe_ids = {r["id"] for r in recipes}
        validated = []
        for s in suggestions:
            if s.get("recipe_id") in recipe_ids:
                validated.append(s)
            else:
                logger.warning(f"AI suggested non-existent recipe_id: {s.get('recipe_id')}")

        return validated

    except Exception as e:
        logger.error(f"AI suggestion failed: {e}", exc_info=True)
        return await _random_suggestions(db, available_dates)


def _build_suggestion_prompt(
    recipes: list[dict],
    rules: list,
    available_dates: list[date],
    recent_meals: list[dict],
    taste_data: dict,
    context: str,
) -> str:
    """Build the prompt for meal suggestions."""
    recipes_text = "\n".join(
        f"  ID {r['id']}: {r['title']} [{', '.join(r['tags'])}] "
        f"(avg rating: {r['avg_rating']:.1f}, times cooked: {r['cook_count']})"
        for r in recipes[:100]  # Limit to avoid token overflow
    )

    rules_text = "\n".join(
        f"  - {r.name}: {json.dumps(r.config)}"
        for r in rules
    ) or "  No rules defined."

    recent_text = "\n".join(
        f"  {m['date']}: {m['title']} [{', '.join(m['tags'])}]"
        for m in recent_meals
    ) or "  No recent meals."

    dates_text = ", ".join(str(d) for d in available_dates)

    taste_text = json.dumps(taste_data, indent=2) if taste_data else "No taste data yet."

    return f"""You are a meal planning assistant. Suggest dinner recipes for these available dates.

AVAILABLE DATES: {dates_text}
{f'CONTEXT: {context}' if context else ''}

RECIPE LIBRARY (pick from these only):
{recipes_text}

DIETARY RULES (must follow):
{rules_text}

RECENT MEALS (avoid repeats, ensure variety):
{recent_text}

TASTE PREFERENCES:
{taste_text}

INSTRUCTIONS:
1. Pick one recipe for each available date
2. Follow ALL dietary rules strictly
3. Avoid repeating recipes from recent meals
4. Maximize variety in proteins, cuisines, and cooking styles
5. Consider the context (weeknight = easy/quick, weekend = can be ambitious)
6. Prefer higher-rated recipes
7. Give a brief reason for each pick

Return ONLY a JSON array:
[
  {{"date": "2026-02-09", "recipe_id": 5, "recipe_title": "Lemon Herb Salmon", "reason": "Haven't had fish in 10 days, and you both rated this 5 stars"}}
]"""


async def _get_recipe_summaries(db: AsyncSession) -> list[dict]:
    """Get all recipes with their tags and ratings for the AI."""
    result = await db.execute(
        select(Recipe).order_by(Recipe.title)
    )
    recipes = result.scalars().all()

    summaries = []
    for r in recipes:
        # Get tags
        tag_result = await db.execute(
            select(Tag.name)
            .join(RecipeTag, RecipeTag.tag_id == Tag.id)
            .where(RecipeTag.recipe_id == r.id)
        )
        tags = [t[0] for t in tag_result.all()]

        # Get average rating
        rating_result = await db.execute(
            select(func.avg(Rating.stars), func.count(Rating.id))
            .where(Rating.recipe_id == r.id)
        )
        avg_rating, rating_count = rating_result.one()

        # Get cook count
        cook_result = await db.execute(
            select(func.count(CookingHistory.id))
            .where(CookingHistory.recipe_id == r.id)
        )
        cook_count = cook_result.scalar() or 0

        summaries.append({
            "id": r.id,
            "title": r.title,
            "tags": tags,
            "avg_rating": float(avg_rating or 0),
            "rating_count": rating_count or 0,
            "cook_count": cook_count,
            "cuisine": r.cuisine,
            "difficulty": r.difficulty,
            "total_time_min": r.total_time_min,
        })

    logger.debug(f"Loaded {len(summaries)} recipe summaries for suggestion engine")
    return summaries


async def _get_recent_meals(db: AsyncSession, reference_date: date, days_back: int = 21) -> list[dict]:
    """Get recent meal plan entries."""
    start = reference_date - timedelta(days=days_back)
    result = await db.execute(
        select(MealPlan, Recipe)
        .join(Recipe, MealPlan.recipe_id == Recipe.id)
        .where(
            and_(
                MealPlan.date >= start,
                MealPlan.date <= reference_date,
                MealPlan.status != "skipped",
            )
        )
        .order_by(MealPlan.date.desc())
    )

    meals = []
    for plan, recipe in result.all():
        tag_result = await db.execute(
            select(Tag.name)
            .join(RecipeTag, RecipeTag.tag_id == Tag.id)
            .where(RecipeTag.recipe_id == recipe.id)
        )
        tags = [t[0] for t in tag_result.all()]

        meals.append({
            "date": str(plan.date),
            "title": recipe.title,
            "tags": tags,
        })

    return meals


async def _get_taste_data(db: AsyncSession) -> dict:
    """Get combined taste profiles."""
    result = await db.execute(select(TasteProfile))
    profiles = result.scalars().all()

    data = {}
    for p in profiles:
        # Get user name
        from app.models import User
        user_result = await db.execute(select(User).where(User.id == p.user_id))
        user = user_result.scalar_one_or_none()
        if user:
            data[user.name] = p.preferences or {}

    return data


async def _random_suggestions(db: AsyncSession, available_dates: list[date]) -> list[dict]:
    """Fallback: random recipe selection."""
    logger.info("Using random fallback for meal suggestions")
    result = await db.execute(
        select(Recipe).order_by(func.random()).limit(len(available_dates))
    )
    recipes = result.scalars().all()

    suggestions = []
    for d, r in zip(available_dates, recipes):
        suggestions.append({
            "date": str(d),
            "recipe_id": r.id,
            "recipe_title": r.title,
            "reason": "Random suggestion (AI unavailable)",
        })

    return suggestions
