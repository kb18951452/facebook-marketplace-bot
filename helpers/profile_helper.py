from selenium.webdriver.common.by import By
from listing_helper import Listing

# profiles_to_monitor = ['100000068273898']


def scan_profile(scraper, profile_id):
    listing = Listing(scraper)
    scraper.go_to_page(f'https://www.facebook.com/marketplace/profile/{profile_id}/')
    search_listings_locator = 'input[placeholder="Search listings"]'
    scraper.element_wait_to_be_present(search_listings_locator)
    listing.find_other_listing_by_title("rent")
    foo = scraper.driver.find_element(By.CSS_SELECTOR, search_listings_locator)
    bar = foo.find_element(By.XPATH, "./../../..")
    matching_listings = bar.find_elements(By.XPATH, "following-sibling::*[1]/child::*[2]/child::*")
    scraper.driver.execute_script("arguments[0].style.border='3px solid red'", foo)
    urls = []
    for i in range(len(matching_listings)):
        matching_listings = bar.find_elements(By.XPATH, "following-sibling::*[1]/child::*[2]/child::*")
        print(urls)
        item = matching_listings[i]
        a_tag = item.find_elements(By.TAG_NAME, 'a')
        if a_tag:
            url = a_tag[0].get_attribute("href")
            urls.append(url)
    for url in urls:
        listing.report_listing(url)