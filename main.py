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
from helpers.slot import from_listing as slot_from_listing, parse as parse_slot

SUMO_ENDPOINT = (
    "https://endpoint4.collection.sumologic.com/receiver/v1/http/"
    "ZaVnC4dhaV1WAXKlyVji5qYz_JFGGVzGAmMiumPVN4oprAXf1_b8seo08i1q9WXgAGF5GcYAxtgdmv9q-g54LzeLLW5JtGwEXJD3hTt-WQvT2cqJLTiUuA=="
)

_CITY_LOOKUP: dict = {}


def _sumo_post(payload):
    try:
        requests.post(SUMO_ENDPOINT, json=payload,
                      headers={"Content-Type": "application/json"}, timeout=5)
    except Exception as e:
        logger.warning(f"Sumo Logic send failed: {e}")


def _city_geo_fields(city: str) -> dict:
    d = _CITY_LOOKUP.get(city, {})
    return {
        "city":  city,
        "state": d.get("state", "TX"),
        "lat":   float(d["lat"]) if d.get("lat") else None,
        "lng":   float(d["lng"]) if d.get("lng") else None,
    }


def _log_published(listable, city):
    _sumo_post({
        "timestamp":      datetime.now(timezone.utc).isoformat(),
        "event":          "published",
        "title":          listable.title,
        "equipment_type": listable.equipment_type,
        **_city_geo_fields(city),
    })


def _log_click_snapshot(title, clicks, title_to_slot):
    slot = title_to_slot.get(title)
    if not slot:
        return
    parsed = parse_slot(slot)
    if not parsed:
        return
    _sumo_post({
        "timestamp":      datetime.now(timezone.utc).isoformat(),
        "event":          "click_snapshot",
        "title":          title,
        "equipment_type": parsed.equipment_type,
        "clicks":         clicks,
        **_city_geo_fields(parsed.city),
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

OUTPUT_DIRECTORY: str = "./images/output/"
STATE_FILE = "state.json"


def _cleanup_images():
    if os.path.exists(OUTPUT_DIRECTORY):
        def _force_remove(func, path, _):
            os.chmod(path, 0o777)
            func(path)
        shutil.rmtree(OUTPUT_DIRECTORY, onerror=_force_remove)
    os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)


def main():
    with open("data/cities_data.json") as _f:
        _CITY_LOOKUP.update({c["city"]: c for c in json.load(_f)})

    scraper = Scraper('https://facebook.com')
    scraper.add_login_functionality('https://facebook.com', 'svg[aria-label="Your profile"]', 'facebook')
    l = Listing(scraper)

    existing_state = {}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            existing_state = json.load(f)
    title_to_slot = {title: slot for slot, title in existing_state.items()}
    state = dict(existing_state)

    def _publish(listable) -> bool:
        """Publish one listing. Returns False on fatal session error, True otherwise."""
        city = listable.location.split(', ')[0]
        slot = slot_from_listing(listable)
        logger.info(f"Publishing slot '{slot}': {listable.title}")
        try:
            l.publish_listing(listable, "item")
        except (InvalidSessionIdException, NoSuchWindowException):
            logger.error("Chrome session died — stopping. Re-run to resume from state.json.")
            return False
        except Exception as e:
            logger.error(f"Listing '{listable.title}' failed: {e}", exc_info=True)
            return True  # non-fatal; move on to next listing
        _log_published(listable, city)
        state[slot] = listable.title
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=4)
        return True

    _cleanup_images()

    # ── Phase 1: Publish brand-new slots (no entry in existing_state) ────────────
    logger.info("Phase 1 — publishing new listings (slots not yet in state)...")
    fatal = False
    for listable in get_listings(output_directory=OUTPUT_DIRECTORY):
        if not hasattr(listable, 'equipment_type') or not hasattr(listable, 'lang'):
            logger.error("ListingData missing equipment_type or lang – skipping")
            _cleanup_images()
            continue

        slot = slot_from_listing(listable)

        if slot in existing_state:
            _cleanup_images()
            continue

        if slot in state:
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

        scraper.go_to_page('https://www.facebook.com/marketplace/you/selling/')
        click_counts = l.collect_click_snapshots()
        logger.info(f"Click snapshot collected for {len(click_counts)} listings.")
        for title, clicks in click_counts.items():
            _log_click_snapshot(title, clicks, title_to_slot)

        _cleanup_images()
        for listable in get_listings(output_directory=OUTPUT_DIRECTORY):
            if not hasattr(listable, 'equipment_type') or not hasattr(listable, 'lang'):
                _cleanup_images()
                continue

            slot = slot_from_listing(listable)

            if slot not in existing_state:
                _cleanup_images()
                continue

            old_title = existing_state[slot]
            logger.info(f"Replacing slot '{slot}': removing '{old_title}'")
            scraper.go_to_page('https://www.facebook.com/marketplace/you/selling/')
            l.remove_listing_by_title(old_title)

            if not _publish(listable):
                break
            _cleanup_images()

    l.remove_duplicate_listings()
    logger.info("All listings processed and state saved.")


if __name__ == "__main__":
    main()
