#!/usr/bin/env python3
"""
One-time batch content generator. Submits all listing slots to the Anthropic
Batches API and saves results to data/generated_content.json.

Usage:
    python scripts/generate_content.py          # submit batch
    python scripts/generate_content.py --poll   # poll + save when complete
    python scripts/generate_content.py --status # check status without saving
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).parent.parent))
from helpers.ads import get_equipment, get_locations

CONTENT_FILE = "data/generated_content.json"
BATCH_ID_FILE = "data/.batch_id"
VARIANTS_PER_SLOT = 20
MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """\
You write Facebook Marketplace listing copy for a Central Texas heavy equipment rental business.

Business address: 5510 Old Lorena Road, Lorena, Texas 76655
Phone: 254.655.3339
Payment accepted: Zelle, Venmo, Cash App, PayPal, Check, Cash

Write direct, practical copy for people who need to get work done. No fluff.
Vary your style across listings: sometimes casual, sometimes professional, sometimes urgent.
Titles should focus on the JOB the customer needs done, not just "equipment rental".\
"""

TASKS = {
    "mini-ex": [
        "drainage and trenching", "French drain installation", "irrigation trenches",
        "yard grading and footings", "pond or landscaping work", "leveling an uneven yard",
        "patio or retaining wall site prep", "tree hole digging or sod removal",
        "backfilling trenches", "redirecting foundation drainage",
    ],
    "trackloader": [
        "driveway grading", "fixing a muddy gravel driveway", "spreading topsoil or gravel",
        "moving dirt and debris", "backfilling trenches", "loading pallets with forks",
        "yard prep for sod or seed", "clearing and leveling a site",
        "gravel driveway base work", "material handling",
    ],
}

EQUIPMENT_NAMES = {
    "mini-ex": "Mini Excavator",
    "trackloader": "Track Loader (Skidsteer)",
}


def make_prompt(eq_type, eq_data, city, delivery_cost, n):
    blurb = eq_data["blurb"]["eng"]
    prices = eq_data["prices"]
    tasks = ", ".join(TASKS[eq_type])
    name = EQUIPMENT_NAMES[eq_type]

    return (
        f"Generate {n} unique Facebook Marketplace listing title+description pairs "
        f"for renting a {name} to customers in {city}, Texas.\n\n"
        f"Equipment specs: {blurb}\n"
        f"Daily rate: ${prices['daily']} (multi-day rates available on request — do not list weekly/monthly prices)\n"
        f"Delivery to {city}: ${delivery_cost:.2f} (fuel + drop-off + pickup included)\n"
        f"Common jobs this equipment is used for: {tasks}\n\n"
        f"Rules:\n"
        f"- Titles must be under 80 characters and focus on the specific task\n"
        f"- Descriptions mention {city}, include pricing, delivery cost, address, and payment methods\n"
        f"- Vary tone and structure across all {n} entries — no repeated opening phrases or title formats\n"
        f"- Descriptions should be 100-200 words\n\n"
        f"Return ONLY a JSON array of {n} objects:\n"
        f'[{{"title": "...", "description": "..."}}, ...]'
    )


def submit(equipment, locations, language="eng"):
    client = anthropic.Anthropic()
    requests = []

    for eq_type, eq_data in equipment.items():
        for loc in locations:
            city = loc["city"]
            slot = f"{eq_type}_{city}_{language}"
            requests.append({
                "custom_id": slot,
                "params": {
                    "model": MODEL,
                    "max_tokens": 8192,
                    "system": SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": make_prompt(
                        eq_type, eq_data, city, loc["estimated_cost"], VARIANTS_PER_SLOT
                    )}],
                },
            })

    print(f"Submitting {len(requests)} requests ({VARIANTS_PER_SLOT} variants × {len(requests)} slots)...")
    batch = client.messages.batches.create(requests=requests)

    os.makedirs("data", exist_ok=True)
    Path(BATCH_ID_FILE).write_text(batch.id)
    print(f"Batch submitted: {batch.id}")
    print(f"Run with --poll to collect results (usually ready in a few minutes to ~1 hour).")
    return batch.id


def check_status(client, batch_id):
    batch = client.messages.batches.retrieve(batch_id)
    c = batch.request_counts
    print(
        f"[{batch.processing_status}]  "
        f"processing={c.processing}  succeeded={c.succeeded}  errored={c.errored}"
    )
    return batch


def poll(language="eng"):
    if not Path(BATCH_ID_FILE).exists():
        sys.exit("No batch ID found. Run without --poll first to submit a batch.")

    batch_id = Path(BATCH_ID_FILE).read_text().strip()
    client = anthropic.Anthropic()

    while True:
        batch = check_status(client, batch_id)
        if batch.processing_status == "ended":
            break
        time.sleep(30)

    # Load existing content so re-runs only overwrite completed slots
    existing = {}
    if Path(CONTENT_FILE).exists():
        with open(CONTENT_FILE) as f:
            existing = json.load(f)

    saved, errors = 0, 0
    for result in client.messages.batches.results(batch_id):
        slot = result.custom_id
        if result.result.type != "succeeded":
            print(f"  FAILED: {slot} ({result.result.type})")
            errors += 1
            continue

        raw = result.result.message.content[0].text.strip()
        # Strip markdown code fences if the model wrapped the JSON
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        try:
            variants = json.loads(raw)
            if isinstance(variants, list) and variants:
                existing[slot] = variants
                saved += 1
            else:
                print(f"  BAD RESPONSE: {slot} — empty or wrong type")
                errors += 1
        except json.JSONDecodeError as e:
            print(f"  JSON ERROR: {slot} — {e} | raw: {raw[:120]}")
            errors += 1

    with open(CONTENT_FILE, "w") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    print(f"\nSaved {saved} slots, {errors} errors → {CONTENT_FILE}")
    if errors == 0:
        Path(BATCH_ID_FILE).unlink()
    else:
        print(f"Batch ID kept in {BATCH_ID_FILE} — fix errors manually or resubmit.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pre-generate listing content via Anthropic Batches API")
    parser.add_argument("--poll", action="store_true", help="Poll for results and save to disk")
    parser.add_argument("--status", action="store_true", help="Print batch status without saving")
    args = parser.parse_args()

    equipment = get_equipment()
    locations = get_locations()

    if args.status:
        if not Path(BATCH_ID_FILE).exists():
            sys.exit("No batch ID found.")
        batch_id = Path(BATCH_ID_FILE).read_text().strip()
        check_status(anthropic.Anthropic(), batch_id)
    elif args.poll:
        poll()
    else:
        submit(equipment, locations)
