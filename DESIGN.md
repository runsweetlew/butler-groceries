# DukeCook — Recipe & Meal Planning App

A personal cooking app for Trevor and Emily. Import recipes from the web (like newhome does for houses), plan meals around your real calendar, and enforce dietary rules automatically.

---

## 1. Core Concept

**The problem:** You find recipes everywhere — Instagram, NYT Cooking, blogs, friends texting links. You forget what you've saved, repeat the same 8 meals, and never plan ahead. When you do plan, you forget what nights you're actually home.

**The solution:** One place to collect recipes, a smart planner that knows your calendar and your rules, and a shopping list that writes itself.

---

## 2. Core Features (MVP)

### 2.1 Recipe Import (à la newhome)

Inspired by how newhome.trevorduke.com imports houses: paste a URL, AI does the rest.

| Source | How It Works |
|--------|-------------|
| **URL paste** | Paste any recipe URL → AI extracts title, ingredients, steps, cook time, servings, photo |
| **Bulk import** | Paste multiple URLs at once (one per line) |
| **Manual entry** | Full editor for family recipes, handwritten cards, etc. |
| **Photo import** | Snap a photo of a recipe card/cookbook page → OCR + AI extraction |
| **Share sheet** | iOS/Android share target — share from any app directly to DukeCook |

**Supported sites** (via structured data + AI fallback):
- NYT Cooking, Bon Appétit, Serious Eats, AllRecipes, Food Network
- Food blogs (most use Recipe schema markup)
- Instagram/TikTok (AI extracts from caption + comments)
- Any URL (AI best-effort extraction from page content)

### 2.2 Recipe Management

- **Tags & categories**: Cuisine (Italian, Mexican, Asian), meal type (breakfast, lunch, dinner, snack), protein (chicken, beef, salmon, vegetarian), effort level (weeknight-easy, weekend-project)
- **Ratings**: Both of you rate 1-5 stars independently, see each other's ratings
- **Notes**: Personal notes on a recipe ("Emily likes extra garlic", "halve the salt")
- **Scaling**: Adjust servings, ingredients recalculate automatically
- **Cook mode**: Large text, screen stays on, step-by-step with swipe navigation
- **Seasonal tags**: Auto-tag based on ingredients (summer = grilling, winter = soups)

### 2.3 Calendar-Aware Meal Planning

The killer feature. Connects to your Google Calendar to know which nights you're home.

| Feature | Details |
|---------|---------|
| **Calendar sync** | Reads Google Calendar for dinner conflicts (events at 5-9 PM, travel, restaurants) |
| **Available nights** | Shows which nights are "cook at home" nights for the week |
| **Drag-and-drop planner** | Weekly view — drag recipes onto available nights |
| **AI suggestions** | "Suggest meals for this week" fills available nights intelligently |
| **Quick confirm** | Both approve the plan, or swap suggestions |

### 2.4 Dietary Rules Engine

Define rules that the meal planner respects:

```
RULES EXAMPLES:
- Never chicken more than 2x per week
- Must eat salmon at least 1x every 2 weeks
- Red meat max 2x per week
- At least 2 vegetarian dinners per week
- No repeating the same recipe within 14 days
- Fish on Fridays (during Lent)
- Light/quick meals on gym nights (from calendar)
```

**How it works:**
- Rules stored as structured data, not free text
- Planner evaluates all rules before suggesting
- Visual indicators: ✅ rule satisfied, ⚠️ at limit, ❌ violated
- Rule history tracking: see your protein distribution over time

### 2.5 Smart Shopping List

Auto-generated from the meal plan:

- **Ingredient aggregation**: 3 recipes need onions? Shows "Onions (5)" not 3 separate lines
- **Pantry awareness**: Check off staples you always have (oil, salt, garlic, rice)
- **Aisle grouping**: Organize by store section (produce, dairy, meat, pantry)
- **Share & check off**: Both users see the same list, real-time sync at the store
- **Store integration** (future): Kroger/Instacart API for price estimates or ordering

---

## 3. Killer Features (Post-MVP)

Researched from Mealie (11.4K ⭐), Tandoor (8K ⭐), Paprika, Plan to Eat, Mealime, Yummly, and Grocy.

