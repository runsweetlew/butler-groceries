"""SQLAlchemy models for DukeCook."""

from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime, Date,
    ForeignKey, JSON, Enum, UniqueConstraint, Index,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


# ---------- Enums ----------

class MealType(str, enum.Enum):
    breakfast = "breakfast"
    lunch = "lunch"
    dinner = "dinner"
    snack = "snack"


class PlanStatus(str, enum.Enum):
    planned = "planned"
    cooked = "cooked"
    skipped = "skipped"


class SwipeDecision(str, enum.Enum):
    like = "like"
    dislike = "dislike"
    skip = "skip"
    superlike = "superlike"


class SessionStatus(str, enum.Enum):
    active = "active"
    completed = "completed"


class Difficulty(str, enum.Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class ImportStatus(str, enum.Enum):
    pending = "pending"
    success = "success"
    failed = "failed"


# ---------- Users ----------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    avatar_emoji = Column(String(10), default="👤")
    created_at = Column(DateTime, server_default=func.now())

    ratings = relationship("Rating", back_populates="user")
    swipe_cards = relationship("SwipeCard", back_populates="user")
    taste_profile = relationship("TasteProfile", back_populates="user", uselist=False)


# ---------- Recipes ----------

class Recipe(Base):
    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, default="")
    source_url = Column(Text, default="")
    image_url = Column(Text, default="")
    image_path = Column(String(500), default="")
    prep_time_min = Column(Integer, nullable=True)
    cook_time_min = Column(Integer, nullable=True)
    total_time_min = Column(Integer, nullable=True)
    servings = Column(Integer, default=4)
    cuisine = Column(String(100), default="")
    difficulty = Column(String(20), default="medium")
    notes = Column(Text, default="")  # Tips, variations, author notes
    original_text = Column(Text, default="")  # Full original recipe text for reference
    archived = Column(Boolean, default=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    ingredients = relationship("RecipeIngredient", back_populates="recipe", cascade="all, delete-orphan", order_by="RecipeIngredient.sort_order")
    steps = relationship("RecipeStep", back_populates="recipe", cascade="all, delete-orphan", order_by="RecipeStep.step_number")
    tags = relationship("RecipeTag", back_populates="recipe", cascade="all, delete-orphan")
    ratings = relationship("Rating", back_populates="recipe", cascade="all, delete-orphan")
    meal_plans = relationship("MealPlan", back_populates="recipe")

    __table_args__ = (
        Index("ix_recipes_title", "title"),
        Index("ix_recipes_cuisine", "cuisine"),
    )


class Ingredient(Base):
    __tablename__ = "ingredients"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), unique=True, nullable=False)
    category = Column(String(50), default="other")  # produce, dairy, meat, pantry, spice, frozen, bakery, other

    recipe_ingredients = relationship("RecipeIngredient", back_populates="ingredient")


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    id = Column(Integer, primary_key=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    ingredient_id = Column(Integer, ForeignKey("ingredients.id"), nullable=True)
    raw_text = Column(String(500), nullable=False)  # Original text: "2 cups diced chicken breast"
    quantity = Column(Float, nullable=True)
    unit = Column(String(50), default="")
    preparation = Column(String(200), default="")  # "diced", "minced", etc.
    group_name = Column(String(200), default="")  # "For the sauce", "For the marinade"
    sort_order = Column(Integer, default=0)

    recipe = relationship("Recipe", back_populates="ingredients")
    ingredient = relationship("Ingredient", back_populates="recipe_ingredients")


class RecipeStep(Base):
    __tablename__ = "recipe_steps"

    id = Column(Integer, primary_key=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    step_number = Column(Integer, nullable=False)
    instruction = Column(Text, nullable=False)
    duration_minutes = Column(Integer, nullable=True)  # For timer support
    timer_label = Column(String(100), default="")  # "Sear", "Simmer", "Rest"

    recipe = relationship("Recipe", back_populates="steps")


# ---------- Tags ----------

class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    type = Column(String(50), default="custom")  # cuisine, meal_type, protein, effort, season, dietary, custom
    color = Column(String(7), default="#6B7280")  # Hex color for UI

    recipe_tags = relationship("RecipeTag", back_populates="tag")

    __table_args__ = (
        UniqueConstraint("name", "type", name="uq_tag_name_type"),
    )


class RecipeTag(Base):
    __tablename__ = "recipe_tags"

    id = Column(Integer, primary_key=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    tag_id = Column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False)

    recipe = relationship("Recipe", back_populates="tags")
    tag = relationship("Tag", back_populates="recipe_tags")

    __table_args__ = (
        UniqueConstraint("recipe_id", "tag_id", name="uq_recipe_tag"),
    )


# ---------- Ratings ----------

class Rating(Base):
    __tablename__ = "ratings"

    id = Column(Integer, primary_key=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    stars = Column(Integer, nullable=False)  # 1-5
    would_make_again = Column(Boolean, default=True)
    notes = Column(Text, default="")
    cooked_at = Column(Date, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    recipe = relationship("Recipe", back_populates="ratings")
    user = relationship("User", back_populates="ratings")

    __table_args__ = (
        Index("ix_ratings_recipe_user", "recipe_id", "user_id"),
    )


# ---------- Meal Planning ----------

class MealPlan(Base):
    __tablename__ = "meal_plan"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    meal_type = Column(String(20), default="dinner")
    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), default="planned")  # planned, cooked, skipped
    notes = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())

    recipe = relationship("Recipe", back_populates="meal_plans")

    __table_args__ = (
        Index("ix_meal_plan_date", "date"),
    )


# ---------- Dietary Rules ----------

class DietaryRule(Base):
    __tablename__ = "dietary_rules"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    rule_type = Column(String(50), nullable=False)
    # protein_max_per_week, protein_min_per_period, no_repeat_within_days, min_tag_per_week, custom
    config = Column(JSON, nullable=False)
    # Examples:
    #   {"protein": "chicken", "max": 2, "period_days": 7}
    #   {"protein": "salmon", "min": 1, "period_days": 14}
    #   {"min_days_between_repeat": 14}
    #   {"tag": "vegetarian", "min": 2, "period_days": 7}
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


# ---------- Swipe (Tinder) ----------

class SwipeSession(Base):
    __tablename__ = "swipe_sessions"

    id = Column(Integer, primary_key=True)
    context = Column(String(100), default="dinner")  # weeknight, weekend, date_night, quick
    status = Column(String(20), default="active")
    target_date = Column(Date, nullable=True)  # Which date we're picking for
    recipe_pool = Column(JSON, default=list)  # List of recipe IDs in the pool
    created_at = Column(DateTime, server_default=func.now())

    cards = relationship("SwipeCard", back_populates="session", cascade="all, delete-orphan")
    matches = relationship("SwipeMatch", back_populates="session", cascade="all, delete-orphan")


class SwipeCard(Base):
    __tablename__ = "swipe_cards"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("swipe_sessions.id", ondelete="CASCADE"), nullable=False)
    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    decision = Column(String(20), nullable=True)  # like, dislike, skip, superlike — null = not yet swiped
    swiped_at = Column(DateTime, nullable=True)

    session = relationship("SwipeSession", back_populates="cards")
    user = relationship("User", back_populates="swipe_cards")
    recipe = relationship("Recipe")

    __table_args__ = (
        UniqueConstraint("session_id", "recipe_id", "user_id", name="uq_swipe_card"),
    )


