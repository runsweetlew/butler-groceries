"""Home Assistant integration routes.

Provides endpoints designed for HA sensors, automations, and notifications.
- /api/ha/tonight — Tonight's dinner info (for HA sensor)
- /api/ha/week-summary — This week's meal plan (for HA sensor)
- /api/ha/shopping-count — Shopping list status (for HA sensor)
- /api/ha/matches — Recent swipe matches (for HA notification)
- /api/ha/pending-ratings — Unrated cooked meals (for HA reminder)
"""

import logging
from datetime import date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.database import get_db
from app.models import MealPlan, Recipe, ShoppingList, ShoppingItem, SwipeMatch, SwipeSession, Rating, CookingHistory

logger = logging.getLogger("dukecook.routers.homeassistant")
router = APIRouter(prefix="/api/ha", tags=["homeassistant"])


@router.get("/tonight")
async def tonight_dinner(db: AsyncSession = Depends(get_db)):
    """What's for dinner tonight? Designed for HA sensor.

    Returns state-friendly data for a template sensor.
    """
    today = date.today()

    result = await db.execute(
        select(MealPlan, Recipe)
        .join(Recipe, MealPlan.recipe_id == Recipe.id)
        .where(
            and_(
                MealPlan.date == today,
                MealPlan.meal_type == "dinner",
            )
        )
    )
    meals = result.all()

    if not meals:
        logger.info("HA sensor: No dinner planned tonight")
        return {
            "state": "Nothing planned",
            "attributes": {
                "friendly_name": "Tonight's Dinner",
                "icon": "mdi:food-off",
                "planned": False,
                "date": str(today),
            }
        }

    plan, recipe = meals[0]
    logger.info(f"HA sensor: Tonight's dinner is {recipe.title}")

    return {
        "state": recipe.title,
        "attributes": {
            "friendly_name": "Tonight's Dinner",
            "icon": "mdi:silverware-fork-knife",
            "planned": True,
            "recipe_id": recipe.id,
            "recipe_title": recipe.title,
            "cuisine": recipe.cuisine or "Unknown",
            "total_time_min": recipe.total_time_min,
            "difficulty": recipe.difficulty,
            "servings": recipe.servings,
            "status": plan.status,
            "date": str(today),
            "url": f"/recipes/{recipe.id}",
            "cook_url": f"/cook/{recipe.id}",
        }
    }


@router.get("/week-summary")
async def week_summary(db: AsyncSession = Depends(get_db)):
    """This week's meal plan summary for HA sensor."""
    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # Monday
    week_end = week_start + timedelta(days=6)

    result = await db.execute(
        select(MealPlan, Recipe)
        .join(Recipe, MealPlan.recipe_id == Recipe.id)
        .where(
            and_(
                MealPlan.date >= week_start,
                MealPlan.date <= week_end,
            )
        )
        .order_by(MealPlan.date)
    )
    meals = result.all()

    planned_count = len(meals)
    cooked_count = sum(1 for p, _ in meals if p.status == "cooked")

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    schedule = {}
    for plan, recipe in meals:
        day_idx = (plan.date - week_start).days
        if 0 <= day_idx < 7:
            schedule[day_names[day_idx]] = recipe.title

    return {
        "state": f"{planned_count} meals planned",
        "attributes": {
            "friendly_name": "Week's Meal Plan",
            "icon": "mdi:calendar-week",
            "planned_count": planned_count,
            "cooked_count": cooked_count,
            "remaining": planned_count - cooked_count,
            "week_start": str(week_start),
            "week_end": str(week_end),
            "schedule": schedule,
        }
    }


