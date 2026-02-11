"""Pydantic schemas for request/response validation."""

from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field


# ---------- Users ----------

class UserOut(BaseModel):
    id: int
    name: str
    avatar_emoji: str
    model_config = {"from_attributes": True}


# ---------- Ingredients ----------

class IngredientOut(BaseModel):
    id: int
    raw_text: str
    quantity: Optional[float] = None
    unit: str = ""
    preparation: str = ""
    group_name: str = ""
    ingredient_name: Optional[str] = None
    ingredient_category: Optional[str] = None
    model_config = {"from_attributes": True}


# ---------- Steps ----------

class StepOut(BaseModel):
    id: int
    step_number: int
    instruction: str
    duration_minutes: Optional[int] = None
    timer_label: str = ""
    model_config = {"from_attributes": True}


# ---------- Tags ----------

class TagOut(BaseModel):
    id: int
    name: str
    type: str
    color: str = "#6B7280"
    model_config = {"from_attributes": True}

class TagCreate(BaseModel):
    name: str
    type: str = "custom"
    color: str = "#6B7280"


# ---------- Ratings ----------

class RatingOut(BaseModel):
    id: int
    user_id: int
    user_name: Optional[str] = None
    stars: int
    would_make_again: bool
    notes: str = ""
    cooked_at: Optional[date] = None
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}

class RatingCreate(BaseModel):
    recipe_id: int
    user_id: int
    stars: int = Field(ge=1, le=5)
    would_make_again: bool = True
    notes: str = ""
    cooked_at: Optional[date] = None


# ---------- Recipes ----------

class RecipeBase(BaseModel):
    title: str
    description: str = ""
    source_url: str = ""
    image_url: str = ""
    prep_time_min: Optional[int] = None
    cook_time_min: Optional[int] = None
    total_time_min: Optional[int] = None
    servings: int = 4
    cuisine: str = ""
    difficulty: str = "medium"

class RecipeCreate(RecipeBase):
    ingredients: list[dict] = []  # [{"raw_text": "2 cups flour", "quantity": 2, "unit": "cups", ...}]
    steps: list[dict] = []  # [{"instruction": "Preheat oven", "duration_minutes": null}]
    tags: list[str] = []  # ["italian", "chicken", "easy"]

class RecipeUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    source_url: Optional[str] = None
    image_url: Optional[str] = None
    prep_time_min: Optional[int] = None
    cook_time_min: Optional[int] = None
    total_time_min: Optional[int] = None
    servings: Optional[int] = None
    cuisine: Optional[str] = None
    difficulty: Optional[str] = None
    ingredients: Optional[list[dict]] = None
    steps: Optional[list[dict]] = None
    tags: Optional[list[str]] = None

class RecipeSummary(BaseModel):
    id: int
    title: str
    description: str = ""
    image_url: str = ""
    image_path: str = ""
    prep_time_min: Optional[int] = None
    cook_time_min: Optional[int] = None
    total_time_min: Optional[int] = None
    cuisine: str = ""
    difficulty: str = ""
    avg_rating: Optional[float] = None
    rating_count: int = 0
    tags: list[TagOut] = []
    model_config = {"from_attributes": True}

class RecipeDetail(RecipeSummary):
    source_url: str = ""
    servings: int = 4
    notes: str = ""
    original_text: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    ingredients: list[IngredientOut] = []
    steps: list[StepOut] = []
    ratings: list[RatingOut] = []


# ---------- Import ----------

class ImportRequest(BaseModel):
    url: str
    user_id: Optional[int] = None

class BulkImportRequest(BaseModel):
    urls: list[str]
    user_id: Optional[int] = None

class ImportResult(BaseModel):
    url: str
    status: str
    recipe_id: Optional[int] = None
    recipe_title: Optional[str] = None
    error: Optional[str] = None
    extraction_method: str = ""
    duration_ms: Optional[int] = None


# ---------- Meal Plan ----------

