"""
Catch rate analysis and pattern summaries.
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from pipeline import db

# Environmental dimensions available for GROUP BY analysis
VALID_DIMENSIONS = [
    "tide_phase",
    "pressure_trend",
    "weather_category",
    "trip_sun_phase",
    "wind_cardinal",
    "tide_type",
]


def _col_width(rows: list[list], col: int, header_len: int) -> int:
    data_max = max((len(str(r[col])) for r in rows), default=0)
    return max(data_max, header_len) + 2


def _print_table(headers: list[str], rows: list[list]) -> None:
    widths = [_col_width(rows, i, len(h)) for i, h in enumerate(headers)]
    sep = "+" + "+".join("-" * w for w in widths) + "+"
    def fmt_row(r):
        return "|" + "|".join(f" {str(v):<{w-2}} " for v, w in zip(r, widths)) + "|"
    print(sep)
    print(fmt_row(headers))
    print(sep)
    for row in rows:
        print(fmt_row(row))
    print(sep)


def catch_rate_by_trip(db_path=config.DB_PATH) -> list[dict]:
    """Return per-trip catch rate (catches / hour)."""
    conn = db.get_conn(db_path)
    rows = conn.execute("""
        SELECT
            t.id,
            t.trip_date,
            t.location_name,
            t.duration_hours,
            COUNT(c.id) AS catch_count,
            CASE
                WHEN t.duration_hours > 0
                THEN ROUND(COUNT(c.id) * 1.0 / t.duration_hours, 2)
                ELSE NULL
            END AS catch_rate
        FROM trips t
        LEFT JOIN catches c ON c.trip_id = t.id
        GROUP BY t.id
        ORDER BY t.trip_date DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def pattern_summary(group_by: str, db_path=config.DB_PATH) -> list[dict]:
    """
    Return catch rate grouped by an environmental dimension.

    Parameters
    ----------
    group_by : str
        One of VALID_DIMENSIONS.
    """
    if group_by not in VALID_DIMENSIONS:
        raise ValueError(
            f"Invalid group_by '{group_by}'. Choose from: {', '.join(VALID_DIMENSIONS)}"
        )

    conn = db.get_conn(db_path)
    rows = conn.execute(f"""
        SELECT
            e.{group_by} AS condition,
            COUNT(DISTINCT t.id) AS trips,
            SUM(t.duration_hours) AS total_hours,
            COUNT(c.id) AS total_catches,
            CASE
                WHEN SUM(t.duration_hours) > 0
                THEN ROUND(COUNT(c.id) * 1.0 / SUM(t.duration_hours), 3)
                ELSE NULL
            END AS catch_rate
        FROM trips t
        JOIN environmental_data e ON e.trip_id = t.id
        LEFT JOIN catches c ON c.trip_id = t.id
        GROUP BY e.{group_by}
        ORDER BY catch_rate DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def print_catch_rates(db_path=config.DB_PATH) -> None:
    """Print per-trip catch rate table."""
    rows = catch_rate_by_trip(db_path)
    if not rows:
        print("No trips found. Run 'ingest' first.")
        return
    table_rows = [
        [r["id"], r["trip_date"], r["location_name"] or "—",
         f"{r['duration_hours']:.2f}h" if r["duration_hours"] else "—",
         r["catch_count"],
         r["catch_rate"] if r["catch_rate"] is not None else "—"]
        for r in rows
    ]
    print("\n=== Catch Rate by Trip ===")
    _print_table(
        ["ID", "Date", "Location", "Duration", "Catches", "Rate/hr"],
        table_rows,
    )


def print_pattern_summary(group_by: str, db_path=config.DB_PATH) -> None:
    """Print pattern summary table for a given dimension."""
    rows = pattern_summary(group_by, db_path)
    if not rows:
        print(f"No data for dimension '{group_by}'. Enrich trips first.")
        return

    table_rows = [
        [r["condition"] or "NULL", r["trips"],
         f"{r['total_hours']:.1f}" if r["total_hours"] else "—",
         r["total_catches"],
         r["catch_rate"] if r["catch_rate"] is not None else "—"]
        for r in rows
    ]
    print(f"\n=== Catch Rate by {group_by} ===")
    _print_table(
        [group_by, "Trips", "Total Hours", "Catches", "Rate/hr"],
        table_rows,
    )


def export_summary_csv(group_by: str, out_path: Path, db_path=config.DB_PATH) -> None:
    """Export pattern summary to CSV."""
    rows = pattern_summary(group_by, db_path)
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["condition", "trips", "total_hours", "total_catches", "catch_rate"]
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Exported {len(rows)} rows to {out_path}")
