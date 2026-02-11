"""Tinder-style recipe swipe routes.

Flow:
1. Create a swipe session → system picks recipe pool
2. Each user swipes (like/dislike/skip) on recipes
3. When both have swiped, matches are revealed
4. Matches can be planned to specific dates
"""

import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.database import get_db
from app.models import SwipeSession, SwipeCard, SwipeMatch, Recipe, User, RecipeTag, Tag, Rating
from app.schemas import (
    SwipeSessionCreate, SwipeSessionOut, SwipeCardOut,
    SwipeAction, SwipeMatchOut, RecipeSummary, TagOut,
)

logger = logging.getLogger("butlergroceries.routers.swipe")
router = APIRouter(prefix="/api/swipe", tags=["swipe"])


@router.post("/sessions", response_model=SwipeSessionOut, status_code=201)
async def create_session(data: SwipeSessionCreate, db: AsyncSession = Depends(get_db)):
    """Start a new swipe session.

    Picks a pool of recipes based on context, creates cards for both users.
    """
    logger.info(f"Creating swipe session: context={data.context}, target_date={data.target_date}")

    # Build recipe pool
    query = select(Recipe)

    # Context-based filtering
    if data.context in ("weeknight", "quick"):
        query = query.where(
            (Recipe.total_time_min <= 45) | (Recipe.total_time_min.is_(None))
        )
    elif data.context == "date_night":
        # Prefer medium/hard difficulty
        query = query.where(Recipe.difficulty.in_(["medium", "hard"]))

    # Randomize and limit
    query = query.order_by(func.random()).limit(data.pool_size)
    result = await db.execute(query)
    recipes = result.scalars().all()

    if not recipes:
        raise HTTPException(status_code=400, detail="No recipes available for swiping")

    recipe_ids = [r.id for r in recipes]

    # Create session
    session = SwipeSession(
        context=data.context,
        target_date=data.target_date,
        recipe_pool=recipe_ids,
    )
    db.add(session)
    await db.flush()

    # Create cards for the couple only (the Butler family)
    COUPLE_IDS = [1, 2]
    users_result = await db.execute(select(User).where(User.id.in_(COUPLE_IDS)))
    users = users_result.scalars().all()

    for user in users:
        for recipe_id in recipe_ids:
            card = SwipeCard(
                session_id=session.id,
                recipe_id=recipe_id,
                user_id=user.id,
            )
            db.add(card)

    await db.flush()

    logger.info(
        f"Swipe session created: id={session.id}, pool_size={len(recipe_ids)}, users={len(users)}",
        extra={
            "extra_data": {
                "session_id": session.id,
                "context": data.context,
                "pool_size": len(recipe_ids),
                "recipe_ids": recipe_ids,
            }
        },
    )

    return SwipeSessionOut(
        id=session.id,
        context=session.context,
        status=session.status,
        target_date=session.target_date,
        total_cards=len(recipe_ids),
        your_progress=0,
        partner_progress=0,
        match_count=0,
        created_at=session.created_at,
    )


