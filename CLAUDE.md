# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the bot

```
python main.py
```

First run opens a Chrome window and requires manual Facebook login (5-minute window). Subsequent runs use saved cookies from `cookies/facebook.pkl`.

## Dependencies

```
python -m pip install selenium webdriver-manager Pillow
```

Requires Google Chrome installed. `webdriver-manager` downloads the matching ChromeDriver automatically.

## Architecture

The bot automates Facebook Marketplace to publish heavy equipment rental listings (mini-excavator `kx71`, track loader `svl75`) across a set of Central Texas cities, rotating titles and descriptions to stay fresh.

**Data flow in `main.py`:**
1. `Scraper` launches Chrome with anti-bot flags and logs in via cookies
2. `get_listings()` (in `helpers/ads.py`) generates a `ListingData` for every `(equipment_type, city, language)` combination
3. `state.json` tracks which slots have already been published (key: `"{equipment_type}_{city}_{lang}"`). Already-completed slots are skipped; if a slot has an old title it gets removed first
4. `Listing.update_listings()` publishes via Selenium form automation, then saves state immediately
5. After all listings, `remove_duplicate_listings()` cleans up any Facebook-flagged duplicates

**Key modules:**

- `helpers/scraper.py` — `Scraper` class: wraps Selenium with random delays (`wait_random_time`), CSS/XPath finders with configurable timeouts, cookie persistence (`cookies/facebook.pkl`), and Chrome options that suppress automation detection
- `helpers/listing_helper.py` — `ListingData` dataclass + `Listing` class: handles publishing (`publish_listing`), deletion by title (`remove_listing_by_title`), bulk deletion (`remove_all_listings`), and post-deletion survey dialogs
- `helpers/ads.py` — content generation: `get_listings()` generator, `get_listing_title()` (80% task-based / 20% classic style), `get_listing_description()` (shuffled sections for variation), `generate_random_controlled_image()` (PIL image manipulation: random rotation, crop, phone-number overlay to defeat duplicate-image detection)
- `helpers/csv_helper.py` — CSV reader (legacy, not used in current main flow)
- `helpers/profile_helper.py` — competitor profile scanner / reporter (standalone utility, not imported by main)
- `data/cities_data.json` — array of Texas cities with `city`, `distance`, and `estimated_cost` (delivery fee) fields
- `data/equipment.json` / inline in `ads.py` — equipment specs, pricing tiers, bilingual names and blurbs

**Image pipeline:** Source photos live in `images/{model}/` (e.g., `images/kx71/`, `images/sc75/`). `generate_random_controlled_image()` picks up to 9 random images, applies random rotation + crop + semi-transparent phone-number banner, and saves unique hashed JPEGs to `images/output/` (wiped and recreated between each listing).

**Anti-detection strategy:** `--disable-blink-features=AutomationControlled`, excluded `enable-automation` switch, 1.2–2.2 second random sleeps before every interaction, cookie-based session reuse.

## State and logs

- `state.json` — persisted slot → title map; delete this file to re-publish all slots
- `listing_progress.log` — appended log of all publish/skip/error events
- `cookies/facebook.pkl` — saved session; delete to force re-login

# CLAUDE.md — 12-rule template

These rules apply to every task in this project unless explicitly overridden.
Bias: caution over speed on non-trivial work. Use judgment on trivial tasks.

## Rule 1 — Think Before Coding
State assumptions explicitly. If uncertain, ask rather than guess.
Present multiple interpretations when ambiguity exists.
Push back when a simpler approach exists.
Stop when confused. Name what's unclear.

## Rule 2 — Simplicity First
Minimum code that solves the problem. Nothing speculative.
No features beyond what was asked. No abstractions for single-use code.
Test: would a senior engineer say this is overcomplicated? If yes, simplify.

## Rule 3 — Surgical Changes
Touch only what you must. Clean up only your own mess.
Don't "improve" adjacent code, comments, or formatting.
Don't refactor what isn't broken. Match existing style.

## Rule 4 — Goal-Driven Execution
Define success criteria. Loop until verified.
Don't follow steps. Define success and iterate.
Strong success criteria let you loop independently.

## Rule 5 — Use the model only for judgment calls
Use me for: classification, drafting, summarization, extraction.
Do NOT use me for: routing, retries, deterministic transforms.
If code can answer, code answers.

## Rule 6 — Token budgets are not advisory
Per-task: 4,000 tokens. Per-session: 30,000 tokens.
If approaching budget, summarize and start fresh.
Surface the breach. Do not silently overrun.

## Rule 7 — Surface conflicts, don't average them
If two patterns contradict, pick one (more recent / more tested).
Explain why. Flag the other for cleanup.
Don't blend conflicting patterns.

## Rule 8 — Read before you write
Before adding code, read exports, immediate callers, shared utilities.
"Looks orthogonal" is dangerous. If unsure why code is structured a way, ask.

## Rule 9 — Tests verify intent, not just behavior
Tests must encode WHY behavior matters, not just WHAT it does.
A test that can't fail when business logic changes is wrong.

## Rule 10 — Checkpoint after every significant step
Summarize what was done, what's verified, what's left.
Don't continue from a state you can't describe back.
If you lose track, stop and restate.

## Rule 11 — Match the codebase's conventions, even if you disagree
Conformance > taste inside the codebase.
If you genuinely think a convention is harmful, surface it. Don't fork silently.

## Rule 12 — Fail loud
"Completed" is wrong if anything was skipped silently.
"Tests pass" is wrong if any were skipped.
Default to surfacing uncertainty, not hiding it.