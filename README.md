# Butler Groceries 🍳

Recipe & Meal Planning for the Butler family.

## Quick Start

```bash
# 1. Copy environment file
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY

# 2. Start everything
docker compose up -d --build

# 3. Open in browser
# UI: http://localhost:3000
# API docs: http://localhost:8080/docs
```

## Features

- **Recipe Import** — Paste a URL, AI extracts everything (title, ingredients, steps, times, photo)
- **Tinder-Style Swipe** — Both swipe on recipes; matches get planned
- **Cook-Along Mode** — Step-by-step with built-in timers, screen stays awake
- **Calendar-Aware Planning** — Mark busy nights, AI fills available ones
- **Dietary Rules** — "Chicken max 2x/week", "Salmon every 2 weeks", "2 veggie nights/week"
- **AI Taste Learning** — Tracks what you rate highly, gets smarter over time
- **Dual Ratings** — Both rate independently after cooking
- **Smart Shopping Lists** — Auto-generated from meal plan, organized by aisle
- **PWA** — Installable on phones

## Architecture

| Component | Stack | Port |
|-----------|-------|------|
| API | Python FastAPI + SQLAlchemy | 8080 |
| UI | Next.js 14 + Tailwind + Framer Motion | 3000 |
| Database | PostgreSQL 15 | 5433 |
| AI | Claude API (Anthropic) | — |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/recipes/import` | Import recipe from URL |
| GET | `/api/recipes` | List/search recipes |
| GET | `/api/recipes/{id}` | Recipe detail |
| GET | `/api/planner/week` | Week plan with calendar |
| POST | `/api/planner/suggest` | AI meal suggestions |
| POST | `/api/swipe/sessions` | Start Tinder session |
| POST | `/api/swipe/sessions/{id}/swipe` | Submit swipe |
| GET | `/api/cookalong/{recipe_id}` | Cook-along mode data |
| POST | `/api/ratings` | Rate a recipe |
| GET | `/api/taste/profile/{user_id}` | Taste profile |
| GET | `/api/taste/compare` | Compare both profiles |
| POST | `/api/shopping/generate` | Generate shopping list |
| GET | `/api/rules` | Dietary rules |
| GET | `/api/health` | Health check |

Full API docs at `/docs` when running.

## Running Locally

```bash
# Start all services
docker compose up -d --build

# View logs
docker compose logs -f

# Stop
docker compose down
```

Access at `http://localhost:3000` (UI) and `http://localhost:8080/docs` (API).
## Default Data

On first start, the app seeds:
- **Users**: Lewis 👨‍🍳, Partner 👩‍🍳
- **Rules**: Chicken max 2x/week, Salmon 1x/2 weeks, Beef max 2x/week, No repeats within 14 days, 2 veggie nights/week
- **Pantry staples**: Salt, pepper, olive oil, garlic, onion, etc.

## Logs

All backend logs are structured JSON:
```json
{"timestamp": "...", "level": "INFO", "logger": "butlergroceries.services.recipe_importer", "message": "Recipe imported: Lemon Herb Salmon", "request_id": "a3f2dd01", "user": "1", "data": {"recipe_id": 5, "url": "...", "method": "schema", "duration_ms": 1234}}
```

View logs: `docker compose logs -f api`
