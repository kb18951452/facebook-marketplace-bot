"""
competitor_scraper.py — Discover competitor skidsteer/excavator rental listings on
FB Marketplace near Waco, TX and save to data/competitors.json.

Two-phase approach:
  Phase 1 — Search several rental terms, collect unique listing URLs + seller profile IDs.
  Phase 2 — Visit each unique seller's marketplace profile to pull ALL their listings.

Run manually when you want to refresh competitor intelligence:
    python competitor_scraper.py
"""

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote

import requests
from selenium.webdriver.common.by import By

from helpers.scraper import Scraper

# ── Config ────────────────────────────────────────────────────────────────────
SEARCH_TERMS = [
    "skidsteer rental",
    "skid steer rental",
    "mini excavator rental",
    "excavator rental",
    "track loader rental",
]
SEARCH_LOCATION = "waco"          # FB Marketplace city slug
SCROLL_PASSES   = 4               # scroll attempts per search page
OUTPUT_FILE     = "data/competitors.json"
LOG_FILE        = "competitor_scraper.log"

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ── Geocoding ─────────────────────────────────────────────────────────────────
with open("data/cities_data.json", encoding="utf-8") as _f:
    _CITIES = json.load(_f)
_CITY_LL = {
    c["city"].lower(): (float(c["lat"]), float(c["lng"]))
    for c in _CITIES if c.get("lat") and c.get("lng")
}

def _geocode(location_text: str):
    loc = location_text.lower()
    for name, ll in _CITY_LL.items():
        if name in loc:
            return ll
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": location_text + ", Texas", "format": "json", "limit": 1},
            headers={"User-Agent": "fb-marketplace-monitor/1.0"},
            timeout=6,
        )
        if r.ok and r.json():
            hit = r.json()[0]
            return float(hit["lat"]), float(hit["lon"])
    except Exception:
        pass
    return 31.5493, -97.1467  # Waco default


# ── Browser init ──────────────────────────────────────────────────────────────
logger.info("Initialising browser and logging in...")
scraper = Scraper("https://facebook.com")
scraper.add_login_functionality(
    "https://facebook.com", 'svg[aria-label="Your profile"]', "facebook"
)
driver = scraper.driver


def _txt(el, css):
    try:
        return el.find_element(By.CSS_SELECTOR, css).text.strip()
    except Exception:
        return ""


def _attr(el, css, attr):
    try:
        return el.find_element(By.CSS_SELECTOR, css).get_attribute(attr) or ""
    except Exception:
        return ""


def _page_text():
    try:
        return driver.find_element(By.TAG_NAME, "body").text
    except Exception:
        return ""


# ── Phase 1: Search — collect unique listing URLs ─────────────────────────────
logger.info("=== Phase 1: Searching for rental listings ===")
listing_urls: set = set()

for term in SEARCH_TERMS:
    url = f"https://www.facebook.com/marketplace/{SEARCH_LOCATION}/search/?query={quote(term)}"
    logger.info(f"Searching: '{term}'")
    try:
        scraper.go_to_page(url)
        time.sleep(3)
        for _ in range(SCROLL_PASSES):
            driver.execute_script("window.scrollBy(0, 1400)")
            time.sleep(1.2)
        links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/marketplace/item/"]')
        before = len(listing_urls)
        for a in links:
            href = (a.get_attribute("href") or "").split("?")[0].rstrip("/")
            if "/marketplace/item/" in href:
                listing_urls.add(href)
        logger.info(f"  +{len(listing_urls) - before} new URLs (total {len(listing_urls)})")
    except Exception as e:
        logger.error(f"  Search failed: {e}")

logger.info(f"Phase 1 complete — {len(listing_urls)} unique listing URLs")


# ── Phase 2: Visit each listing — extract seller profile IDs + basic metadata ──
logger.info("=== Phase 2: Visiting listings to find sellers ===")

# sellers[profile_id] = {name, profile_url, profile_id, listings: [...]}
sellers: dict = {}
seen_listing_urls: set = set()


def _extract_location(text: str) -> str:
    """Pull 'City, TX' or 'City, Texas' from arbitrary text."""
    m = re.search(r"([A-Za-z\s\-]+),\s*(TX|Texas)", text)
    return m.group(0).strip() if m else ""


def _extract_price(text: str) -> str:
    m = re.search(r"\$[\d,]+(?:\s*/\s*(?:day|week|month|hr|hour))?", text, re.IGNORECASE)
    return m.group(0) if m else ""


