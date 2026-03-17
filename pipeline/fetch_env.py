"""
Fetch environmental data from external APIs and enrich trip records.

APIs used:
  - Open-Meteo Archive API (weather)
  - Open-Meteo Marine API (sea temp, waves)
  - NOAA CO-OPS Tides API (high/low predictions)
  - Sunrise-Sunset.org API (solar events)
"""

import sys
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from pipeline import db
from pipeline import derive_metrics
from pipeline.models import EnvironmentalData

try:
    import requests  # type: ignore
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mean_nonnull(values: list) -> Optional[float]:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def _max_nonnull(values: list) -> Optional[float]:
    vals = [v for v in values if v is not None]
    return max(vals) if vals else None


def _sum_nonnull(values: list) -> Optional[float]:
    vals = [v for v in values if v is not None]
    return sum(vals) if vals else None


def _parse_iso(s: str) -> datetime:
    """Parse ISO 8601 string to UTC datetime."""
    s = s.rstrip("Z")
    if "+" in s:
        s = s[:s.index("+")]
    dt = datetime.fromisoformat(s)
    return dt.replace(tzinfo=timezone.utc)


def _hourly_indices(times: list[str], start: datetime, end: datetime) -> list[int]:
    """Return indices of hourly timestamps falling within [start, end]."""
    result = []
    for i, t in enumerate(times):
        try:
            dt = _parse_iso(t)
            if start <= dt <= end:
                result.append(i)
        except Exception:
            pass
    return result


def _hourly_index_at(times: list[str], target: datetime) -> Optional[int]:
    """Return index of hour closest to target."""
    best_i = None
    best_diff = timedelta(hours=999)
    for i, t in enumerate(times):
        try:
            dt = _parse_iso(t)
            diff = abs(dt - target)
            if diff < best_diff:
                best_diff = diff
                best_i = i
        except Exception:
            pass
    return best_i


# ---------------------------------------------------------------------------
# Weather (Open-Meteo Archive)
# ---------------------------------------------------------------------------

