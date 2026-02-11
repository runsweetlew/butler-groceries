"""AI-powered recipe extraction using Claude API.

Extracts structured recipe data from HTML pages when structured data (schema.org)
is not available. Also handles recipe enrichment (auto-tagging proteins, cuisine, etc.)
"""

import json
import logging
from typing import Optional
import anthropic
from app.config import get_settings

logger = logging.getLogger("dukecook.services.ai_extractor")


async def extract_recipe_from_html(html: str, url: str) -> Optional[dict]:
    """Use Claude to extract recipe data from raw HTML.

    Returns a dict matching our recipe schema, or None on failure.
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        logger.error("ANTHROPIC_API_KEY not configured — cannot extract recipe from HTML")
        return None

    logger.info(f"AI extracting recipe from URL: {url}", extra={
        "extra_data": {"url": url, "html_length": len(html)}
    })

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    # Truncate HTML to avoid token limits
    max_html = 50000
    truncated_html = html[:max_html] if len(html) > max_html else html
    if len(html) > max_html:
        logger.info(f"Truncated HTML from {len(html)} to {max_html} chars")

    prompt = f"""Extract the recipe from this webpage HTML. Return a JSON object with these fields:

{{
  "title": "Recipe title",
  "description": "Full description of the dish — include what makes it special, flavor notes, etc.",
  "prep_time_min": 15,
  "cook_time_min": 30,
  "total_time_min": 45,
  "servings": 4,
  "cuisine": "Italian",
  "difficulty": "easy|medium|hard",
  "image_url": "URL of the main recipe image",
  "notes": "All tips, author notes, variations, make-ahead instructions, storage tips, serving suggestions — everything beyond the core recipe",
  "ingredients": [
    {{"raw_text": "2 cups all-purpose flour", "quantity": 2, "unit": "cups", "name": "all-purpose flour", "preparation": "", "group": ""}},
    {{"raw_text": "1 lb chicken breast, diced", "quantity": 1, "unit": "lb", "name": "chicken breast", "preparation": "diced", "group": ""}}
  ],
  "steps": [
    {{"instruction": "Preheat oven to 375°F.", "duration_minutes": null, "timer_label": ""}},
    {{"instruction": "In a large skillet, heat olive oil over medium-high heat. Sear chicken for 3 minutes per side until golden brown. Don't move the chicken while it sears — you want a good crust.", "duration_minutes": 6, "timer_label": "Sear chicken"}}
  ],
  "tags": ["italian", "chicken", "easy", "weeknight"]
}}

CRITICAL RULES — READ CAREFULLY:
- Extract EVERY ingredient exactly as written. Do NOT skip optional ingredients, garnishes, or "for serving" items.
- Extract EVERY step with FULL DETAIL. Do NOT summarize, condense, or combine steps.
- Keep the EXACT wording and details from the original recipe. Include temperatures, visual cues ("until golden brown"), texture descriptions ("until the dough is smooth and elastic"), and technique tips.
- If a step contains multiple sentences, keep ALL of them. A step like "Season the chicken. Let it rest for 10 minutes. This allows the salt to penetrate the meat." should be kept in full.
- Include ALL author tips, headnotes, variations, make-ahead notes, storage instructions, and serving suggestions in the "notes" field.
- Parse quantities as numbers (1.5, 0.25, etc.)
- Preserve ingredient groupings (e.g., "For the sauce", "For the crust") in the "group" field
- If a step has a clear timer (e.g., "cook for 10 minutes"), set duration_minutes and timer_label
- Tags should include: cuisine, primary protein, difficulty, and any other relevant categories
- If info is missing, use null
- Return ONLY the JSON, no other text

URL: {url}

