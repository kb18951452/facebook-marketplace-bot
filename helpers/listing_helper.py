# Remove and then publish each listing
import os
import random
import re

from selenium.webdriver.common.by import By
from dataclasses import dataclass
from typing import List, Optional
import logging
import time
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, StaleElementReferenceException


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

    def _extract_clicks_from_card(self, button_element):
        """Walk up the DOM from the 'More options' button to find 'N clicks on listing'."""
        node = button_element
        for _ in range(8):
            try:
                node = node.find_element(By.XPATH, "..")
                m = re.search(r'(\d[\d,]*)\s*clicks?\s+on\s+listing', node.text, re.IGNORECASE)
                if m:
                    return int(m.group(1).replace(",", ""))
            except Exception:
                break
        return None

    def _safe_click(self, element):
        """Click an element, retrying once on StaleElementReferenceException."""
        try:
            element.click()
        except StaleElementReferenceException:
            return False
        except ElementClickInterceptedException:
            self.scraper.driver.execute_script("arguments[0].click();", element)
        return True

    def remove_all_listings(self, before_delete=None):
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

            try:
                self.scraper.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", more_options)
            except StaleElementReferenceException:
                continue

            # Snapshot clicks and title before deleting
            if before_delete:
                try:
                    aria  = more_options.get_attribute("aria-label") or ""
                    title = aria.replace("More options for ", "", 1).strip()
                    clicks = self._extract_clicks_from_card(more_options)
                    before_delete(title, clicks)
                except Exception:
                    pass

            self.scraper.wait_random_time()
            if not self._safe_click(more_options):
                continue  # stale — re-find on next iteration

            # Click "Delete listing"
            self.scraper.wait_random_time()
            delete_btn = self.scraper.find_element_by_xpath(
                '//span[normalize-space(text())="Delete listing"]',
                exit_on_missing_element=False,
                wait_element_time=10
            )
            if not delete_btn:
                continue
            if not self._safe_click(delete_btn):
                continue

            # Confirm deletion
            self.scraper.wait_random_time()
            confirm_xpath = (
                '//div[@aria-label="Delete" and @role="button" and @tabindex="0" '
                'and descendant::span[normalize-space(text())="Delete"]]'
            )
            confirm_btn = self.scraper.find_element_by_xpath(
                confirm_xpath, exit_on_missing_element=False, wait_element_time=10
            )
            if not confirm_btn:
                continue
            if not self._safe_click(confirm_btn):
                continue

            print("Confirmed deletion...")

            # Handle the survey dialog ("I'd rather not answer" → Next)
            self.scraper.wait_random_time()
            self.handle_delete_confirmation_dialog()

            print("Deleted one listing.")
            self.scraper.wait_random_time()


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

        # Log all inputs/textareas visible on the page so we can identify changed selectors
        fields_info = self.scraper.driver.execute_script("""
            return Array.from(document.querySelectorAll('input:not([type="file"]), textarea'))
                .map(function(el) {
                    return '[' + (el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.tagName) + ']';
                }).join(', ');
        """)
        logger.info(f"Form fields on create page: {fields_info}")

        images_path = data.images
        self.scraper.input_file_add_files('input[accept="image/*,image/heif,image/heic"]', images_path)

        # Add specific fields based on the listing_type
        function_name = f'add_fields_for_{listing_type}'
        getattr(self, function_name)(data)

        self.scraper.element_send_keys_by_xpath("//span[normalize-space(text())='Price']/following-sibling::input[1]",
                                                data.price)

        # Try multiple selectors for Description
        desc_filled = False
        desc_xpaths = [
            "//label[.//span[normalize-space(text())='Description']]//textarea",
            "//textarea[@aria-label='Description']",
            "//textarea[contains(@aria-label,'escription')]",
            "//textarea[contains(@placeholder,'escription') or contains(@placeholder,'escription')]",
            "//textarea[1]",
        ]
        for xp in desc_xpaths:
            el = self.scraper.find_element_by_xpath(xp, exit_on_missing_element=False, wait_element_time=5)
            if el:
                self.scraper.element_send_keys_by_xpath(xp, data.description)
                logger.info(f"Description filled via: {xp}")
                desc_filled = True
                break
        if not desc_filled:
            logger.error("Could not find Description textarea — listing will be incomplete.")

        # Fill Location on page 1 if it's there (FB moved it from page 2 to page 1)
        location_xpaths = [
            '//input[@aria-label="Location"]',
            '//input[@placeholder="Location"]',
            '//input[@aria-label="Neighborhood"]',
            '//input[contains(@aria-label,"ocation")]',
        ]
        for xp in location_xpaths:
            el = self.scraper.find_element_by_xpath(xp, exit_on_missing_element=False, wait_element_time=5)
            if el:
                self.scraper.element_send_keys_by_xpath(xp, data.location)
                self.scraper.element_click('ul[role="listbox"] li:first-child > div')
                logger.info("Location filled on page 1.")
                break

        self.find_and_click_next()

        # If FB still shows a location page (old flow), fill it there too
        location_el = None
        for xp in location_xpaths:
            el = self.scraper.find_element_by_xpath(xp, exit_on_missing_element=False, wait_element_time=5)
            if el:
                location_el = xp
                break
        if location_el:
            self.scraper.element_send_keys_by_xpath(location_el, data.location)
            self.scraper.element_click('ul[role="listbox"] li:first-child > div')
            self.find_and_click_next()

        # Try to click Publish — works whether we went through 1 or 2 Next steps
        publish_candidates = [
            ('css',   'div[aria-label="Publish"]:not([aria-disabled])'),
            ('xpath', '//div[@aria-label="Publish" and @role="button" and not(@aria-disabled)]'),
            ('xpath', '//span[normalize-space(text())="Publish"]/ancestor::div[@role="button"][1]'),
        ]
        published = False
        for kind, sel in publish_candidates:
            if kind == 'css':
                el = self.scraper.find_element(sel, exit_on_missing_element=False, wait_element_time=8)
            else:
                el = self.scraper.find_element_by_xpath(sel, exit_on_missing_element=False, wait_element_time=8)
            if el:
                if kind == 'css':
                    self.scraper.element_click(sel)
                else:
                    self.scraper.element_click_by_xpath(sel)
                published = True
                break

        if not published:
            screenshot_path = f"screenshot_publish_missing_{int(time.time())}.png"
            self.scraper.driver.save_screenshot(screenshot_path)
            logger.error(f"Could not find Publish button. Screenshot saved to {screenshot_path}.")

        if not next_button:
            self.post_listing_to_multiple_groups(data, listing_type)

    def find_and_click_next(self):
        candidates = [
            ('xpath', '//div[@aria-label="Next" and @role="button" and @tabindex="0"]'),
            ('css',   'div[aria-label="Next"][role="button"][tabindex="0"]'),
            ('xpath', '//div[@aria-label="Next" and @role="button"]'),
            ('xpath', '//div[@role="button" and .//span[normalize-space(text())="Next"] and not(ancestor::*[@aria-label="Image"])]'),
        ]
        for kind, sel in candidates:
            if kind == 'css':
                el = self.scraper.find_element(sel, exit_on_missing_element=False, wait_element_time=5)
            else:
                el = self.scraper.find_element_by_xpath(sel, exit_on_missing_element=False, wait_element_time=5)
            if el:
                self.scraper.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                time.sleep(0.5)
                el.click()
                self.scraper.wait_random_time()
                return True

        # JS fallback: find first role=button whose visible text is exactly "Next"
        clicked = self.scraper.driver.execute_script("""
            var btns = Array.from(document.querySelectorAll('[role="button"]'));
            var btn = btns.find(function(el) {
                return el.innerText && el.innerText.trim() === 'Next';
            });
            if (btn) { btn.click(); return true; }
            // Log what buttons exist for debugging
            return btns.map(function(el) {
                return (el.getAttribute('aria-label') || el.innerText || '').trim().substring(0,40);
            }).join(' | ');
        """)
        if clicked is True:
            self.scraper.wait_random_time()
            return True
        logger.warning(f"find_and_click_next: no Next button found. Buttons on page: {clicked}")
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
        # Try known selectors for the Category field (FB changes these periodically)
        category_selectors = [
            "input[aria-label='Category']",
            "input[placeholder='Category']",
            "input[aria-label='category']",
        ]
        category_xpaths = [
            "//label[.//span[normalize-space(text())='Category']]//input",
            "//div[@aria-label='Category' and @role='combobox']",
            "//span[normalize-space(text())='Category']/ancestor::div[@role='button'][1]",
        ]
        category_el = None
        for sel in category_selectors:
            el = self.scraper.find_element(sel, exit_on_missing_element=False, wait_element_time=5)
            if el:
                category_el = ('css', sel)
                break
        if not category_el:
            for xp in category_xpaths:
                el = self.scraper.find_element_by_xpath(xp, exit_on_missing_element=False, wait_element_time=5)
                if el:
                    category_el = ('xpath', xp)
                    break

        if not category_el:
            logger.warning("Category field not found — Facebook may have removed it. Skipping.")
        else:
            if category_el[0] == 'css':
                self.scraper.scroll_to_element(category_el[1])
                self.scraper.element_click(category_el[1])
            else:
                self.scraper.scroll_to_element_by_xpath(category_el[1])
                self.scraper.element_click_by_xpath(category_el[1])

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
