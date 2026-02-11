"""Dietary rules routes."""

import json
import logging
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import anthropic

from app.config import get_settings
from app.database import get_db
from app.models import DietaryRule
from app.schemas import RuleCreate, RuleUpdate, RuleOut, RuleEvaluation
from app.services.rules_engine import evaluate_rules, get_rule_status_for_week

logger = logging.getLogger("butlergroceries.routers.rules")
router = APIRouter(prefix="/api/rules", tags=["rules"])


@router.get("", response_model=list[RuleOut])
async def list_rules(db: AsyncSession = Depends(get_db)):
    """List all dietary rules."""
    logger.info("Listing dietary rules")
    result = await db.execute(select(DietaryRule).order_by(DietaryRule.id))
    rules = result.scalars().all()
    logger.info(f"Found {len(rules)} rules ({sum(1 for r in rules if r.active)} active)")
    return rules


@router.post("", response_model=RuleOut, status_code=201)
async def create_rule(data: RuleCreate, db: AsyncSession = Depends(get_db)):
    """Create a new dietary rule."""
    logger.info(f"Creating rule: {data.name} (type={data.rule_type})", extra={
        "extra_data": {"name": data.name, "type": data.rule_type, "config": data.config}
    })

    rule = DietaryRule(
        name=data.name,
        rule_type=data.rule_type,
        config=data.config,
        active=data.active,
    )
    db.add(rule)
    await db.flush()

    logger.info(f"Rule created: {rule.name} (id={rule.id})")
    return RuleOut.model_validate(rule)


@router.put("/{rule_id}", response_model=RuleOut)
async def update_rule(rule_id: int, data: RuleUpdate, db: AsyncSession = Depends(get_db)):
    """Update a dietary rule."""
    logger.info(f"Updating rule {rule_id}")

    result = await db.execute(select(DietaryRule).where(DietaryRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    if data.name is not None:
        rule.name = data.name
    if data.config is not None:
        rule.config = data.config
    if data.active is not None:
        rule.active = data.active

    await db.flush()
    logger.info(f"Rule updated: {rule.name} (id={rule.id})")
    return RuleOut.model_validate(rule)


@router.delete("/{rule_id}", status_code=204)
async def delete_rule(rule_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a dietary rule."""
    logger.info(f"Deleting rule {rule_id}")
    result = await db.execute(select(DietaryRule).where(DietaryRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.delete(rule)
    await db.flush()
    logger.info(f"Rule deleted: {rule.name} (id={rule_id})")


class NaturalLanguageRule(BaseModel):
    text: str


@router.post("/parse")
async def parse_natural_language_rule(data: NaturalLanguageRule):
    """Parse a natural language description into a structured dietary rule.

    Uses Claude to interpret phrases like:
      - "No more than 3 pasta dishes per week"
      - "We should eat fish at least twice a month"
      - "Don't repeat the same meal within 10 days"
      - "At least one soup per week in winter"
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=500, detail="AI not configured")

    logger.info(f"Parsing natural language rule: {data.text!r}")

    prompt = f"""You are a dietary rule parser for a meal planning app called Butler Groceries.

Convert the user's natural language rule into a structured JSON rule. The app supports these rule types:

1. **protein_max_per_week** — Limit a protein/ingredient to X times per period
   Config: {{"protein": "chicken", "max": 2, "period_days": 7}}

2. **protein_min_per_period** — Require a protein/ingredient at least X times per period
   Config: {{"protein": "salmon", "min": 1, "period_days": 14}}

3. **no_repeat_within_days** — Don't repeat the same recipe within X days
   Config: {{"min_days_between_repeat": 14}}

4. **min_tag_per_week** — Require at least X meals with a tag per period
   Config: {{"tag": "vegetarian", "min": 2, "period_days": 7}}

5. **max_tag_per_week** — Limit meals with a tag to X per period
   Config: {{"tag": "pasta", "max": 2, "period_days": 7}}

Notes:
- "protein" values are tag names on recipes (chicken, beef, salmon, pork, tofu, shrimp, etc.)
- "tag" values can be cuisine types (italian, mexican, asian), dietary labels (vegetarian, vegan, gluten-free), meal styles (comfort-food, quick, soup), or ingredients (pasta, rice)
- "per week" = period_days: 7, "per 2 weeks" / "every other week" = period_days: 14, "per month" = period_days: 30
- For limits use max types, for minimums use min types
- If the user's request doesn't map to any rule type, set rule_type to "unsupported"

User's rule: "{data.text}"

Respond with ONLY valid JSON (no markdown, no explanation):
{{
  "name": "Human-readable rule name",
  "rule_type": "one of the types above",
  "config": {{...}},
  "explanation": "Brief explanation of what this rule does"
}}"""

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        parsed = json.loads(raw)
        logger.info(f"Parsed rule: {parsed['name']} (type={parsed['rule_type']})", extra={
            "extra_data": {"input": data.text, "parsed": parsed}
        })

        if parsed.get("rule_type") == "unsupported":
            return {
                "success": False,
                "error": parsed.get("explanation", "Could not understand this as a dietary rule"),
                "parsed": parsed,
            }

        return {
            "success": True,
            "name": parsed["name"],
            "rule_type": parsed["rule_type"],
            "config": parsed["config"],
            "explanation": parsed.get("explanation", ""),
        }
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response as JSON: {e}", extra={"extra_data": {"raw": raw}})
        raise HTTPException(status_code=422, detail="AI returned invalid response. Try rephrasing your rule.")
    except Exception as e:
        logger.error(f"AI rule parsing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"AI error: {str(e)}")


@router.post("/evaluate", response_model=list[RuleEvaluation])
async def evaluate(
    recipe_id: int = Query(...),
    plan_date: date = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Evaluate all rules against a proposed meal plan entry."""
    logger.info(f"Evaluating rules: recipe {recipe_id} on {plan_date}")
    evaluations = await evaluate_rules(db, plan_date, recipe_id)
    return [RuleEvaluation(**e) for e in evaluations]


@router.get("/status")
async def week_rule_status(
    week_start: date = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get rule status for an entire week."""
    logger.info(f"Getting rule status for week of {week_start}")
    statuses = await get_rule_status_for_week(db, week_start)
    return {"week_start": str(week_start), "rules": statuses}
