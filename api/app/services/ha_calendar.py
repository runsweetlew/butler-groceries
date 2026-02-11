"""Home Assistant calendar integration.

Pulls calendar events from HA to show on the meal planner.
Detects dinner conflicts (events during 5-9pm) automatically.
"""

import logging
from datetime import date, datetime, time, timedelta
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger("butlergroceries.services.ha_calendar")

# Events during this window suggest "eating out" / busy evening
DINNER_WINDOW_START = time(17, 0)  # 5:00 PM
DINNER_WINDOW_END = time(21, 0)    # 9:00 PM

# Keywords that strongly suggest a dinner conflict
DINNER_KEYWORDS = [
    "dinner", "restaurant", "reservation", "date night",
    "happy hour", "drinks", "cocktails", "eating out",
    "flight", "travel", "airport", "hotel",
]

# Keywords that are NOT dinner conflicts even if in the evening
NOT_DINNER_KEYWORDS = [
    "cook", "meal prep", "grocery", "groceries",
]


def _is_dinner_conflict(event: dict) -> bool:
    """Determine if a calendar event conflicts with cooking dinner at home."""
    summary = (event.get("summary") or "").lower()

    # Check explicit keywords first
    for kw in NOT_DINNER_KEYWORDS:
        if kw in summary:
            return False
    for kw in DINNER_KEYWORDS:
        if kw in summary:
            return True

    # All-day events: travel/flight is a conflict, others probably not
    start = event.get("start", {})
    if "date" in start and "dateTime" not in start:
        # All-day event — only conflict if travel-related
        for kw in ["flight", "travel", "trip", "vacation", "out of town"]:
            if kw in summary:
                return True
        return False

    # Timed events: check if they overlap the dinner window
    start_dt = _parse_datetime(start.get("dateTime", ""))
    end_dt = _parse_datetime(event.get("end", {}).get("dateTime", ""))

    if not start_dt:
        return False

    # If event starts before 9pm and ends after 5pm, it overlaps dinner
    event_start_time = start_dt.time()
    event_end_time = end_dt.time() if end_dt else time(23, 59)

    if event_start_time < DINNER_WINDOW_END and event_end_time > DINNER_WINDOW_START:
        return True

    return False


def _parse_datetime(dt_str: str) -> Optional[datetime]:
    """Parse HA datetime string."""
    if not dt_str:
        return None
    try:
        # HA returns ISO format with timezone offset
        return datetime.fromisoformat(dt_str)
    except (ValueError, TypeError):
        return None


async def fetch_ha_events(
    start_date: date,
    end_date: date,
) -> list[dict]:
    """Fetch calendar events from Home Assistant for a date range.

    Returns a list of normalized event dicts with:
      - date, start_time, end_time, summary, source, is_dinner_conflict, calendar
    """
    settings = get_settings()

    if not settings.ha_url or not settings.ha_token:
        logger.debug("HA calendar not configured (no HA_URL or HA_TOKEN)")
        return []

    calendars = [c.strip() for c in settings.ha_calendars.split(",") if c.strip()]
    if not calendars:
        return []

    headers = {
        "Authorization": f"Bearer {settings.ha_token}",
        "Content-Type": "application/json",
    }

    start_str = f"{start_date}T00:00:00Z"
    end_str = f"{end_date + timedelta(days=1)}T00:00:00Z"

    all_events = []

    async with httpx.AsyncClient(timeout=15.0, verify=False) as client:
        for cal_entity in calendars:
            try:
                url = f"{settings.ha_url}/api/calendars/{cal_entity}"
                resp = await client.get(
                    url,
                    headers=headers,
                    params={"start": start_str, "end": end_str},
                )

                if resp.status_code != 200:
                    logger.warning(f"HA calendar {cal_entity}: HTTP {resp.status_code}")
                    continue

                events = resp.json()
                cal_name = cal_entity.replace("calendar.", "").replace("_", " ").title()

                for ev in events:
                    start_info = ev.get("start", {})
                    end_info = ev.get("end", {})

                    # Determine the date
                    if "date" in start_info:
                        # All-day event
                        event_date = date.fromisoformat(start_info["date"])
                        event_start_time = None
                        event_end_time = None
                    elif "dateTime" in start_info:
                        dt = _parse_datetime(start_info["dateTime"])
                        if dt:
                            event_date = dt.date()
                            event_start_time = dt.strftime("%H:%M")
                        else:
                            continue
                        end_dt = _parse_datetime(end_info.get("dateTime", ""))
                        event_end_time = end_dt.strftime("%H:%M") if end_dt else None
                    else:
                        continue

                    normalized = {
                        "date": str(event_date),
                        "start_time": event_start_time,
                        "end_time": event_end_time,
                        "summary": ev.get("summary", ""),
                        "description": ev.get("description", ""),
                        "location": ev.get("location", ""),
                        "source": "homeassistant",
                        "calendar": cal_name,
                        "is_dinner_conflict": _is_dinner_conflict(ev),
                        "all_day": "date" in start_info,
                    }
                    all_events.append(normalized)

                logger.info(f"HA calendar {cal_entity}: {len(events)} events")

            except httpx.HTTPError as e:
                logger.error(f"HA calendar {cal_entity} error: {e}")
            except Exception as e:
                logger.error(f"HA calendar {cal_entity} unexpected error: {e}", exc_info=True)

    # Sort by date, then time
    all_events.sort(key=lambda e: (e["date"], e.get("start_time") or ""))

    logger.info(
        f"Fetched {len(all_events)} HA calendar events ({start_date} to {end_date}), "
        f"{sum(1 for e in all_events if e['is_dinner_conflict'])} dinner conflicts"
    )

    return all_events