for listing_url in list(listing_urls):
    if listing_url in seen_listing_urls:
        continue
    seen_listing_urls.add(listing_url)
    try:
        scraper.go_to_page(listing_url)
        time.sleep(2)

        page = _page_text()

        # Title: first h1 with meaningful text
        title = ""
        for h1 in driver.find_elements(By.TAG_NAME, "h1"):
            t = h1.text.strip()
            if t and len(t) > 4:
                title = t
                break

        price    = _extract_price(page)
        location = _extract_location(page)

        # Seller profile link
        profile_url = ""
        profile_id  = ""
        seller_name = ""
        prof_links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/marketplace/profile/"]')
        if prof_links:
            href = (prof_links[0].get_attribute("href") or "").split("?")[0].rstrip("/")
            profile_id  = href.split("/")[-1]
            profile_url = href
            # Try to get name from text near the link
            try:
                parent = driver.execute_script(
                    "return arguments[0].closest('[role]') || arguments[0].parentElement.parentElement",
                    prof_links[0]
                )
                blk = parent.text.strip().split("\n")[0] if parent else ""
                # The seller name usually appears before "Seller" or as the only short line
                seller_name = blk if blk and len(blk) < 60 else ""
            except Exception:
                pass

        if not profile_id:
            logger.warning(f"  No seller profile found for {listing_url} — skipping")
            continue

        lat, lng = _geocode(location or "Waco, TX")
        listing_data = {
            "url":        listing_url,
            "title":      title,
            "price":      price,
            "location":   location or "Waco, TX",
            "lat":        lat,
            "lng":        lng,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }

        if profile_id not in sellers:
            sellers[profile_id] = {
                "name":        seller_name or profile_id,
                "profile_id":  profile_id,
                "profile_url": profile_url,
                "listings":    [],
            }
        elif seller_name and len(seller_name) > len(sellers[profile_id]["name"]):
            sellers[profile_id]["name"] = seller_name  # prefer longer / more descriptive name

        existing = {l["url"] for l in sellers[profile_id]["listings"]}
        if listing_url not in existing:
            sellers[profile_id]["listings"].append(listing_data)

        logger.info(f"  ✓ {title[:50]!r} → seller {profile_id} ({location})")

    except Exception as e:
        logger.error(f"  Failed {listing_url}: {e}")

logger.info(f"Phase 2 complete — {len(sellers)} unique sellers found")


def _save():
    os.makedirs("data", exist_ok=True)
    output = {
        "scraped_at":   datetime.now(timezone.utc).isoformat(),
        "search_terms": SEARCH_TERMS,
        "location":     SEARCH_LOCATION,
        "sellers":      sellers,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    total = sum(len(s["listings"]) for s in sellers.values())
    logger.info(f"[checkpoint] {len(sellers)} sellers / {total} listings saved")


_save()  # immediately available after Phase 2


# ── Phase 3: Visit each seller's marketplace profile for full listing list ────
logger.info("=== Phase 3: Scraping each seller's full profile ===")

for profile_id, seller in sellers.items():
    profile_url = seller["profile_url"] or f"https://www.facebook.com/marketplace/profile/{profile_id}/"
    logger.info(f"Visiting profile: {seller['name']} ({profile_id})")
    try:
        scraper.go_to_page(profile_url)
        time.sleep(3)

        # Try to get the real seller name from the profile header
        try:
            h2_els = driver.find_elements(By.TAG_NAME, "h2")
            for h in h2_els:
                t = h.text.strip()
                if t and len(t) < 60 and "facebook" not in t.lower():
                    seller["name"] = t
                    break
        except Exception:
            pass

        # Scroll to load their listings
        for _ in range(SCROLL_PASSES):
            driver.execute_script("window.scrollBy(0, 1400)")
            time.sleep(1.0)

        # Collect all listing links from their profile
        profile_links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/marketplace/item/"]')
        profile_item_urls = set()
        for a in profile_links:
            href = (a.get_attribute("href") or "").split("?")[0].rstrip("/")
            if "/marketplace/item/" in href:
                profile_item_urls.add(href)

        logger.info(f"  Found {len(profile_item_urls)} listings on profile")

        existing_urls = {l["url"] for l in seller["listings"]}
        new_urls = profile_item_urls - existing_urls

        # Visit each new listing found on their profile
        for item_url in new_urls:
            if item_url in seen_listing_urls:
                continue
            seen_listing_urls.add(item_url)
            try:
                scraper.go_to_page(item_url)
                time.sleep(1.8)
                page = _page_text()

                title = ""
                for h1 in driver.find_elements(By.TAG_NAME, "h1"):
                    t = h1.text.strip()
                    if t and len(t) > 4:
                        title = t
                        break

                price    = _extract_price(page)
                location = _extract_location(page)
                lat, lng = _geocode(location or "Waco, TX")

                seller["listings"].append({
                    "url":        item_url,
                    "title":      title,
                    "price":      price,
                    "location":   location or "Waco, TX",
                    "lat":        lat,
                    "lng":        lng,
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                })
                logger.info(f"  + {title[:50]!r}")
            except Exception as e:
                logger.warning(f"  Failed to visit {item_url}: {e}")

    except Exception as e:
        logger.error(f"Failed to scrape profile {profile_id}: {e}")

    _save()  # persist after each seller profile

logger.info(f"Phase 3 complete")


_save()  # final save

try:
    driver.quit()
except Exception:
    pass
