"""
check_city_distances.py — Flag cities in data/cities_data.json whose geocoded
lat/lng puts them implausibly far from Waco, TX (e.g. a city name that
resolved to a same-named town in another state or country).

The legitimate Central Texas service area tops out around 55 miles from
Waco. A bad geocode lands hundreds or thousands of miles away, so a 100-mile
threshold catches those with no false positives among real cities.

Run once (or on a schedule):
    python check_city_distances.py            # report only
    python check_city_distances.py --add       # also append new flags to data/bad_cities.json
"""

import argparse
import json
import math

CITIES_FILE = "data/cities_data.json"
BAD_CITIES_FILE = "data/bad_cities.json"
WACO = (31.5493, -97.1467)  # matches competitor_scraper.py's "Waco default"
THRESHOLD_MILES = 100


def haversine_miles(lat1, lng1, lat2, lng2) -> float:
    R = 3958.8  # earth radius, miles
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def find_far_cities(threshold_miles: float = THRESHOLD_MILES) -> list:
    with open(CITIES_FILE, encoding="utf-8") as f:
        cities = json.load(f)

    flagged = []
    for c in cities:
        try:
            lat, lng = float(c["lat"]), float(c["lng"])
        except (TypeError, ValueError, KeyError):
            flagged.append({"city": c.get("city", "?"), "distance_miles": None, "reason": "missing/invalid lat/lng"})
            continue
        distance = haversine_miles(*WACO, lat, lng)
        if distance > threshold_miles:
            flagged.append({"city": c["city"], "distance_miles": round(distance, 1), "reason": "too far from Waco"})
    return flagged


def load_bad_cities() -> list:
    with open(BAD_CITIES_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_bad_cities(cities: list) -> None:
    with open(BAD_CITIES_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(cities), f, indent=4)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=THRESHOLD_MILES, help=f"Flag cities farther than this many miles from Waco (default: {THRESHOLD_MILES})")
    parser.add_argument("--add", action="store_true", help="Append newly-flagged cities to data/bad_cities.json (picked up by cleanup_bad_cities.py)")
    args = parser.parse_args()

    flagged = find_far_cities(args.threshold)

    if not flagged:
        print(f"No cities beyond {args.threshold} miles from Waco. Nothing to flag.")
        return

    print(f"Flagged {len(flagged)} cities beyond {args.threshold} miles from Waco:")
    for f in flagged:
        print(f"  {f['city']:25s} {f['distance_miles']}mi  ({f['reason']})")

    if args.add:
        existing = set(load_bad_cities())
        new = {f["city"] for f in flagged} - existing
        if new:
            save_bad_cities(list(existing | new))
            print(f"\nAdded {len(new)} new cities to {BAD_CITIES_FILE}: {sorted(new)}")
            print("Run cleanup_bad_cities.py to remove their live listings.")
        else:
            print(f"\nAll flagged cities are already in {BAD_CITIES_FILE}.")
    else:
        print("\n(dry run — re-run with --add to append these to data/bad_cities.json)")


if __name__ == "__main__":
    main()
