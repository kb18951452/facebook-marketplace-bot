"""
find_orphaned_listings.py — Find live Facebook listings that look like
equipment rentals (mini-excavator / track loader) but have no entry in
state.json, so the bot can't track, refresh, or manage them.

This happens when a Phase 2 refresh publishes a replacement listing but the
old one's deletion silently fails (a real case found 2026-07-07: "Track
Loader Rental - Land Clearing - Moffat" stayed live under trackloader_Moffat_
eng_clearing after that slot was re-listed under a different rolled title).
daily_agent.py's Phase 2 now checks the deletion result before publishing a
replacement, so this shouldn't recur — this script is for finding orphans
that predate that fix, or slipped through some other way (manual FB edits,
crashes mid-publish).

Read-only: scrapes the selling page, reports findings, deletes nothing.

Run once (or periodically):
    python find_orphaned_listings.py
"""

import json
import logging

from helpers.scraper import Scraper
from helpers.listing_helper import Listing
from helpers.slot import parse as parse_slot

STATE_FILE = "state.json"
CITIES_FILE = "data/cities_data.json"
LOG_FILE = "listing_progress.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode="a"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Keyword check for "does this title look like one of our equipment ads" —
# not exhaustive (one rare Spanish trackloader/foundation template has no
# matching keyword), but covers every current English template and all but
# one Spanish/legacy template, and won't false-positive on unrelated
# personal marketplace activity on the same account.
EQUIPMENT_KEYWORDS = [
    "excavator", "excavation", "excavaci", "mini ex",
    "track loader", "skid steer", "excavadora", "cargadora", "trackloader",
]


def looks_like_equipment(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in EQUIPMENT_KEYWORDS)


def guess_equipment_type(title: str) -> str:
    t = title.lower()
    if any(k in t for k in ("track loader", "skid steer", "trackloader", "cargadora")):
        return "trackloader"
    return "mini-ex"


def guess_city(title: str, known_cities: list) -> str:
    """Best-effort: return the longest known city name that appears in the
    title. Longest-first avoids "Eddy" matching inside "Bruceville-Eddy"."""
    matches = [c for c in known_cities if c in title]
    if not matches:
        return ""
    return max(matches, key=len)


def main():
    with open(STATE_FILE, encoding="utf-8") as f:
        state = json.load(f)
    with open(CITIES_FILE, encoding="utf-8") as f:
        known_cities = [c["city"] for c in json.load(f)]

    known_titles = set(state.values())

    scraper = Scraper("https://facebook.com")
    scraper.add_login_functionality(
        "https://facebook.com", 'svg[aria-label="Your profile"]', "facebook"
    )
    listing = Listing(scraper)

    logger.info("find_orphaned_listings — scanning selling page...")
    scraper.go_to_page("https://www.facebook.com/marketplace/you/selling/")
    live_stats = listing.collect_listing_stats()
    logger.info(f"find_orphaned_listings — {len(live_stats)} listings found on selling page.")

    unmatched = {title: stats for title, stats in live_stats.items() if title not in known_titles}
    orphans = {title: stats for title, stats in unmatched.items() if looks_like_equipment(title)}
    personal = len(unmatched) - len(orphans)

    logger.info(
        f"find_orphaned_listings — {len(unmatched)} unmatched titles, "
        f"{len(orphans)} look like equipment orphans, {personal} look like unrelated personal listings."
    )

    if not orphans:
        print("No orphaned equipment listings found.")
        return

    print(f"\n{len(orphans)} orphaned equipment listing(s) — live on Facebook, no state.json entry:\n")
    for title, stats in orphans.items():
        equip = guess_equipment_type(title)
        city = guess_city(title, known_cities)
        note = "city not recognized — needs manual review"
        if city:
            existing = [
                (slot, existing_title)
                for slot, existing_title in state.items()
                if (parsed := parse_slot(slot)) and parsed.city == city and parsed.equipment_type == equip
            ]
            if existing:
                note = f"slot(s) for {equip}/{city} already relisted under a different title — likely a Phase 2 leftover"
            else:
                note = f"no active {equip} slot for {city} in state.json — needs manual review"
        print(f"  {title!r}")
        print(f"    clicks={stats.get('clicks')}  guessed_equipment={equip}  guessed_city={city or '?'}")
        print(f"    {note}\n")

    print("This script deletes nothing. Use Listing.remove_listing_by_title_via_search(title)")
    print("(or the normal Facebook UI) to remove confirmed orphans.")


if __name__ == "__main__":
    main()
