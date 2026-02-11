"""Dietary rules engine.

Evaluates meal plans against user-defined dietary rules.
Supports: protein frequency limits, variety minimums, repeat prevention, tag quotas.
"""

import logging
from datetime import date, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models import DietaryRule, MealPlan, Recipe, RecipeTag, Tag, CookingHistory

logger = logging.getLogger("butlergroceries.services.rules_engine")


async def get_active_rules(db: AsyncSession) -> list[DietaryRule]:
    """Get all active dietary rules."""
    result = await db.execute(select(DietaryRule).where(DietaryRule.active == True))
    rules = result.scalars().all()
    logger.debug(f"Loaded {len(rules)} active dietary rules")
    return list(rules)


async def evaluate_rules(
    db: AsyncSession,
    plan_date: date,
    recipe_id: int,
    existing_plan: Optional[list[dict]] = None,
) -> list[dict]:
    """Evaluate all active rules against a proposed meal plan entry.

    Returns list of rule evaluations:
    [{"rule_id": 1, "rule_name": "...", "status": "ok|warning|violated", "message": "..."}]
    """
    rules = await get_active_rules(db)
    if not rules:
        logger.info("No active rules to evaluate")
        return []

    evaluations = []
    for rule in rules:
        try:
            eval_result = await _evaluate_single_rule(db, rule, plan_date, recipe_id)
            evaluations.append(eval_result)
            logger.info(
                f"Rule '{rule.name}' → {eval_result['status']}",
                extra={"extra_data": eval_result}
            )
        except Exception as e:
            logger.error(f"Error evaluating rule '{rule.name}': {e}", exc_info=True)
            evaluations.append({
                "rule_id": rule.id,
                "rule_name": rule.name,
                "status": "error",
                "message": f"Error evaluating rule: {e}",
                "details": {},
            })

    return evaluations


async def _evaluate_single_rule(
    db: AsyncSession,
    rule: DietaryRule,
    plan_date: date,
    recipe_id: int,
) -> dict:
    """Evaluate a single rule."""
    config = rule.config
    rule_type = rule.rule_type

    if rule_type == "protein_max_per_week":
        return await _eval_protein_max(db, rule, config, plan_date, recipe_id)
    elif rule_type == "protein_min_per_period":
        return await _eval_protein_min(db, rule, config, plan_date, recipe_id)
    elif rule_type == "no_repeat_within_days":
        return await _eval_no_repeat(db, rule, config, plan_date, recipe_id)
    elif rule_type == "min_tag_per_week":
        return await _eval_min_tag(db, rule, config, plan_date, recipe_id)
    elif rule_type == "max_tag_per_week":
        return await _eval_max_tag(db, rule, config, plan_date, recipe_id)
    else:
        return {
            "rule_id": rule.id,
            "rule_name": rule.name,
            "status": "ok",
            "message": f"Unknown rule type: {rule_type}",
            "details": {},
        }


async def _eval_protein_max(db, rule, config, plan_date, recipe_id):
    """E.g., chicken max 2x per week."""
    protein = config.get("protein", "")
    max_count = config.get("max", 2)
    period_days = config.get("period_days", 7)

    period_start = plan_date - timedelta(days=period_days)

    # Count how many times this protein appears in the plan within the period
    count = await _count_protein_in_plan(db, protein, period_start, plan_date)

    # Check if the proposed recipe also has this protein
    proposed_has_protein = await _recipe_has_tag(db, recipe_id, protein)

    if proposed_has_protein:
        count += 1

    if count > max_count:
        return {
            "rule_id": rule.id,
            "rule_name": rule.name,
            "status": "violated",
            "message": f"{protein.title()} would appear {count}x in {period_days} days (max {max_count})",
            "details": {"protein": protein, "count": count, "max": max_count, "period_days": period_days},
        }
    elif count == max_count:
        return {
            "rule_id": rule.id,
            "rule_name": rule.name,
            "status": "warning",
            "message": f"{protein.title()} at limit: {count}x in {period_days} days (max {max_count})",
            "details": {"protein": protein, "count": count, "max": max_count, "period_days": period_days},
        }
    else:
        return {
            "rule_id": rule.id,
            "rule_name": rule.name,
            "status": "ok",
            "message": f"{protein.title()}: {count}/{max_count} in {period_days} days",
            "details": {"protein": protein, "count": count, "max": max_count, "period_days": period_days},
        }


