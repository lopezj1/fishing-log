"""Database schema creation and upsert helpers."""

import sqlite3
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from pipeline.models import Trip, Catch, EnvironmentalData


def get_conn(db_path: Path = config.DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path = config.DB_PATH) -> None:
    """Create all tables if they don't exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_conn(db_path)
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS trips (
                id              INTEGER PRIMARY KEY,
                trip_date       TEXT NOT NULL,
                start_time      TEXT NOT NULL,
                end_time        TEXT NOT NULL,
                duration_hours  REAL,
                lat             REAL NOT NULL,
                lon             REAL NOT NULL,
                location_name   TEXT,
                water_body      TEXT DEFAULT 'saltwater',
                fit_file_path   TEXT,
                noaa_station_id TEXT,
                notes           TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS catches (
                id          INTEGER PRIMARY KEY,
                trip_id     INTEGER NOT NULL REFERENCES trips(id),
                caught_at   TEXT,
                species     TEXT,
                length_cm   REAL,
                weight_kg   REAL,
                kept        INTEGER DEFAULT 1,
                notes       TEXT
            );

            CREATE TABLE IF NOT EXISTS environmental_data (
                id                  INTEGER PRIMARY KEY,
                trip_id             INTEGER NOT NULL UNIQUE REFERENCES trips(id),
                wind_speed_mps      REAL,
                wind_direction_deg  INTEGER,
                wind_cardinal       TEXT,
                air_temp_c          REAL,
                cloudcover_pct      INTEGER,
                precipitation_mm    REAL,
                pressure_msl_hpa    REAL,
                pressure_3h_before  REAL,
                pressure_trend      TEXT,
                water_temp_c        REAL,
                wave_height_m       REAL,
                tide_station_id     TEXT,
                tide_phase          TEXT,
                mins_to_next_high   INTEGER,
                mins_to_next_low    INTEGER,
                tide_type           TEXT,
                sunrise_utc         TEXT,
                sunset_utc          TEXT,
                solar_noon_utc      TEXT,
                trip_sun_phase      TEXT,
                weather_category    TEXT,
                fetched_at          TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS gps_track (
                id         INTEGER PRIMARY KEY,
                trip_id    INTEGER NOT NULL REFERENCES trips(id),
                ts         TEXT NOT NULL,
                lat        REAL,
                lon        REAL,
                altitude_m REAL,
                speed_mps  REAL
            );
        """)
    conn.close()


