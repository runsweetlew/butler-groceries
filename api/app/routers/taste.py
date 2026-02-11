"""Taste profile and AI learning routes."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User
from app.schemas import TasteProfileOut
from app.services.taste_learner import get_taste_profile, generate_insights, update_taste_profile

logger = logging.getLogger("butlergroceries.routers.taste")
router = APIRouter(prefix="/api/taste", tags=["taste"])


@router.get("/profile/{user_id}", response_model=TasteProfileOut)
async def get_profile(user_id: int, db: AsyncSession = Depends(get_db)):
    """Get a user's taste profile."""
    logger.info(f"Getting taste profile for user {user_id}")

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    profile = await get_taste_profile(db, user_id)

    return TasteProfileOut(
        user_id=user_id,
        user_name=user.name,
        preferences=profile.get("preferences", {}),
        insights=[i.get("message", "") if isinstance(i, dict) else str(i) for i in profile.get("insights", [])],
    )


@router.post("/profile/{user_id}/refresh")
async def refresh_profile(user_id: int, db: AsyncSession = Depends(get_db)):
    """Recompute taste profile from all ratings."""
    logger.info(f"Refreshing taste profile for user {user_id}")

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    preferences = await update_taste_profile(db, user_id)
    return {"status": "ok", "user_id": user_id, "preferences": preferences}


@router.get("/profile/{user_id}/insights")
async def get_insights(user_id: int, db: AsyncSession = Depends(get_db)):
    """Generate AI-powered taste insights."""
    logger.info(f"Generating taste insights for user {user_id}")

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    insights = await generate_insights(db, user_id)
    return {"user_id": user_id, "user_name": user.name, "insights": insights}


@router.get("/compare")
async def compare_profiles(db: AsyncSession = Depends(get_db)):
    """Compare taste profiles between both users.

    Shows where the Butler family agree and disagree.
    """
    logger.info("Comparing taste profiles")

    # Compare only the couple (the Butler family)
    COUPLE_IDS = [1, 2]
    users_result = await db.execute(select(User).where(User.id.in_(COUPLE_IDS)).order_by(User.id))
    users = users_result.scalars().all()

    if len(users) < 2:
        return {"message": "Need at least 2 users to compare"}

    profiles = {}
    for user in users:
        profile = await get_taste_profile(db, user.id)
        profiles[user.name] = profile.get("preferences", {})

    # Find agreements and disagreements
    user_names = list(profiles.keys())
    if len(user_names) < 2:
        return {"profiles": profiles, "agreements": [], "disagreements": []}

    p1 = profiles[user_names[0]]
    p2 = profiles[user_names[1]]

    agreements = []
    disagreements = []

    for dimension in set(list(p1.keys()) + list(p2.keys())):
        d1 = p1.get(dimension, {})
        d2 = p2.get(dimension, {})

        all_values = set(list(d1.keys()) + list(d2.keys()))
        for value in all_values:
            s1 = d1.get(value, 0)
            s2 = d2.get(value, 0)
            diff = abs(s1 - s2)

            item = {
                "dimension": dimension,
                "value": value,
                user_names[0]: round(s1, 2),
                user_names[1]: round(s2, 2),
                "diff": round(diff, 2),
            }

            if diff < 0.2:
                agreements.append(item)
            elif diff > 0.4:
                disagreements.append(item)

    # Sort by most agreement/disagreement
    agreements.sort(key=lambda x: x["diff"])
    disagreements.sort(key=lambda x: -x["diff"])

    logger.info(f"Taste comparison: {len(agreements)} agreements, {len(disagreements)} disagreements")

    return {
        "profiles": profiles,
        "agreements": agreements[:10],
        "disagreements": disagreements[:10],
    }
