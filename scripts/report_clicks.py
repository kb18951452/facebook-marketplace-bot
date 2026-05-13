"""
Scrapes view counts from the FB Marketplace selling dashboard and
ships one JSON event per listing to Sumo Logic.

Usage (run from repo root):
    python scripts/report_clicks.py
"""
import sys
import os
import json
import re
import requests
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helpers.scraper import Scraper
from selenium.webdriver.common.by import By

SUMO_ENDPOINT = (
    "https://endpoint4.collection.sumologic.com/receiver/v1/http/"
    "ZaVnC4dhaV1WAXKlyVji5qYz_JFGGVzGAmMiumPVN4oprAXf1_b8seo08i1q9WXgAGF5GcYAxtgdmv9q-g54LzeLLW5JtGwEXJD3hTt-WQvT2cqJLTiUuA=="
)


def load_city_lookup():
    with open("data/cities_data.json") as f:
        return {c["city"]: c for c in json.load(f)}


def load_title_to_slot():
    """Returns {title: slot_key} from state.json."""
    if not os.path.exists("state.json"):
        return {}
    with open("state.json") as f:
        state = json.load(f)
    return {title: slot for slot, title in state.items()}


def city_from_slot(slot):
    # slot = "mini-ex_Waco_eng"  or  "trackloader_Harker Heights_eng"
    parts = slot.split("_")
    return " ".join(parts[1:-1])


def equip_from_slot(slot):
    return slot.split("_")[0]


def extract_clicks(driver, button_element):
    """
    Walk up the DOM from the 'More options' button to find a view count.
    Facebook typically renders "N views" somewhere in the listing card.
    Returns an int or None if not found.
    """
    node = button_element
    for _ in range(8):
        try:
            node = node.find_element(By.XPATH, "..")
            text = node.text
            m = re.search(r'(\d[\d,]*)\s*clicks?\s+on\s+listing', text, re.IGNORECASE)
            if m:
                return int(m.group(1).replace(",", ""))
        except Exception:
            break
    return None


def send_to_sumo(payload):
    resp = requests.post(
        SUMO_ENDPOINT,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=10,
    )
    resp.raise_for_status()


def main():
    city_lookup   = load_city_lookup()
    title_to_slot = load_title_to_slot()

    if not title_to_slot:
        print("state.json is empty or missing — nothing to report.")
        return

    scraper = Scraper("https://facebook.com")
    scraper.add_login_functionality(
        "https://facebook.com", 'svg[aria-label="Your profile"]', "facebook"
    )
    scraper.go_to_page("https://www.facebook.com/marketplace/you/selling/")

    # Wait for listings to render
    scraper.wait_random_time()
    scraper.wait_random_time()

    buttons = scraper.driver.find_elements(
        By.XPATH,
        '//div[starts-with(@aria-label, "More options for ") and @role="button"]',
    )

    if not buttons:
        print("No listing buttons found — page may not have loaded or no active listings.")
        return

    print(f"\nFound {len(buttons)} listing(s) on the selling page.\n")
    print(f"{'STATUS':<8} {'EQUIP':<14} {'CITY':<26} {'CLICKS':>6}  TITLE")
    print("-" * 100)

    ts   = datetime.now(timezone.utc).isoformat()
    sent = skipped = errors = 0

    for btn in buttons:
        aria  = btn.get_attribute("aria-label") or ""
        title = aria.removeprefix("More options for ").strip()

        slot = title_to_slot.get(title)
        if not slot:
            print(f"{'[SKIP]':<8} — title not in state.json: {title[:70]}")
            skipped += 1
            continue

        city      = city_from_slot(slot)
        equip     = equip_from_slot(slot)
        city_data = city_lookup.get(city, {})
        clicks    = extract_clicks(scraper.driver, btn)

        payload = {
            "timestamp":      ts,
            "title":          title,
            "city":           city,
            "state":          city_data.get("state", "TX"),
            "lat":            float(city_data["lat"])  if city_data.get("lat")  else None,
            "lng":            float(city_data["lng"])  if city_data.get("lng")  else None,
            "equipment_type": equip,
            "clicks":         clicks,
        }

        try:
            send_to_sumo(payload)
            clicks_str = str(clicks) if clicks is not None else "n/a"
            print(f"{'[SENT]':<8} {equip:<14} {city:<26} {clicks_str:>6}  {title[:50]}")
            sent += 1
        except Exception as e:
            print(f"{'[ERR]':<8} Sumo POST failed — {e} — {title[:50]}")
            errors += 1

    print("-" * 100)
    print(f"\nDone: {sent} sent, {skipped} skipped (not in state.json), {errors} errors.")


if __name__ == "__main__":
    main()
