"""Bulk downloader for the two SEC EDGAR datasets this ingestion runs against.

This is the script that replicates the raw data export: given a cache
directory, it re-downloads exactly what the parsers expect, straight from
sec.gov, with no third-party mirror or paid API in between.

SEC enforces a "fair access" policy: every request must carry a User-Agent
identifying a real contact, or it returns 403/429. Set ``EDGAR_USER_AGENT``
to your own contact if you fork this.

Data source pages (for reference / manual browsing):
- https://www.sec.gov/data-research/sec-markets-data/form-d-data-sets
- https://www.sec.gov/foia-services/frequently-requested-documents/form-adv-data
"""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

_FORM_D_BASE = "https://www.sec.gov/files/datastandardsinnovation/data/form-d-data-sets"
# Nov 2011–Dec 2024 historical bulk export, split by SEC into two ZIPs
# (Exempt Reporting Advisers + registered Investment Advisers respectively).
_FORM_ADV_PARTS = {
    "part1": "https://www.sec.gov/files/adv-filing-data-20111105-20241231-part1.zip",
    "part2": "https://www.sec.gov/files/adv-filing-data-20111105-20241231-part2.zip",
}
_TIMEOUT = httpx.Timeout(300.0, connect=30.0)


def form_d_quarter_dir(data_dir: Path, quarter: str) -> Path:
    return data_dir / "form_d" / quarter


def form_adv_dir(data_dir: Path) -> Path:
    return data_dir / "form_adv"


def download_form_d(
    quarter: str, *, settings: Settings | None = None, force: bool = False
) -> Path:
    """Download + extract one quarter (e.g. ``"2026q2"``) of the Form D bulk
    dataset. Returns the directory containing the extracted TSVs."""
    settings = settings or get_settings()
    data_dir = Path(settings.edgar_data_dir)
    dest_dir = form_d_quarter_dir(data_dir, quarter)
    if dest_dir.exists() and not force:
        logger.info("Form D %s already downloaded at %s", quarter, dest_dir)
        return dest_dir

    zip_path = data_dir / "form_d" / f"{quarter}_d.zip"
    _download(f"{_FORM_D_BASE}/{quarter}_d.zip", zip_path, settings)
    _extract_flat(zip_path, dest_dir)
    return dest_dir


def download_form_adv(*, settings: Settings | None = None, force: bool = False) -> Path:
    """Download + extract both parts of the Form ADV bulk dataset (~1.1GB
    zipped). Returns the flat directory containing every extracted CSV."""
    settings = settings or get_settings()
    data_dir = Path(settings.edgar_data_dir)
    dest_dir = form_adv_dir(data_dir)
    if dest_dir.exists() and not force:
        logger.info("Form ADV bulk data already downloaded at %s", dest_dir)
        return dest_dir

    for part, url in _FORM_ADV_PARTS.items():
        zip_path = data_dir / "form_adv" / f"{part}.zip"
        _download(url, zip_path, settings)
        _extract_flat(zip_path, dest_dir)
    return dest_dir


def _download(url: str, dest: Path, settings: Settings) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading %s -> %s", url, dest)
    headers = {"User-Agent": settings.edgar_user_agent}
    with httpx.stream(
        "GET", url, headers=headers, timeout=_TIMEOUT, follow_redirects=True
    ) as resp:
        resp.raise_for_status()
        with dest.open("wb") as f:
            for chunk in resp.iter_bytes(1024 * 1024):
                f.write(chunk)
    logger.info("Downloaded %s (%d bytes)", dest, dest.stat().st_size)


def _extract_flat(zip_path: Path, dest_dir: Path) -> None:
    """Extract every file in the zip directly into ``dest_dir`` (dropping any
    nested top-level folder the archive wraps its contents in)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            target = dest_dir / Path(info.filename).name
            with zf.open(info) as src, target.open("wb") as dst:
                dst.write(src.read())
