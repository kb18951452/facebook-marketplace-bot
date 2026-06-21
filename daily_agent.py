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
import subprocess
import sys
import time
from datetime import datetime, timezone

import requests
from selenium.common.exceptions import InvalidSessionIdException, NoSuchWindowException

from helpers.ads import get_listings, get_locations, TASK_VARIANTS
from helpers.scraper import Scraper
from helpers.listing_helper import Listing

# ── Args ──────────────────────────────────────────────────────────────────────
_parser = argparse.ArgumentParser(description="FB Marketplace daily listing agent")
_parser.add_argument("--no-jitter", action="store_true", help="Skip startup random delay (useful for manual runs / supervisor)")
_parser.add_argument("--budget-min", type=float, default=None, help="Override the random runtime budget (minutes). Used by run_session.py.")
_args = _parser.parse_args()

# ── Config ────────────────────────────────────────────────────────────────────
BUDGET_MIN_MIN = 210
BUDGET_MAX_MIN = 250
JITTER_MAX_MIN = 10

STATE_FILE = "state.json"
DUPE_HISTORY_FILE = "data/duplicate_history.json"
METADATA_FILE = "data/slot_metadata.json"
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
if _args.budget_min is not None:
    _budget_secs = max(0.0, _args.budget_min * 60)
else:
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
metadata = _load_json(METADATA_FILE)


def _save_state():
    _dump_json(STATE_FILE, state)


def _save_dupe_history():
    _dump_json(DUPE_HISTORY_FILE, dupe_history)


def _save_metadata():
    _dump_json(METADATA_FILE, metadata)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _make_slot(listable) -> str:
    city = listable.location.split(", ")[0]
    base = f"{listable.equipment_type}_{city}_{listable.lang}"
    task = getattr(listable, "task_slug", None)
    return f"{base}_{task}" if task else base


def _cleanup_images():
    if os.path.exists(OUTPUT_DIR):
        def _force_rm(func, path, _):
            os.chmod(path, 0o777)
            func(path)
        shutil.rmtree(OUTPUT_DIR, onerror=_force_rm)
    os.makedirs(OUTPUT_DIR, exist_ok=True)


# ── Scraper / Listing init ────────────────────────────────────────────────────
# Exit code 2 == startup/login could not complete (needs a human, e.g. 2FA).
# run_session.py treats this differently from a mid-run crash (exit 1).
try:
    scraper = Scraper("https://facebook.com")
    scraper.add_login_functionality(
        "https://facebook.com", 'svg[aria-label="Your profile"]', "facebook"
    )
except SystemExit:
    logger.error("Startup/login did not complete — exiting with code 2 (human action needed).")
    sys.exit(2)
l = Listing(scraper)

_cleanup_images()

# ── Startup inventory — full scan before any mutations ────────────────────────
logger.info("Startup — taking inventory of all active listings...")
scraper.go_to_page("https://www.facebook.com/marketplace/you/selling/")

_inventory = l.collect_listing_stats()  # {title: {clicks, price, days_listed_fb, views, is_duplicate}}
logger.info(f"Inventory: {len(_inventory)} listings found on selling page.")

_inv_title_to_slot = {title: slot for slot, title in state.items()}
_inv_now = datetime.now(timezone.utc).isoformat()
_dupe_titles_found: list = []
_new_clicks_total = 0

for _title, _stats in _inventory.items():
    if _stats.get("is_duplicate"):
        _dupe_titles_found.append(_title)

    _slot = _inv_title_to_slot.get(_title)
    if not _slot:
        continue

    metadata.setdefault(_slot, {})
    _m = metadata[_slot]
    _snaps = _m.setdefault("click_snapshots", [])
    _clicks = _stats.get("clicks")
    if _clicks is not None:
        _last = _snaps[-1]["clicks"] if _snaps else 0
        _new_clicks_total += max(0, _clicks - _last)
        if not _snaps or _snaps[-1]["clicks"] != _clicks:
            _snaps.append({"ts": _inv_now, "clicks": _clicks})
            if len(_snaps) > 8:
                _m["click_snapshots"] = _snaps[-8:]