def insert_trip(trip: Trip, db_path: Path = config.DB_PATH) -> int:
    """Insert a trip row and return the new row id."""
    conn = get_conn(db_path)
    with conn:
        cur = conn.execute(
            """INSERT INTO trips
               (trip_date, start_time, end_time, duration_hours, lat, lon,
                location_name, water_body, fit_file_path, noaa_station_id, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (trip.trip_date, trip.start_time, trip.end_time, trip.duration_hours,
             trip.lat, trip.lon, trip.location_name, trip.water_body,
             trip.fit_file_path, trip.noaa_station_id, trip.notes),
        )
        return cur.lastrowid


def insert_gps_track(trip_id: int, records: list[dict],
                     db_path: Path = config.DB_PATH) -> None:
    """Bulk-insert GPS track records."""
    conn = get_conn(db_path)
    with conn:
        conn.executemany(
            """INSERT INTO gps_track (trip_id, ts, lat, lon, altitude_m, speed_mps)
               VALUES (:trip_id, :ts, :lat, :lon, :altitude_m, :speed_mps)""",
            [{"trip_id": trip_id, **r} for r in records],
        )
    conn.close()


def insert_catch(catch: Catch, db_path: Path = config.DB_PATH) -> int:
    conn = get_conn(db_path)
    with conn:
        cur = conn.execute(
            """INSERT INTO catches
               (trip_id, caught_at, species, length_cm, weight_kg, kept, notes)
               VALUES (?,?,?,?,?,?,?)""",
            (catch.trip_id, catch.caught_at, catch.species,
             catch.length_cm, catch.weight_kg, catch.kept, catch.notes),
        )
        return cur.lastrowid


def upsert_env(env: EnvironmentalData, db_path: Path = config.DB_PATH) -> None:
    """Insert or replace environmental data for a trip."""
    conn = get_conn(db_path)
    with conn:
        conn.execute(
            """INSERT INTO environmental_data
               (trip_id, wind_speed_mps, wind_direction_deg, wind_cardinal,
                air_temp_c, cloudcover_pct, precipitation_mm,
                pressure_msl_hpa, pressure_3h_before, pressure_trend,
                water_temp_c, wave_height_m,
                tide_station_id, tide_phase, mins_to_next_high, mins_to_next_low, tide_type,
                sunrise_utc, sunset_utc, solar_noon_utc, trip_sun_phase,
                weather_category, fetched_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))
               ON CONFLICT(trip_id) DO UPDATE SET
                 wind_speed_mps=excluded.wind_speed_mps,
                 wind_direction_deg=excluded.wind_direction_deg,
                 wind_cardinal=excluded.wind_cardinal,
                 air_temp_c=excluded.air_temp_c,
                 cloudcover_pct=excluded.cloudcover_pct,
                 precipitation_mm=excluded.precipitation_mm,
                 pressure_msl_hpa=excluded.pressure_msl_hpa,
                 pressure_3h_before=excluded.pressure_3h_before,
                 pressure_trend=excluded.pressure_trend,
                 water_temp_c=excluded.water_temp_c,
                 wave_height_m=excluded.wave_height_m,
                 tide_station_id=excluded.tide_station_id,
                 tide_phase=excluded.tide_phase,
                 mins_to_next_high=excluded.mins_to_next_high,
                 mins_to_next_low=excluded.mins_to_next_low,
                 tide_type=excluded.tide_type,
                 sunrise_utc=excluded.sunrise_utc,
                 sunset_utc=excluded.sunset_utc,
                 solar_noon_utc=excluded.solar_noon_utc,
                 trip_sun_phase=excluded.trip_sun_phase,
                 weather_category=excluded.weather_category,
                 fetched_at=datetime('now')""",
            (env.trip_id, env.wind_speed_mps, env.wind_direction_deg, env.wind_cardinal,
             env.air_temp_c, env.cloudcover_pct, env.precipitation_mm,
             env.pressure_msl_hpa, env.pressure_3h_before, env.pressure_trend,
             env.water_temp_c, env.wave_height_m,
             env.tide_station_id, env.tide_phase, env.mins_to_next_high,
             env.mins_to_next_low, env.tide_type,
             env.sunrise_utc, env.sunset_utc, env.solar_noon_utc, env.trip_sun_phase,
             env.weather_category),
        )
    conn.close()


def get_trip(trip_id: int, db_path: Path = config.DB_PATH) -> Optional[sqlite3.Row]:
    conn = get_conn(db_path)
    row = conn.execute("SELECT * FROM trips WHERE id=?", (trip_id,)).fetchone()
    conn.close()
    return row


def get_trips_missing_env(db_path: Path = config.DB_PATH) -> list[sqlite3.Row]:
    conn = get_conn(db_path)
    rows = conn.execute(
        """SELECT t.* FROM trips t
           LEFT JOIN environmental_data e ON e.trip_id = t.id
           WHERE e.id IS NULL
           ORDER BY t.trip_date"""
    ).fetchall()
    conn.close()
    return rows


def trip_exists_for_date_location(trip_date: str, location_name: str,
                                   db_path: Path = config.DB_PATH) -> bool:
    conn = get_conn(db_path)
    row = conn.execute(
        "SELECT id FROM trips WHERE trip_date=? AND location_name=?",
        (trip_date, location_name),
    ).fetchone()
    conn.close()
    return row is not None


def get_trip_by_date_location(trip_date: str, location_name: str,
                               db_path: Path = config.DB_PATH) -> Optional[dict]:
    conn = get_conn(db_path)
    row = conn.execute(
        "SELECT * FROM trips WHERE trip_date=? AND location_name=?",
        (trip_date, location_name),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def trip_exists_for_fit(fit_path: str, db_path: Path = config.DB_PATH) -> bool:
    conn = get_conn(db_path)
    row = conn.execute(
        "SELECT id FROM trips WHERE fit_file_path=?", (fit_path,)
    ).fetchone()
    conn.close()
    return row is not None