@router.get("/shopping-count")
async def shopping_count(db: AsyncSession = Depends(get_db)):
    """Shopping list status for HA sensor."""
    result = await db.execute(
        select(ShoppingList).order_by(ShoppingList.created_at.desc()).limit(1)
    )
    shopping_list = result.scalar_one_or_none()

    if not shopping_list:
        return {
            "state": "No list",
            "attributes": {
                "friendly_name": "Shopping List",
                "icon": "mdi:cart-outline",
                "total": 0,
                "checked": 0,
                "remaining": 0,
            }
        }

    items_result = await db.execute(
        select(ShoppingItem).where(ShoppingItem.list_id == shopping_list.id)
    )
    items = items_result.scalars().all()

    total = len(items)
    checked = sum(1 for i in items if i.checked)
    remaining = total - checked

    return {
        "state": f"{remaining} items left",
        "attributes": {
            "friendly_name": "Shopping List",
            "icon": "mdi:cart" if remaining > 0 else "mdi:cart-check",
            "total": total,
            "checked": checked,
            "remaining": remaining,
            "list_name": shopping_list.name,
            "percent_complete": round((checked / max(total, 1)) * 100),
        }
    }


@router.get("/matches")
async def recent_matches(db: AsyncSession = Depends(get_db)):
    """Recent swipe matches for HA notification trigger."""
    yesterday = date.today() - timedelta(days=1)

    result = await db.execute(
        select(SwipeMatch, Recipe)
        .join(Recipe, SwipeMatch.recipe_id == Recipe.id)
        .join(SwipeSession, SwipeMatch.session_id == SwipeSession.id)
        .where(SwipeMatch.matched_at >= yesterday)
        .order_by(SwipeMatch.matched_at.desc())
    )
    matches = result.all()

    match_list = [
        {"recipe": recipe.title, "recipe_id": recipe.id, "matched_at": str(match.matched_at)}
        for match, recipe in matches
    ]

    return {
        "state": len(match_list),
        "attributes": {
            "friendly_name": "Recipe Matches",
            "icon": "mdi:heart",
            "matches": match_list,
            "has_new_matches": len(match_list) > 0,
        }
    }


@router.get("/pending-ratings")
async def pending_ratings(db: AsyncSession = Depends(get_db)):
    """Meals cooked but not yet rated — for HA reminder notification."""
    # Find cooked meals in the last 7 days that don't have 2 ratings
    week_ago = date.today() - timedelta(days=7)

    result = await db.execute(
        select(MealPlan, Recipe)
        .join(Recipe, MealPlan.recipe_id == Recipe.id)
        .where(
            and_(
                MealPlan.status == "cooked",
                MealPlan.date >= week_ago,
            )
        )
    )
    cooked = result.all()

    pending = []
    for plan, recipe in cooked:
        rating_result = await db.execute(
            select(func.count(Rating.id)).where(
                and_(
                    Rating.recipe_id == recipe.id,
                    Rating.cooked_at == plan.date,
                )
            )
        )
        rating_count = rating_result.scalar() or 0
        if rating_count < 2:  # Need both users to rate
            pending.append({
                "recipe": recipe.title,
                "recipe_id": recipe.id,
                "cooked_date": str(plan.date),
                "ratings_so_far": rating_count,
            })

    return {
        "state": len(pending),
        "attributes": {
            "friendly_name": "Pending Ratings",
            "icon": "mdi:star-half-full" if pending else "mdi:star-check",
            "pending": pending,
            "has_pending": len(pending) > 0,
        }
    }


@router.get("/stats")
async def cooking_stats(db: AsyncSession = Depends(get_db)):
    """Overall cooking stats for HA dashboard."""
    # Total recipes
    recipe_count = await db.execute(select(func.count(Recipe.id)))
    total_recipes = recipe_count.scalar() or 0

    # Meals cooked this week
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_cooked = await db.execute(
        select(func.count(MealPlan.id)).where(
            and_(MealPlan.date >= week_start, MealPlan.status == "cooked")
        )
    )
    cooked_this_week = week_cooked.scalar() or 0

    # Total meals cooked ever
    total_cooked = await db.execute(
        select(func.count(CookingHistory.id))
    )
    total_meals_cooked = total_cooked.scalar() or 0

    # Average rating
    avg_result = await db.execute(select(func.avg(Rating.stars)))
    avg_rating = avg_result.scalar()

    return {
        "state": f"{total_recipes} recipes",
        "attributes": {
            "friendly_name": "DukeCook Stats",
            "icon": "mdi:chef-hat",
            "total_recipes": total_recipes,
            "cooked_this_week": cooked_this_week,
            "total_meals_cooked": total_meals_cooked,
            "average_rating": round(float(avg_rating), 1) if avg_rating else 0,
        }
    }