HTML:
{truncated_html}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1]  # Remove first line
            if text.endswith("```"):
                text = text[:-3]
            elif "```" in text:
                text = text[:text.rfind("```")]
            text = text.strip()

        recipe_data = json.loads(text)

        logger.info(
            f"AI extracted recipe: {recipe_data.get('title', 'Unknown')}",
            extra={
                "extra_data": {
                    "url": url,
                    "title": recipe_data.get("title"),
                    "ingredient_count": len(recipe_data.get("ingredients", [])),
                    "step_count": len(recipe_data.get("steps", [])),
                    "tokens_in": response.usage.input_tokens,
                    "tokens_out": response.usage.output_tokens,
                }
            },
        )
        return recipe_data

    except json.JSONDecodeError as e:
        logger.error(f"AI returned invalid JSON: {e}", extra={
            "extra_data": {"url": url, "response_text": text[:500] if text else ""}
        })
        return None
    except anthropic.APIError as e:
        logger.error(f"Anthropic API error: {e}", exc_info=True, extra={
            "extra_data": {"url": url}
        })
        return None
    except Exception as e:
        logger.error(f"Unexpected error in AI extraction: {e}", exc_info=True, extra={
            "extra_data": {"url": url}
        })
        return None


async def extract_recipe_from_image(image_data: bytes, media_type: str, filename: str = "") -> Optional[dict]:
    """Use Claude Vision to extract recipe data from a photo.

    Handles photos of cookbook pages, handwritten recipes, recipe cards,
    magazine clippings, screenshots, etc.

    Returns a dict matching our recipe schema, or None on failure.
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        logger.error("ANTHROPIC_API_KEY not configured — cannot extract recipe from image")
        return None

    import base64
    encoded = base64.standard_b64encode(image_data).decode("utf-8")

    logger.info(f"AI extracting recipe from image: {filename} ({len(image_data)} bytes, {media_type})")

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    prompt = """Look at this image of a recipe. Extract ALL the recipe information you can see and return it as a JSON object.

{
  "title": "Recipe title",
  "description": "Full description of the dish",
  "prep_time_min": 15,
  "cook_time_min": 30,
  "total_time_min": 45,
  "servings": 4,
  "cuisine": "Italian",
  "difficulty": "easy|medium|hard",
  "notes": "All tips, author notes, variations, storage tips, serving suggestions — everything beyond the core recipe",
  "ingredients": [
    {"raw_text": "2 cups all-purpose flour", "quantity": 2, "unit": "cups", "name": "all-purpose flour", "preparation": "", "group": ""},
    {"raw_text": "1 lb chicken breast, diced", "quantity": 1, "unit": "lb", "name": "chicken breast", "preparation": "diced", "group": ""}
  ],
  "steps": [
    {"instruction": "Preheat oven to 375°F.", "duration_minutes": null, "timer_label": ""},
    {"instruction": "In a large skillet, heat olive oil over medium-high heat. Sear chicken for 3 minutes per side until golden brown. Don't move the chicken while it sears — you want a good crust.", "duration_minutes": 6, "timer_label": "Sear chicken"}
  ],
  "tags": ["italian", "chicken", "easy", "weeknight"]
}

CRITICAL RULES — READ CAREFULLY:
- Transcribe EVERY ingredient EXACTLY as written. Do NOT skip optional ingredients, garnishes, or "for serving" items.
- Transcribe EVERY step with FULL DETAIL. Do NOT summarize, condense, or combine steps. Keep the EXACT wording.
- Include ALL temperatures, visual cues, texture descriptions, and technique tips from every step.
- If a step has multiple sentences, keep ALL of them verbatim.
- Include ALL tips, headnotes, variations, notes, and serving suggestions in the "notes" field.
- Parse quantities as numbers (1.5, 0.25, etc.)
- Preserve ingredient groupings in the "group" field
- If a step has a timer, set duration_minutes and timer_label
- For handwritten recipes, do your best to read the handwriting
- If the image shows multiple recipes, extract only the main/first one
- If something is unclear, make your best guess and note it in the "notes" field
- If info is missing (no servings listed, etc.), use reasonable defaults
- Tags should include: cuisine, primary protein, difficulty, and any relevant categories
- Return ONLY the JSON, no other text"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": encoded,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
            }],
        )

        text = response.content[0].text.strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]
            elif "```" in text:
                text = text[:text.rfind("```")]
            text = text.strip()

        recipe_data = json.loads(text)

        logger.info(
            f"AI extracted recipe from image: {recipe_data.get('title', 'Unknown')}",
            extra={
                "extra_data": {
                    "filename": filename,
                    "title": recipe_data.get("title"),
                    "ingredient_count": len(recipe_data.get("ingredients", [])),
                    "step_count": len(recipe_data.get("steps", [])),
                    "tokens_in": response.usage.input_tokens,
                    "tokens_out": response.usage.output_tokens,
                }
            },
        )
        return recipe_data

    except json.JSONDecodeError as e:
        logger.error(f"AI returned invalid JSON from image: {e}", extra={
            "extra_data": {"filename": filename, "response_text": text[:500] if 'text' in dir() else ""}
        })
        return None
    except anthropic.APIError as e:
        logger.error(f"Anthropic API error (image): {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error in image extraction: {e}", exc_info=True)
        return None


