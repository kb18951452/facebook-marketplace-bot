"""
fuel_price_agent.py — daily diesel price updater

Fetches the current Gulf Coast retail diesel price from the EIA API,
recalculates estimated delivery costs for all 208 cities, and updates
data/cities_data.json if the price has moved more than $0.10/gallon.

Delivery cost formula (reverse-engineered from original data, verified
against all 208 cities):

    estimated_cost = BASE + RATE * distance

    BASE = 25 + 10 * diesel_price        ($25 fixed overhead + 10gal machine fuel)
    RATE = 2.75 + (2/8) * diesel_price   ($2.75/mi labor + round-trip truck fuel)

Original basis: $5.00/gal, 8mpg transport truck, 10gal machine fuel included.

Usage:
    python fuel_price_agent.py            # fetch live price and update if changed
    python fuel_price_agent.py --dry-run  # show what would change, don't write
    python fuel_price_agent.py --price 4.25  # override price (for testing)
"""

import argparse
import json
import logging
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import requests

from helpers.run_outcome import install_crash_logger, record_run

# ── paths ────────────────────────────────────────────────────────────────────
CITIES_FILE      = Path("data/cities_data.json")
FUEL_STATE_FILE  = Path("data/fuel_price.json")
FUEL_HISTORY     = Path("data/fuel_price_history.json")
LOG_FILE         = "fuel_price_agent.log"

# ── constants ─────────────────────────────────────────────────────────────────
FIXED_OVERHEAD   = 25.00   # non-fuel fixed cost per delivery
LABOR_PER_MILE   = 2.75    # non-fuel cost per mile (labor, wear, time)
MACHINE_GALLONS  = 10      # gallons of diesel included with each rental
TRUCK_MPG        = 8.0     # transport truck fuel efficiency

CHANGE_THRESHOLD = 0.10    # minimum price move to trigger an update ($/gal)
ROUND_TO         = 0.10    # round estimated_cost to nearest $0.10

# EIA weekly retail diesel — Gulf Coast (PADD 3), product DPF
# V2 API requires a free key: https://www.eia.gov/opendata/register.php
# Set env var EIA_API_KEY to use it; otherwise falls back to HTML scrape.
EIA_API_URL = (
    "https://api.eia.gov/v2/petroleum/pri/gnd/data/"
    "?frequency=weekly&data[0]=value"
    "&facets[product][]=DPF&facets[duoarea][]=R30"
    "&sort[0][column]=period&sort[0][direction]=desc&length=1"
    "&api_key={key}"
)
# Public HTML page — no key required
EIA_HTML_URL = "https://www.eia.gov/petroleum/gasdiesel/"

# ── logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode="a"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)
install_crash_logger("fuel_price_agent")


# ── cost formula ──────────────────────────────────────────────────────────────
def calc_cost(distance: float, diesel: float) -> float:
    base = FIXED_OVERHEAD + MACHINE_GALLONS * diesel
    rate = LABOR_PER_MILE + (2 / TRUCK_MPG) * diesel
    raw  = base + rate * distance
    return round(round(raw / ROUND_TO) * ROUND_TO, 2)


# ── price fetch ───────────────────────────────────────────────────────────────
def fetch_eia_api(api_key: str) -> float | None:
    """EIA v2 API — requires a free key from https://www.eia.gov/opendata/register.php"""
    try:
        url = EIA_API_URL.format(key=api_key)
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        value = resp.json()["response"]["data"][0]["value"]
        return float(value)
    except Exception as e:
        log.warning(f"EIA API fetch failed: {e}")
        return None


