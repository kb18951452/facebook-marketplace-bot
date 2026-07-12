"""
stats_tracker.py — Hourly stats collector.

Scrapes the FB Marketplace selling page for clicks, price, views, age, and
duplicate flags, then merges results into data/slot_metadata.json.

Runtime: ~3–5 minutes (read-only, no publishing, no deletions).
Runs hourly via FacebookStatsTracker_Hourly scheduled task.

Usage:
    python stats_tracker.py
"""

import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone

from helpers.scraper import Scraper
from helpers.listing_helper import Listing
from helpers.click_history import record_snapshot
from helpers.scan_health import record_scan
from helpers.run_outcome import install_crash_logger, record_run

# ── Config ────────────────────────────────────────────────────────────────────
STATE_FILE    = "state.json"
DUPE_FILE     = "data/duplicate_history.json"
METADATA_FILE = "data/slot_metadata.json"
LOG_FILE      = "listing_progress.log"

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, mode="a")],
)
logger = logging.getLogger(__name__)
install_crash_logger("stats_tracker")

# ── State I/O ─────────────────────────────────────────────────────────────────
def _load(path: str) -> dict:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}

def _save(path: str, data: dict):
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

state    = _load(STATE_FILE)
metadata = _load(METADATA_FILE)
title_to_slot = {title: slot for slot, title in state.items()}

# ── Scraper init ──────────────────────────────────────────────────────────────
logger.info("Stats tracker starting...")
scraper = Scraper("https://facebook.com")
scraper.add_login_functionality(
    "https://facebook.com", 'svg[aria-label="Your profile"]', "facebook"
)
l = Listing(scraper)

# ── Collect ───────────────────────────────────────────────────────────────────
logger.info("Navigating to selling page...")
scraper.go_to_page("https://www.facebook.com/marketplace/you/selling/")

logger.info("Collecting listing stats...")
listing_stats = l.collect_listing_stats()
logger.info(f"Found {len(listing_stats)} listings on selling page.")
record_scan("stats_tracker", len(listing_stats))

# ── Merge into metadata ───────────────────────────────────────────────────────
now = datetime.now(timezone.utc).isoformat()
matched = 0
unmatched = []

for title, stats in listing_stats.items():
    slot = title_to_slot.get(title)
    if not slot:
        unmatched.append(title)
        continue
    matched += 1

    metadata.setdefault(slot, {})
    m = metadata[slot]

    # Rolling click snapshots — always record every run so 7-day delta is computable from any point
    record_snapshot(metadata, slot, stats["clicks"], ts=now)

    if stats["views"] is not None:
        m["last_views"] = stats["views"]
        m["last_views_at"] = now

    if stats["price"] is not None:
        m["price"] = stats["price"]

    if stats["days_listed_fb"] is not None:
        m["days_listed_fb"] = stats["days_listed_fb"]
        m["days_listed_at"] = now

    if stats["is_duplicate"]:
        m["fb_duplicate_flag"] = True
        m["fb_duplicate_flagged_at"] = now
        logger.warning(f"Duplicate flag active on slot '{slot}'")
    else:
        m.pop("fb_duplicate_flag", None)
        m.pop("fb_duplicate_flagged_at", None)

_save(METADATA_FILE, metadata)

logger.info(
    f"Stats tracker complete — matched {matched} listings, "
    f"{len(unmatched)} unmatched titles."
)
if unmatched:
    logger.info(f"Unmatched titles (not in state.json): {unmatched[:10]}")

record_run(
    "stats_tracker",
    "no-op" if matched == 0 else "success",
    metrics={"found": len(listing_stats), "matched": matched, "unmatched": len(unmatched)},
    note=None if matched else "0 listings matched state.json — scrape may have failed or state.json is stale",
)

# Keep the viewer up to date after every stats collection.
try:
    subprocess.run([sys.executable, "map_listings.py"], check=False, timeout=30)
    logger.info("Map regenerated.")
except Exception as _e:
    logger.warning(f"Map regeneration failed: {_e}")