async def _eval_protein_min(db, rule, config, plan_date, recipe_id):
    """E.g., salmon at least 1x every 2 weeks."""
    protein = config.get("protein", "")
    min_count = config.get("min", 1)
    period_days = config.get("period_days", 14)

    period_start = plan_date - timedelta(days=period_days)
    count = await _count_protein_in_plan(db, protein, period_start, plan_date)

    proposed_has_protein = await _recipe_has_tag(db, recipe_id, protein)
    if proposed_has_protein:
        count += 1

    if count < min_count:
        return {
            "rule_id": rule.id,
            "rule_name": rule.name,
            "status": "warning",
            "message": f"{protein.title()} only {count}x in last {period_days} days (need {min_count}+)",
            "details": {"protein": protein, "count": count, "min": min_count, "period_days": period_days},
        }
    else:
        return {
            "rule_id": rule.id,
            "rule_name": rule.name,
            "status": "ok",
            "message": f"{protein.title()}: {count}/{min_count}+ in {period_days} days ✓",
            "details": {"protein": protein, "count": count, "min": min_count, "period_days": period_days},
        }


async def _eval_no_repeat(db, rule, config, plan_date, recipe_id):
    """E.g., don't repeat the same recipe within 14 days."""
    min_days = config.get("min_days_between_repeat", 14)
    period_start = plan_date - timedelta(days=min_days)

    result = await db.execute(
        select(MealPlan).where(
            and_(
                MealPlan.recipe_id == recipe_id,
                MealPlan.date >= period_start,
                MealPlan.date <= plan_date,
                MealPlan.status != "skipped",
            )
        )
    )
    recent = result.scalars().all()

    if recent:
        last_date = max(r.date for r in recent)
        days_since = (plan_date - last_date).days
        return {
            "rule_id": rule.id,
            "rule_name": rule.name,
            "status": "violated",
            "message": f"This recipe was planned {days_since} days ago (minimum gap: {min_days} days)",
            "details": {"last_date": str(last_date), "days_since": days_since, "min_days": min_days},
        }
    else:
        return {
            "rule_id": rule.id,
            "rule_name": rule.name,
            "status": "ok",
            "message": f"Not repeated within {min_days} days ✓",
            "details": {"min_days": min_days},
        }


async def _eval_min_tag(db, rule, config, plan_date, recipe_id):
    """E.g., at least 2 vegetarian dinners per week."""
    tag_name = config.get("tag", "")
    min_count = config.get("min", 2)
    period_days = config.get("period_days", 7)

    period_start = plan_date - timedelta(days=period_days)
    count = await _count_tag_in_plan(db, tag_name, period_start, plan_date)

    proposed_has_tag = await _recipe_has_tag(db, recipe_id, tag_name)
    if proposed_has_tag:
        count += 1

    if count < min_count:
        return {
            "rule_id": rule.id,
            "rule_name": rule.name,
            "status": "warning",
            "message": f"'{tag_name}' only {count}x in {period_days} days (want {min_count}+)",
            "details": {"tag": tag_name, "count": count, "min": min_count},
        }
    else:
        return {
            "rule_id": rule.id,
            "rule_name": rule.name,
            "status": "ok",
            "message": f"'{tag_name}': {count}/{min_count}+ ✓",
            "details": {"tag": tag_name, "count": count, "min": min_count},
        }


async def _eval_max_tag(db, rule, config, plan_date, recipe_id):
    """E.g., max 2 pasta dishes per week."""
    tag_name = config.get("tag", "")
    max_count = config.get("max", 2)
    period_days = config.get("period_days", 7)

    period_start = plan_date - timedelta(days=period_days)
    count = await _count_tag_in_plan(db, tag_name, period_start, plan_date)

    proposed_has_tag = await _recipe_has_tag(db, recipe_id, tag_name)
    if proposed_has_tag:
        count += 1

    if count > max_count:
        return {
            "rule_id": rule.id,
            "rule_name": rule.name,
            "status": "violated",
            "message": f"'{tag_name}' would appear {count}x in {period_days} days (max {max_count})",
            "details": {"tag": tag_name, "count": count, "max": max_count, "period_days": period_days},
        }
    elif count == max_count:
        return {
            "rule_id": rule.id,
            "rule_name": rule.name,
            "status": "warning",
            "message": f"'{tag_name}' at limit: {count}x in {period_days} days (max {max_count})",
            "details": {"tag": tag_name, "count": count, "max": max_count, "period_days": period_days},
        }
    else:
        return {
            "rule_id": rule.id,
            "rule_name": rule.name,
            "status": "ok",
            "message": f"'{tag_name}': {count}/{max_count} in {period_days} days",
            "details": {"tag": tag_name, "count": count, "max": max_count, "period_days": period_days},
        }


