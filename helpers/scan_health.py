"""
Scan Health — tracks how many listings each live-page scrape actually found,
so a scroll/lazy-load failure (scrape cut short) can be told apart from a
real change in listing count.

Motivating case (2026-07-07): two find_orphaned_listings.py runs ten minutes
apart found 138 and then 23 listings on the same selling page. The second
number was quietly trusted — a scroll-loop that stops once
document.body.scrollHeight looks stable can be fooled by a page that hadn't
finished lazy-loading yet. Nothing compared it against the previous scan, so
the drop went unnoticed until a chat transcript happened to be re-read.

Every caller of collect_listing_stats()/collect_click_snapshots() should
report its result count here via record_scan() so this class of problem
gets flagged the moment it happens, not the next time someone compares logs
by hand.
"""

import json
import logging
import os
from statistics import median
from typing import Optional

logger = logging.getLogger(__name__)

HEALTH_FILE = "data/scan_health.json"
HISTORY_LEN = 20
DROP_THRESHOLD = 0.5  # flag if a scan finds less than this fraction of the recent baseline


def _load() -> dict:
    if os.path.exists(HEALTH_FILE):
        with open(HEALTH_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(HEALTH_FILE), exist_ok=True)
    with open(HEALTH_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def record_scan(source: str, count: int) -> Optional[str]:
    """Record a scan's listing count for `source` (e.g. 'daily_agent_inventory',
    'stats_tracker', 'find_orphaned_listings'). Logs and returns a warning
    message if this count is a suspicious drop from the recent baseline —
    likely an incomplete scrape, not a real change in listings. Returns None
    when there's nothing to flag."""
    data = _load()
    history = data.setdefault(source, [])

    warning = None
    if history:
        baseline = median(history[-HISTORY_LEN:])
        if baseline > 0 and count < baseline * DROP_THRESHOLD:
            warning = (
                f"{source}: scan found {count} listings, well below the recent "
                f"baseline of {baseline:.0f} (last {min(len(history), HISTORY_LEN)} scans) — "
                "likely an incomplete scrape (scroll/lazy-load cut short), not a real listing drop."
            )
            logger.warning(warning)

    history.append(count)
    data[source] = history[-HISTORY_LEN:]
    _save(data)
    return warning
