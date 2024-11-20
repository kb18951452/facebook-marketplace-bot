# Remove and then publish each listing
import json
import os
from selenium.webdriver.common.by import By
from dataclasses import dataclass, asdict
from typing import List, Optional


@dataclass
class ListingData:
    Photos_Folder: str
    Photos_Names: List[str]
    Price: str
    Description: str
    Location: str
    Delivery: float
    Groups: Optional[str] = None

    # Specific to items
    Title: Optional[str] = None
    Category: Optional[str] = None
    Condition: Optional[str] = None
    Vehicle_Type: Optional[str] = None
    Make: Optional[str] = None
    Model: Optional[str] = None

    # For equipment listings
    Equipment: Optional[List[str]] = None


def transform_item(item):
    transformed = {
        'Photos_Folder': item.get('photos_folder', ''),
        'Photos_Names': item.get('photos_names', []),
        'Price': str(item.get('price', '')),
        'Description': item.get('description', ''),
        'Location': item.get('location', ''),
        'Groups': ';'.join(item.get('groups', [])),
    }
    return ListingData(**transformed)


def create_listing_data_from_iterable(iterable):
    return [transform_item(item) for item in iterable]


class Listing:
    def __init__(self, scraper):
        self.scraper = scraper

    def update_listings(self, listings, listing_type):
        # If listings are empty stop the function
        if not listings:
            return

        # Check if listing is already listed and remove it then publish it like a new one
        for listing in listings:
            # Remove listing if it is already published
            self.remove_listing(listing, listing_type)

            # Publish the listing in marketplace
            self.publish_listing(listing, listing_type)

    def remove_listing(self, data: ListingData, listing_type):
        title = self.generate_title_for_listing_type(data, listing_type)
        listing_title = self.find_listing_by_title(title)

        # Listing not found so stop the function
        if not listing_title:
            return

        listing_title.click()

        # Click on the delete listing button
        self.scraper.element_click('div:not([role="gridcell"]) > div[aria-label="Delete"][tabindex="0"]')

        # Click on confirm button to delete
        confirm_delete_selector = 'div[aria-label="Delete listing"] div[aria-label="Delete"][tabindex="0"]'
        if self.scraper.find_element(confirm_delete_selector, False, 3):
            self.scraper.element_click(confirm_delete_selector)
        else:
            if self.scraper.find_element(confirm_delete_selector, True, 3):
                self.scraper.element_click(confirm_delete_selector)

        # Wait until the popup is closed
        self.scraper.element_wait_to_be_invisible('div[aria-label="Your Listing"]')

    def publish_listing(self, data: ListingData, listing_type):
        # Click on create new listing button
        self.scraper.element_click('div[aria-label="Marketplace sidebar"] a[aria-label="Create new listing"]')
        # Choose listing type
        self.scraper.element_click(f'a[href="/marketplace/create/{listing_type}/"]')

        # Create string that contains all the image paths separated by \n
        images_path = self.generate_multiple_images_path(data.Photos_Folder, data.Photos_Names)
        # Add images to the listing
        # TODO: Allow image file-like objects to be referenced instead of a string/path.
        self.scraper.input_file_add_files('input[accept="image/*,image/heif,image/heic"]', images_path)

        # Add specific fields based on the listing_type
        function_name = f'add_fields_for_{listing_type}'
        # Call functions by name dynamically
        getattr(self, function_name)(data)

        self.scraper.element_send_keys('label[aria-label="Price"] input', data.Price)
        self.scraper.element_send_keys('label[aria-label="Description"] textarea', data.Description)

        next_button = self.find_and_click_next()
        if next_button:
            self.scraper.element_send_keys('label[aria-label="Location"] input', data.Location)
            self.scraper.element_click('ul[role="listbox"] li:first-child > div')
            # # Add listing to multiple groups
            # self.add_listing_to_multiple_groups(data)
            self.find_and_click_next()
            # Publish the listing
            self.scraper.element_click('div[aria-label="Publish"]:not([aria-disabled])')

        if not next_button:
            self.post_listing_to_multiple_groups(data, listing_type)

    def find_and_click_next(self):
        next_button_selector = 'div [aria-label="Next"] > div'
        next_button = self.scraper.find_element(next_button_selector, False, 3)
        if next_button:
            self.scraper.element_click(next_button_selector)
            return True
        else:
            return False

    @staticmethod
    def generate_multiple_images_path(folder_path, image_names):
        # Convert folder_path to an absolute path if it's not already
        absolute_folder_path = os.path.abspath(folder_path)

        # Ensure the folder path ends with the correct separator
        if not absolute_folder_path.endswith(os.sep):
            absolute_folder_path += os.sep

        images_paths = []

        # If image_names is provided, process each name
        if image_names:
            for image_name in image_names:
                # Strip any leading or trailing whitespace from the image name
                image_name = image_name.strip()
                # Use os.path.join for cross-platform compatibility
                full_path = os.path.join(absolute_folder_path, image_name)
                images_paths.append(full_path)

        # Join all paths with newline for return
        return '\n'.join(images_paths)

    # Add specific fields for listing from type vehicle
    def add_fields_for_vehicle(self, data: ListingData):
        # Expand vehicle type select
        self.scraper.element_click('label[aria-label="Vehicle type"]')
        # Select vehicle type
        self.scraper.element_click_by_xpath(f'//span[text()="{data.Vehicle_Type}"]')

        # Scroll to years select
        self.scraper.scroll_to_element('label[aria-label="Year"]')
        # Expand years select
        self.scraper.element_click('label[aria-label="Year"]')
        self.scraper.element_click_by_xpath(f'//span[text()="{data.Year}"]')

        self.scraper.element_send_keys('label[aria-label="Make"] input', data.Make)
        self.scraper.element_send_keys('label[aria-label="Model"] input', data.Model)

        # Scroll to mileage input
        self.scraper.scroll_to_element('label[aria-label="Mileage"] input')
        # Click on the mileage input
        self.scraper.element_send_keys('label[aria-label="Mileage"] input', data.Mileage)

        # Expand fuel type select
        self.scraper.element_click('label[aria-label="Fuel type"]')
        # Select fuel type
        self.scraper.element_click_by_xpath(f'//span[text()="{data.Fuel_Type}"]')

    # Add specific fields for listing from type item
    def add_fields_for_item(self, data: ListingData):
        self.scraper.element_send_keys('label[aria-label="Title"] input', data.Title)

        # Scroll to "Category" select field
        self.scraper.scroll_to_element('label[aria-label="Category"]')
        # Expand category select
        self.scraper.element_click('label[aria-label="Category"]')
        # Select category
        self.scraper.element_click_by_xpath(f'//span[text()="{data.Category}"]')

        # Expand category select
        self.scraper.element_click('label[aria-label="Condition"]')
        # Select category
        self.scraper.element_click_by_xpath(f'//span[@dir="auto"][text()="{data.Condition}"]')

        if data.Category == 'Sports & Outdoors':
            self.scraper.element_send_keys('label[aria-label="Brand"] input', data.Brand)

    @staticmethod
    def generate_title_for_listing_type(data: ListingData, listing_type):
        title = ''

        if listing_type == 'item':
            title = data.Title

        if listing_type == 'vehicle':
            title = f'{data.Year} {data.Make} {data.Model}'

        return title

    def add_listing_to_multiple_groups(self, data: ListingData):
        # Create an array for group names by splitting the string by this symbol ";"
        group_names = data.Groups.split(';')

        # If the groups are empty do not do anything
        if not group_names:
            return

        # Post in different groups
        for group_name in group_names:
            # Remove whitespace before and after the name
            group_name = group_name.strip()

            self.scraper.element_click_by_xpath(f'//span[text()="{group_name}"]')

    def post_listing_to_multiple_groups(self, data: ListingData, listing_type):
        title = self.generate_title_for_listing_type(data, listing_type)
        title_element = self.find_listing_by_title(title)

        # If there is no add with this title do not do anything
        if not title_element:
            return None

        # Create an array for group names by splitting the string by this symbol ";"
        group_names = data.Groups.split(';')

        # If the groups are empty do not do anything
        if not group_names:
            return None

        search_input_selector = '[aria-label="Search for groups"]'

        # Post in different groups
        for group_name in group_names:
            # Click on the Share button to the listing that we want to share
            self.scraper.element_click(f'[aria-label="{title}"] + div [aria-label="Share"]')
            # Click on the Share to a group button
            self.scraper.element_click_by_xpath('//span[text()="Share to a group"]')

            # Remove whitespace before and after the name
            group_name = group_name.strip()

            # Remove current text from this input
            self.scraper.element_delete_text(search_input_selector)
            # Enter the title of the group in the input for search
            self.scraper.element_send_keys(search_input_selector, group_name[:51])

            self.scraper.element_click_by_xpath(f'//span[text()="{group_name}"]')

            if self.scraper.find_element('[aria-label="Create a public post…"]', False, 3):
                self.scraper.element_send_keys('[aria-label="Create a public post…"]', data.Description)
            elif self.scraper.find_element('[aria-label="Write something..."]', False, 3):
                self.scraper.element_send_keys('[aria-label="Write something..."]', data.Description)

            self.scraper.element_click('[aria-label="Post"]:not([aria-disabled])')
            # Wait till the post is posted successfully
            self.scraper.element_wait_to_be_invisible('[role="dialog"]')
            self.scraper.element_wait_to_be_invisible('[aria-label="Loading...]"')
            self.scraper.find_element_by_xpath('//span[text()="Shared to your group."]', False, 10)

    def find_listing_by_title(self, title):
        search_input = self.scraper.find_element('input[placeholder="Search your listings"]', False)
        # Search input field is not existing
        if not search_input:
            return None

        # Clear input field for searching listings before entering title
        self.scraper.element_delete_text('input[placeholder="Search your listings"]')
        # Enter the title of the listing in the input for search
        self.scraper.element_send_keys('input[placeholder="Search your listings"]', title)

        return self.scraper.find_element_by_xpath(f'//span[text()="{title}"]', False, 10)

    def find_other_listing_by_title(self, title):
        locator = 'input[placeholder="Search listings"]'
        search_input = self.scraper.find_element(locator, False)
        # Search input field is not existing
        if not search_input:
            return None

        # Clear input field for searching listings before entering title
        self.scraper.element_delete_text(locator)
        # Enter the title of the listing in the input for search
        self.scraper.element_send_keys(locator, title)

        return self.scraper.find_element_by_xpath(f'//span[text()="{title}"]', False, 10)

    def report_listing(self, url: str):
        self.scraper.go_to_page(url)
        more_options_locator = '[aria-label="More Item Options"]'
        report_option_locator = '//span[contains(text(), "Report listing")]'
        report_list_locator = '[role="list"]'
        done_button_locator = "[aria-label='Done']"
        self.scraper.element_wait_to_be_present(more_options_locator)
        more_options = self.scraper.driver.find_element(By.CSS_SELECTOR, more_options_locator)
        more_options.click()
        foo = self.scraper.element_wait_to_be_present(report_option_locator, By.XPATH)
        report_option = self.scraper.find_element_by_xpath(report_option_locator)
        report_option.click()
        self.scraper.element_wait_to_be_present(report_list_locator)
        report_list = self.scraper.driver.find_element(By.CSS_SELECTOR, report_list_locator)
        promote_business = report_list.find_element(By.XPATH, "./child::*[2]")
        # self.scraper.driver.execute_script("arguments[0].style.border='3px solid red'", promote_business)
        promote_business.click()
        self.scraper.element_wait_to_be_present(done_button_locator)
        self.scraper.find_element(done_button_locator).click()

    @classmethod
    def load_listings_from_json(cls, file_path: str, equipment_filter: Optional[List[str]] = None) -> List[ListingData]:
        with open(file_path, 'r') as file:
            data = json.load(file)

        listings = []
        for listing in data.get('listings', []):
            # Convert JSON dictionary to ListingData object
            listing_data = ListingData(**listing)

            # Filter based on equipment if the filter is provided
            if equipment_filter:
                # Check if any of the equipment in the filter matches any of the listing's equipment
                if listing_data.Equipment and any(eq in listing_data.Equipment for eq in equipment_filter):
                    listings.append(listing_data)
            else:
                # If no filter, add all listings
                listings.append(listing_data)

        return listings

    @classmethod
    def load_and_templatize_listings(cls, file_path: str) -> List[ListingData]:
        with open(file_path, 'r') as file:
            data = json.load(file)

        listings = []
        for listing in data.get('listings', []):
            # Create ListingData object
            listing_data = ListingData(**listing)

            # Convert the ListingData object to a dictionary for string formatting
            listing_dict = asdict(listing_data)

            # Replace placeholders in Description with actual values
            listing_data.Description = listing_data.Description.format(**listing_dict)
            listings.append(listing_data)

        return listings