_save_metadata()
logger.info(
    f"Inventory: {len(_dupe_titles_found)} duplicate-flagged, "
    f"{_new_clicks_total} new clicks since last scan."
)

# ── Phase 0: Remove FB-flagged duplicates ─────────────────────────────────────
logger.info(f"Phase 0 — removing {len(_dupe_titles_found)} FB-flagged duplicate listings...")

# Dedup is best-effort: never let a stray UI exception abort the whole session.
try:
    removed_titles = l.remove_duplicate_listings()
except (InvalidSessionIdException, NoSuchWindowException):
    raise  # genuine session death — let it propagate so the supervisor restarts
except Exception as e:
    logger.error(f"Phase 0 dedup failed (non-fatal, continuing): {e}", exc_info=True)
    removed_titles = []
title_to_slot = {title: slot for slot, title in state.items()}

for title in removed_titles:
    if not title:
        logger.warning("Phase 0 — removed a duplicate but could not resolve its title.")
        continue
    slot = title_to_slot.get(title)
    if slot:
        # Carry final known clicks into lifetime total before clearing snapshots
        _snaps = metadata.get(slot, {}).get("click_snapshots", [])
        if _snaps:
            metadata.setdefault(slot, {})
            metadata[slot]["lifetime_clicks"] = metadata[slot].get("lifetime_clicks", 0) + _snaps[-1]["clicks"]
            metadata[slot]["click_snapshots"] = []
        dupe_history[slot] = datetime.now(timezone.utc).isoformat()
        del state[slot]
        logger.info(f"Phase 0 — slot '{slot}' marked duplicate-removed.")
    else:
        logger.warning(f"Phase 0 — removed duplicate '{title}' but slot not found in state.")

_save_state()
_save_dupe_history()

# Snapshot of slots that existed before Phase 1 (Phase 2 will only replace these)
_pre_phase1_slots = set(state.keys())

# (city, equip) pairs already covered — Phase 1a posts one of each equipment type per city
_covered_equip: set = {
    (s.split("_")[1], s.split("_")[0]) for s in state if len(s.split("_")) > 1
}

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
    metadata.setdefault(slot, {})
    metadata[slot]["title"] = listable.title
    metadata[slot]["published_at"] = datetime.now(timezone.utc).isoformat()
    metadata[slot]["equipment_type"] = listable.equipment_type
    metadata[slot]["city"] = city
    metadata[slot]["click_snapshots"] = []   # reset for new listing instance; lifetime_clicks preserved
    _save_metadata()
    return True


# ── Phase 1a: Coverage pass — one listing per uncovered city ─────────────────
# Ensures every city gets at least one listing before we fill additional variants.
logger.info("Phase 1a — coverage pass (one listing per uncovered city)...")
fatal = False

# Also skip task-variant slots for (city, equip) pairs that are already covered —
# Phase 1a would only defer them to Phase 1b anyway.
_covered_equip_slots = {
    f"{equip}_{city}_eng_{task['slug']}"
    for (city, equip) in _covered_equip
    for task in TASK_VARIANTS.get(equip, [])
}
_phase1a_skip = set(_pre_phase1_slots) | set(dupe_history.keys()) | _covered_equip_slots
for listable in get_listings(output_directory=OUTPUT_DIR, skip_slots=_phase1a_skip):
    if not within_budget():
        logger.info("Phase 1a — budget exhausted.")
        break
    if not hasattr(listable, "equipment_type") or not hasattr(listable, "lang"):
        _cleanup_images()
        continue

    slot = _make_slot(listable)
    if slot in _pre_phase1_slots or slot in dupe_history or slot in state:
        _cleanup_images()
        continue

    city = listable.location.split(", ")[0]
    if (city, listable.equipment_type) in _covered_equip:  # this equip type covered — defer to Phase 1b
        _cleanup_images()
        continue

    if not _publish(listable):
        fatal = True
        break
    _covered_equip.add((city, listable.equipment_type))
    _cleanup_images()

