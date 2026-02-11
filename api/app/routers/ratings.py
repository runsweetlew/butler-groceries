"""Rating and cooking history routes.

Both users rate recipes independently after cooking.
Ratings feed into the taste learning system.
"""

import logging
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.database import get_db
from app.models import Rating, Recipe, User, MealPlan
from app.schemas import RatingCreate, RatingOut
from app.services.taste_learner import update_taste_profile, record_cooking

logger = logging.getLogger("butlergroceries.routers.ratings")
router = APIRouter(prefix="/api/ratings", tags=["ratings"])


@router.post("", response_model=RatingOut, status_code=201)
async def create_rating(data: RatingCreate, db: AsyncSession = Depends(get_db)):
    """Rate a recipe after cooking it.

    Each user rates independently (1-5 stars, would make again, notes).
    Triggers taste profile update.
    """
    logger.info(
        f"New rating: user={data.user_id}, recipe={data.recipe_id}, stars={data.stars}",
        extra={
            "extra_data": {
                "user_id": data.user_id,
                "recipe_id": data.recipe_id,
                "stars": data.stars,
                "would_make_again": data.would_make_again,
            }
        },
    )

    # Verify recipe and user exist
    recipe_result = await db.execute(select(Recipe).where(Recipe.id == data.recipe_id))
    recipe = recipe_result.scalar_one_or_none()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    user_result = await db.execute(select(User).where(User.id == data.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Create rating
    rating = Rating(
        recipe_id=data.recipe_id,
        user_id=data.user_id,
        stars=data.stars,
        would_make_again=data.would_make_again,
        notes=data.notes,
        cooked_at=data.cooked_at or date.today(),
    )
    db.add(rating)
    await db.flush()

    # Record cooking event
    await record_cooking(db, data.recipe_id, rating.cooked_at, [data.user_id])

    # Mark meal plan entry as cooked if one exists for today
    plan_result = await db.execute(
        select(MealPlan).where(
            and_(
                MealPlan.recipe_id == data.recipe_id,
                MealPlan.date == rating.cooked_at,
                MealPlan.status == "planned",
            )
        )
    )
    plan = plan_result.scalar_one_or_none()
    if plan:
        plan.status = "cooked"
        await db.flush()
        logger.info(f"Marked meal plan entry {plan.id} as cooked")

    # Update taste profile (async)
    await update_taste_profile(db, data.user_id)

    logger.info(
        f"Rating saved: {user.name} gave {recipe.title} {data.stars}★ "
        f"(would make again: {data.would_make_again})",
        extra={
            "extra_data": {
                "rating_id": rating.id,
                "user_name": user.name,
                "recipe_title": recipe.title,
            }
        },
    )

    return RatingOut(
        id=rating.id,
        user_id=rating.user_id,
        user_name=user.name,
        stars=rating.stars,
        would_make_again=rating.would_make_again,
        notes=rating.notes,
        cooked_at=rating.cooked_at,
        created_at=rating.created_at,
    )


@router.get("/recipe/{recipe_id}", response_model=list[RatingOut])
async def get_recipe_ratings(recipe_id: int, db: AsyncSession = Depends(get_db)):
    """Get all ratings for a recipe (from both users)."""
    logger.info(f"Getting ratings for recipe {recipe_id}")

    result = await db.execute(
        select(Rating)
        .where(Rating.recipe_id == recipe_id)
        .order_by(Rating.created_at.desc())
    )
    ratings = result.scalars().all()

    out = []
    for r in ratings:
        user_result = await db.execute(select(User).where(User.id == r.user_id))
        user = user_result.scalar_one_or_none()
        out.append(RatingOut(
            id=r.id,
            user_id=r.user_id,
            user_name=user.name if user else None,
            stars=r.stars,
            would_make_again=r.would_make_again,
            notes=r.notes,
            cooked_at=r.cooked_at,
            created_at=r.created_at,
        ))

    logger.info(f"Found {len(out)} ratings for recipe {recipe_id}")
    return out


@router.get("/history")
async def rating_history(
    user_id: int = Query(None),
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get recent rating history."""
    logger.info(f"Getting rating history (user_id={user_id}, limit={limit})")

    query = select(Rating).order_by(Rating.created_at.desc()).limit(limit)
    if user_id:
        query = query.where(Rating.user_id == user_id)

    result = await db.execute(query)
    ratings = result.scalars().all()

    history = []
    for r in ratings:
        recipe_result = await db.execute(select(Recipe).where(Recipe.id == r.recipe_id))
        recipe = recipe_result.scalar_one_or_none()
        user_result = await db.execute(select(User).where(User.id == r.user_id))
        user = user_result.scalar_one_or_none()

        history.append({
            "id": r.id,
            "recipe_id": r.recipe_id,
            "recipe_title": recipe.title if recipe else "Unknown",
            "user_id": r.user_id,
            "user_name": user.name if user else "Unknown",
            "stars": r.stars,
            "would_make_again": r.would_make_again,
            "notes": r.notes,
            "cooked_at": str(r.cooked_at) if r.cooked_at else None,
            "created_at": str(r.created_at) if r.created_at else None,
        })

    return {"history": history}


@router.get("/stats")
async def rating_stats(db: AsyncSession = Depends(get_db)):
    """Get aggregate rating statistics."""
    logger.info("Computing rating stats")

    # Total ratings per user
    users_result = await db.execute(select(User))
    users = users_result.scalars().all()

    user_stats = []
    for user in users:
        rating_result = await db.execute(
            select(
                func.count(Rating.id),
                func.avg(Rating.stars),
                func.sum(Rating.would_make_again.cast(int)),
            ).where(Rating.user_id == user.id)
        )
        count, avg_stars, would_make_again = rating_result.one()

        user_stats.append({
            "user_id": user.id,
            "user_name": user.name,
            "total_ratings": count or 0,
            "avg_stars": round(float(avg_stars), 2) if avg_stars else 0,
            "would_make_again_pct": round(float(would_make_again) / count * 100, 1) if count else 0,
        })

    # Overall stats
    total_result = await db.execute(select(func.count(Rating.id)))
    total_ratings = total_result.scalar() or 0

    return {
        "total_ratings": total_ratings,
        "users": user_stats,
    }
