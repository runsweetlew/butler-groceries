"""AI taste learning service.

Analyzes cooking history and ratings to build taste profiles for each user.
Generates insights like "You love Mediterranean but rarely cook it."
"""

import logging
from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models import (
    User, Rating, Recipe, RecipeTag, Tag, CookingHistory,
    TasteProfile, TastePreference,
)
from app.services.ai_extractor import generate_taste_insights

logger = logging.getLogger("dukecook.services.taste_learner")


async def update_taste_profile(db: AsyncSession, user_id: int) -> dict:
    """Recompute taste profile for a user based on all their ratings and cooking history.

    This builds a multi-dimensional preference map:
    - Cuisine preferences (how much they like Italian vs Thai vs Mexican)
    - Protein preferences (chicken vs salmon vs beef vs vegetarian)
    - Effort tolerance (easy vs hard recipes)
    - Repeat affinity (how often they want to revisit favorites)
    """
    logger.info(f"Updating taste profile for user {user_id}")

    # Get user
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        logger.error(f"User {user_id} not found")
        return {}

    # Get all ratings for this user
    ratings_result = await db.execute(
        select(Rating, Recipe)
        .join(Recipe, Rating.recipe_id == Recipe.id)
        .where(Rating.user_id == user_id)
        .order_by(Rating.created_at.desc())
    )
    ratings = ratings_result.all()

    if not ratings:
        logger.info(f"No ratings for user {user_id} — skipping profile update")
        return {}

    logger.info(f"Processing {len(ratings)} ratings for user {user.name}")

    # Build preference scores by dimension
    dimension_scores = {
        "cuisine": {},
        "protein": {},
        "effort": {},
        "dietary": {},
    }

    # Tag type → dimension mapping
    tag_type_to_dimension = {
        "cuisine": "cuisine",
        "protein": "protein",
        "effort": "effort",
        "dietary": "dietary",
    }

    for rating, recipe in ratings:
        # Normalize star rating to 0-1 scale
        score = (rating.stars - 1) / 4.0  # 1★=0.0, 5★=1.0

        # Boost/penalty for "would make again"
        if not rating.would_make_again:
            score *= 0.5

        # Get tags for this recipe
        tag_result = await db.execute(
            select(Tag)
            .join(RecipeTag, RecipeTag.tag_id == Tag.id)
            .where(RecipeTag.recipe_id == recipe.id)
        )
        tags = tag_result.scalars().all()

        for tag in tags:
            dimension = tag_type_to_dimension.get(tag.type)
            if dimension:
                if tag.name not in dimension_scores[dimension]:
                    dimension_scores[dimension][tag.name] = {"total": 0, "count": 0}
                dimension_scores[dimension][tag.name]["total"] += score
                dimension_scores[dimension][tag.name]["count"] += 1

        # Also track cuisine from recipe.cuisine field
        if recipe.cuisine:
            cuisine = recipe.cuisine.lower()
            if cuisine not in dimension_scores["cuisine"]:
                dimension_scores["cuisine"][cuisine] = {"total": 0, "count": 0}
            dimension_scores["cuisine"][cuisine]["total"] += score
            dimension_scores["cuisine"][cuisine]["count"] += 1

        # Track effort from difficulty
        if recipe.difficulty:
            diff = recipe.difficulty.lower()
            if diff not in dimension_scores["effort"]:
                dimension_scores["effort"][diff] = {"total": 0, "count": 0}
            dimension_scores["effort"][diff]["total"] += score
            dimension_scores["effort"][diff]["count"] += 1

    # Compute average scores per dimension
    preferences = {}
    for dimension, values in dimension_scores.items():
        if values:
            preferences[dimension] = {}
            for value, data in values.items():
                avg = data["total"] / data["count"] if data["count"] > 0 else 0
                preferences[dimension][value] = round(avg, 3)
                # Also save to TastePreference table
                await _upsert_preference(db, user_id, dimension, value, avg, data["count"])

    # Save profile
    profile_result = await db.execute(
        select(TasteProfile).where(TasteProfile.user_id == user_id)
    )
    profile = profile_result.scalar_one_or_none()

    if profile:
        profile.preferences = preferences
    else:
        profile = TasteProfile(user_id=user_id, preferences=preferences)
        db.add(profile)

    await db.flush()

    logger.info(
        f"Taste profile updated for {user.name}",
        extra={
            "extra_data": {
                "user_id": user_id,
                "user_name": user.name,
                "dimensions": {k: len(v) for k, v in preferences.items()},
                "total_ratings": len(ratings),
            }
        },
    )

    return preferences


