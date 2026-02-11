"""Meal planner routes."""

import logging
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.database import get_db
from app.models import MealPlan, Recipe, CalendarEvent
from app.schemas import (
    MealPlanCreate, MealPlanUpdate, MealPlanOut, WeekPlanOut,
    SuggestRequest, CalendarEventCreate, CalendarEventOut, AvailabilityOut,
)
from app.services.rules_engine import evaluate_rules, get_rule_status_for_week
from app.services.suggestion_engine import suggest_meals
from app.services.ha_calendar import fetch_ha_events

logger = logging.getLogger("butlergroceries.routers.planner")
router = APIRouter(prefix="/api/planner", tags=["planner"])


@router.get("/week", response_model=WeekPlanOut)
async def get_week_plan(
    start: date = Query(None, description="Week start date (Monday). Defaults to current week."),
    db: AsyncSession = Depends(get_db),
):
    """Get the meal plan for a week, including calendar availability."""
    if not start:
        today = date.today()
        start = today - timedelta(days=today.weekday())  # Monday

    week_end = start + timedelta(days=6)

    logger.info(f"Getting week plan: {start} to {week_end}")

    # Get meal plans
    plan_result = await db.execute(
        select(MealPlan)
        .where(and_(MealPlan.date >= start, MealPlan.date <= week_end))
        .order_by(MealPlan.date)
    )
    plans = plan_result.scalars().all()

    # Get local calendar events
    cal_result = await db.execute(
        select(CalendarEvent)
        .where(and_(CalendarEvent.date >= start, CalendarEvent.date <= week_end))
        .order_by(CalendarEvent.date)
    )
    cal_events = cal_result.scalars().all()

    # Fetch HA calendar events
    try:
        ha_events = await fetch_ha_events(start, week_end)
    except Exception as e:
        logger.warning(f"Failed to fetch HA calendar events: {e}")
        ha_events = []

    # Get rule statuses
    rule_status = await get_rule_status_for_week(db, start)

    # Build day-by-day view
    days = []
    for i in range(7):
        d = start + timedelta(days=i)
        day_plans = [p for p in plans if p.date == d]
        day_local_events = [e for e in cal_events if e.date == d]
        day_ha_events = [e for e in ha_events if e["date"] == str(d)]
        has_conflict = (
            any(e.is_dinner_conflict for e in day_local_events)
            or any(e["is_dinner_conflict"] for e in day_ha_events)
        )

        # Build meal plan entries with recipe info
        meals = []
        for p in day_plans:
            recipe_result = await db.execute(select(Recipe).where(Recipe.id == p.recipe_id))
            recipe = recipe_result.scalar_one_or_none()
            meals.append({
                "id": p.id,
                "meal_type": p.meal_type,
                "recipe_id": p.recipe_id,
                "recipe_title": recipe.title if recipe else "Unknown",
                "recipe_image": recipe.image_url if recipe else "",
                "status": p.status,
                "notes": p.notes,
            })

        # Merge local + HA events
        events = [
            CalendarEventOut.model_validate(e).model_dump()
            for e in day_local_events
        ]
        for ha_ev in day_ha_events:
            events.append({
                "id": None,
                "date": ha_ev["date"],
                "start_time": ha_ev.get("start_time"),
                "end_time": ha_ev.get("end_time"),
                "summary": ha_ev["summary"],
                "is_dinner_conflict": ha_ev["is_dinner_conflict"],
                "source": "homeassistant",
                "calendar": ha_ev.get("calendar", ""),
                "location": ha_ev.get("location", ""),
                "all_day": ha_ev.get("all_day", False),
            })

        days.append({
            "date": str(d),
            "day_name": d.strftime("%A"),
            "available": not has_conflict,
            "meals": meals,
            "calendar_events": events,
        })

    logger.info(
        f"Week plan loaded: {sum(len(d['meals']) for d in days)} meals, "
        f"{sum(1 for d in days if d['available'])} available nights",
    )

    return WeekPlanOut(
        week_start=start,
        week_end=week_end,
        days=days,
        rule_status=rule_status,
    )


