"""User management routes."""

import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User
from app.schemas import UserOut

logger = logging.getLogger("dukecook.routers.users")
router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut])
async def list_users(db: AsyncSession = Depends(get_db)):
    """List all users."""
    logger.info("Listing all users")
    result = await db.execute(select(User).order_by(User.id))
    users = result.scalars().all()
    logger.info(f"Found {len(users)} users")
    return users


@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific user."""
    logger.info(f"Getting user {user_id}")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="User not found")
    return user
