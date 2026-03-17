"""
Import legacy trip data from a Google Sheets CSV export.

One-time historical import: conditions are NOT imported from the sheet;
run `enrich --all` afterwards to backfill environmental data via APIs.
"""

import csv
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from pipeline import db
from pipeline.ingest_fit import _nearest_station
from pipeline.models import Trip


def _resolve_timezone(lat: float, lon: float) -> str:
    """Return IANA timezone string for a lat/lon, fallback to UTC."""
    try:
        from timezonefinder import TimezoneFinder
        tz = TimezoneFinder().timezone_at(lat=lat, lng=lon)
        return tz or "UTC"
    except Exception:
        return "UTC"


def _local_to_utc(time_str: str, trip_date: str, tz_str: str) -> Optional[str]:
    """Convert 'HH:MM' local time + trip_date to UTC ISO 8601 string."""
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        try:
            from backports.zoneinfo import ZoneInfo  # type: ignore
        except ImportError:
            ZoneInfo = None

    try:
        dt = datetime.strptime(f"{trip_date} {time_str}", "%Y-%m-%d %H:%M")
        if ZoneInfo and tz_str and tz_str != "UTC":
            dt = dt.replace(tzinfo=ZoneInfo(tz_str))
        else:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def import_trips_csv(csv_path: Path) -> list[int]:
    """
    Import legacy trip rows from a CSV file exported from Google Sheets.

    Expected columns (order doesn't matter, header required):
      date            YYYY-MM-DD (required)
      location_name   Must match a key in config.LOCATION_COORDS (required)
      start_time      HH:MM local (optional)
      end_time        HH:MM local (optional)
      duration_hours  Float; computed from start/end if blank (optional)
      water_body      Defaults to 'saltwater' (optional)
      notes           Free text (optional)

    Returns list of inserted trip IDs.
    """
    db.init_db()
    inserted_ids: list[int] = []

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):  # row 1 = header
            trip_date = row.get("date", "").strip()
            location_name = row.get("location_name", "").strip()

            if not trip_date or not location_name:
                print(f"  Row {i}: SKIPPED — missing date or location_name")
                continue

            coords = config.LOCATION_COORDS.get(location_name)
            if coords is None:
                print(
                    f"  Row {i}: SKIPPED — location '{location_name}' not found in "
                    "config.LOCATION_COORDS"
                )
                continue

            lat, lon = coords

            if db.trip_exists_for_date_location(trip_date, location_name):
                print(f"  Row {i}: SKIPPED — trip already exists ({trip_date} / {location_name})")
                continue

            # Resolve timezone once per location
            tz_str = _resolve_timezone(lat, lon)

            start_raw = row.get("start_time", "").strip()
            end_raw = row.get("end_time", "").strip()
            dur_raw = row.get("duration_hours", "").strip()

            if start_raw:
                start_utc = _local_to_utc(start_raw, trip_date, tz_str)
                if start_utc is None:
                    print(f"  Row {i}: WARNING — could not parse start_time '{start_raw}', using midnight UTC")
                    start_utc = f"{trip_date}T00:00:00+00:00"
            else:
                start_utc = f"{trip_date}T00:00:00+00:00"

            if end_raw:
                end_utc = _local_to_utc(end_raw, trip_date, tz_str)
                if end_utc is None:
                    print(f"  Row {i}: WARNING — could not parse end_time '{end_raw}', using start_time")
                    end_utc = start_utc
            else:
                end_utc = start_utc

            duration_hours: Optional[float] = None
            if dur_raw:
                try:
                    duration_hours = float(dur_raw)
                except ValueError:
                    pass
            elif start_raw and end_raw and start_utc != end_utc:
                try:
                    from datetime import timedelta
                    from zoneinfo import ZoneInfo
                    fmt = "%Y-%m-%dT%H:%M:%S%z"
                    # isoformat strings include offset like +00:00; fromisoformat handles this
                    s = datetime.fromisoformat(start_utc)
                    e = datetime.fromisoformat(end_utc)
                    duration_hours = (e - s).total_seconds() / 3600.0
                except Exception:
                    pass

            noaa_station = _nearest_station(lat, lon)
            water_body = row.get("water_body", "").strip() or "saltwater"
            notes = row.get("notes", "").strip() or None

            trip = Trip(
                trip_date=trip_date,
                start_time=start_utc,
                end_time=end_utc,
                duration_hours=duration_hours,
                lat=lat,
                lon=lon,
                location_name=location_name,
                water_body=water_body,
                noaa_station_id=noaa_station,
                notes=notes,
            )

            trip_id = db.insert_trip(trip)
            inserted_ids.append(trip_id)
            dur_str = f"{duration_hours:.2f}h" if duration_hours is not None else "duration unknown"
            print(f"  Row {i}: IMPORTED trip_id={trip_id} — {trip_date} @ {location_name} ({dur_str})")

    print(f"\nDone. {len(inserted_ids)} new trip(s) imported from {csv_path.name}.")
    return inserted_ids