async def _upsert_preference(
    db: AsyncSession, user_id: int, dimension: str, value: str, score: float, count: int
):
    """Insert or update a single taste preference."""
    result = await db.execute(
        select(TastePreference).where(
            and_(
                TastePreference.user_id == user_id,
                TastePreference.dimension == dimension,
                TastePreference.value == value,
            )
        )
    )
    pref = result.scalar_one_or_none()

    if pref:
        pref.score = score
        pref.sample_count = count
    else:
        pref = TastePreference(
            user_id=user_id,
            dimension=dimension,
            value=value,
            score=score,
            sample_count=count,
        )
        db.add(pref)


async def get_taste_profile(db: AsyncSession, user_id: int) -> dict:
    """Get a user's taste profile."""
    result = await db.execute(
        select(TasteProfile).where(TasteProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        logger.info(f"No taste profile for user {user_id} — building now")
        preferences = await update_taste_profile(db, user_id)
        return {
            "user_id": user_id,
            "preferences": preferences,
            "insights": [],
        }

    return {
        "user_id": user_id,
        "preferences": profile.preferences or {},
        "insights": profile.insights or [],
    }


async def generate_insights(db: AsyncSession, user_id: int) -> list[dict]:
    """Generate AI-powered taste insights for a user."""
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        return []

    profile = await get_taste_profile(db, user_id)

    # Get recent ratings for context
    ratings_result = await db.execute(
        select(Rating, Recipe)
        .join(Recipe, Rating.recipe_id == Recipe.id)
        .where(Rating.user_id == user_id)
        .order_by(Rating.created_at.desc())
        .limit(20)
    )
    ratings_data = [
        {
            "recipe": r.title,
            "stars": rating.stars,
            "would_make_again": rating.would_make_again,
            "cooked_at": str(rating.cooked_at) if rating.cooked_at else None,
        }
        for rating, r in ratings_result.all()
    ]

    # Get cooking history
    history_result = await db.execute(
        select(CookingHistory, Recipe)
        .join(Recipe, CookingHistory.recipe_id == Recipe.id)
        .where(CookingHistory.cooked_at >= date.today() - timedelta(days=30))
        .order_by(CookingHistory.cooked_at.desc())
    )
    history_data = [
        {"recipe": r.title, "date": str(h.cooked_at)}
        for h, r in history_result.all()
    ]

    insights = await generate_taste_insights(
        user_name=user.name,
        ratings=ratings_data,
        cooking_history=history_data,
        preferences=profile.get("preferences", {}),
    )

    # Save insights to profile
    profile_result = await db.execute(
        select(TasteProfile).where(TasteProfile.user_id == user_id)
    )
    tp = profile_result.scalar_one_or_none()
    if tp:
        tp.insights = insights
        await db.flush()

    logger.info(
        f"Generated {len(insights)} insights for {user.name}",
        extra={"extra_data": {"user_id": user_id, "insight_count": len(insights)}}
    )

    return insights


async def record_cooking(
    db: AsyncSession, recipe_id: int, cooked_at: date, user_ids: list[int]
) -> CookingHistory:
    """Record that a recipe was cooked. Updates taste profiles."""
    logger.info(
        f"Recording cooking: recipe {recipe_id} on {cooked_at}",
        extra={"extra_data": {"recipe_id": recipe_id, "cooked_at": str(cooked_at), "users": user_ids}}
    )

    entry = CookingHistory(
        recipe_id=recipe_id,
        cooked_at=cooked_at,
        cooked_by=user_ids,
    )
    db.add(entry)
    await db.flush()

    # Update taste profiles for all involved users
    for uid in user_ids:
        await update_taste_profile(db, uid)

    return entry