@router.get("/sessions/{session_id}", response_model=SwipeSessionOut)
async def get_session(session_id: int, user_id: int = Query(...), db: AsyncSession = Depends(get_db)):
    """Get session status including progress for both users."""
    logger.info(f"Getting swipe session {session_id} for user {user_id}")

    result = await db.execute(select(SwipeSession).where(SwipeSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    total = len(session.recipe_pool)

    # Your progress
    your_result = await db.execute(
        select(func.count(SwipeCard.id)).where(
            and_(
                SwipeCard.session_id == session_id,
                SwipeCard.user_id == user_id,
                SwipeCard.decision.isnot(None),
            )
        )
    )
    your_progress = your_result.scalar() or 0

    # Jill's progress
    partner_result = await db.execute(
        select(func.count(SwipeCard.id)).where(
            and_(
                SwipeCard.session_id == session_id,
                SwipeCard.user_id != user_id,
                SwipeCard.decision.isnot(None),
            )
        )
    )
    partner_progress = partner_result.scalar() or 0

    # Match count
    match_result = await db.execute(
        select(func.count(SwipeMatch.id)).where(SwipeMatch.session_id == session_id)
    )
    match_count = match_result.scalar() or 0

    return SwipeSessionOut(
        id=session.id,
        context=session.context,
        status=session.status,
        target_date=session.target_date,
        total_cards=total,
        your_progress=your_progress,
        partner_progress=partner_progress,
        match_count=match_count,
        created_at=session.created_at,
    )


@router.get("/sessions/{session_id}/next", response_model=SwipeCardOut)
async def get_next_card(session_id: int, user_id: int = Query(...), db: AsyncSession = Depends(get_db)):
    """Get the next unswiped recipe card for this user."""
    logger.info(f"Getting next swipe card: session={session_id}, user={user_id}")

    # Find the next unswiped card
    result = await db.execute(
        select(SwipeCard)
        .where(
            and_(
                SwipeCard.session_id == session_id,
                SwipeCard.user_id == user_id,
                SwipeCard.decision.is_(None),
            )
        )
        .order_by(SwipeCard.id)
        .limit(1)
    )
    card = result.scalar_one_or_none()

    if not card:
        raise HTTPException(status_code=404, detail="No more cards to swipe")

    # Get recipe summary
    recipe_result = await db.execute(select(Recipe).where(Recipe.id == card.recipe_id))
    recipe = recipe_result.scalar_one_or_none()

    # Get tags
    tag_result = await db.execute(
        select(Tag).join(RecipeTag, RecipeTag.tag_id == Tag.id).where(RecipeTag.recipe_id == recipe.id)
    )
    tags = [TagOut.model_validate(t) for t in tag_result.scalars().all()]

    # Get rating info
    rating_result = await db.execute(
        select(func.avg(Rating.stars), func.count(Rating.id)).where(Rating.recipe_id == recipe.id)
    )
    avg_rating, rating_count = rating_result.one()

    # Count swiped + remaining
    total_result = await db.execute(
        select(func.count(SwipeCard.id)).where(
            and_(SwipeCard.session_id == session_id, SwipeCard.user_id == user_id)
        )
    )
    total = total_result.scalar()

    swiped_result = await db.execute(
        select(func.count(SwipeCard.id)).where(
            and_(
                SwipeCard.session_id == session_id,
                SwipeCard.user_id == user_id,
                SwipeCard.decision.isnot(None),
            )
        )
    )
    swiped = swiped_result.scalar()

    summary = RecipeSummary(
        id=recipe.id,
        title=recipe.title,
        description=recipe.description,
        image_url=recipe.image_url,
        image_path=recipe.image_path or "",
        prep_time_min=recipe.prep_time_min,
        cook_time_min=recipe.cook_time_min,
        total_time_min=recipe.total_time_min,
        cuisine=recipe.cuisine,
        difficulty=recipe.difficulty,
        avg_rating=float(avg_rating) if avg_rating else None,
        rating_count=rating_count or 0,
        tags=tags,
    )

    return SwipeCardOut(
        recipe=summary,
        card_index=swiped + 1,
        total_cards=total,
    )


@router.post("/sessions/{session_id}/swipe")
async def swipe(session_id: int, action: SwipeAction, db: AsyncSession = Depends(get_db)):
    """Submit a swipe decision."""
    logger.info(
        f"Swipe: session={session_id}, user={action.user_id}, "
        f"recipe={action.recipe_id}, decision={action.decision}",
    )

    # Find the card
    result = await db.execute(
        select(SwipeCard).where(
            and_(
                SwipeCard.session_id == session_id,
                SwipeCard.recipe_id == action.recipe_id,
                SwipeCard.user_id == action.user_id,
            )
        )
    )
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    if card.decision is not None:
        raise HTTPException(status_code=400, detail="Already swiped on this card")

    card.decision = action.decision
    card.swiped_at = datetime.utcnow()
    await db.flush()

    # Check for match (both users liked)
    match_found = False
    if action.decision in ("like", "superlike"):
        # Check if the other user also liked this recipe
        other_result = await db.execute(
            select(SwipeCard).where(
                and_(
                    SwipeCard.session_id == session_id,
                    SwipeCard.recipe_id == action.recipe_id,
                    SwipeCard.user_id != action.user_id,
                    SwipeCard.decision.in_(["like", "superlike"]),
                )
            )
        )
        other_card = other_result.scalar_one_or_none()

        if other_card:
            # It's a match!
            match = SwipeMatch(
                session_id=session_id,
                recipe_id=action.recipe_id,
            )
            db.add(match)
            await db.flush()
            match_found = True

            logger.info(
                f"🎉 MATCH: recipe {action.recipe_id} in session {session_id}",
                extra={
                    "extra_data": {
                        "session_id": session_id,
                        "recipe_id": action.recipe_id,
                        "match_id": match.id,
                    }
                },
            )

    # Check if session is complete (all users done swiping)
    unswiped_result = await db.execute(
        select(func.count(SwipeCard.id)).where(
            and_(
                SwipeCard.session_id == session_id,
                SwipeCard.decision.is_(None),
            )
        )
    )
    remaining = unswiped_result.scalar()
    if remaining == 0:
        session_result = await db.execute(
            select(SwipeSession).where(SwipeSession.id == session_id)
        )
        session = session_result.scalar_one()
        session.status = "completed"
        await db.flush()
        logger.info(f"Swipe session {session_id} completed")

    return {
        "status": "ok",
        "decision": action.decision,
        "match": match_found,
        "recipe_id": action.recipe_id,
    }


@router.get("/sessions/{session_id}/matches", response_model=list[SwipeMatchOut])
async def get_matches(session_id: int, db: AsyncSession = Depends(get_db)):
    """Get all matches for a swipe session."""
    logger.info(f"Getting matches for session {session_id}")

    result = await db.execute(
        select(SwipeMatch)
        .where(SwipeMatch.session_id == session_id)
        .order_by(SwipeMatch.matched_at)
    )
    matches = result.scalars().all()

    match_list = []
    for m in matches:
        recipe_result = await db.execute(select(Recipe).where(Recipe.id == m.recipe_id))
        recipe = recipe_result.scalar_one_or_none()

        # Get tags
        tag_result = await db.execute(
            select(Tag).join(RecipeTag, RecipeTag.tag_id == Tag.id).where(RecipeTag.recipe_id == recipe.id)
        )
        tags = [TagOut.model_validate(t) for t in tag_result.scalars().all()]

        # Check if either user super-liked
        superlike_result = await db.execute(
            select(SwipeCard).where(
                and_(
                    SwipeCard.session_id == session_id,
                    SwipeCard.recipe_id == m.recipe_id,
                    SwipeCard.decision == "superlike",
                )
            )
        )
        is_superlike = superlike_result.scalar_one_or_none() is not None

        match_list.append(SwipeMatchOut(
            recipe=RecipeSummary(
                id=recipe.id,
                title=recipe.title,
                description=recipe.description,
                image_url=recipe.image_url,
                image_path=recipe.image_path or "",
                cuisine=recipe.cuisine,
                difficulty=recipe.difficulty,
                tags=tags,
            ),
            matched_at=m.matched_at,
            planned_for_date=m.planned_for_date,
            is_superlike=is_superlike,
        ))

    logger.info(f"Found {len(match_list)} matches for session {session_id}")
    return match_list


@router.get("/sessions/active")
async def list_active_sessions(db: AsyncSession = Depends(get_db)):
    """List all active swipe sessions."""
    result = await db.execute(
        select(SwipeSession)
        .where(SwipeSession.status == "active")
        .order_by(SwipeSession.created_at.desc())
    )
    sessions = result.scalars().all()
    return [{"id": s.id, "context": s.context, "target_date": str(s.target_date) if s.target_date else None, "created_at": str(s.created_at)} for s in sessions]
