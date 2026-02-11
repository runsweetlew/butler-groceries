"""Recipe CRUD routes."""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.database import get_db
from app.models import Recipe, RecipeIngredient, RecipeStep, Tag, RecipeTag, Rating, Ingredient
from app.schemas import RecipeCreate, RecipeUpdate, RecipeSummary, RecipeDetail, TagOut, IngredientOut, StepOut, RatingOut
from app.services.recipe_importer import get_or_create_tag, get_or_create_ingredient

logger = logging.getLogger("dukecook.routers.recipes")
router = APIRouter(prefix="/api/recipes", tags=["recipes"])


@router.get("", response_model=list[RecipeSummary])
async def list_recipes(
    search: Optional[str] = Query(None, description="Search by title"),
    cuisine: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    archived: bool = Query(False, description="Include archived recipes"),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    """List recipes with optional filters."""
    logger.info(
        "Listing recipes",
        extra={"extra_data": {"search": search, "cuisine": cuisine, "tag": tag, "limit": limit, "offset": offset}}
    )

    query = select(Recipe)

    if not archived:
        query = query.where(Recipe.archived == False)

    if search:
        query = query.where(Recipe.title.ilike(f"%{search}%"))
    if cuisine:
        query = query.where(Recipe.cuisine.ilike(f"%{cuisine}%"))
    if difficulty:
        query = query.where(Recipe.difficulty == difficulty)

    # Tag filter requires a join
    if tag:
        query = (
            query.join(RecipeTag, RecipeTag.recipe_id == Recipe.id)
            .join(Tag, RecipeTag.tag_id == Tag.id)
            .where(Tag.name.ilike(f"%{tag}%"))
        )

    query = query.order_by(Recipe.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    recipes = result.scalars().all()

    # Build summaries with tags and ratings
    summaries = []
    for r in recipes:
        summary = await _build_recipe_summary(db, r)
        summaries.append(summary)

    logger.info(f"Returning {len(summaries)} recipes")
    return summaries


@router.get("/{recipe_id}", response_model=RecipeDetail)
async def get_recipe(recipe_id: int, db: AsyncSession = Depends(get_db)):
    """Get full recipe details."""
    logger.info(f"Getting recipe {recipe_id}")

    result = await db.execute(select(Recipe).where(Recipe.id == recipe_id))
    recipe = result.scalar_one_or_none()
    if not recipe:
        logger.warning(f"Recipe {recipe_id} not found")
        raise HTTPException(status_code=404, detail="Recipe not found")

    detail = await _build_recipe_detail(db, recipe)
    logger.info(f"Returning recipe: {recipe.title} (id={recipe.id})")
    return detail


@router.post("", response_model=RecipeDetail, status_code=201)
async def create_recipe(data: RecipeCreate, db: AsyncSession = Depends(get_db)):
    """Create a recipe manually."""
    logger.info(f"Creating recipe: {data.title}")

    recipe = Recipe(
        title=data.title,
        description=data.description,
        source_url=data.source_url,
        image_url=data.image_url,
        prep_time_min=data.prep_time_min,
        cook_time_min=data.cook_time_min,
        total_time_min=data.total_time_min,
        servings=data.servings,
        cuisine=data.cuisine,
        difficulty=data.difficulty,
    )
    db.add(recipe)
    await db.flush()

    # Add ingredients
    for i, ing_data in enumerate(data.ingredients):
        ing_name = ing_data.get("name", ing_data.get("raw_text", ""))
        normalized = await get_or_create_ingredient(db, ing_name)
        ri = RecipeIngredient(
            recipe_id=recipe.id,
            ingredient_id=normalized.id,
            raw_text=ing_data.get("raw_text", ing_name),
            quantity=ing_data.get("quantity"),
            unit=ing_data.get("unit", ""),
            preparation=ing_data.get("preparation", ""),
            group_name=ing_data.get("group", ""),
            sort_order=i,
        )
        db.add(ri)

    # Add steps
    for i, step_data in enumerate(data.steps):
        rs = RecipeStep(
            recipe_id=recipe.id,
            step_number=i + 1,
            instruction=step_data.get("instruction", ""),
            duration_minutes=step_data.get("duration_minutes"),
            timer_label=step_data.get("timer_label", ""),
        )
        db.add(rs)

    # Add tags
    for tag_name in data.tags:
        tag = await get_or_create_tag(db, tag_name)
        rt = RecipeTag(recipe_id=recipe.id, tag_id=tag.id)
        db.add(rt)

    await db.flush()

    logger.info(f"Recipe created: {recipe.title} (id={recipe.id})", extra={
        "extra_data": {
            "recipe_id": recipe.id,
            "ingredient_count": len(data.ingredients),
            "step_count": len(data.steps),
            "tag_count": len(data.tags),
        }
    })

    return await _build_recipe_detail(db, recipe)


@router.put("/{recipe_id}", response_model=RecipeDetail)
async def update_recipe(recipe_id: int, data: RecipeUpdate, db: AsyncSession = Depends(get_db)):
    """Update a recipe."""
    logger.info(f"Updating recipe {recipe_id}")

    result = await db.execute(select(Recipe).where(Recipe.id == recipe_id))
    recipe = result.scalar_one_or_none()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    # Update simple fields
    for field in ["title", "description", "source_url", "image_url", "prep_time_min",
                  "cook_time_min", "total_time_min", "servings", "cuisine", "difficulty"]:
        value = getattr(data, field, None)
        if value is not None:
            setattr(recipe, field, value)

    # Update ingredients if provided
    if data.ingredients is not None:
        # Delete existing
        existing = await db.execute(
            select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe_id)
        )
        for ri in existing.scalars().all():
            await db.delete(ri)

        # Add new
        for i, ing_data in enumerate(data.ingredients):
            ing_name = ing_data.get("name", ing_data.get("raw_text", ""))
            normalized = await get_or_create_ingredient(db, ing_name)
            ri = RecipeIngredient(
                recipe_id=recipe.id,
                ingredient_id=normalized.id,
                raw_text=ing_data.get("raw_text", ing_name),
                quantity=ing_data.get("quantity"),
                unit=ing_data.get("unit", ""),
                preparation=ing_data.get("preparation", ""),
                group_name=ing_data.get("group", ""),
                sort_order=i,
            )
            db.add(ri)

    # Update steps if provided
    if data.steps is not None:
        existing = await db.execute(
            select(RecipeStep).where(RecipeStep.recipe_id == recipe_id)
        )
        for rs in existing.scalars().all():
            await db.delete(rs)

        for i, step_data in enumerate(data.steps):
            rs = RecipeStep(
                recipe_id=recipe.id,
                step_number=i + 1,
                instruction=step_data.get("instruction", ""),
                duration_minutes=step_data.get("duration_minutes"),
                timer_label=step_data.get("timer_label", ""),
            )
            db.add(rs)

    # Update tags if provided
    if data.tags is not None:
        existing = await db.execute(
            select(RecipeTag).where(RecipeTag.recipe_id == recipe_id)
        )
        for rt in existing.scalars().all():
            await db.delete(rt)

        for tag_name in data.tags:
            tag = await get_or_create_tag(db, tag_name)
            rt = RecipeTag(recipe_id=recipe.id, tag_id=tag.id)
            db.add(rt)

    await db.flush()
    logger.info(f"Recipe updated: {recipe.title} (id={recipe.id})")

    return await _build_recipe_detail(db, recipe)


@router.delete("/{recipe_id}", status_code=204)
async def delete_recipe(recipe_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a recipe."""
    logger.info(f"Deleting recipe {recipe_id}")
    result = await db.execute(select(Recipe).where(Recipe.id == recipe_id))
    recipe = result.scalar_one_or_none()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    await db.delete(recipe)
    await db.flush()
    logger.info(f"Recipe deleted: {recipe.title} (id={recipe_id})")


@router.post("/{recipe_id}/archive")
async def archive_recipe(recipe_id: int, db: AsyncSession = Depends(get_db)):
    """Archive a recipe (hide from main list)."""
    result = await db.execute(select(Recipe).where(Recipe.id == recipe_id))
    recipe = result.scalar_one_or_none()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    recipe.archived = True
    await db.flush()
    logger.info(f"Recipe archived: {recipe.title} (id={recipe_id})")
    return {"id": recipe_id, "archived": True}


@router.post("/{recipe_id}/unarchive")
async def unarchive_recipe(recipe_id: int, db: AsyncSession = Depends(get_db)):
    """Unarchive a recipe (restore to main list)."""
    result = await db.execute(select(Recipe).where(Recipe.id == recipe_id))
    recipe = result.scalar_one_or_none()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    recipe.archived = False
    await db.flush()
    logger.info(f"Recipe unarchived: {recipe.title} (id={recipe_id})")
    return {"id": recipe_id, "archived": False}


@router.get("/tags/all", response_model=list[TagOut])
async def list_all_tags(db: AsyncSession = Depends(get_db)):
    """List all available tags."""
    result = await db.execute(select(Tag).order_by(Tag.type, Tag.name))
    return result.scalars().all()


# ---------- Helpers ----------

async def _build_recipe_summary(db: AsyncSession, recipe: Recipe) -> dict:
    """Build a recipe summary with tags and average rating."""
    # Tags
    tag_result = await db.execute(
        select(Tag).join(RecipeTag, RecipeTag.tag_id == Tag.id).where(RecipeTag.recipe_id == recipe.id)
    )
    tags = [TagOut.model_validate(t) for t in tag_result.scalars().all()]

    # Average rating
    rating_result = await db.execute(
        select(func.avg(Rating.stars), func.count(Rating.id)).where(Rating.recipe_id == recipe.id)
    )
    avg_rating, rating_count = rating_result.one()

    return RecipeSummary(
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


async def _build_recipe_detail(db: AsyncSession, recipe: Recipe) -> dict:
    """Build full recipe detail."""
    summary = await _build_recipe_summary(db, recipe)

    # Ingredients
    ing_result = await db.execute(
        select(RecipeIngredient)
        .where(RecipeIngredient.recipe_id == recipe.id)
        .order_by(RecipeIngredient.sort_order)
    )
    ingredients = []
    for ri in ing_result.scalars().all():
        ing_name = None
        ing_category = None
        if ri.ingredient_id:
            i_result = await db.execute(select(Ingredient).where(Ingredient.id == ri.ingredient_id))
            i = i_result.scalar_one_or_none()
            if i:
                ing_name = i.name
                ing_category = i.category
        ingredients.append(IngredientOut(
            id=ri.id,
            raw_text=ri.raw_text,
            quantity=ri.quantity,
            unit=ri.unit,
            preparation=ri.preparation,
            group_name=ri.group_name,
            ingredient_name=ing_name,
            ingredient_category=ing_category,
        ))

    # Steps
    step_result = await db.execute(
        select(RecipeStep)
        .where(RecipeStep.recipe_id == recipe.id)
        .order_by(RecipeStep.step_number)
    )
    steps = [StepOut.model_validate(s) for s in step_result.scalars().all()]

    # Ratings
    rating_result = await db.execute(
        select(Rating)
        .where(Rating.recipe_id == recipe.id)
        .order_by(Rating.created_at.desc())
    )
    ratings = []
    for r in rating_result.scalars().all():
        from app.models import User
        user_result = await db.execute(select(User).where(User.id == r.user_id))
        user = user_result.scalar_one_or_none()
        ratings.append(RatingOut(
            id=r.id,
            user_id=r.user_id,
            user_name=user.name if user else None,
            stars=r.stars,
            would_make_again=r.would_make_again,
            notes=r.notes,
            cooked_at=r.cooked_at,
            created_at=r.created_at,
        ))

    return RecipeDetail(
        **summary.model_dump(),
        source_url=recipe.source_url,
        servings=recipe.servings,
        created_at=recipe.created_at,
        updated_at=recipe.updated_at,
        ingredients=ingredients,
        steps=steps,
        ratings=ratings,
    )