### 3.1 🧠 AI Taste Learning

Track what you actually cook (vs. just save) and what you rate highly. Over time the AI learns:
- "You both love Thai but never cook it — here are easy Thai weeknight recipes"
- "You always skip recipes with more than 30 min prep on weekdays"
- Suggest new recipes from the web that match your taste profile

### 3.2 🥘 "What Can I Cook?" (Pantry Mode)

- Snap a photo of your fridge/pantry
- Or maintain a simple pantry inventory
- AI suggests recipes you can make with what you have
- Highlights recipes that need just 1-2 extra ingredients ("you just need cream and dill")

### 3.3 📚 Cookbooks / Collections

Group recipes into themed collections:
- "Date Night Dinners"
- "Emily's Favorites"
- "Under 30 Minutes"
- "Impress the Guests"
- "Meal Prep Sundays"
- Share collections with family/friends via link

### 3.4 🎲 "Surprise Me" / Decision Fatigue Killer

When you can't decide:
- Spin the wheel from your favorites
- "Give me something new I haven't tried"
- "Something like [recipe] but different"
- Tinder-style swipe on recipe suggestions (both swipe, matches get planned)

### 3.5 📊 Cooking Stats & History

- What you've cooked over the last month/year
- Protein distribution charts (are you hitting your variety goals?)
- Most cooked recipes
- "Forgotten favorites" — recipes you loved but haven't made in 3+ months
- Streak tracking ("cooked at home 4 nights this week!")

### 3.6 ⏱️ Cook-Along Mode (Enhanced)

Step-by-step cooking assistant:
- Large text, one step at a time
- Built-in timers per step ("sear 3 minutes per side" → tap to start timer)
- Voice control: "next step", "start timer", "repeat"
- Simultaneous recipe coordination: cooking 2 things? Interleaved timeline
- "Start cooking" → sends notification to spouse ("dinner in ~45 min")

### 3.7 🔄 Leftover & Prep Planning

- Mark a recipe as "makes leftovers for tomorrow's lunch"
- Meal prep mode: batch cook Sunday, plan portioning for the week
- Ingredient reuse: "Monday's roast chicken → Wednesday's chicken salad"
- Freezer inventory: track what's frozen and when

### 3.8 🌡️ Seasonal & Occasion Suggestions