async def _count_protein_in_plan(db: AsyncSession, protein: str, start: date, end: date) -> int:
    """Count how many planned meals in the period have a given protein tag."""
    result = await db.execute(
        select(MealPlan)
        .join(Recipe, MealPlan.recipe_id == Recipe.id)
        .join(RecipeTag, RecipeTag.recipe_id == Recipe.id)
        .join(Tag, RecipeTag.tag_id == Tag.id)
        .where(
            and_(
                Tag.name == protein.lower(),
                MealPlan.date >= start,
                MealPlan.date <= end,
                MealPlan.status != "skipped",
            )
        )
    )
    return len(result.scalars().all())


async def _count_tag_in_plan(db: AsyncSession, tag_name: str, start: date, end: date) -> int:
    """Count planned meals with a given tag."""
    return await _count_protein_in_plan(db, tag_name, start, end)


async def _recipe_has_tag(db: AsyncSession, recipe_id: int, tag_name: str) -> bool:
    """Check if a recipe has a specific tag."""
    result = await db.execute(
        select(RecipeTag)
        .join(Tag, RecipeTag.tag_id == Tag.id)
        .where(
            and_(
                RecipeTag.recipe_id == recipe_id,
                Tag.name == tag_name.lower(),
            )
        )
    )
    return result.scalar_one_or_none() is not None


async def get_rule_status_for_week(db: AsyncSession, week_start: date) -> list[dict]:
    """Get the status of all rules for a given week."""
    rules = await get_active_rules(db)
    week_end = week_start + timedelta(days=6)

    statuses = []
    for rule in rules:
        config = rule.config
        rule_type = rule.rule_type

        try:
            if rule_type == "protein_max_per_week":
                protein = config.get("protein", "")
                max_count = config.get("max", 2)
                count = await _count_protein_in_plan(db, protein, week_start, week_end)
                status = "violated" if count > max_count else ("warning" if count == max_count else "ok")
                statuses.append({
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "status": status,
                    "message": f"{protein.title()}: {count}/{max_count}",
                })

            elif rule_type == "protein_min_per_period":
                protein = config.get("protein", "")
                min_count = config.get("min", 1)
                period_days = config.get("period_days", 14)
                period_start = week_start - timedelta(days=period_days)
                count = await _count_protein_in_plan(db, protein, period_start, week_end)
                status = "warning" if count < min_count else "ok"
                statuses.append({
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "status": status,
                    "message": f"{protein.title()}: {count}/{min_count}+ in {period_days}d",
                })

            elif rule_type == "min_tag_per_week":
                tag = config.get("tag", "")
                min_count = config.get("min", 2)
                count = await _count_tag_in_plan(db, tag, week_start, week_end)
                status = "warning" if count < min_count else "ok"
                statuses.append({
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "status": status,
                    "message": f"'{tag}': {count}/{min_count}+",
                })

            elif rule_type == "max_tag_per_week":
                tag = config.get("tag", "")
                max_count = config.get("max", 2)
                count = await _count_tag_in_plan(db, tag, week_start, week_end)
                status = "violated" if count > max_count else ("warning" if count == max_count else "ok")
                statuses.append({
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "status": status,
                    "message": f"'{tag}': {count}/{max_count}",
                })

            else:
                statuses.append({
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "status": "ok",
                    "message": "",
                })

        except Exception as e:
            logger.error(f"Error computing rule status: {e}", exc_info=True)
            statuses.append({
                "rule_id": rule.id,
                "rule_name": rule.name,
                "status": "error",
                "message": str(e),
            })

    return statuses