@router.post("", response_model=MealPlanOut, status_code=201)
async def create_plan_entry(data: MealPlanCreate, db: AsyncSession = Depends(get_db)):
    """Add a recipe to the meal plan."""
    logger.info(f"Planning recipe {data.recipe_id} for {data.date}")

    # Verify recipe exists
    recipe_result = await db.execute(select(Recipe).where(Recipe.id == data.recipe_id))
    recipe = recipe_result.scalar_one_or_none()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    # Evaluate rules
    rule_evals = await evaluate_rules(db, data.date, data.recipe_id)
    violations = [e for e in rule_evals if e["status"] == "violated"]
    if violations:
        logger.warning(f"Rule violations for plan entry: {violations}")
        # Don't block, but include in response

    plan = MealPlan(
        date=data.date,
        meal_type=data.meal_type,
        recipe_id=data.recipe_id,
        notes=data.notes,
    )
    db.add(plan)
    await db.flush()

    logger.info(
        f"Meal planned: {recipe.title} on {data.date}",
        extra={"extra_data": {"plan_id": plan.id, "recipe_id": data.recipe_id, "date": str(data.date)}}
    )

    return MealPlanOut(
        id=plan.id,
        date=plan.date,
        meal_type=plan.meal_type,
        recipe_id=plan.recipe_id,
        status=plan.status,
        notes=plan.notes,
    )


@router.put("/{plan_id}", response_model=MealPlanOut)
async def update_plan_entry(plan_id: int, data: MealPlanUpdate, db: AsyncSession = Depends(get_db)):
    """Update a meal plan entry."""
    logger.info(f"Updating plan entry {plan_id}")

    result = await db.execute(select(MealPlan).where(MealPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan entry not found")

    for field in ["date", "meal_type", "recipe_id", "status", "notes"]:
        value = getattr(data, field, None)
        if value is not None:
            setattr(plan, field, value)

    await db.flush()
    logger.info(f"Plan entry updated: {plan_id}")
    return MealPlanOut.model_validate(plan)


@router.delete("/{plan_id}", status_code=204)
async def delete_plan_entry(plan_id: int, db: AsyncSession = Depends(get_db)):
    """Remove a meal from the plan."""
    logger.info(f"Deleting plan entry {plan_id}")
    result = await db.execute(select(MealPlan).where(MealPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan entry not found")
    await db.delete(plan)
    await db.flush()
    logger.info(f"Plan entry deleted: {plan_id}")


@router.post("/suggest")
async def suggest_week_meals(data: SuggestRequest, db: AsyncSession = Depends(get_db)):
    """AI-suggest meals for available dates."""
    logger.info(f"Suggesting meals for week of {data.week_start}", extra={
        "extra_data": {
            "week_start": str(data.week_start),
            "available_dates": [str(d) for d in data.available_dates],
            "context": data.context,
        }
    })

    suggestions = await suggest_meals(
        db=db,
        week_start=data.week_start,
        available_dates=data.available_dates,
        context=data.context,
    )

    return {"suggestions": suggestions}


# ---------- Calendar ----------

@router.post("/calendar", response_model=CalendarEventOut, status_code=201)
async def add_calendar_event(data: CalendarEventCreate, db: AsyncSession = Depends(get_db)):
    """Add a calendar event (manual entry)."""
    logger.info(f"Adding calendar event: {data.summary} on {data.date}")
    event = CalendarEvent(
        date=data.date,
        start_time=data.start_time,
        end_time=data.end_time,
        summary=data.summary,
        is_dinner_conflict=data.is_dinner_conflict,
        source="manual",
    )
    db.add(event)
    await db.flush()
    return CalendarEventOut.model_validate(event)


@router.delete("/calendar/{event_id}", status_code=204)
async def delete_calendar_event(event_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a calendar event."""
    logger.info(f"Deleting calendar event {event_id}")
    result = await db.execute(select(CalendarEvent).where(CalendarEvent.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    await db.delete(event)
    await db.flush()


@router.get("/availability", response_model=list[AvailabilityOut])
async def get_availability(
    start: date = Query(...),
    end: date = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get dinner availability for a date range."""
    logger.info(f"Checking availability: {start} to {end}")

    result = await db.execute(
        select(CalendarEvent)
        .where(and_(CalendarEvent.date >= start, CalendarEvent.date <= end))
        .order_by(CalendarEvent.date)
    )
    events = result.scalars().all()

    availability = []
    current = start
    while current <= end:
        day_events = [e for e in events if e.date == current]
        has_conflict = any(e.is_dinner_conflict for e in day_events)
        availability.append(AvailabilityOut(
            date=current,
            available=not has_conflict,
            events=[CalendarEventOut.model_validate(e) for e in day_events],
        ))
        current += timedelta(days=1)

    return availability


@router.get("/calendar/ha")
async def get_ha_calendar_events(
    start: date = Query(...),
    end: date = Query(...),
):
    """Fetch events from Home Assistant calendars."""
    events = await fetch_ha_events(start, end)
    conflicts = sum(1 for e in events if e["is_dinner_conflict"])
    return {
        "events": events,
        "total": len(events),
        "dinner_conflicts": conflicts,
    }
