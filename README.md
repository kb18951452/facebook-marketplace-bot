# FB Marketplace Bot — Heavy Equipment Rental Automation

Automates Facebook Marketplace listings for mini-excavator and track loader rentals across Central Texas cities.

---

## View the Dashboard

After any agent run, open the interactive coverage and clicks map:

```powershell
python map_listings.py --open
```

This regenerates `listings_map.html` with current data and opens it in your browser. The map shows every city — green dots (mini-ex active), blue dots (track loader active), orange (duplicate queue), gray (not yet listed) — with click counts and listing age in each popup.

To open without regenerating (shows data from last run):

```powershell
# Windows Explorer
start listings_map.html

# PowerShell
Invoke-Item listings_map.html
```

---

## What it does

Each scheduled run:

1. **Removes** any listings Facebook has flagged as duplicates
2. **Publishes new listings** for cities not yet covered (breadth-first — every city gets at least one listing before any city gets its second)
3. **Re-lists** slots that were previously duplicate-removed (restores lost coverage)
4. **Refreshes** aging existing listings with fresh titles/descriptions (only if time budget remains)

Images are sourced from a local library (`images/kx71/`, `images/svl75/`), manipulated with random rotation, crop, brightness, and a phone-number banner to defeat Facebook duplicate-image detection.

---

## Agents

| Script | Purpose | Schedule |
|---|---|---|
| `daily_agent.py` | Publish/refresh listings on FB Marketplace | Mon–Fri, 08:00 (90 min supervised session), one rotating day off per week |
| `stats_tracker.py` | Collect click counts and views from selling page | Every 3 days, ~14:00 |
| `map_listings.py` | Generate `listings_map.html` viewer | Auto-runs at end of daily_agent + stats_tracker |

### daily_agent.py — priority order

The agent works through phases in this order, stopping when the time budget runs out. Each scheduled run is a run_session.py-supervised 90-minute window that keeps relaunching daily_agent.py (resuming from state.json) if it crashes, passing the time remaining in the window as its budget:

```
Phase 0  Remove FB-flagged duplicates; record in duplicate_history.json
Phase 1a Coverage pass — one listing per city with zero active slots
Phase 1b Fill pass — remaining new slot/task/language variants
Phase 3  Re-list dupe-removed slots (restores lost coverage)
Phase 2  Refresh existing listings with new titles/descriptions  <- lowest priority
```

State is persisted to `state.json` after every publish so interrupted runs resume correctly.

---

## Setup

### Dependencies

```powershell
python -m pip install selenium webdriver-manager Pillow numpy requests anthropic
```

External tools (must be on PATH):

- **Google Chrome** — the browser the bot controls

`webdriver-manager` downloads the matching ChromeDriver automatically on first run.

### First run / login

```powershell
python main.py
```

A Chrome window opens. You have 5 minutes to log in to Facebook manually. After login, cookies are saved to `cookies/facebook.pkl`. All future runs reuse the saved session.

Delete `cookies/facebook.pkl` to force a fresh login.

### Environment variables

```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."   # required for scripts/generate_content.py
```

---

## Schedule setup

Run once from an **elevated** PowerShell prompt to register all Windows Task Scheduler tasks:

```powershell
.\setup_schedule.ps1
```

This registers:
- 5 listing agent tasks (1 run/day, Mon–Fri, one rotating day off per week)
- 1 stats tracker task (every 3 days)

To remove all tasks:

```powershell
.\setup_schedule.ps1 -Unregister
```

---

## Data files

| File | Contents |
|---|---|
| `state.json` | Active slot -> listing title map. Delete to re-publish all slots from scratch. |
| `data/slot_metadata.json` | Per-slot click snapshots, lifetime clicks, publish timestamps, views. |
| `data/duplicate_history.json` | Slots removed by FB as duplicates, with timestamp. |
| `data/cities_data.json` | All target cities with lat/lng, distance, and estimated delivery cost. |
| `listing_progress.log` | Full append log of every publish/skip/error/phase event. |
| `cookies/facebook.pkl` | Saved FB session. Delete to force re-login. |
| `listings_map.html` | Generated viewer (regenerated after each agent run). |

---

## Equipment and cities

**Equipment:**
- `mini-ex` — Kubota KX030-4 (listed as KX71), $200/day
- `trackloader` — Kubota SVL75-2, $280/day

**Cities:** Central Texas coverage from `data/cities_data.json`. Slots are keyed as `{equip}_{city}_{lang}_{task}` (e.g., `mini-ex_Lorena_eng_drainage`).

**Languages:** English (`eng`) and Spanish (`spa`) variants for every listing.

**Task variants:** Each equipment type has 4–5 task categories (drainage, grading, pond, site_prep, tree_work for mini-ex; clearing, grading, demo, foundation for track loader). Each city x equipment x task x language = one slot.

---

## Key constants

| Constant | Where | Default | Effect |
|---|---|---|---|
| `SESSION_MINUTES` | `run_session.py` | 90 | Length of each scheduled supervised window. This is the constant that actually governs daily runtime in production — it's passed to `daily_agent.py` as `--budget-min`, which overrides that script's own `BUDGET_MIN_MIN`/`BUDGET_MAX_MIN`/jitter (those only apply to a standalone manual run, not the scheduled one). |
| `BUDGET_MIN_MIN` / `BUDGET_MAX_MIN` | `daily_agent.py` | 210 / 250 | Random session length range, used only when `daily_agent.py` is run manually without `--budget-min` |
| `JITTER_MAX_MIN` | `daily_agent.py` | 10 | Max random startup delay in minutes for a manual run (skipped via `--no-jitter`, which is how the scheduler always invokes it) |

Pass `--no-jitter` for immediate starts during manual testing.
