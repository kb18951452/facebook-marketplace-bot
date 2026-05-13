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

# Navigate to Marketplace → Your Listings
marketplace_xpath = "//a[@href='https://www.facebook.com/marketplace/?ref=bookmark']"
scraper.element_click_by_xpath(marketplace_xpath)

selling_xpath = "//a[@href='/marketplace/create/']"
scraper.element_click_by_xpath(selling_xpath)

# Create the Listing helper
l = Listing(scraper)

# Output directory for generated images
output_directory: str = "./images/output/"
if os.path.exists(output_directory):
    shutil.rmtree(output_directory)
os.makedirs(output_directory, exist_ok=True)

# State file to remember which title belongs to which slot (equipment + city + language)
state_file = 'state.json'
state = {}
if os.path.exists(state_file):
    with open(state_file, 'r') as f:
        state = json.load(f)
    logger.info(f"Loaded state with {len(state)} completed slots.")

# Process each listing from the generator, but skip if already in state (i.e., iteration done)
for listable in get_listings(output_directory=output_directory):
    # Safety check – ensure the extra fields we added are present
    if not hasattr(listable, 'equipment_type') or not hasattr(listable, 'lang'):
        logger.error("ListingData missing equipment_type or lang – skipping")
        continue

    # Create a unique slot key: e.g., "mini-ex_Austin_eng"
    city = listable.location.split(', ')[0]  # "Austin, Texas" → "Austin"
    slot = f"{listable.equipment_type}_{city}_{listable.lang}"

    # If this slot is already in state, skip it (already done)
    if slot in state:
        logger.info(f"Skipping already processed slot: {slot} (title: {state[slot]})")
        # Clean up any generated images for this skipped listing
        if os.path.exists(output_directory):
            shutil.rmtree(output_directory)
            os.makedirs(output_directory, exist_ok=True)
        continue

    # If we previously published but state is outdated (shouldn't happen), but for safety:
    old_title = state.get(slot)
    if old_title:
        logger.info(f"Removing old listing for slot '{slot}' with title: {old_title}")
        l.remove_listing_by_title(old_title)

    # Publish the new (randomly generated) listing
    logger.info(f"Publishing new listing for slot '{slot}' with title: {listable.title}")
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