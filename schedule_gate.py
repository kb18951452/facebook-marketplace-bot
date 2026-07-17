"""
schedule_gate.py — Decides whether today's listing-agent run should proceed.

Runs 4 of 5 weekdays (Mon-Fri, no weekends). Each week a new random day off
is picked so the skip pattern doesn't repeat predictably. State persisted in
data/schedule_state.json.

Exit code 0 = proceed with the run. Exit code 3 = skip today.
"""

import json
import logging
import random
from datetime import date, timedelta
from pathlib import Path

STATE_FILE = Path("data/schedule_state.json")
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("listing_progress.log", mode="a")],
)
logger = logging.getLogger("schedule_gate")


def _monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def main() -> int:
    today = date.today()

    if today.weekday() >= 5:
        logger.info("schedule_gate: weekend — no listing agent runs.")
        return 3

    today_name = WEEKDAYS[today.weekday()]
    week_start = _monday_of(today)

    state = {}
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text())

    if state.get("week_start") != week_start.isoformat():
        prev_skip = state.get("skip_day")
        candidates = [d for d in WEEKDAYS if d != prev_skip] or WEEKDAYS
        skip_day = random.choice(candidates)
        state = {"week_start": week_start.isoformat(), "skip_day": skip_day}
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state))
        logger.info(f"schedule_gate: new week ({week_start}) — day off is {skip_day}.")

    if today_name == state["skip_day"]:
        logger.info(f"schedule_gate: today ({today_name}) is this week's day off — skipping.")
        return 3

    logger.info(f"schedule_gate: today ({today_name}) is a run day (day off this week: {state['skip_day']}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
