"""
Catch logging: interactive CLI prompt and CSV batch import.
"""

import csv
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline import db
from pipeline.models import Catch


def _parse_local_time(time_str: str, trip_date: str, tz_str: str) -> Optional[str]:
    """
    Parse "HH:MM" local time string, combine with trip_date, and convert to UTC ISO string.
    Returns None if parsing fails.
    """
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        try:
            from backports.zoneinfo import ZoneInfo  # type: ignore
        except ImportError:
            ZoneInfo = None

    try:
        dt_local = datetime.strptime(f"{trip_date} {time_str}", "%Y-%m-%d %H:%M")
        if ZoneInfo and tz_str and tz_str != "UTC":
            dt_local = dt_local.replace(tzinfo=ZoneInfo(tz_str))
        else:
            dt_local = dt_local.replace(tzinfo=timezone.utc)
        return dt_local.astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def _prompt(label: str, default: str = "") -> str:
    if default:
        return input(f"  {label} [{default}]: ").strip() or default
    return input(f"  {label}: ").strip()


def log_catch_interactive(trip_id: int) -> int:
    """
    Interactively prompt for catch entries for a trip.
    Returns number of catches entered.
    """
    db.init_db()
    trip = db.get_trip(trip_id)
    if trip is None:
        print(f"ERROR: Trip {trip_id} not found.")
        return 0

    trip_date = trip["trip_date"]
    lat = trip["lat"]
    lon = trip["lon"]

    from pipeline.derive_metrics import get_timezone
    tz_str = get_timezone(lat, lon)

    print(f"\nLogging catches for trip {trip_id} ({trip_date})")
    print(f"Local timezone: {tz_str}")
    print("Type 'done' at any prompt to finish.\n")

    count = 0
    while True:
        species = _prompt("Species (or 'done' to finish)")
        if species.lower() in ("done", ""):
            break

        time_raw = _prompt("Time caught (HH:MM local, or blank if unknown)")
        caught_at: Optional[str] = None
        if time_raw and time_raw.lower() != "done":
            caught_at = _parse_local_time(time_raw, trip_date, tz_str)
            if caught_at is None:
                print(f"  (could not parse '{time_raw}', leaving time unknown)")

        length_raw = _prompt("Length (cm, or blank)")
        length_cm: Optional[float] = float(length_raw) if length_raw else None

        weight_raw = _prompt("Weight (kg, or blank)")
        weight_kg: Optional[float] = float(weight_raw) if weight_raw else None

        kept_raw = _prompt("Kept? (y/n)", "y")
        kept = 0 if kept_raw.lower() in ("n", "no") else 1

        notes = _prompt("Notes (or blank)")

        catch = Catch(
            trip_id=trip_id,
            species=species,
            caught_at=caught_at,
            length_cm=length_cm,
            weight_kg=weight_kg,
            kept=kept,
            notes=notes or None,
        )
        catch_id = db.insert_catch(catch)
        count += 1
        print(f"  Saved catch #{catch_id}\n")

    print(f"Done. {count} catch(es) logged for trip {trip_id}.")
    return count


def import_catches_csv(csv_path: Path) -> int:
    """
    Bulk-import catches from a CSV file.

    Expected columns (order doesn't matter, header required):
      trip_id      Integer trip ID (required unless trip_date + location_name are provided)
      trip_date    YYYY-MM-DD — used when trip_id is blank to look up the trip
      location_name Paired with trip_date to find the trip when trip_id is blank
      caught_at    ISO 8601 or blank (time unknown)
      species      Text
      length_cm    Float
      weight_kg    Float
      kept         1 (default) or 0
      notes        Text

    Returns number of rows imported.
    """
    db.init_db()
    count = 0

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):
            def _float(v: str) -> Optional[float]:
                v = v.strip()
                return float(v) if v else None

            def _int(v: str) -> int:
                v = v.strip()
                return int(v) if v else 1

            trip_id_raw = row.get("trip_id", "").strip()
            if trip_id_raw:
                trip_id = int(trip_id_raw)
            else:
                trip_date = row.get("trip_date", "").strip()
                location_name = row.get("location_name", "").strip()
                if not trip_date or not location_name:
                    print(f"  Row {i}: SKIPPED — no trip_id and missing trip_date/location_name")
                    continue
                trip_row = db.get_trip_by_date_location(trip_date, location_name)
                if trip_row is None:
                    print(
                        f"  Row {i}: SKIPPED — no trip found for {trip_date} / {location_name}"
                    )
                    continue
                trip_id = trip_row["id"]

            catch = Catch(
                trip_id=trip_id,
                caught_at=row.get("caught_at", "").strip() or None,
                species=row.get("species", "").strip() or None,
                length_cm=_float(row.get("length_cm", "")),
                weight_kg=_float(row.get("weight_kg", "")),
                kept=_int(row.get("kept", "1")),
                notes=row.get("notes", "").strip() or None,
            )
            db.insert_catch(catch)
            count += 1

    print(f"Imported {count} catches from {csv_path.name}.")
    return count
