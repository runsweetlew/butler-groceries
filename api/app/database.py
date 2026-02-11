"""Database engine, session, and base model configuration."""

import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

logger = logging.getLogger("butlergroceries.database")

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """Dependency that yields a database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """Create all tables."""
    logger.info("Initializing database tables")
    async with engine.begin() as conn:
        from app.models import (
            User, Recipe, Ingredient, RecipeIngredient, RecipeStep,
            Tag, RecipeTag, Rating, MealPlan, DietaryRule,
            SwipeSession, SwipeCard, SwipeMatch,
            TasteProfile, TastePreference, CookingHistory,
            ShoppingList, ShoppingItem, PantryStaple,
            CalendarEvent, ImportLog, MeijerToken,
        )
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created successfully")
