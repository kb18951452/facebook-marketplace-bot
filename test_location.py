"""
Smoke-test for the location field fix.
Uses the same production code path as main.py (add_fields_for_item) so the form
reaches page 2 in the same state as a real listing run.
Does NOT click Publish — closes after reading the location field value.
"""
import sys
import time
import logging
import os
import shutil

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
                    handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

from helpers.scraper import Scraper
from helpers.listing_helper import Listing, ListingData
from helpers.ads import (get_equipment, get_listing_title, get_listing_description,
                         random_images_from_directory, generate_random_controlled_image)

TEST_CITY = "Waco"
TEST_LOCATION = f"{TEST_CITY}, Texas"
OUTPUT_DIR = "./images/output_test/"

scraper = Scraper('https://facebook.com')
scraper.add_login_functionality('https://facebook.com', 'svg[aria-label="Your profile"]', 'facebook')

listing = Listing(scraper)

# Build a minimal ListingData matching the real production structure
os.makedirs(OUTPUT_DIR, exist_ok=True)
src_images = random_images_from_directory("./images/kx71", number=1)
test_image = generate_random_controlled_image(input_image=src_images[0], output_directory=OUTPUT_DIR)
logger.info(f"Test image: {test_image}")

equipment = get_equipment()["mini-ex"]
data = ListingData(
    images=[test_image],
    price=str(equipment["prices"]["daily"]),
    description=get_listing_description(
        language="eng",
        blurb=equipment["blurb"]["eng"],
        title="TEST LISTING",
        daily_price=str(equipment["prices"]["daily"]),
        delivery_cost=50.0,
        location=TEST_LOCATION,
    ),
    location=TEST_LOCATION,
    title="TEST LISTING - DO NOT PUBLISH",
    category="Miscellaneous",
    condition="Used - Like New",
    equipment_type="mini-ex",
    lang="eng",
)

print(f"\n=== Testing location field with: {TEST_LOCATION} ===\n")
scraper.go_to_page('https://facebook.com/marketplace/create/item')

# Upload image
scraper.input_file_add_files('input[accept="image/*,image/heif,image/heic"]', data.images)

# Fill all form fields via production code path
listing.add_fields_for_item(data)

# Price
scraper.element_send_keys_by_xpath(
    "//span[normalize-space(text())='Price']/following-sibling::input[1]",
    data.price
)

# Description
for xp in [
    "//label[.//span[normalize-space(text())='Description']]//textarea",
    "//textarea[@aria-label='Description']",
    "//textarea[1]",
]:
    from selenium.webdriver.common.by import By
    el = scraper.find_element_by_xpath(xp, exit_on_missing_element=False, wait_element_time=2)
    if el:
        scraper.element_send_keys_by_xpath(xp, data.description)
        logger.info(f"Description filled via: {xp}")
        break

# Scroll so location is accessible
scraper.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
time.sleep(0.3)

# Log page 1 fields
fields_p1 = scraper.driver.execute_script("""
    return Array.from(document.querySelectorAll('input:not([type="file"]):not([type="hidden"]), [role="combobox"]'))
        .filter(function(el){ return el.offsetParent !== null; })
        .map(function(el){ return el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.tagName+'/'+el.getAttribute('role'); })
        .join(', ');
""")
logger.info(f"Page 1 fields: {fields_p1}")

p1_loc = listing._fill_location(data.location, wait=2)
logger.info(f"Page 1 _fill_location: {p1_loc}")
scraper.driver.save_screenshot("test_location_page1.png")

# Advance to page 2
listing.find_and_click_next()
time.sleep(2)

# Log page 2 fields
fields_p2 = scraper.driver.execute_script("""
    return Array.from(document.querySelectorAll('input:not([type="file"]):not([type="hidden"])'))
        .filter(function(el){ return el.offsetParent !== null; })
        .map(function(el){ return '[' + (el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.id || '?') + ']'; })
        .join(', ');
""")
logger.info(f"Page 2 visible inputs: {fields_p2}")

# Fill location on page 2
p2_loc = listing._fill_location(data.location, wait=4)
logger.info(f"Page 2 _fill_location: {p2_loc}")
scraper.driver.save_screenshot("test_location_page2.png")

# Read back location input value
loc_value = scraper.driver.execute_script("""
    var el = document.querySelector('input[aria-label="Location"]');
    return el ? el.value : 'NO INPUT FOUND';
""")
logger.info(f"Location input value: '{loc_value}'")

# Check preview pane
preview_loc = scraper.driver.execute_script("""
    var els = Array.from(document.querySelectorAll('*'));
    for (var i = 0; i < els.length; i++) {
        var el = els[i];
        if (el.children.length === 0 && el.textContent && el.textContent.includes('ago in')) {
            return el.textContent.trim();
        }
    }
    return null;
""")
logger.info(f"Preview location text: '{preview_loc}'")

shutil.rmtree(OUTPUT_DIR, ignore_errors=True)

print(f"\n=== RESULTS ===")
print(f"Location input value : '{loc_value}'")
print(f"Preview text         : '{preview_loc}'")

if loc_value and TEST_CITY.lower() in loc_value.lower():
    print(f"PASS: Location input contains '{TEST_CITY}'")
    sys.exit(0)
else:
    print(f"FAIL: Expected '{TEST_CITY}' in location, got '{loc_value}'")
    sys.exit(1)