def fetch_weather(
    lat: float, lon: float, start_dt: datetime, end_dt: datetime
) -> Optional[dict]:
    """
    Fetch hourly weather for the trip window + 3 hours before start.
    Returns raw API response dict or None on failure.
    """
    fetch_start = start_dt - timedelta(hours=3)
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": fetch_start.strftime("%Y-%m-%d"),
        "end_date": end_dt.strftime("%Y-%m-%d"),
        "hourly": "wind_speed_10m,wind_direction_10m,temperature_2m,pressure_msl,cloudcover,precipitation",
        "wind_speed_unit": "ms",
        "timezone": "UTC",
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        print(f"  WARNING: fetch_weather failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# Marine (Open-Meteo Marine)
# ---------------------------------------------------------------------------

def fetch_marine(
    lat: float, lon: float, start_dt: datetime, end_dt: datetime
) -> Optional[dict]:
    """Fetch sea surface temperature and wave height."""
    url = "https://marine-api.open-meteo.com/v1/marine"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_dt.strftime("%Y-%m-%d"),
        "end_date": end_dt.strftime("%Y-%m-%d"),
        "hourly": "sea_surface_temperature,wave_height",
        "timezone": "UTC",
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        print(f"  WARNING: fetch_marine failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# NOAA Tides
# ---------------------------------------------------------------------------

def fetch_tides_noaa(
    station_id: str,
    start_dt: datetime,
    end_dt: datetime,
) -> list[dict]:
    """
    Fetch NOAA high/low tide predictions around the trip window (24-hr window).
    Returns list of {"time": datetime (UTC), "height_m": float, "type": "H"|"L"}.
    """
    midpoint = start_dt + (end_dt - start_dt) / 2
    window_start = midpoint - timedelta(hours=12)
    window_end = midpoint + timedelta(hours=12)

    url = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
    params = {
        "station": station_id,
        "product": "predictions",
        "datum": "MLLW",
        "time_zone": "GMT",
        "interval": "hilo",
        "units": "metric",
        "format": "json",
        "begin_date": window_start.strftime("%Y%m%d %H:%M"),
        "end_date": window_end.strftime("%Y%m%d %H:%M"),
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        predictions = data.get("predictions", [])
        events = []
        for p in predictions:
            t = datetime.strptime(p["t"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
            try:
                height_ft = float(p["v"])
                height_m = height_ft * 0.3048
            except ValueError:
                height_m = 0.0
            tide_t = p.get("type", "H")
            events.append({"time": t, "height_m": height_m, "type": tide_t})
        return events
    except Exception as exc:
        print(f"  WARNING: fetch_tides_noaa failed for station {station_id}: {exc}")
        return []


# ---------------------------------------------------------------------------
# Sunrise / Sunset
# ---------------------------------------------------------------------------

def fetch_sunrise(lat: float, lon: float, trip_date: date) -> Optional[dict]:
    """
    Fetch sunrise, sunset, solar noon from sunrise-sunset.org.
    Returns dict with keys sunrise, sunset, solar_noon as UTC datetime objects.
    """
    url = "https://api.sunrise-sunset.org/json"
    params = {
        "lat": lat,
        "lng": lon,
        "date": trip_date.strftime("%Y-%m-%d"),
        "formatted": 0,
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        results = resp.json().get("results", {})
        return {
            "sunrise": _parse_iso(results["sunrise"]),
            "sunset": _parse_iso(results["sunset"]),
            "solar_noon": _parse_iso(results["solar_noon"]),
        }
    except Exception as exc:
        print(f"  WARNING: fetch_sunrise failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------

def enrich_trip(trip_id: int) -> bool:
    """
    Fetch all environmental data for a trip and write to environmental_data table.
    Returns True on success, False on failure.
    """
    row = db.get_trip(trip_id)
    if row is None:
        print(f"  ERROR: Trip {trip_id} not found in database.")
        return False

    start_dt = _parse_iso(row["start_time"])
    end_dt = _parse_iso(row["end_time"])
    midpoint = start_dt + (end_dt - start_dt) / 2
    lat = row["lat"]
    lon = row["lon"]
    station_id = row["noaa_station_id"]
    trip_date = start_dt.date()

    print(f"  Enriching trip {trip_id} ({row['trip_date']}, lat={lat:.3f}, lon={lon:.3f})...")

    # --- Fetch all data sources -----------------------------------------
    weather_data = fetch_weather(lat, lon, start_dt, end_dt)
    marine_data = fetch_marine(lat, lon, start_dt, end_dt)
    tide_events = fetch_tides_noaa(station_id, start_dt, end_dt) if station_id else []
    solar = fetch_sunrise(lat, lon, trip_date)

    env = EnvironmentalData(trip_id=trip_id, tide_station_id=station_id)

    # --- Process weather ------------------------------------------------
    if weather_data and "hourly" in weather_data:
        h = weather_data["hourly"]
        times = h.get("time", [])
        trip_indices = _hourly_indices(times, start_dt, end_dt)
        mid_idx = _hourly_index_at(times, midpoint)
        before_idx = _hourly_index_at(times, start_dt - timedelta(hours=3))

        wind_speeds = [h["wind_speed_10m"][i] for i in trip_indices if i < len(h.get("wind_speed_10m", []))]
        wind_dirs = [h["wind_direction_10m"][i] for i in trip_indices if i < len(h.get("wind_direction_10m", []))]
        temps = [h["temperature_2m"][i] for i in trip_indices if i < len(h.get("temperature_2m", []))]
        clouds = [h["cloudcover"][i] for i in trip_indices if i < len(h.get("cloudcover", []))]
        precip = [h["precipitation"][i] for i in trip_indices if i < len(h.get("precipitation", []))]
        pressures = [h["pressure_msl"][i] for i in trip_indices if i < len(h.get("pressure_msl", []))]

        env.wind_speed_mps = _mean_nonnull(wind_speeds)
        env.air_temp_c = _mean_nonnull(temps)
        env.cloudcover_pct = int(_mean_nonnull(clouds)) if _mean_nonnull(clouds) is not None else None
        env.precipitation_mm = _sum_nonnull(precip)

        if wind_dirs:
            mean_dir = _mean_nonnull(wind_dirs)
            if mean_dir is not None:
                env.wind_direction_deg = int(mean_dir)
                env.wind_cardinal = derive_metrics.wind_cardinal(mean_dir)

        if mid_idx is not None and mid_idx < len(h.get("pressure_msl", [])):
            env.pressure_msl_hpa = h["pressure_msl"][mid_idx]

        if before_idx is not None and before_idx < len(h.get("pressure_msl", [])):
            env.pressure_3h_before = h["pressure_msl"][before_idx]

        if env.pressure_msl_hpa is not None and env.pressure_3h_before is not None:
            env.pressure_trend = derive_metrics.pressure_trend(
                env.pressure_msl_hpa, env.pressure_3h_before
            )

        max_cloud = _max_nonnull(clouds)
        total_precip = _sum_nonnull(precip)
        if max_cloud is not None and total_precip is not None:
            env.weather_category = derive_metrics.weather_category(max_cloud, total_precip)

    # --- Process marine -------------------------------------------------
    if marine_data and "hourly" in marine_data:
        h = marine_data["hourly"]
        times = h.get("time", [])
        trip_indices = _hourly_indices(times, start_dt, end_dt)

        sst = [h["sea_surface_temperature"][i] for i in trip_indices if i < len(h.get("sea_surface_temperature", []))]
        waves = [h["wave_height"][i] for i in trip_indices if i < len(h.get("wave_height", []))]

        env.water_temp_c = _mean_nonnull(sst)
        env.wave_height_m = _mean_nonnull(waves)

    # --- Process tides --------------------------------------------------
    if tide_events:
        phase, mins_high, mins_low = derive_metrics.tide_phase(tide_events, midpoint)
        env.tide_phase = phase
        env.mins_to_next_high = mins_high
        env.mins_to_next_low = mins_low
        env.tide_type = derive_metrics.tide_type(start_dt)

    # --- Process solar --------------------------------------------------
    if solar:
        env.sunrise_utc = solar["sunrise"].isoformat()
        env.sunset_utc = solar["sunset"].isoformat()
        env.solar_noon_utc = solar["solar_noon"].isoformat()
        env.trip_sun_phase = derive_metrics.sun_phase(
            solar["sunrise"], solar["sunset"], solar["solar_noon"], midpoint
        )

    db.upsert_env(env)
    print(f"  Done. weather={env.weather_category}, tide={env.tide_phase}, sun={env.trip_sun_phase}")
    return True
