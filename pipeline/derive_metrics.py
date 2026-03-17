"""
Pure functions for deriving environmental metrics.
No I/O — all inputs are plain Python values.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional


def pressure_trend(pressure_now: float, pressure_3h_before: float) -> str:
    """Return 'rising', 'falling', or 'stable' based on hPa delta."""
    delta = pressure_now - pressure_3h_before
    if delta > 1.0:
        return "rising"
    if delta < -1.0:
        return "falling"
    return "stable"


def weather_category(max_cloudcover_pct: float, total_precip_mm: float) -> str:
    if total_precip_mm > 0.5:
        return "rain"
    if max_cloudcover_pct >= 80:
        return "overcast"
    if max_cloudcover_pct >= 40:
        return "partly_cloudy"
    return "sunny"


def tide_phase(
    high_low_events: list[dict],
    trip_midpoint: datetime,
) -> tuple[str, Optional[int], Optional[int]]:
    """
    Determine tide phase and time to next events.

    Parameters
    ----------
    high_low_events : list of {"time": datetime (UTC), "type": "H"|"L", "height_m": float}
    trip_midpoint   : UTC datetime

    Returns
    -------
    (phase, mins_to_next_high, mins_to_next_low)
    phase is "rising" | "falling"
    """
    if not high_low_events:
        return ("rising", None, None)

    # Ensure all event times are tz-aware UTC
    def _ensure_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    if trip_midpoint.tzinfo is None:
        trip_midpoint = trip_midpoint.replace(tzinfo=timezone.utc)

    events = sorted(high_low_events, key=lambda e: e["time"])
    events = [{**e, "time": _ensure_utc(e["time"])} for e in events]

    # Last event before midpoint
    past = [e for e in events if e["time"] <= trip_midpoint]
    future = [e for e in events if e["time"] > trip_midpoint]

    phase = "rising"
    if past:
        last = past[-1]
        phase = "rising" if last["type"] == "L" else "falling"

    next_high = next((e for e in future if e["type"] == "H"), None)
    next_low = next((e for e in future if e["type"] == "L"), None)

    mins_high = int((next_high["time"] - trip_midpoint).total_seconds() / 60) if next_high else None
    mins_low = int((next_low["time"] - trip_midpoint).total_seconds() / 60) if next_low else None

    return (phase, mins_high, mins_low)


def tide_type(trip_date: datetime) -> str:
    """
    Return 'spring' or 'neap' based on lunar phase.
    Spring = within 2 days of new or full moon.
    Requires 'ephem' package.
    """
    try:
        import ephem  # type: ignore
        d = ephem.Date(trip_date.strftime("%Y/%m/%d"))
        prev_new = ephem.previous_new_moon(d)
        next_new = ephem.next_new_moon(d)
        prev_full = ephem.previous_full_moon(d)
        next_full = ephem.next_full_moon(d)

        def days_from(moon_date: ephem.Date) -> float:
            return abs(float(d) - float(moon_date))

        nearest = min(
            days_from(prev_new),
            days_from(next_new),
            days_from(prev_full),
            days_from(next_full),
        )
        return "spring" if nearest <= 2 else "neap"
    except ImportError:
        return "neap"  # safe default if ephem not installed


def sun_phase(
    sunrise: datetime,
    sunset: datetime,
    solar_noon: datetime,
    trip_midpoint: datetime,
) -> str:
    """Return sun phase label for the trip midpoint."""
    def _utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    sr = _utc(sunrise)
    ss = _utc(sunset)
    sn = _utc(solar_noon)
    mp = _utc(trip_midpoint)

    if mp < sr - timedelta(minutes=30):
        return "pre-dawn"
    if mp < sr + timedelta(minutes=30):
        return "dawn"
    if mp < sn - timedelta(hours=2):
        return "morning"
    if mp < ss - timedelta(hours=2):
        return "afternoon"
    if mp < ss + timedelta(minutes=30):
        return "dusk"
    return "night"


def wind_cardinal(degrees: float) -> str:
    """Convert wind direction degrees to 8-point cardinal string."""
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = round(degrees / 45) % 8
    return dirs[idx]


def get_timezone(lat: float, lon: float) -> str:
    """Return IANA timezone string for GPS coordinates. Requires timezonefinder."""
    try:
        from timezonefinder import TimezoneFinder  # type: ignore
        tf = TimezoneFinder()
        tz = tf.timezone_at(lat=lat, lng=lon)
        return tz or "UTC"
    except ImportError:
        return "UTC"
