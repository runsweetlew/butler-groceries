"""Cook-along mode routes.

Step-by-step cooking assistant with timer support.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Recipe, RecipeStep, RecipeIngredient, Ingredient
from app.schemas import CookAlongSession, StepOut

logger = logging.getLogger("butlergroceries.routers.cookalong")
router = APIRouter(prefix="/api/cookalong", tags=["cookalong"])


@router.get("/{recipe_id}", response_model=CookAlongSession)
async def get_cookalong(recipe_id: int, servings_multiplier: float = 1.0, db: AsyncSession = Depends(get_db)):
    """Get cook-along data for a recipe.

    Returns all steps with timer info for the step-by-step cooking mode.
    Steps with duration_minutes get timer support in the UI.
    """
    logger.info(f"Starting cook-along for recipe {recipe_id} (multiplier={servings_multiplier})")

    result = await db.execute(select(Recipe).where(Recipe.id == recipe_id))
    recipe = result.scalar_one_or_none()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    # Get steps
    step_result = await db.execute(
        select(RecipeStep)
        .where(RecipeStep.recipe_id == recipe_id)
        .order_by(RecipeStep.step_number)
    )
    steps = step_result.scalars().all()

    if not steps:
        raise HTTPException(status_code=400, detail="Recipe has no steps for cook-along mode")

    step_list = [
        StepOut(
            id=s.id,
            step_number=s.step_number,
            instruction=s.instruction,
            duration_minutes=s.duration_minutes,
            timer_label=s.timer_label,
        )
        for s in steps
    ]

    # Identify steps that have timers
    active_timers = []
    for s in steps:
        if s.duration_minutes and s.duration_minutes > 0:
            active_timers.append({
                "step_number": s.step_number,
                "label": s.timer_label or f"Step {s.step_number}",
                "duration_minutes": s.duration_minutes,
                "duration_seconds": s.duration_minutes * 60,
            })

    logger.info(
        f"Cook-along ready: {recipe.title} — {len(steps)} steps, {len(active_timers)} timers",
        extra={
            "extra_data": {
                "recipe_id": recipe_id,
                "recipe_title": recipe.title,
                "step_count": len(steps),
                "timer_count": len(active_timers),
            }
        },
    )

    return CookAlongSession(
        recipe_id=recipe.id,
        recipe_title=recipe.title,
        total_steps=len(steps),
        current_step=1,
        steps=step_list,
        active_timers=active_timers,
        servings_multiplier=servings_multiplier,
    )


@router.get("/{recipe_id}/ingredients")
async def get_scaled_ingredients(
    recipe_id: int,
    servings_multiplier: float = 1.0,
    db: AsyncSession = Depends(get_db),
):
    """Get ingredients scaled by multiplier for cook-along reference."""
    logger.info(f"Getting scaled ingredients for recipe {recipe_id} (x{servings_multiplier})")

    result = await db.execute(select(Recipe).where(Recipe.id == recipe_id))
    recipe = result.scalar_one_or_none()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    ing_result = await db.execute(
        select(RecipeIngredient)
        .where(RecipeIngredient.recipe_id == recipe_id)
        .order_by(RecipeIngredient.sort_order)
    )
    ingredients = ing_result.scalars().all()

    scaled = []
    current_group = ""
    for ing in ingredients:
        quantity = None
        if ing.quantity:
            quantity = round(ing.quantity * servings_multiplier, 2)

        item = {
            "raw_text": ing.raw_text,
            "quantity": quantity,
            "unit": ing.unit,
            "preparation": ing.preparation,
            "group": ing.group_name,
        }

        if ing.group_name != current_group:
            current_group = ing.group_name

        scaled.append(item)

    return {
        "recipe_id": recipe_id,
        "original_servings": recipe.servings,
        "multiplier": servings_multiplier,
        "adjusted_servings": round(recipe.servings * servings_multiplier),
        "ingredients": scaled,
    }
