"""DukeCook API — Recipe & Meal Planning for Trevor & Emily."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.config import get_settings
from app.logging_config import setup_logging, RequestLoggingMiddleware
from app.database import init_db

settings = get_settings()

# Initialize logging first
setup_logging(settings.log_level)
logger = logging.getLogger("dukecook.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("🍳 DukeCook starting up...")

    # Create database tables
    await init_db()

    # Seed default data
    await seed_defaults()

    # Ensure image directory exists
    Path(settings.image_dir).mkdir(parents=True, exist_ok=True)

    logger.info("✅ DukeCook ready!")
    yield
    logger.info("👋 DukeCook shutting down...")


app = FastAPI(
    title="DukeCook",
    description="Recipe & Meal Planning for Trevor & Emily",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
origins = [o.strip() for o in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging
app.add_middleware(RequestLoggingMiddleware)

# Static files for recipe images
image_dir = Path(settings.image_dir)
image_dir.mkdir(parents=True, exist_ok=True)
app.mount("/images", StaticFiles(directory=str(image_dir)), name="images")

# Register routers
from app.routers import recipes, import_recipe, planner, rules, swipe, ratings, cookalong, shopping, users, taste, homeassistant, kroger

app.include_router(users.router)
app.include_router(recipes.router)
app.include_router(import_recipe.router)
app.include_router(planner.router)
app.include_router(rules.router)
app.include_router(swipe.router)
app.include_router(ratings.router)
app.include_router(cookalong.router)
app.include_router(shopping.router)
app.include_router(taste.router)
app.include_router(homeassistant.router)
app.include_router(kroger.router)


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "app": "DukeCook", "version": "1.0.0"}


async def seed_defaults():
    """Create default users and sample rules if they don't exist."""
    from app.database import AsyncSessionLocal
    from app.models import User, DietaryRule, PantryStaple
    from sqlalchemy import select

    logger.info("Checking default data...")

    async with AsyncSessionLocal() as db:
        # Create default users
        result = await db.execute(select(User))
        existing = result.scalars().all()

        if not existing:
            logger.info("Seeding default users: Trevor, Emily & Carolina")
            db.add(User(name="Trevor", avatar_emoji="👨‍🍳"))
            db.add(User(name="Emily", avatar_emoji="👩‍🍳"))
            db.add(User(name="Carolina", avatar_emoji="🌸"))
            await db.commit()

        # Create sample dietary rules if none exist
        result = await db.execute(select(DietaryRule))
        if not result.scalars().first():
            logger.info("Seeding sample dietary rules")
            sample_rules = [
                DietaryRule(
                    name="Chicken max 2x per week",
                    rule_type="protein_max_per_week",
                    config={"protein": "chicken", "max": 2, "period_days": 7},
                ),
                DietaryRule(
                    name="Salmon at least 1x every 2 weeks",
                    rule_type="protein_min_per_period",
                    config={"protein": "salmon", "min": 1, "period_days": 14},
                ),
                DietaryRule(
                    name="Red meat max 2x per week",
                    rule_type="protein_max_per_week",
                    config={"protein": "beef", "max": 2, "period_days": 7},
                ),
                DietaryRule(
                    name="No repeat recipes within 14 days",
                    rule_type="no_repeat_within_days",
                    config={"min_days_between_repeat": 14},
                ),
                DietaryRule(
                    name="At least 2 vegetarian dinners per week",
                    rule_type="min_tag_per_week",
                    config={"tag": "vegetarian", "min": 2, "period_days": 7},
                ),
            ]
            for rule in sample_rules:
                db.add(rule)
            await db.commit()

        # Seed pantry staples if none exist
        result = await db.execute(select(PantryStaple))
        if not result.scalars().first():
            logger.info("Seeding common pantry staples")
            staples = [
                ("salt", "spice"), ("black pepper", "spice"), ("olive oil", "pantry"),
                ("vegetable oil", "pantry"), ("butter", "dairy"), ("garlic", "produce"),
                ("onion", "produce"), ("sugar", "pantry"), ("flour", "pantry"),
                ("rice", "pantry"), ("pasta", "pantry"), ("soy sauce", "pantry"),
                ("vinegar", "pantry"), ("eggs", "dairy"), ("milk", "dairy"),
            ]
            for name, category in staples:
                db.add(PantryStaple(name=name, category=category))
            await db.commit()

    logger.info("Default data check complete")
