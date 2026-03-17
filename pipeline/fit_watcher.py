"""
Scan a local directory for .FIT files exported from Garmin Connect.

To export a single activity: gear icon → "Export Original"
To export in bulk: Garmin Connect → Account → Data Export

Place the exported .fit files in FISHING_LOG_FITS_DIR (default: data/fits/)
then run: fishing-log ingest --all
"""

from pathlib import Path


def scan_fits(fits_dir: Path) -> list[Path]:
    """Return all .fit/.FIT files found in fits_dir."""
    fits_dir = Path(fits_dir)
    if not fits_dir.exists():
        return []
    return sorted(fits_dir.glob("*.[fF][iI][tT]"))