- Seasonal ingredient highlighting (what's fresh/cheap right now)
- Holiday menus (Thanksgiving, Christmas, 4th of July)
- Weather-aware: cold snap → suggest soups & stews
- "Having 6 people over Saturday" → suggests scalable entertaining recipes

### 3.9 🔗 Social / Sharing

- Share individual recipes or meal plans with a link
- Import from friends' DukeCook (if they have one)
- "Emily's mom's lasagna" — attribute recipes to people
- Recipe request: "Mom, can you add your meatloaf recipe?"

### 3.10 🏪 Multi-Store Price Optimization (Ambitious)

- Know which store has better prices for certain items
- Split shopping list by store
- Kroger/Meijer API integration for actual prices
- "This week's meal plan costs ~$87 in groceries"

---

## 4. Technical Architecture

Following the same pattern as other Duke projects (DukeCam, newhome, aireis):

### Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **Backend** | Python FastAPI | Same as newhome, DukeCam — consistent |
| **Frontend** | Next.js 14 or Vanilla JS + Jinja2 | TBD — Next.js for richer interactivity |
| **Database** | PostgreSQL | Framework Docker, same as everything else |
| **AI** | Claude API | Recipe extraction, meal suggestions, taste learning |
| **Calendar** | Google Calendar API | Read-only access to check availability |
| **Hosting** | Framework Docker | Same infra as DukeCam, aireis |
| **Domain** | `cook.trevorduke.com` or `dukecook.trevorduke.com` | Via Cloudflare tunnel |
| **Mobile** | PWA | Installable, works offline (like DukeCam) |

### Data Model (Simplified)

```
recipes
  id, title, url, source, image_url, description
  prep_time, cook_time, total_time, servings
  cuisine, difficulty, created_at, updated_at

recipe_ingredients
  id, recipe_id, ingredient_id, quantity, unit, preparation, group_name

ingredients
  id, name, category (produce/dairy/meat/pantry/spice)

recipe_steps
  id, recipe_id, step_number, instruction, duration_minutes

recipe_tags
  recipe_id, tag_id

tags
  id, name, type (cuisine/meal_type/protein/effort/custom)

ratings
  id, recipe_id, user, stars, notes, cooked_at

meal_plan
  id, date, meal_type (breakfast/lunch/dinner), recipe_id, status (planned/cooked/skipped)

dietary_rules
  id, rule_type, protein, operator, value, period, active

shopping_list
  id, week_of, generated_from_plan_id

shopping_items
  id, list_id, ingredient_id, quantity, unit, checked, aisle

pantry_staples
  id, ingredient_id, always_have (boolean)

users
  id, name (Trevor/Emily)
```

### Recipe Import Pipeline

```
URL submitted
  → Fetch page HTML
  → Check for Recipe schema (ld+json / microdata)
  → If structured data found:
      → Parse directly into recipe model
  → If not:
      → Send HTML to Claude API
      → "Extract the recipe from this page: title, ingredients, steps, times, servings"
  → Download hero image
  → Save to database
  → User reviews & edits extracted data
```

This mirrors newhome's approach: try structured data first, fall back to AI extraction.

---

## 5. MVP Scope (Phase 1)

Get these working first:

1. ✅ Recipe import from URL (AI extraction)
2. ✅ Manual recipe entry/editing
3. ✅ Recipe browsing, search, filtering by tags
4. ✅ Weekly meal planner (manual drag-and-drop)
5. ✅ Google Calendar integration (show available nights)
6. ✅ Dietary rules engine (basic rules)
7. ✅ AI meal suggestions respecting rules
8. ✅ Auto-generated shopping list from plan
9. ✅ PWA (installable on phone)
10. ✅ Two-user system (Trevor & Emily)

### Phase 2 (Fast Follow)
- Cook-along mode with timers
- Photo import (OCR)
- Pantry staples management
- Cooking history & stats
- "Surprise me" feature
- Cookbooks/collections

### Phase 3 (Nice to Have)
- AI taste learning
- "What can I cook?" pantry mode
- Leftover/prep planning
- Seasonal suggestions
- Share links

---

## 6. Competitive Landscape

| App | Stars/Users | Strengths | Weaknesses (for you) |
|-----|------------|-----------|---------------------|
| **Mealie** | 11.4K ⭐ | Self-hosted, great import, meal planning with rules | No calendar integration, complex setup, no AI suggestions |
| **Tandoor** | 8K ⭐ | Powerful search, AI features, shopping lists | Heavy/complex, no calendar, German-oriented |
| **Paprika** | Popular paid | Great import, cook mode, grocery lists | Not self-hosted, no calendar, no AI planning, $5/device |
| **Plan to Eat** | Popular paid | Best meal planning UX, drag-and-drop | $5/mo subscription, no AI, no calendar |
| **Mealime** | Popular free | Beautiful, dietary profiles, quick meals | Not self-hosted, limited recipe import, no rules engine |
| **Yummly** | Millions | AI recommendations, huge recipe DB | Ad-heavy, not self-hosted, no calendar, no couple features |
| **DukeCook** | Just us 😎 | Calendar-aware, rules engine, AI suggestions, couple-focused, self-hosted, free | We have to build it |

**DukeCook's unique advantages:**
1. **Calendar awareness** — No other app checks your actual calendar
2. **Couple-focused** — Dual ratings, shared planning, "both swipe" features
3. **AI-first** — Not bolted on, AI is core to import + planning + suggestions
4. **Rules engine** — More flexible than Mealie's basic planner rules
5. **Self-hosted** — Your data, your rules, runs on Framework

---

## 7. Open Questions

- [ ] Next.js vs. vanilla JS frontend? (Next.js probably better for the interactivity needed)
- [ ] Google Calendar — use service account or OAuth per user?
- [ ] Recipe schema: use Mealie's recipe-scraper library? (Python, well-maintained)
- [ ] Nutritional data: worth including? (adds complexity but useful for health tracking)
- [ ] Multiple households: just Trevor+Emily, or design for sharing with family?
- [ ] Name: DukeCook? DukeEats? Something else?
