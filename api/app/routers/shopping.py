"""Shopping list routes."""

import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import ShoppingList, ShoppingItem, PantryStaple
from app.schemas import ShoppingListOut, ShoppingItemUpdate, GenerateListRequest
from app.services.shopping_generator import generate_shopping_list

logger = logging.getLogger("dukecook.routers.shopping")
router = APIRouter(prefix="/api/shopping", tags=["shopping"])


@router.get("/current", response_model=ShoppingListOut)
async def get_current_list(db: AsyncSession = Depends(get_db)):
    """Get the most recent shopping list."""
    logger.info("Getting current shopping list")

    result = await db.execute(
        select(ShoppingList).order_by(ShoppingList.created_at.desc()).limit(1)
    )
    shopping_list = result.scalar_one_or_none()

    if not shopping_list:
        return ShoppingListOut(id=0, name="No list yet", items=[], total_items=0, checked_items=0)

    return await _build_list_response(db, shopping_list)


@router.post("/generate", response_model=ShoppingListOut, status_code=201)
async def generate_list(data: GenerateListRequest, db: AsyncSession = Depends(get_db)):
    """Generate a shopping list from the week's meal plan."""
    logger.info(f"Generating shopping list for week of {data.week_of}")

    shopping_list = await generate_shopping_list(db, data.week_of, data.name)
    return await _build_list_response(db, shopping_list)


@router.get("/{list_id}", response_model=ShoppingListOut)
async def get_list(list_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific shopping list."""
    result = await db.execute(select(ShoppingList).where(ShoppingList.id == list_id))
    shopping_list = result.scalar_one_or_none()
    if not shopping_list:
        raise HTTPException(status_code=404, detail="List not found")
    return await _build_list_response(db, shopping_list)


@router.put("/items/{item_id}")
async def update_item(item_id: int, data: ShoppingItemUpdate, db: AsyncSession = Depends(get_db)):
    """Check/uncheck a shopping item."""
    logger.info(f"Updating shopping item {item_id}", extra={
        "extra_data": {"item_id": item_id, "checked": data.checked, "checked_by": data.checked_by}
    })

    result = await db.execute(select(ShoppingItem).where(ShoppingItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if data.checked is not None:
        item.checked = data.checked
        item.checked_at = datetime.utcnow() if data.checked else None
    if data.checked_by is not None:
        item.checked_by = data.checked_by
    if data.quantity is not None:
        item.quantity = data.quantity

    await db.flush()
    logger.info(f"Shopping item updated: {item.name} (checked={item.checked})")
    return {"status": "ok", "item_id": item_id}


@router.delete("/{list_id}", status_code=204)
async def delete_list(list_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a shopping list."""
    result = await db.execute(select(ShoppingList).where(ShoppingList.id == list_id))
    shopping_list = result.scalar_one_or_none()
    if not shopping_list:
        raise HTTPException(status_code=404, detail="List not found")
    await db.delete(shopping_list)
    await db.flush()
    logger.info(f"Shopping list deleted: {list_id}")


# ---------- Pantry Staples ----------

@router.get("/pantry/staples")
async def list_pantry_staples(db: AsyncSession = Depends(get_db)):
    """List all pantry staples (items you always have)."""
    result = await db.execute(select(PantryStaple).order_by(PantryStaple.category, PantryStaple.name))
    staples = result.scalars().all()
    return [{"id": s.id, "name": s.name, "category": s.category} for s in staples]


@router.post("/pantry/staples", status_code=201)
async def add_pantry_staple(name: str = Query(...), category: str = Query("pantry"), db: AsyncSession = Depends(get_db)):
    """Add a pantry staple."""
    logger.info(f"Adding pantry staple: {name} ({category})")
    staple = PantryStaple(name=name, category=category)
    db.add(staple)
    await db.flush()
    return {"id": staple.id, "name": staple.name, "category": staple.category}


@router.delete("/pantry/staples/{staple_id}", status_code=204)
async def remove_pantry_staple(staple_id: int, db: AsyncSession = Depends(get_db)):
    """Remove a pantry staple."""
    result = await db.execute(select(PantryStaple).where(PantryStaple.id == staple_id))
    staple = result.scalar_one_or_none()
    if not staple:
        raise HTTPException(status_code=404, detail="Staple not found")
    await db.delete(staple)
    await db.flush()
    logger.info(f"Pantry staple removed: {staple.name}")


# ---------- Helpers ----------

async def _build_list_response(db: AsyncSession, shopping_list: ShoppingList) -> ShoppingListOut:
    """Build a shopping list response with items."""
    result = await db.execute(
        select(ShoppingItem)
        .where(ShoppingItem.list_id == shopping_list.id)
        .order_by(ShoppingItem.aisle, ShoppingItem.name)
    )
    items = result.scalars().all()

    item_list = [
        {
            "id": i.id,
            "name": i.name,
            "quantity": i.quantity,
            "unit": i.unit,
            "aisle": i.aisle,
            "checked": i.checked,
            "checked_by": i.checked_by,
        }
        for i in items
    ]

    return ShoppingListOut(
        id=shopping_list.id,
        name=shopping_list.name,
        week_of=shopping_list.week_of,
        items=item_list,
        total_items=len(items),
        checked_items=sum(1 for i in items if i.checked),
        created_at=shopping_list.created_at,
    )
