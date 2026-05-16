import logging
import os
import shutil
import json
import requests
from datetime import datetime, timezone

from selenium.common.exceptions import InvalidSessionIdException, NoSuchWindowException

from helpers.ads import get_listings
from helpers.scraper import Scraper
from helpers.listing_helper import Listing

SUMO_ENDPOINT = (
    "https://endpoint4.collection.sumologic.com/receiver/v1/http/"
    "ZaVnC4dhaV1WAXKlyVji5qYz_JFGGVzGAmMiumPVN4oprAXf1_b8seo08i1q9WXgAGF5GcYAxtgdmv9q-g54LzeLLW5JtGwEXJD3hTt-WQvT2cqJLTiUuA=="
)

with open("data/cities_data.json") as _f:
    _CITY_LOOKUP = {c["city"]: c for c in json.load(_f)}

def _sumo_post(payload):
    try:
        requests.post(SUMO_ENDPOINT, json=payload,
                      headers={"Content-Type": "application/json"}, timeout=5)
    except Exception as e:
        logger.warning(f"Sumo Logic send failed: {e}")

def _log_published(listable, city):
    city_data = _CITY_LOOKUP.get(city, {})
    _sumo_post({
        "timestamp":      datetime.now(timezone.utc).isoformat(),
        "event":          "published",
        "title":          listable.title,
        "city":           city,
        "state":          city_data.get("state", "TX"),
        "lat":            float(city_data["lat"]) if city_data.get("lat") else None,
        "lng":            float(city_data["lng"]) if city_data.get("lng") else None,
        "equipment_type": listable.equipment_type,
    })

def _log_click_snapshot(title, clicks, title_to_slot):
    slot = title_to_slot.get(title)
    if not slot:
        return
    parts = slot.split("_")
    city  = " ".join(parts[1:-1])
    equip = parts[0]
    city_data = _CITY_LOOKUP.get(city, {})
    _sumo_post({
        "timestamp":      datetime.now(timezone.utc).isoformat(),
        "event":          "click_snapshot",
        "title":          title,
        "city":           city,
        "state":          city_data.get("state", "TX"),
        "lat":            float(city_data["lat"]) if city_data.get("lat") else None,
        "lng":            float(city_data["lng"]) if city_data.get("lng") else None,
        "equipment_type": equip,
        "clicks":         clicks,
    })

# Configure logging
LOG_FILE = "listing_progress.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, mode='a')
    ]
)
logger = logging.getLogger(__name__)

# Initialize scraper and login
scraper = Scraper('https://facebook.com')
scraper.add_login_functionality('https://facebook.com', 'svg[aria-label="Your profile"]', 'facebook')

# Create the Listing helper
l = Listing(scraper)

# State file
state_file = 'state.json'

# Load existing state (slots published in a prior run)
existing_state = {}
if os.path.exists(state_file):
    with open(state_file) as f:
        existing_state = json.load(f)
title_to_slot = {title: slot for slot, title in existing_state.items()}

# Working state — starts as a copy of existing so Phase 1 can add to it
state = dict(existing_state)

# Output directory for generated images
output_directory: str = "./images/output/"

def _cleanup_images():
    if os.path.exists(output_directory):
        shutil.rmtree(output_directory)
    os.makedirs(output_directory, exist_ok=True)

def _publish(listable) -> bool:
    """Publish one listing. Returns False on fatal session error, True otherwise."""
    city = listable.location.split(', ')[0]
    slot = f"{listable.equipment_type}_{city}_{listable.lang}"
    logger.info(f"Publishing slot '{slot}': {listable.title}")
    try:
        l.update_listings(listings=[listable], listing_type="item")
    except (InvalidSessionIdException, NoSuchWindowException):
        logger.error("Chrome session died — stopping. Re-run to resume from state.json.")
        return False
    except Exception as e:
        logger.error(f"Listing '{listable.title}' failed: {e}", exc_info=True)
        return True  # non-fatal; move on to next listing
    _log_published(listable, city)
    state[slot] = listable.title
    with open(state_file, 'w') as f:
        json.dump(state, f, indent=4)
    return True

_cleanup_images()

# ── Phase 1: Publish brand-new slots (no entry in existing_state) ────────────
logger.info("Phase 1 — publishing new listings (slots not yet in state)...")
fatal = False
for listable in get_listings(output_directory=output_directory):
    if not hasattr(listable, 'equipment_type') or not hasattr(listable, 'lang'):
        logger.error("ListingData missing equipment_type or lang – skipping")
        _cleanup_images()
        continue

    city = listable.location.split(', ')[0]
    slot = f"{listable.equipment_type}_{city}_{listable.lang}"

    if slot in existing_state:
        # Already published before this run — Phase 2 will replace it
        _cleanup_images()
        continue

    if slot in state:
        # Already published earlier in Phase 1 (crash-recovery guard)
        logger.info(f"Slot already published this run, skipping: {slot}")
        _cleanup_images()
        continue

    if not _publish(listable):
        fatal = True
        break
    _cleanup_images()

# ── Phase 2: Replace existing slots ─────────────────────────────────────────
if not fatal:
    logger.info("Phase 2 — replacing existing listings...")

    # Snapshot click counts for all current listings before any deletions
    scraper.go_to_page('https://www.facebook.com/marketplace/you/selling/')
    click_counts = l.collect_click_snapshots()
    logger.info(f"Click snapshot collected for {len(click_counts)} listings.")
    for title, clicks in click_counts.items():
        _log_click_snapshot(title, clicks, title_to_slot)

    _cleanup_images()
    for listable in get_listings(output_directory=output_directory):
        if not hasattr(listable, 'equipment_type') or not hasattr(listable, 'lang'):
            _cleanup_images()
            continue

        city = listable.location.split(', ')[0]
        slot = f"{listable.equipment_type}_{city}_{listable.lang}"

        if slot not in existing_state:
            # New slot — was handled (or failed) in Phase 1
            _cleanup_images()
            continue

        old_title = existing_state[slot]
        logger.info(f"Replacing slot '{slot}': removing '{old_title}'")
        scraper.go_to_page('https://www.facebook.com/marketplace/you/selling/')
        l.remove_listing_by_title(old_title)

        if not _publish(listable):
            break
        _cleanup_images()

# Final cleanup: remove any duplicate listings Facebook may have flagged
l.remove_duplicate_listings()

logger.info("All listings processed and state saved.")