def fetch_eia_html() -> float | None:
    """Scrape EIA's public petroleum/gasdiesel page — no key required.
    Extracts retail diesel prices from the weekly table and returns the
    Gulf Coast / national average value."""
    try:
        resp = requests.get(EIA_HTML_URL, timeout=15,
                            headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        # EIA table cells contain prices like "3.789" or "3.8" (no $ sign in HTML)
        # Match decimal numbers in the diesel price range
        prices = []
        for m in re.finditer(r'>\s*(\d\.\d{2,3})\s*<', resp.text):
            v = float(m.group(1))
            if 2.50 < v < 7.00:
                prices.append(v)
        if not prices:
            return None
        prices.sort()
        # Use the median to avoid outliers (state min/max skew the average)
        median = prices[len(prices) // 2]
        log.info(f"EIA HTML scrape — {len(prices)} price cells found, median ${median:.3f}/gal")
        return median
    except Exception as e:
        log.warning(f"EIA HTML scrape failed: {e}")
        return None


def fetch_diesel_price() -> float | None:
    # 1. Try API key from environment
    api_key = os.environ.get("EIA_API_KEY", "")
    if api_key:
        price = fetch_eia_api(api_key)
        if price is not None:
            log.info(f"EIA API — Gulf Coast diesel: ${price:.3f}/gal")
            return price

    # 2. Scrape EIA public HTML page (no key needed)
    price = fetch_eia_html()
    if price is not None:
        return price

    log.warning("All price sources failed — use --price to set manually")
    return None


# ── state helpers ─────────────────────────────────────────────────────────────
def load_state() -> dict:
    if FUEL_STATE_FILE.exists():
        return json.loads(FUEL_STATE_FILE.read_text())
    return {"diesel_price": 5.00, "last_updated": "never"}


def save_state(price: float):
    FUEL_STATE_FILE.write_text(json.dumps({
        "diesel_price": price,
        "last_updated": date.today().isoformat(),
    }, indent=2))


def append_history(old_price: float, new_price: float, changes: int):
    history = []
    if FUEL_HISTORY.exists():
        history = json.loads(FUEL_HISTORY.read_text())
    history.append({
        "timestamp":  datetime.now(timezone.utc).isoformat(),
        "old_price":  old_price,
        "new_price":  new_price,
        "delta":      round(new_price - old_price, 3),
        "cities_updated": changes,
    })
    FUEL_HISTORY.write_text(json.dumps(history, indent=2))


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run",  action="store_true", help="Show changes without writing")
    parser.add_argument("--price",    type=float, default=None, help="Override diesel price")
    args = parser.parse_args()

    state     = load_state()
    old_price = state["diesel_price"]

    if args.price is not None:
        new_price = args.price
        log.info(f"Using manual override price: ${new_price:.3f}/gal")
    else:
        new_price = fetch_diesel_price()
        if new_price is None:
            record_run("fuel_price_agent", "fatal", note="all price sources failed (EIA API and HTML scrape both unavailable)")
            sys.exit(1)

    delta = abs(new_price - old_price)
    log.info(f"Old price: ${old_price:.3f}  New price: ${new_price:.3f}  Delta: ${delta:.3f}")

    if delta < CHANGE_THRESHOLD and args.price is None:
        log.info(f"Price change ${delta:.3f} below threshold ${CHANGE_THRESHOLD} — no update needed.")
        record_run("fuel_price_agent", "success",
                   metrics={"old_price": old_price, "new_price": new_price, "delta": round(delta, 3), "cities_updated": 0})
        return

    cities = json.loads(CITIES_FILE.read_text())

    changes = 0
    for city in cities:
        old_cost = city["estimated_cost"]
        new_cost = calc_cost(city["distance"], new_price)
        if new_cost != old_cost:
            if not args.dry_run:
                city["estimated_cost"] = new_cost
            changes += 1
            log.info(f"  {city['city']:<25} {old_cost:>8.2f} -> {new_cost:>8.2f}")

    if args.dry_run:
        log.info(f"DRY RUN — would update {changes} cities from ${old_price:.2f} to ${new_price:.2f}/gal.")
        record_run("fuel_price_agent", "success",
                   metrics={"old_price": old_price, "new_price": new_price, "cities_updated": changes, "dry_run": True})
        return

    CITIES_FILE.write_text(json.dumps(cities, indent=4))
    save_state(new_price)
    append_history(old_price, new_price, changes)
    log.info(f"Updated {changes} cities. New diesel basis: ${new_price:.3f}/gal.")
    record_run("fuel_price_agent", "success",
               metrics={"old_price": old_price, "new_price": new_price, "delta": round(delta, 3), "cities_updated": changes})


if __name__ == "__main__":
    main()
