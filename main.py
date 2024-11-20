import json
import logging

from selenium.webdriver.support import wait

from helpers.scraper import Scraper
from helpers.listing_helper import Listing, ListingData

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

scraper = Scraper('https://facebook.com')

# Add login functionality to the scraper
scraper.add_login_functionality('https://facebook.com', 'svg[aria-label="Your profile"]', 'facebook')

marketplace_xpath = "//a[@href='https://www.facebook.com/marketplace/?ref=bookmark']"
scraper.element_click_by_xpath(marketplace_xpath)

selling_xpath = "//a[@href='/marketplace/you/selling/']"
scraper.element_click_by_xpath(selling_xpath)


l = Listing(scraper)
# listings = l.load_listings_from_json("./data/listings.json")


def transform_item(project, equipment, city):
    transformed = {
        'Photos_Folder': equipment.get('Photos_Folder', ''),
        'Photos_Names': equipment.get('Photos_Names', []),
        'Price': str(equipment.get('daily_cost', '')),
        'Description': project.get('description', ''),
        'Location': f"{city.get('city', '')}, {city.get('state', '')}",
        'Title': f"{project.get('type', '').format(equipment_title=equipment.get('title',''))} in {city.get('city', '')}, {city.get('state', '')}",
        'Category': "Miscellaneous",
        'Condition': "Used - Like New",
        'Make': equipment.get('make', ''),
        'Model': equipment.get('model', ''),
        'Vehicle_Type': equipment.get('title', ''),
        'Delivery': city.get('estimated_cost', ''),
    }
    return ListingData(**transformed)


# TODO: Create Listing Merger mechanism
with \
        open('./data/projects_sample.json', 'r') as projects_file, \
        open('data/equipment.json', 'r') as equipment_file, \
        open('data/cities_data_sample.json', 'r') as cities_file:
            projects = json.load(projects_file)
            equipments = json.load(equipment_file)
            cities = json.load(cities_file)

items = []
for project in projects:
    for equipment in equipments:
        for city in cities:
            items.append(transform_item(project, equipment, city))


l.update_listings(listings=items, listing_type="item")