class SwipeMatch(Base):
    __tablename__ = "swipe_matches"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("swipe_sessions.id", ondelete="CASCADE"), nullable=False)
    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    matched_at = Column(DateTime, server_default=func.now())
    planned_for_date = Column(Date, nullable=True)

    session = relationship("SwipeSession", back_populates="matches")
    recipe = relationship("Recipe")


# ---------- Taste Learning ----------

class TasteProfile(Base):
    __tablename__ = "taste_profiles"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    preferences = Column(JSON, default=dict)
    # {
    #   "cuisines": {"italian": 0.9, "thai": 0.8, "mexican": 0.5},
    #   "proteins": {"chicken": 0.7, "salmon": 0.9, "beef": 0.6},
    #   "effort": {"easy": 0.8, "medium": 0.6, "hard": 0.3},
    #   "flavors": {"spicy": 0.4, "creamy": 0.8, "fresh": 0.7},
    # }
    insights = Column(JSON, default=list)  # AI-generated insights
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="taste_profile")


class TastePreference(Base):
    """Individual preference data points from ratings and cooking history."""
    __tablename__ = "taste_preferences"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    dimension = Column(String(50), nullable=False)  # cuisine, protein, effort, flavor
    value = Column(String(100), nullable=False)  # "italian", "chicken", "easy", "spicy"
    score = Column(Float, nullable=False)  # 0.0 to 1.0
    sample_count = Column(Integer, default=1)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "dimension", "value", name="uq_taste_pref"),
        Index("ix_taste_pref_user", "user_id"),
    )


