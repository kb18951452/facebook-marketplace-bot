"""
Dry-run: iterate get_listings() and print what would be published.
No browser, no Facebook — just verifies pool coverage and content.

Usage:
    python scripts/dry_run.py            # first 20 listings
    python scripts/dry_run.py 50         # first 50
    python scripts/dry_run.py all        # all 416
"""

import sys
import os
import itertools

# Allow imports from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helpers.ads import get_listings, _pick_from_pool

def main():
    limit_arg = sys.argv[1] if len(sys.argv) > 1 else "20"
    limit = None if limit_arg == "all" else int(limit_arg)

    pool_hits = 0
    fallbacks = 0
    seen_slots = set()

    listings = get_listings()
    if limit:
        listings = itertools.islice(listings, limit)

    print(f"\n{'SOURCE':<10} {'EQUIPMENT':<12} {'CITY':<28} {'TITLE'}")
    print("-" * 100)

    for listing in listings:
        city = listing.location.split(', ')[0]
        slot = f"{listing.equipment_type}_{city}_{listing.lang}"

        # Check if this came from the pool
        pool_title, _ = _pick_from_pool(listing.equipment_type, city, listing.lang)
        from_pool = pool_title is not None

        if from_pool:
            pool_hits += 1
            source = "[POOL]"
        else:
            fallbacks += 1
            source = "[FALLBACK]"

        seen_slots.add(slot)
        title_preview = listing.title[:60] + ("…" if len(listing.title) > 60 else "")
        print(f"{source:<10} {listing.equipment_type:<12} {city:<28} {title_preview}")

    total = pool_hits + fallbacks
    print("-" * 100)
    print(f"\nSummary: {total} listings — {pool_hits} from pool ({100*pool_hits//total if total else 0}%), {fallbacks} fallback")

    if fallbacks:
        print(f"\nFALLBACK slots (missing from pool):")
        listings2 = get_listings()
        if limit:
            listings2 = itertools.islice(listings2, limit)
        for listing in listings2:
            city = listing.location.split(', ')[0]
            pool_title, _ = _pick_from_pool(listing.equipment_type, city, listing.lang)
            if pool_title is None:
                print(f"  {listing.equipment_type}_{city}_{listing.lang}")

if __name__ == "__main__":
    main()
