"""
daily_agent.py — Time-budgeted Facebook Marketplace listing agent.

Priority order each run:
  0. Remove FB-flagged duplicate listings; record their slots in duplicate_history.json
  1. Publish new slots (not yet in state, not in dupe history)
  2. Replace non-duplicate existing slots (all that fit in budget)
  3. Re-list previously-duplicate slots (end of queue)

Scheduling: Tue–Sun via Windows Task Scheduler (see setup_schedule.ps1).
Jitter: random 0–25 min sleep at startup + random 50–75 min runtime budget.
"""

import argparse
import json
import logging
import os
import random
import shutil
import time
from datetime import datetime, timezone

import requests
from selenium.common.exceptions import InvalidSessionIdException, NoSuchWindowException

from helpers.ads import get_listings
from helpers.scraper import Scraper
from helpers.listing_helper import Listing

# ── Args ──────────────────────────────────────────────────────────────────────
_parser = argparse.ArgumentParser(description="FB Marketplace daily listing agent")
_parser.add_argument("--no-jitter", action="store_true", help="Skip startup random delay (useful for manual runs)")
_args = _parser.parse_args()

# ── Config ────────────────────────────────────────────────────────────────────
BUDGET_MIN_MIN = 50
BUDGET_MAX_MIN = 75
JITTER_MAX_MIN = 25

STATE_FILE = "state.json"
DUPE_HISTORY_FILE = "data/duplicate_history.json"
LOG_FILE = "listing_progress.log"
OUTPUT_DIR = "./images/output/"

SUMO_ENDPOINT = (
    "https://endpoint4.collection.sumologic.com/receiver/v1/http/"
    "ZaVnC4dhaV1WAXKlyVji5qYz_JFGGVzGAmMiumPVN4oprAXf1_b8seo08i1q9WXgAGF5GcYAxtgdmv9q-g54LzeLLW5JtGwEXJD3hTt-WQvT2cqJLTiUuA=="
)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, mode="a")],
)
logger = logging.getLogger(__name__)

# ── Sumo Logic ────────────────────────────────────────────────────────────────
with open("data/cities_data.json") as _f:
    _CITY_LOOKUP = {c["city"]: c for c in json.load(_f)}


def _sumo_post(payload: dict):
    try:
        requests.post(
            SUMO_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
    except Exception as e:
        logger.warning(f"Sumo Logic send failed: {e}")


def _log_published(listable, city: str):
    city_data = _CITY_LOOKUP.get(city, {})
    _sumo_post(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "published",
            "title": listable.title,
            "city": city,
            "state": city_data.get("state", "TX"),
            "lat": float(city_data["lat"]) if city_data.get("lat") else None,
            "lng": float(city_data["lng"]) if city_data.get("lng") else None,
            "equipment_type": listable.equipment_type,
        }
    )


# ── Startup jitter ────────────────────────────────────────────────────────────
if _args.no_jitter:
    logger.info("Agent starting — jitter skipped (--no-jitter)")
else:
    _jitter_secs = random.uniform(0, JITTER_MAX_MIN * 60)
    logger.info(f"Agent starting — jitter delay: {_jitter_secs / 60:.1f} min")
    time.sleep(_jitter_secs)

# ── Time budget ───────────────────────────────────────────────────────────────
_budget_secs = random.uniform(BUDGET_MIN_MIN * 60, BUDGET_MAX_MIN * 60)
_deadline = time.time() + _budget_secs
logger.info(
    f"Budget: {_budget_secs / 60:.1f} min — deadline "
    f"{datetime.fromtimestamp(_deadline).strftime('%H:%M:%S')}"
)


def within_budget(buffer_secs: int = 180) -> bool:
    """True when at least buffer_secs remain before the hard deadline."""
    return (_deadline - time.time()) > buffer_secs


# ── State I/O ─────────────────────────────────────────────────────────────────
def _load_json(path: str) -> dict:
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def _dump_json(path: str, data: dict):
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


state = _load_json(STATE_FILE)
dupe_history = _load_json(DUPE_HISTORY_FILE)


def _save_state():
    _dump_json(STATE_FILE, state)


def _save_dupe_history():
    _dump_json(DUPE_HISTORY_FILE, dupe_history)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _make_slot(listable) -> str:
    city = listable.location.split(", ")[0]
    return f"{listable.equipment_type}_{city}_{listable.lang}"


def _cleanup_images():
    if os.path.exists(OUTPUT_DIR):
        def _force_rm(func, path, _):
            os.chmod(path, 0o777)
            func(path)
        shutil.rmtree(OUTPUT_DIR, onerror=_force_rm)
    os.makedirs(OUTPUT_DIR, exist_ok=True)


# ── Scraper / Listing init ────────────────────────────────────────────────────
scraper = Scraper("https://facebook.com")
scraper.add_login_functionality(
    "https://facebook.com", 'svg[aria-label="Your profile"]', "facebook"
)
l = Listing(scraper)

