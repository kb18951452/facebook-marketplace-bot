# Remove and then publish each listing
import os
import random

from selenium.webdriver.common.by import By
from dataclasses import dataclass
from typing import List, Optional
import logging
import time
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException


logger = logging.getLogger(__name__)


@dataclass
class ListingData:
    images: Optional[List[str]] = None
    price: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    title: Optional[str] = None
    category: Optional[str] = None
    condition: Optional[str] = "Used - Like New"
    groups: Optional[str] = None
    equipment_type: Optional[str] = None
    lang: Optional[str] = None


class Listing:
    def __init__(self, scraper):
        self.scraper = scraper

    def delete_open_listing(self):
        # Click on the delete listing button
        self.scraper.element_click('div[aria-label="Delete marketplace listing"][role="button"]')
        # Click on confirm button to delete
        confirm_delete_selector_xpath = '//*[@aria-label="Delete" and @role="button" and @tabindex="0" and descendant::span[text()="Delete"]]'

        if self.scraper.find_element_by_xpath(confirm_delete_selector_xpath, False):
            self.scraper.element_click_by_xpath(confirm_delete_selector_xpath)
        else:
            dialog_selector = 'div[aria-label="Delete listing"] div[aria-label="Delete"][tabindex="0"]'
            dialog = self.scraper.find_element(dialog_selector)

            # Find the 'Delete' button within the dialog
            delete_button = dialog.find_element(By.XPATH, ".//div[@aria-label='Delete']")

        # Wait until the popup is closed
        self.scraper.element_wait_to_be_invisible('div[aria-label="Your Listing"]')

    def update_listings(self, listings: List[ListingData], listing_type: str) -> None:
        if not listings:
            return

        for listing in listings:
            self.publish_listing(listing, listing_type)

    def remove_listing_by_title(self, title: str):
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
            confirm_delete_selector = 'div[aria-label="Delete Listing"] div[aria-label="Delete"][tabindex="0"]'
            if self.scraper.find_element(confirm_delete_selector, True, 3):
                self.scraper.element_click(confirm_delete_selector)

        # Wait until the popup is closed
        self.scraper.element_wait_to_be_invisible('div[aria-label="Your Listing"]')

    def remove_all_listings(self):
        print("Starting to delete all Marketplace listings...")

        while True:
            more_options = self.scraper.find_element_by_xpath(
                '//div[starts-with(@aria-label, "More options for ") and @role="button" and @tabindex="0"]',
                exit_on_missing_element=False,
                wait_element_time=15
            )

            if not more_options:
                print("No more listings found — all deleted!")
                return

            self.scraper.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", more_options)

            try:
                more_options.click()
            except ElementClickInterceptedException:
                self.scraper.driver.execute_script("""
                    const el = arguments[0];

                    // Mousedown
                    let downEvent = new MouseEvent('mousedown', {
                        bubbles: true,
                        cancelable: true,
                        view: window,
                        button: 0
                    });
                    el.dispatchEvent(downEvent);

                    // Small delay
                    setTimeout(() => {
                        // Mouseup
                        let upEvent = new MouseEvent('mouseup', {
                            bubbles: true,
                            cancelable: true,
                            view: window,
                            button: 0
                        });
                        el.dispatchEvent(upEvent);

                        // Click (as fallback)
                        let clickEvent = new MouseEvent('click', {
                            bubbles: true,
                            cancelable: true,
                            view: window,
                            button: 0
                        });
                        el.dispatchEvent(clickEvent);
                    }, 50);
                """, more_options)

            # Click "Delete listing"
            delete_btn = self.scraper.find_element_by_xpath(
                '//span[normalize-space(text())="Delete listing"]',
                wait_element_time=10
            )
            if delete_btn:
                try:
                    delete_btn.click()
                except ElementClickInterceptedException:
                    self.scraper.driver.execute_script("arguments[0].click();", delete_btn)

            # Confirm deletion
            confirm_xpath = (
                '//div[@aria-label="Delete" and @role="button" and @tabindex="0" '
                'and descendant::span[normalize-space(text())="Delete"]]'
            )
            confirm_btn = self.scraper.find_element_by_xpath(
                confirm_xpath, wait_element_time=10
            )
            if confirm_btn:
                try:
                    confirm_btn.click()
                except ElementClickInterceptedException:
                    self.scraper.driver.execute_script("arguments[0].click();", confirm_btn)

            print("Confirmed deletion...")

            # Handle the new survey dialog ("I'd rather not answer" → Next)
            self.handle_delete_confirmation_dialog()

            print("Deleted one listing.")


    def remove_duplicate_listings(self):
        while True:
            duplicate = self.find_duplicate_listing()

            # Listing not found so stop the function
            if not duplicate:
                return False

            duplicate.click()

            self.delete_open_listing()

            # return True

    def remove_listing(self,data, listing_type):
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
            confirm_delete_selector = 'div[aria-label="Delete Listing"] div[aria-label="Delete"][tabindex="0"]'
            if self.scraper.find_element(confirm_delete_selector, True, 3):
                self.scraper.element_click(confirm_delete_selector)

        # Wait until the popup is closed
        self.scraper.element_wait_to_be_invisible('div[aria-label="Your Listing"]')

    def publish_listing(self, data: ListingData, listing_type):
        logger.info(f"Creating \"{data.title}\"")
        self.scraper.go_to_page('https://facebook.com/marketplace/create/' + listing_type)

        # Add a delay before starting form filling

        images_path = data.images
        # Add images to the listing
        self.scraper.input_file_add_files('input[accept="image/*,image/heif,image/heic"]', images_path)


        # Add specific fields based on the listing_type
        function_name = f'add_fields_for_{listing_type}'
        # Call functions by name dynamically
        getattr(self, function_name)(data)


        self.scraper.element_send_keys_by_xpath("//span[normalize-space(text())='Price']/following-sibling::input[1]",
                                                data.price)

        self.scraper.element_send_keys_by_xpath("//label[.//span[normalize-space(text())='Description']]//textarea",
                                                data.description)

        next_button = self.find_and_click_next()
        self.scraper.element_send_keys_by_xpath('//input[@aria-label="Location"]', data.location)
        self.scraper.element_click('ul[role="listbox"] li:first-child > div')
        new_next_button = self.find_and_click_next()

        if new_next_button:
            # # Add listing to multiple groups
            # self.add_listing_to_multiple_groups(data)
            # self.find_and_click_next()
            # Publish the listing
            self.scraper.element_click('div[aria-label="Publish"]:not([aria-disabled])')

        if not next_button:
            self.post_listing_to_multiple_groups(data, listing_type)

    def find_and_click_next(self):
        next_button_selector = 'div [aria-label="Next"] > div'
        next_button = self.scraper.find_element(next_button_selector, False)
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

    def add_fields_for_item(self, data: ListingData):
        self.scraper.element_send_keys_by_xpath("//span[normalize-space(text())='Title']/following-sibling::input[1]",
                                                data.title)

        # Scroll to "Category" select field
        self.scraper.scroll_to_element("input[aria-label='Category']")
        # Expand category select
        self.scraper.element_click("input[aria-label='Category']")
        # Select category
        self.scraper.element_click_by_xpath(f'//span[text()="{data.category}"]')


        # --- Condition selection (updated for robustness) ---
        try:
            # First, try to expand the Condition dropdown
            condition_combobox_xpath = "//label[@role='combobox' and .//span[normalize-space(text())='Condition']]"
            self.scraper.scroll_to_element_by_xpath(condition_combobox_xpath)
            self.scraper.element_click_by_xpath(condition_combobox_xpath, delay=True)

            # Now select "Used - Like New"
            condition_option_xpath = f'//span[@dir="auto"][text()="{data.condition}"]'
            self.scraper.element_click_by_xpath(condition_option_xpath)

            logger.info("Condition selected successfully.")
        except Exception as e:
            logger.error(f"Failed to select Condition: {e}")

            # --- Take screenshot on failure for debugging ---
            screenshot_path = f"screenshot_condition_error_{int(time.time())}.png"
            self.scraper.driver.save_screenshot(screenshot_path)
            logger.info(f"Screenshot saved to: {screenshot_path}")

            # Re-raise to let the script crash (so you see the issue) or handle gracefully
            raise

    @staticmethod
    def generate_title_for_listing_type(data: ListingData, listing_type):
        title = ''

        if listing_type == 'item':
            title = data.title

        # if listing_type == 'vehicle':
        #     title = f'{data.Year} {data.Make} {data.Model}'

        return title

    def add_listing_to_multiple_groups(self, data: ListingData):
        # Create an array for group names by splitting the string by this symbol ";"
        group_names = data.groups.split(';')

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
        group_names = data.groups.split(';')

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

            if self.scraper.find_element('[aria-label="Create a public post…"]', False):
                self.scraper.element_send_keys('[aria-label="Create a public post…"]', data.description)
            elif self.scraper.find_element('[aria-label="Write something..."]', False):
                self.scraper.element_send_keys('[aria-label="Write something..."]', data.description)

            self.scraper.element_click('[aria-label="Post"]:not([aria-disabled])')
            # Wait till the post is posted successfully
            self.scraper.element_wait_to_be_invisible('[role="dialog"]')
            self.scraper.element_wait_to_be_invisible('[aria-label="Loading...]"')
            self.scraper.find_element_by_xpath('//span[text()="Shared to your group."]', False)

    def find_listing_by_title(self, title):
        search_input = self.scraper.find_element('input[placeholder="Search your listings"]', False)
        # Search input field is not existing
        if not search_input:
            return None

        # Clear input field for searching listings before entering title
        self.scraper.element_delete_text('input[placeholder="Search your listings"]')
        # Enter the title of the listing in the input for search
        self.scraper.element_send_keys('input[placeholder="Search your listings"]', title)

        return self.scraper.find_element_by_xpath(f'//span[text()="{title}"]', False, 5)

    def find_duplicate_listing(self):
        return self.scraper.find_element_by_xpath(f'//div[text()="It looks like you created a duplicate listing."]', False)

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

        return self.scraper.find_element_by_xpath(f'//span[text()="{title}"]', False)

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

    # Add this method to your Listing class in listing_helper.py
    # (or call it separately after triggering the delete flow)

    def handle_delete_confirmation_dialog(self):
        """
        Handles the additional survey dialog that appears after confirming deletion.
        Selects "I'd rather not answer" (or "I'd rather not say") and clicks "Next".
        """
        print("Handling post-deletion survey dialog...")

        # Wait for the radio button group / dialog to appear
        radio_label_xpath = '//span[normalize-space(text())="I\'d rather not answer" or normalize-space(text())="I\'d rather not say"]'
        radio_label = self.scraper.find_element_by_xpath(
            radio_label_xpath,
            exit_on_missing_element=False,
            wait_element_time=5
        )

        if not radio_label:
            print("No survey dialog detected — skipping.")
            return

        # The <label> wraps the radio input, clicking the label is safest
        label_container = radio_label.find_element(By.XPATH, "./ancestor::label[1]")

        try:
            label_container.click()
        except ElementClickInterceptedException:
            self.scraper.driver.execute_script("arguments[0].click();", label_container)

        print("Selected 'I'd rather not answer'")

        # Now click the "Next" button
        next_button_xpath = (
            '//div[@aria-label="Next" and @role="button" and @tabindex="0" '
            'and descendant::span[normalize-space(text())="Next"]]'
        )

        next_btn = self.scraper.find_element_by_xpath(
            next_button_xpath,
            wait_element_time=10
        )

        if next_btn:
            try:
                next_btn.click()
            except ElementClickInterceptedException:
                self.scraper.driver.execute_script("arguments[0].click();", next_btn)
            print("Clicked 'Next' in survey dialog")
        else:
            print("Warning: Could not find 'Next' button in survey dialog")
