"""
cleanup.py — One-time script to delete all active FB Marketplace listings
and reset state so the daily agent starts fresh.

Run once before switching to the new task-variant slot format:
    python cleanup.py

Backs up state.json -> state.json.bak before clearing it.
"""

import json
import logging
import os
import shutil

from helpers.scraper import Scraper
from helpers.listing_helper import Listing

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

STATE_FILE = "state.json"
DUPE_FILE = "data/duplicate_history.json"

scraper = Scraper("https://facebook.com")
scraper.add_login_functionality(
    "https://facebook.com", 'svg[aria-label="Your profile"]', "facebook"
)
l = Listing(scraper)

logger.info("Cleanup — navigating to selling page...")
scraper.go_to_page("https://www.facebook.com/marketplace/you/selling/")

logger.info("Cleanup — removing all listings...")
l.remove_all_listings()
logger.info("Cleanup — all listings removed.")

# Back up then clear state files
if os.path.exists(STATE_FILE):
    shutil.copy(STATE_FILE, STATE_FILE + ".bak")
    with open(STATE_FILE, "w") as f:
        json.dump({}, f)
    logger.info("Cleanup — state.json cleared (backup: state.json.bak)")

if os.path.exists(DUPE_FILE):
    shutil.copy(DUPE_FILE, DUPE_FILE + ".bak")
    with open(DUPE_FILE, "w") as f:
        json.dump({}, f)
    logger.info("Cleanup — duplicate_history.json cleared (backup: .bak)")

logger.info("Cleanup complete. Run daily_agent.py to start fresh.")
