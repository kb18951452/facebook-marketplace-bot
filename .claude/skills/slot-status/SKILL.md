---
name: slot-status
description: Reports FB Marketplace listing slot coverage — how many of the current (city x equipment x task-variant) slots are published, pending, legacy, or duplicate-flagged. Use when asked what's left to publish, how many slots are pending, or for a breakdown of listing coverage by city/equipment.
---

Run the bundled script from the repo root and relay its output:

```
python .claude/skills/slot-status/slot_status.py
```

Pass `--json` if the numbers need to be filtered/sorted further than the default report provides.

This is a pure read of `state.json`, `data/duplicate_history.json`, and the expected-slot universe derived from `helpers/ads.py` (`get_equipment`, `get_locations`, `TASK_VARIANTS`) — it does not touch Facebook, Selenium, or any live session, and it makes no writes. Safe to run any time, including while `daily_agent.py` is running.

**Legacy slots**: entries in `state.json` that no longer match the current expected universe (e.g. `spa`-language slots — Spanish listings are currently disabled in `get_listings()`, or slots for cities/tasks since removed from `data/cities_data.json`/`TASK_VARIANTS`). These aren't errors, just published listings that predate a scope change — flag them but don't suggest deleting anything without the user asking.

If the user wants a specific breakdown not covered by the script's output (e.g. by task_slug, or a diff since a prior run), read `--json` output and compute it directly rather than re-deriving the whole slot universe by hand.
