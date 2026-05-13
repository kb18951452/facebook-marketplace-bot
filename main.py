import logging
import os
import shutil
import json

from helpers.ads import get_listings
from helpers.scraper import Scraper
from helpers.listing_helper import Listing

# Configure logging
LOG_FILE = "listing_progress.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, mode='a')  # Append mode to keep history
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

# Delete all existing listings and reset state so every slot gets re-published fresh
logger.info("Deleting all existing listings before re-publishing...")
scraper.go_to_page('https://www.facebook.com/marketplace/you/selling/')
l.remove_all_listings()
logger.info("All existing listings deleted.")

state = {}
with open(state_file, 'w') as f:
    json.dump(state, f)
logger.info("State cleared — all slots will be re-published.")

# Navigate to Marketplace → Create
marketplace_xpath = "//a[@href='https://www.facebook.com/marketplace/?ref=bookmark']"
scraper.element_click_by_xpath(marketplace_xpath)

selling_xpath = "//a[@href='/marketplace/create/']"
scraper.element_click_by_xpath(selling_xpath)

# Output directory for generated images
output_directory: str = "./images/output/"
if os.path.exists(output_directory):
    shutil.rmtree(output_directory)
os.makedirs(output_directory, exist_ok=True)

# Process each listing from the generator, skipping slots already published in this run
for listable in get_listings(output_directory=output_directory):
    # Safety check – ensure the extra fields we added are present
    if not hasattr(listable, 'equipment_type') or not hasattr(listable, 'lang'):
        logger.error("ListingData missing equipment_type or lang – skipping")
        continue

    # Create a unique slot key: e.g., "mini-ex_Austin_eng"
    city = listable.location.split(', ')[0]  # "Austin, Texas" → "Austin"
    slot = f"{listable.equipment_type}_{city}_{listable.lang}"

    # Skip if already published in this run (crash-recovery guard)
    if slot in state:
        logger.info(f"Skipping already processed slot: {slot} (title: {state[slot]})")
        if os.path.exists(output_directory):
            shutil.rmtree(output_directory)
            os.makedirs(output_directory, exist_ok=True)
        continue

    # Publish the listing
    logger.info(f"Publishing listing for slot '{slot}' with title: {listable.title}")
    l.update_listings(listings=[listable], listing_type="item")

    # Update state with the new title
    state[slot] = listable.title

    # Persist state immediately – this makes the script resilient to crashes/interruptions
    with open(state_file, 'w') as f:
        json.dump(state, f, indent=4)

    # Clean up generated images for this listing
    if os.path.exists(output_directory):
        shutil.rmtree(output_directory)
        os.makedirs(output_directory, exist_ok=True)

# Final cleanup: remove any duplicate listings that Facebook might flag
l.remove_duplicate_listings()

logger.info("All listings processed and state saved.")