# Fishing Log

Personal saltwater fishing log pipeline. Ingests Garmin `.FIT` activity files, enriches trips with environmental data from free public APIs, and analyzes catch rates against conditions like tide phase, pressure trend, and sun phase.

## Features

- **FIT ingestion** — decode Garmin activity exports into a local SQLite database with full GPS track
- **Environmental enrichment** — automatically fetches weather, water temp, wave height, tides, and solar events for each trip
- **Catch logging** — interactive CLI entry or bulk CSV import
- **Legacy import** — import historical trips from Google Sheets CSV exports
- **Pattern analysis** — catch rate tables grouped by tide phase, pressure trend, weather, wind, and more
- **CSV export** — export summaries to `reports/` for use in spreadsheets

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

```bash
git clone <repo-url>
cd fishing-log

# with uv (recommended)
uv sync

# or with pip
pip install -e .
```

## Configuration

Copy `.env.example` to `.env` and set your data directory:

```bash
cp .env.example .env
```

```env
# .env
FISHING_LOG_DATA_DIR=/path/to/your/nas/fishing-log
```

The database (`fishing_log.db`) and FIT files (`fits/`) both live under `FISHING_LOG_DATA_DIR`. If unset, defaults to `data/` inside the project root.

### Locations and NOAA stations

Edit `config.py` to add your fishing spots:

```python
# Map location names to NOAA CO-OPS station IDs
# Find IDs at: https://tidesandcurrents.noaa.gov/stations.html
NOAA_STATION_IDS = {
    "Your Spot": "1234567",
}

# Map location names to (lat, lon) — required for CSV imports
LOCATION_COORDS = {
    "Your Spot": (38.5, -76.2),
}
```

### Display units

Also in `config.py`:

```python
DISPLAY_TEMP_UNIT   = "F"      # "C" or "F"
DISPLAY_SPEED_UNIT  = "mph"    # "mps", "mph", or "knots"
DISPLAY_LENGTH_UNIT = "in"     # "cm" or "in"
DISPLAY_WEIGHT_UNIT = "lb"     # "kg" or "lb"
```

> The database always stores SI units (°C, m/s, cm, kg). Display units only affect analysis output.

## Usage

### Ingest FIT files

Export activities from Garmin Connect ("Export Original" or bulk Data Export), place the `.fit` files in `<FISHING_LOG_DATA_DIR>/fits/`, then run:

```bash
# Ingest all new FIT files
fishing-log ingest --all

# Ingest a single file
fishing-log ingest path/to/activity.fit
```

Already-ingested files are skipped automatically.

### Enrich with environmental data

Fetches weather, tides, and solar data for each trip using free public APIs (no API keys required):

```bash
# Enrich all trips missing environmental data
fishing-log enrich --all

# Enrich a specific trip
fishing-log enrich 42
```

**APIs used:**
| Data | Source |
|---|---|
| Weather (wind, temp, pressure, clouds, rain) | [Open-Meteo Archive](https://open-meteo.com/) |
| Water temp, wave height | [Open-Meteo Marine](https://marine-api.open-meteo.com/) |
| Tide predictions (high/low) | [NOAA CO-OPS](https://tidesandcurrents.noaa.gov/api/) |
| Sunrise, sunset, solar noon | [sunrise-sunset.org](https://sunrise-sunset.org/api) |

### Log catches

Interactive prompt to add catches to an existing trip:

```bash
fishing-log log-catch <trip_id>
```

Prompts for species, time caught, length, weight, kept/released, and notes. Time is entered in local time and stored as UTC.

### Import legacy data

**Trips from Google Sheets CSV:**

```bash
fishing-log import-trips trips.csv
```

Expected columns: `date`, `location_name`, `start_time` (HH:MM), `end_time` (HH:MM), `duration_hours`, `water_body`, `notes`. Only `date` and `location_name` are required. `location_name` must match a key in `config.LOCATION_COORDS`.

**Catches from CSV:**

```bash
fishing-log import-catches catches.csv
```

Expected columns: `trip_id` (or `trip_date` + `location_name`), `caught_at`, `species`, `length_cm`, `weight_kg`, `kept`, `notes`.

### Analyze

```bash
# Show all catch rate tables
fishing-log analyze

# Group by a specific dimension
fishing-log analyze --by tide_phase
fishing-log analyze --by pressure_trend
fishing-log analyze --by weather_category
fishing-log analyze --by trip_sun_phase
fishing-log analyze --by wind_cardinal
fishing-log analyze --by tide_type

# Export to CSV
fishing-log analyze --by tide_phase --export
```

Available dimensions: `tide_phase`, `pressure_trend`, `weather_category`, `trip_sun_phase`, `wind_cardinal`, `tide_type`.

## Database Schema

SQLite database with four tables:

| Table | Description |
|---|---|
| `trips` | One row per fishing trip — date, time, GPS centroid, duration |
| `catches` | Catch records linked to a trip — species, size, weight, kept/released |
| `environmental_data` | One row per trip — weather, tides, solar, marine conditions |
| `gps_track` | Full GPS track points from FIT files |

## Project Structure

```
fishing-log/
├── cli.py               # CLI entry point
├── config.py            # Locations, units, paths
├── .env.example         # Environment variable template
├── pipeline/
│   ├── models.py        # Trip, Catch, EnvironmentalData dataclasses
│   ├── db.py            # SQLite schema and query helpers
│   ├── ingest_fit.py    # Garmin FIT file decoder
│   ├── fetch_env.py     # External API calls (weather, tides, solar)
│   ├── derive_metrics.py# Pure functions: tide phase, pressure trend, sun phase, etc.
│   ├── analysis.py      # Catch rate queries and table output
│   ├── import_sheets.py # Legacy Google Sheets CSV import
│   ├── catch_entry.py   # Interactive catch logging and CSV import
│   └── fit_watcher.py   # FIT file directory scanner
├── data/                # Default data directory (db + fits/)
└── reports/             # CSV export output
```
