"""
Central configuration for the fishing log pipeline.
Edit this file to match your fishing locations and preferences.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = Path(os.environ.get("FISHING_LOG_DATA_DIR", BASE_DIR / "data"))
FITS_DIR = DATA_DIR / "fits"
DB_PATH = DATA_DIR / "fishing_log.db"
REPORTS_DIR = BASE_DIR / "reports"

# ---------------------------------------------------------------------------
# NOAA Tide Stations
# Map location names (used in trips.location_name) to NOAA CO-OPS station IDs.
# Find station IDs at: https://tidesandcurrents.noaa.gov/stations.html
# ---------------------------------------------------------------------------
NOAA_STATION_IDS: dict[str, str] = {
    "Chesapeake Bay": "8638610",    # Sewells Point, VA
    "Outer Banks": "8654467",       # Hatteras Inlet, NC
    "Cape Cod": "8443970",          # Boston, MA (nearest major)
    "Florida Keys": "8724580",      # Key West, FL
    "Gulf of Mexico": "8771341",    # Galveston, TX
    # Add your spots:
    # "Your Location": "NOAA_STATION_ID",
}

# ---------------------------------------------------------------------------
# Location Coordinates
# Map location names to (lat, lon) tuples for GPS-less legacy import.
# Must include every location used in imported trips.csv files.
# ---------------------------------------------------------------------------
LOCATION_COORDS: dict[str, tuple[float, float]] = {
    "Chesapeake Bay": (37.0, -76.3),
    "Outer Banks":    (35.9, -75.7),
    "Cape Cod":       (41.8, -70.1),
    "Florida Keys":   (24.7, -81.1),
    "Gulf of Mexico": (27.5, -90.5),
    # Add your spots:
    # "Your Location": (lat, lon),
}

# Default NOAA station to use when location_name is not in the map above.
# Set to None to skip tide enrichment when station can't be determined.
DEFAULT_NOAA_STATION: str | None = None

# ---------------------------------------------------------------------------
# Unit preferences (used in display / analysis output only; DB stores SI)
# ---------------------------------------------------------------------------
DISPLAY_TEMP_UNIT = "F"       # "C" or "F"
DISPLAY_SPEED_UNIT = "mph"    # "mps" or "mph" or "knots"
DISPLAY_LENGTH_UNIT = "in"    # "cm" or "in"
DISPLAY_WEIGHT_UNIT = "lb"    # "kg" or "lb"
