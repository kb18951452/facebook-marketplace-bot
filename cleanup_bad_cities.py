"""
cleanup_bad_cities.py — Remove FB Marketplace listings for cities that resolve
to wrong locations (not near Waco, TX).

The removal list lives in data/bad_cities.json, not here — check_city_distances.py
appends to it automatically when it finds a new city whose geocoded lat/lng is
implausibly far from Waco. Known past offenders (already removed from
cities_data.json, but with live listings that needed cleanup):
  Beverly       -> Beverly, IL
  Beverly Hills -> Beverly Hills, NC (sometimes)
  Windsor       -> Windsor, QLD Australia
  Downs         -> Downs, KS (inconsistent)
  Jewell        -> Jewell, KS (inconsistent)

Run once (or re-run — idempotent, only removes slots still in state.json):
    python cleanup_bad_cities.py
"""

import json
import logging
import sys

from selenium.common.exceptions import InvalidSessionIdException, NoSuchWindowException

from helpers.scraper import Scraper
from helpers.listing_helper import Listing
from helpers.slot import parse as parse_slot

BAD_CITIES_FILE = "data/bad_cities.json"
STATE_FILE = "state.json"
LOG_FILE = "listing_progress.log"

with open(BAD_CITIES_FILE, encoding="utf-8") as _f:
    REMOVE_CITIES = set(json.load(_f))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode="a"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def _slots_to_remove(state: dict) -> dict:
    result = {}
    for slot, title in state.items():
        parsed = parse_slot(slot)
        if parsed and parsed.city in REMOVE_CITIES:
            result[slot] = title
    return result


def main():
    with open(STATE_FILE) as f:
        state = json.load(f)

    to_remove = _slots_to_remove(state)
    if not to_remove:
        logger.info("No listings to remove — already clean.")
        return

    logger.info(
        f"=== cleanup_bad_cities: removing {len(to_remove)} listings "
        f"for cities {sorted(REMOVE_CITIES)} ==="
    )

    scraper = Scraper("https://facebook.com")
    scraper.add_login_functionality(
        "https://facebook.com", 'svg[aria-label="Your profile"]', "facebook"
    )
    listing = Listing(scraper)

    removed = 0
    failed = 0
    total = len(to_remove)

    for slot, title in list(to_remove.items()):
        logger.info(f"Removing '{title}' (slot: {slot})")
        scraper.go_to_page("https://www.facebook.com/marketplace/you/selling/")

        try:
            ok = listing.remove_listing_by_title_via_search(title)
        except (InvalidSessionIdException, NoSuchWindowException):
            logger.error("Chrome session died — stopping. Re-run to resume from state.json.")
            sys.exit(1)
        except Exception as e:
            logger.warning(f"Unexpected error removing '{title}': {e}")
            ok = False

        if not ok:
            failed += 1
            logger.warning(f"  Failed ({failed} total failures) — leaving in state.json for re-run.")
            continue

        state.pop(slot, None)
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=4)
        removed += 1
        logger.info(f"Removed and de-listed from state: {slot} ({removed}/{total})")

    logger.info(
        f"=== cleanup_bad_cities done: {removed} removed, {failed} failed ==="
    )
    if failed:
        logger.warning(f"Re-run to retry {failed} failed removals.")


if __name__ == "__main__":
    main()
