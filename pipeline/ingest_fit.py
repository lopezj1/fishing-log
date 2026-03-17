"""
Decode a .FIT activity file into the trips and gps_track tables.

Requires:
  - garmin-fit-sdk  (pip install garmin-fit-sdk)
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from pipeline import db
from pipeline.models import Trip


def _to_utc_str(dt) -> Optional[str]:
    """Convert a datetime (or datetime-like) to ISO 8601 UTC string."""
    if dt is None:
        return None
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    # Some FIT SDK versions return date objects — try to handle
    return str(dt)


def _nearest_station(lat: float, lon: float) -> Optional[str]:
    """
    Return NOAA station id from config based on location.
    Simple proximity check — returns first station whose name key matches
    a rough bounding box heuristic. Falls back to DEFAULT_NOAA_STATION.
    """
    # Rough lat/lon bounding boxes for known station keys
    BOUNDS: dict[str, tuple[float, float, float, float]] = {
        "Chesapeake Bay":  (36.5, -77.5, 39.5, -75.0),
        "Outer Banks":     (35.0, -76.5, 36.5, -75.0),
        "Cape Cod":        (41.5, -71.0, 42.5, -69.5),
        "Florida Keys":    (24.0, -82.0, 25.5, -80.0),
        "Gulf of Mexico":  (25.0, -98.0, 30.5, -82.0),
    }
    for name, (lat_min, lon_min, lat_max, lon_max) in BOUNDS.items():
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            station = config.NOAA_STATION_IDS.get(name)
            if station:
                return station
    return config.DEFAULT_NOAA_STATION


def ingest_fit(fit_path: Path, skip_if_exists: bool = True) -> Optional[int]:
    """
    Decode a FIT file and write trip + GPS track to the database.

    Returns the trip_id of the inserted row, or None if skipped.
    """
    try:
        from garmin_fit_sdk import Decoder, Stream  # type: ignore
    except ImportError:
        print("ERROR: garmin-fit-sdk not installed. Run: pip install garmin-fit-sdk")
        sys.exit(1)

    db.init_db()

    fit_str = str(fit_path.resolve())
    if skip_if_exists and db.trip_exists_for_fit(fit_str):
        print(f"  Skipping {fit_path.name} — already ingested.")
        return None

    stream = Stream.from_file(str(fit_path))
    decoder = Decoder(stream)
    messages, errors = decoder.read(
        apply_scale_and_offset=True,
        convert_datetimes_to_dates=True,
        convert_types_to_strings=True,
    )

    if errors:
        print(f"  WARNING: FIT decode errors in {fit_path.name}: {errors[:3]}")

    # --- Extract session message -----------------------------------------
    sessions = messages.get("session_mesgs", [])
    if not sessions:
        print(f"  ERROR: No session data found in {fit_path.name}")
        return None

    session = sessions[0]
    start_dt = session.get("start_time")
    elapsed_s = session.get("total_elapsed_time")  # seconds

    if start_dt is None:
        print(f"  ERROR: No start_time in {fit_path.name}")
        return None

    start_str = _to_utc_str(start_dt)
    duration_hours: Optional[float] = None
    end_str: Optional[str] = None

    if elapsed_s is not None:
        from datetime import timedelta
        start_dt_obj = start_dt if isinstance(start_dt, datetime) else None
        if start_dt_obj:
            if start_dt_obj.tzinfo is None:
                start_dt_obj = start_dt_obj.replace(tzinfo=timezone.utc)
            end_dt_obj = start_dt_obj + timedelta(seconds=float(elapsed_s))
            end_str = end_dt_obj.astimezone(timezone.utc).isoformat()
            duration_hours = float(elapsed_s) / 3600.0

    if end_str is None:
        end_str = start_str  # fallback

    # --- Extract GPS track records ----------------------------------------
    records = messages.get("record_mesgs", [])
    track_rows: list[dict] = []
    lats: list[float] = []
    lons: list[float] = []

    for rec in records:
        ts = rec.get("timestamp")
        lat = rec.get("position_lat")
        lon = rec.get("position_long")
        alt = rec.get("altitude")
        spd = rec.get("speed")

        ts_str = _to_utc_str(ts) if ts else start_str

        track_rows.append({
            "ts": ts_str,
            "lat": lat,
            "lon": lon,
            "altitude_m": alt,
            "speed_mps": spd,
        })
        if lat is not None and lon is not None:
            lats.append(lat)
            lons.append(lon)

    # Centroid
    if lats and lons:
        centroid_lat = mean(lats)
        centroid_lon = mean(lons)
    else:
        # Fall back to session position if available
        centroid_lat = session.get("start_position_lat", 0.0) or 0.0
        centroid_lon = session.get("start_position_long", 0.0) or 0.0

    noaa_station = _nearest_station(centroid_lat, centroid_lon)

    trip_date = start_str[:10] if start_str else "unknown"

    trip = Trip(
        trip_date=trip_date,
        start_time=start_str,
        end_time=end_str,
        duration_hours=duration_hours,
        lat=centroid_lat,
        lon=centroid_lon,
        fit_file_path=fit_str,
        noaa_station_id=noaa_station,
    )

    trip_id = db.insert_trip(trip)
    if track_rows:
        db.insert_gps_track(trip_id, track_rows)

    n_pts = len([r for r in track_rows if r["lat"] is not None])
    print(
        f"  Ingested {fit_path.name}: trip_id={trip_id}, "
        f"{n_pts} GPS points, {duration_hours:.2f}h" if duration_hours else
        f"  Ingested {fit_path.name}: trip_id={trip_id}, {n_pts} GPS points"
    )
    return trip_id


def ingest_all(fits_dir: Path = config.FITS_DIR) -> list[int]:
    """Ingest all .FIT files in fits_dir that haven't been ingested yet."""
    fits = sorted(fits_dir.glob("*.fit")) + sorted(fits_dir.glob("*.FIT"))
    if not fits:
        print(f"No .FIT files found in {fits_dir}")
        return []

    trip_ids: list[int] = []
    for f in fits:
        tid = ingest_fit(f)
        if tid is not None:
            trip_ids.append(tid)
    return trip_ids