async def enrich_recipe_tags(recipe_data: dict) -> list[str]:
    """Use AI to generate appropriate tags for a recipe.

    Analyzes ingredients and title to auto-detect proteins, cuisine, dietary info.
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        logger.warning("No API key — skipping AI tag enrichment")
        return recipe_data.get("tags", [])

    title = recipe_data.get("title", "")
    ingredients = [i.get("raw_text", "") for i in recipe_data.get("ingredients", [])]

    logger.info(f"Enriching tags for: {title}")

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=256,
            messages=[{
                "role": "user",
                "content": f"""Given this recipe, return a JSON array of tags. Include:
- Primary protein (chicken, beef, pork, salmon, shrimp, tofu, none/vegetarian)
- Cuisine (italian, mexican, thai, japanese, american, mediterranean, indian, etc.)
- Meal type (weeknight, weekend, date-night, meal-prep)
- Effort (easy, medium, hard)
- Any dietary labels (vegetarian, vegan, gluten-free, dairy-free, low-carb)
- Season (summer, winter, fall, spring) if clearly seasonal

Title: {title}
Ingredients: {', '.join(ingredients[:20])}

Return ONLY a JSON array of lowercase strings, nothing else."""
            }],
        )

        tags = json.loads(response.content[0].text.strip())
        logger.info(f"AI generated tags: {tags}", extra={
            "extra_data": {"title": title, "tags": tags}
        })
        return tags

    except Exception as e:
        logger.error(f"Tag enrichment failed: {e}", exc_info=True)
        return recipe_data.get("tags", [])


async def generate_taste_insights(
    user_name: str,
    ratings: list[dict],
    cooking_history: list[dict],
    preferences: dict,
) -> list[dict]:
    """Generate AI insights about a user's taste profile.

    Returns observations like "You love Mediterranean but rarely cook it."
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        logger.warning("No API key — cannot generate taste insights")
        return []

    logger.info(f"Generating taste insights for {user_name}", extra={
        "extra_data": {
            "rating_count": len(ratings),
            "history_count": len(cooking_history),
        }
    })

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": f"""You're analyzing cooking preferences for {user_name}. Based on their data, generate 3-5 fun, actionable insights.

Taste Preferences (0-1 scores):
{json.dumps(preferences, indent=2)}

Recent Ratings (newest first):
{json.dumps(ratings[:20], indent=2)}

Cooking History (last 30 days):
{json.dumps(cooking_history[:20], indent=2)}

Return a JSON array of objects:
[
  {{"category": "observation|suggestion|trend", "message": "You both love Thai food but only cooked it twice this month!", "data": {{}}}}
]

Be specific, friendly, and reference actual data. Return ONLY the JSON array."""
            }],
        )

        insights = json.loads(response.content[0].text.strip())
        logger.info(f"Generated {len(insights)} taste insights for {user_name}")
        return insights

    except Exception as e:
        logger.error(f"Taste insight generation failed: {e}", exc_info=True)
        return []