# ── Phase 1b: Fill pass — remaining new slots for already-covered cities ───────
if not fatal and within_budget():
    logger.info("Phase 1b — fill pass (remaining new slots for covered cities)...")

    _phase1b_skip = set(state.keys()) | set(dupe_history.keys())
    for listable in get_listings(output_directory=OUTPUT_DIR, skip_slots=_phase1b_skip):
        if not within_budget():
            logger.info("Phase 1b — budget exhausted.")
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

# Pre-compute all slot keys so Phase 3 and Phase 2 skip image generation for irrelevant slots
_all_slots = {
    f"{equip}_{loc['city']}_eng_{task['slug']}"
    for equip, tasks in TASK_VARIANTS.items()
    for task in tasks
    for loc in get_locations()
}
_phase3_skip = _all_slots - set(dupe_history.keys())
_phase2_skip = _all_slots - (_pre_phase1_slots - set(dupe_history.keys()))

# ── Phase 3: Re-list previously-duplicate slots ───────────────────────────────
# Restores listings for cities that lost coverage to FB duplicate removal.
if not fatal and within_budget():
    logger.info("Phase 3 — re-listing previously-duplicate slots...")

    _cleanup_images()
    for listable in get_listings(output_directory=OUTPUT_DIR, skip_slots=_phase3_skip):
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

# ── Phase 2: Replace non-duplicate existing slots (refresh — lowest priority) ──
if not fatal and within_budget():
    logger.info("Phase 2 — replacing non-duplicate existing slots (refresh)...")

    # Snapshot click counts before any deletions
    scraper.go_to_page("https://www.facebook.com/marketplace/you/selling/")
    click_counts = l.collect_click_snapshots()
    logger.info(f"Phase 2 — click snapshot: {len(click_counts)} listings.")
    _current_title_to_slot = {title: slot for slot, title in state.items()}
    _clicks_at = datetime.now(timezone.utc).isoformat()
    for _title, _clicks in click_counts.items():
        _slot = _current_title_to_slot.get(_title)
        if _slot and _clicks is not None:
            metadata.setdefault(_slot, {})
            snaps = metadata[_slot].setdefault("click_snapshots", [])
            snaps.append({"ts": _clicks_at, "clicks": _clicks})
            if len(snaps) > 8:
                metadata[_slot]["click_snapshots"] = snaps[-8:]
    _save_metadata()

    _cleanup_images()
    for listable in get_listings(output_directory=OUTPUT_DIR, skip_slots=_phase2_skip):
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
        # Carry final click count into lifetime total before this listing is deleted
        _final_clicks = click_counts.get(old_title)
        if _final_clicks is not None:
            metadata.setdefault(slot, {})
            metadata[slot]["lifetime_clicks"] = metadata[slot].get("lifetime_clicks", 0) + _final_clicks
            metadata[slot]["click_snapshots"] = []  # _publish will reset anyway, but be explicit
            _save_metadata()
        scraper.go_to_page("https://www.facebook.com/marketplace/you/selling/")
        l.remove_listing_by_title(old_title)

        if not _publish(listable):
            fatal = True
            break
        _cleanup_images()

# ── Done ──────────────────────────────────────────────────────────────────────
remaining = max(0, _deadline - time.time())
logger.info(
    f"Agent run complete. "
    f"Remaining budget: {remaining / 60:.1f} min. "
    f"Fatal stop: {fatal}."
)

# Regenerate the map with fresh data so the viewer is always current.
try:
    subprocess.run([sys.executable, "map_listings.py"], check=False, timeout=30)
    logger.info("Map regenerated.")
except Exception as _e:
    logger.warning(f"Map regeneration failed: {_e}")

# Exit non-zero on a fatal session error so run_session.py restarts and resumes.
sys.exit(1 if fatal else 0)
