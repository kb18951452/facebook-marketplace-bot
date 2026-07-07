"""
slot_status.py — Deterministic slot-coverage report for the FB Marketplace bot.

Compares the current expected slot universe (cities x equipment x task
variants x 'eng', per helpers/ads.py:get_listings) against state.json
(published) and data/duplicate_history.json (FB-flagged duplicates).

Run from repo root:
    python .claude/skills/slot-status/slot_status.py
    python .claude/skills/slot-status/slot_status.py --json
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from helpers.ads import get_equipment, get_locations, TASK_VARIANTS  # noqa: E402
from helpers.slot import build as build_slot, parse as parse_slot  # noqa: E402


def expected_slots() -> set:
    equipment = get_equipment()
    cities = [loc["city"] for loc in get_locations()]
    slots = set()
    for city in cities:
        for item in equipment:
            for task in TASK_VARIANTS.get(item, []):
                slots.add(build_slot(item, city, "eng", task["slug"]))
    return slots


def load_json(path: str) -> dict:
    p = ROOT / path
    if not p.exists():
        return {}
    with open(p) as f:
        return json.load(f)


def build_report() -> dict:
    expected = expected_slots()
    state = load_json("state.json")
    dupes = load_json("data/duplicate_history.json")

    published = set(state.keys())
    pending = expected - published
    published_current = expected & published
    legacy = published - expected  # e.g. old 'spa' slots, removed cities/tasks

    by_city = Counter()
    for slot in pending:
        parsed = parse_slot(slot)
        if parsed:
            by_city[parsed.city] += 1

    by_equipment_pending = Counter()
    for slot in pending:
        parsed = parse_slot(slot)
        if parsed:
            by_equipment_pending[parsed.equipment_type] += 1

    legacy_lang = Counter()
    for slot in legacy:
        parsed = parse_slot(slot)
        legacy_lang[parsed.lang if parsed else "unparsed"] += 1

    return {
        "expected_total": len(expected),
        "published_count": len(published_current),
        "pending_count": len(pending),
        "legacy_count": len(legacy),
        "duplicate_flagged_count": len(dupes),
        "duplicate_still_pending": len(set(dupes.keys()) & pending),
        "pending_by_city_top20": by_city.most_common(20),
        "pending_by_equipment": dict(by_equipment_pending),
        "legacy_by_lang": dict(legacy_lang),
    }


def print_report(report: dict) -> None:
    print("=== Slot Status ===")
    print(f"Expected slots (current cities x equipment x tasks, eng only): {report['expected_total']}")
    print(f"Published (in state.json, still expected):                    {report['published_count']}")
    print(f"Pending (expected, not yet published):                        {report['pending_count']}")
    print(f"Legacy (in state.json, no longer in expected universe):       {report['legacy_count']}")
    print(f"  by language: {report['legacy_by_lang']}")
    print(f"Duplicate-flagged (data/duplicate_history.json):              {report['duplicate_flagged_count']}")
    print(f"  of which still pending:                                     {report['duplicate_still_pending']}")
    print()
    print("Pending by equipment type:")
    for k, v in report["pending_by_equipment"].items():
        print(f"  {k}: {v}")
    print()
    print("Top 20 cities by pending slot count:")
    for city, count in report["pending_by_city_top20"]:
        print(f"  {city}: {count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Print raw JSON instead of a formatted report")
    args = parser.parse_args()

    rep = build_report()
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print_report(rep)