class CookingHistory(Base):
    """Track every time a recipe is cooked — feeds taste learning."""
    __tablename__ = "cooking_history"

    id = Column(Integer, primary_key=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="SET NULL"), nullable=True)
    cooked_at = Column(Date, nullable=False)
    cooked_by = Column(JSON, default=list)  # [user_id, ...]
    notes = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())

    recipe = relationship("Recipe")

    __table_args__ = (
        Index("ix_cooking_history_date", "cooked_at"),
        Index("ix_cooking_history_recipe", "recipe_id"),
    )


# ---------- Shopping ----------

class ShoppingList(Base):
    __tablename__ = "shopping_lists"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), default="")
    week_of = Column(Date, nullable=True)
    meal_plan_ids = Column(JSON, default=list)
    created_at = Column(DateTime, server_default=func.now())

    items = relationship("ShoppingItem", back_populates="shopping_list", cascade="all, delete-orphan")


class ShoppingItem(Base):
    __tablename__ = "shopping_items"

    id = Column(Integer, primary_key=True)
    list_id = Column(Integer, ForeignKey("shopping_lists.id", ondelete="CASCADE"), nullable=False)
    ingredient_id = Column(Integer, ForeignKey("ingredients.id"), nullable=True)
    name = Column(String(300), nullable=False)
    quantity = Column(Float, nullable=True)
    unit = Column(String(50), default="")
    aisle = Column(String(100), default="Other")
    checked = Column(Boolean, default=False)
    checked_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    checked_at = Column(DateTime, nullable=True)

    shopping_list = relationship("ShoppingList", back_populates="items")


class PantryStaple(Base):
    __tablename__ = "pantry_staples"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False, unique=True)
    category = Column(String(50), default="pantry")


# ---------- Calendar ----------

class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    start_time = Column(String(10), nullable=True)  # "17:00"
    end_time = Column(String(10), nullable=True)  # "21:00"
    summary = Column(String(500), default="")
    is_dinner_conflict = Column(Boolean, default=False)
    source = Column(String(50), default="manual")  # manual, google_calendar
    synced_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_calendar_date", "date"),
    )


# ---------- Kroger Integration ----------

class KrogerToken(Base):
    """Store Kroger OAuth tokens per user."""
    __tablename__ = "kroger_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    store_id = Column(String(20), default="01800661")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User")


# ---------- Import Log ----------

class ImportLog(Base):
    __tablename__ = "import_log"

    id = Column(Integer, primary_key=True)
    url = Column(Text, nullable=False)
    status = Column(String(20), default="pending")  # pending, success, failed
    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="SET NULL"), nullable=True)
    error = Column(Text, default="")
    raw_data = Column(JSON, nullable=True)
    extraction_method = Column(String(50), default="")  # schema, ai, manual
    duration_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
