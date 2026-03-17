"""Dataclasses representing core domain objects."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Trip:
    trip_date: str                          # "YYYY-MM-DD"
    start_time: str                         # ISO 8601 UTC
    end_time: str                           # ISO 8601 UTC
    lat: float
    lon: float
    duration_hours: Optional[float] = None
    location_name: Optional[str] = None
    water_body: str = "saltwater"
    fit_file_path: Optional[str] = None
    noaa_station_id: Optional[str] = None
    notes: Optional[str] = None
    id: Optional[int] = None


@dataclass
class Catch:
    trip_id: int
    species: Optional[str] = None
    caught_at: Optional[str] = None         # ISO 8601 UTC; None = time unknown
    length_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    kept: int = 1                           # 0 = catch-and-release
    notes: Optional[str] = None
    id: Optional[int] = None


@dataclass
class EnvironmentalData:
    trip_id: int
    # Open-Meteo Weather
    wind_speed_mps: Optional[float] = None
    wind_direction_deg: Optional[int] = None
    wind_cardinal: Optional[str] = None
    air_temp_c: Optional[float] = None
    cloudcover_pct: Optional[int] = None
    precipitation_mm: Optional[float] = None
    pressure_msl_hpa: Optional[float] = None
    pressure_3h_before: Optional[float] = None
    pressure_trend: Optional[str] = None
    # Open-Meteo Marine
    water_temp_c: Optional[float] = None
    wave_height_m: Optional[float] = None
    # NOAA CO-OPS Tides
    tide_station_id: Optional[str] = None
    tide_phase: Optional[str] = None
    mins_to_next_high: Optional[int] = None
    mins_to_next_low: Optional[int] = None
    tide_type: Optional[str] = None
    # Sunrise-Sunset.org
    sunrise_utc: Optional[str] = None
    sunset_utc: Optional[str] = None
    solar_noon_utc: Optional[str] = None
    trip_sun_phase: Optional[str] = None
    # Composite
    weather_category: Optional[str] = None
    id: Optional[int] = None
