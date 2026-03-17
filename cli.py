#!/usr/bin/env python3
"""
Fishing Log CLI — entry point for all pipeline subcommands.

Usage:
  python cli.py ingest <fit_file>
  python cli.py ingest --all
  python cli.py log-catch <trip_id>
  python cli.py import-trips <csv_file>
  python cli.py import-catches <csv_file>
  python cli.py enrich <trip_id>
  python cli.py enrich --all
  python cli.py analyze
  python cli.py analyze --by <dimension>
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent))

import config
from pipeline import db


def cmd_ingest(args):
    db.init_db()
    from pipeline.ingest_fit import ingest_fit, ingest_all

    if args.all:
        trip_ids = ingest_all(config.FITS_DIR)
        print(f"Ingested {len(trip_ids)} new trip(s).")
    elif args.fit_file:
        fit_path = Path(args.fit_file)
        if not fit_path.exists():
            print(f"ERROR: File not found: {fit_path}")
            sys.exit(1)
        tid = ingest_fit(fit_path)
        if tid:
            print(f"Trip {tid} created.")
    else:
        print("ERROR: Provide a .FIT file path or --all")
        sys.exit(1)


def cmd_log_catch(args):
    from pipeline.catch_entry import log_catch_interactive
    log_catch_interactive(args.trip_id)


def cmd_import_trips(args):
    from pipeline.import_sheets import import_trips_csv
    csv_path = Path(args.csv_file)
    if not csv_path.exists():
        print(f"ERROR: File not found: {csv_path}")
        sys.exit(1)
    trip_ids = import_trips_csv(csv_path)
    print(f"{len(trip_ids)} new trip(s) imported.")


def cmd_import_catches(args):
    from pipeline.catch_entry import import_catches_csv
    csv_path = Path(args.csv_file)
    if not csv_path.exists():
        print(f"ERROR: File not found: {csv_path}")
        sys.exit(1)
    import_catches_csv(csv_path)


def cmd_enrich(args):
    from pipeline.fetch_env import enrich_trip

    if args.all:
        trips = db.get_trips_missing_env()
        if not trips:
            print("All trips already have environmental data.")
            return
        print(f"Enriching {len(trips)} trip(s)...")
        success = 0
        for trip in trips:
            if enrich_trip(trip["id"]):
                success += 1
        print(f"Done. {success}/{len(trips)} enriched successfully.")
    elif args.trip_id is not None:
        enrich_trip(args.trip_id)
    else:
        print("ERROR: Provide a trip_id or --all")
        sys.exit(1)


def cmd_analyze(args):
    from pipeline.analysis import (
        print_catch_rates,
        print_pattern_summary,
        export_summary_csv,
        VALID_DIMENSIONS,
    )

    if args.export:
        dim = args.by or "tide_phase"
        out = config.REPORTS_DIR / f"summary_{dim}.csv"
        export_summary_csv(dim, out)
        return

    if args.by:
        if args.by not in VALID_DIMENSIONS:
            print(f"ERROR: --by must be one of: {', '.join(VALID_DIMENSIONS)}")
            sys.exit(1)
        print_pattern_summary(args.by)
    else:
        # Default: show all
        print_catch_rates()
        for dim in VALID_DIMENSIONS:
            print_pattern_summary(dim)


def main():
    parser = argparse.ArgumentParser(
        prog="fishing-log",
        description="Personal fishing log pipeline",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ingest
    p_ingest = sub.add_parser(
        "ingest",
        help=(
            "Decode FIT file(s) into database. "
            "Place exported .FIT files in FISHING_LOG_FITS_DIR (default: data/fits/) "
            "then run with --all."
        ),
    )
    p_ingest.add_argument("fit_file", nargs="?", help="Path to .FIT file")
    p_ingest.add_argument(
        "--all",
        action="store_true",
        help="Process all .FIT files in FISHING_LOG_FITS_DIR (default: data/fits/)",
    )

    # log-catch
    p_log = sub.add_parser("log-catch", help="Interactive catch entry for a trip")
    p_log.add_argument("trip_id", type=int, help="Trip ID")

    # import-trips
    p_import_trips = sub.add_parser(
        "import-trips",
        help="Import legacy trip rows from a Google Sheets CSV export",
    )
    p_import_trips.add_argument("csv_file", help="Path to trips CSV file")

    # import-catches
    p_import = sub.add_parser("import-catches", help="Bulk catch import from CSV")
    p_import.add_argument("csv_file", help="Path to CSV file")

    # enrich
    p_enrich = sub.add_parser("enrich", help="Fetch environmental data for trip(s)")
    p_enrich.add_argument("trip_id", nargs="?", type=int, help="Trip ID")
    p_enrich.add_argument("--all", action="store_true", help="Enrich all trips missing env data")

    # analyze
    p_analyze = sub.add_parser("analyze", help="Print catch rate pattern analysis")
    p_analyze.add_argument(
        "--by",
        metavar="DIMENSION",
        help="Group by: tide_phase, pressure_trend, weather_category, trip_sun_phase, wind_cardinal, tide_type",
    )
    p_analyze.add_argument(
        "--export",
        action="store_true",
        help="Export summary to CSV in reports/",
    )

    args = parser.parse_args()

    dispatch = {
        "ingest": cmd_ingest,
        "log-catch": cmd_log_catch,
        "import-trips": cmd_import_trips,
        "import-catches": cmd_import_catches,
        "enrich": cmd_enrich,
        "analyze": cmd_analyze,
    }

    dispatch[args.command](args)


if __name__ == "__main__":
    main()