_cleanup_images()

# ── Phase 0: Remove FB-flagged duplicates ─────────────────────────────────────
logger.info("Phase 0 — removing FB-flagged duplicate listings...")
scraper.go_to_page("https://www.facebook.com/marketplace/you/selling/")

removed_titles = l.remove_duplicate_listings()
title_to_slot = {title: slot for slot, title in state.items()}

for title in removed_titles:
    if not title:
        logger.warning("Phase 0 — removed a duplicate but could not resolve its title.")
        continue
    slot = title_to_slot.get(title)
    if slot:
        dupe_history[slot] = datetime.now(timezone.utc).isoformat()
        del state[slot]
        logger.info(f"Phase 0 — slot '{slot}' marked duplicate-removed.")
    else:
        logger.warning(f"Phase 0 — removed duplicate '{title}' but slot not found in state.")

_save_state()
_save_dupe_history()

# Snapshot of slots that existed before Phase 1 (Phase 2 will only replace these)
_pre_phase1_slots = set(state.keys())

# ── Publish helper ────────────────────────────────────────────────────────────
def _publish(listable) -> bool:
    """Publish one listing. Returns False on fatal session error, True otherwise."""
    slot = _make_slot(listable)
    logger.info(f"Publishing slot '{slot}': {listable.title}")
    try:
        l.update_listings(listings=[listable], listing_type="item")
    except (InvalidSessionIdException, NoSuchWindowException):
        logger.error("Chrome session died — stopping. Re-run to resume from state.json.")
        return False
    except Exception as e:
        logger.error(f"Listing '{listable.title}' failed: {e}", exc_info=True)
        return True  # non-fatal

    city = listable.location.split(", ")[0]
    _log_published(listable, city)
    state[slot] = listable.title
    _save_state()
    return True


# ── Phase 1: Publish new slots ────────────────────────────────────────────────
logger.info("Phase 1 — publishing new slots...")
fatal = False

for listable in get_listings(output_directory=OUTPUT_DIR):
    if not within_budget():
        logger.info("Phase 1 — budget exhausted, stopping.")
        break
    if not hasattr(listable, "equipment_type") or not hasattr(listable, "lang"):
        _cleanup_images()
        continue

    slot = _make_slot(listable)
    if slot in _pre_phase1_slots or slot in dupe_history or slot in state:
        _cleanup_images()
        continue

    if not _publish(listable):
        fatal = True
        break
    _cleanup_images()

# ── Phase 2: Replace non-duplicate existing slots ─────────────────────────────
if not fatal and within_budget():
    logger.info("Phase 2 — replacing non-duplicate existing slots...")

    # Snapshot click counts before any deletions
    scraper.go_to_page("https://www.facebook.com/marketplace/you/selling/")
    click_counts = l.collect_click_snapshots()
    logger.info(f"Phase 2 — click snapshot: {len(click_counts)} listings.")

    _cleanup_images()
    for listable in get_listings(output_directory=OUTPUT_DIR):
        if not within_budget():
            logger.info("Phase 2 — budget exhausted, stopping.")
            break
        if not hasattr(listable, "equipment_type") or not hasattr(listable, "lang"):
            _cleanup_images()
            continue

        slot = _make_slot(listable)
        if slot not in _pre_phase1_slots or slot in dupe_history:
            _cleanup_images()
            continue

        old_title = state[slot]
        logger.info(f"Phase 2 — replacing '{slot}': removing '{old_title}'")
        scraper.go_to_page("https://www.facebook.com/marketplace/you/selling/")
        l.remove_listing_by_title(old_title)

        if not _publish(listable):
            fatal = True
            break
        _cleanup_images()

# ── Phase 3: Re-list previously-duplicate slots ───────────────────────────────
if not fatal and within_budget():
    logger.info("Phase 3 — re-listing previously-duplicate slots (end of queue)...")

    _cleanup_images()
    for listable in get_listings(output_directory=OUTPUT_DIR):
        if not within_budget():
            logger.info("Phase 3 — budget exhausted, stopping.")
            break
        if not hasattr(listable, "equipment_type") or not hasattr(listable, "lang"):
            _cleanup_images()
            continue

        slot = _make_slot(listable)
        if slot not in dupe_history:
            _cleanup_images()
            continue

        logger.info(f"Phase 3 — re-listing previously-duplicate slot: {slot}")
        if not _publish(listable):
            fatal = True
            break

        del dupe_history[slot]
        _save_dupe_history()
        _cleanup_images()

# ── Done ──────────────────────────────────────────────────────────────────────
remaining = max(0, _deadline - time.time())
logger.info(
    f"Agent run complete. "
    f"Remaining budget: {remaining / 60:.1f} min. "
    f"Fatal stop: {fatal}."
)