class MealPlanCreate(BaseModel):
    date: date
    meal_type: str = "dinner"
    recipe_id: int
    notes: str = ""

class MealPlanUpdate(BaseModel):
    date: Optional[date] = None
    meal_type: Optional[str] = None
    recipe_id: Optional[int] = None
    status: Optional[str] = None
    notes: Optional[str] = None

class MealPlanOut(BaseModel):
    id: int
    date: date
    meal_type: str
    recipe_id: int
    recipe: Optional[RecipeSummary] = None
    status: str
    notes: str = ""
    model_config = {"from_attributes": True}

class WeekPlanOut(BaseModel):
    week_start: date
    week_end: date
    days: list[dict]  # [{"date": "2026-02-09", "available": true, "meals": [...], "calendar_events": [...]}]
    rule_status: list[dict] = []  # [{"rule": "...", "status": "ok|warning|violated"}]

class SuggestRequest(BaseModel):
    week_start: date
    available_dates: list[date] = []
    meal_type: str = "dinner"
    context: str = ""  # "quick weeknight", "date night", etc.


# ---------- Dietary Rules ----------

class RuleCreate(BaseModel):
    name: str
    rule_type: str  # protein_max_per_week, protein_min_per_period, no_repeat_within_days, min_tag_per_week
    config: dict
    active: bool = True

class RuleUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[dict] = None
    active: Optional[bool] = None

class RuleOut(BaseModel):
    id: int
    name: str
    rule_type: str
    config: dict
    active: bool
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}

class RuleEvaluation(BaseModel):
    rule_id: int
    rule_name: str
    status: str  # ok, warning, violated
    message: str
    details: dict = {}


# ---------- Swipe ----------

class SwipeSessionCreate(BaseModel):
    context: str = "dinner"  # weeknight, weekend, date_night, quick
    target_date: Optional[date] = None
    pool_size: int = 15

class SwipeSessionOut(BaseModel):
    id: int
    context: str
    status: str
    target_date: Optional[date] = None
    total_cards: int = 0
    your_progress: int = 0
    partner_progress: int = 0
    match_count: int = 0
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}

class SwipeCardOut(BaseModel):
    recipe: RecipeSummary
    card_index: int
    total_cards: int

class SwipeAction(BaseModel):
    recipe_id: int
    user_id: int
    decision: str  # like, dislike, skip, superlike

class SwipeMatchOut(BaseModel):
    recipe: RecipeSummary
    matched_at: Optional[datetime] = None
    planned_for_date: Optional[date] = None
    is_superlike: bool = False


# ---------- Shopping ----------

class ShoppingListOut(BaseModel):
    id: int
    name: str
    week_of: Optional[date] = None
    items: list[dict] = []
    total_items: int = 0
    checked_items: int = 0
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}

class ShoppingItemUpdate(BaseModel):
    checked: Optional[bool] = None
    checked_by: Optional[int] = None
    quantity: Optional[float] = None

class GenerateListRequest(BaseModel):
    week_of: date
    name: str = ""


# ---------- Calendar ----------

class CalendarEventCreate(BaseModel):
    date: date
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    summary: str = ""
    is_dinner_conflict: bool = False

class CalendarEventOut(BaseModel):
    id: int
    date: date
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    summary: str
    is_dinner_conflict: bool
    source: str
    model_config = {"from_attributes": True}

class AvailabilityOut(BaseModel):
    date: date
    available: bool
    events: list[CalendarEventOut] = []


# ---------- Taste Profile ----------

class TasteProfileOut(BaseModel):
    user_id: int
    user_name: str = ""
    preferences: dict = {}
    insights: list[str] = []
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}

class TasteInsight(BaseModel):
    category: str  # observation, suggestion, trend
    message: str
    data: dict = {}


# ---------- Cook-Along ----------

class CookAlongSession(BaseModel):
    recipe_id: int
    recipe_title: str
    total_steps: int
    current_step: int = 1
    steps: list[StepOut] = []
    active_timers: list[dict] = []
    servings_multiplier: float = 1.0
