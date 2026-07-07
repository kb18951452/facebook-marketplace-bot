---
name: repo-cleanup
description: Purges stale debug screenshots (screenshot_publish_missing_*, screenshot_category_debug_*, etc.) and rotates listing_progress.log once it gets large. User-invoked only — never run automatically.
disable-model-invocation: true
---

Run the bundled script from the repo root, dry run first:

```
python .claude/skills/repo-cleanup/repo_cleanup.py
```

This prints what would be deleted/rotated without touching anything: debug screenshots older than 3 days (`--keep-days` to change), and whether `listing_progress.log` is over the 20MB rotation threshold (`--log-threshold-mb` to change).

Show the user the dry-run counts and sizes, then ask for confirmation before re-running with `--apply`:

```
python .claude/skills/repo-cleanup/repo_cleanup.py --apply
```

Notes:
- Deletion is permanent (no send-to-trash) — this is why the script defaults to dry run and why you must confirm with the user before adding `--apply`.
- Log rotation renames `listing_progress.log` to a timestamped `.bak` next to it and creates a fresh empty log — it does not delete history. If `daily_agent.py`/`main.py` is running at the same time on Windows, the rename can fail with a file-in-use error; if that happens, tell the user to retry when no agent is running, don't force it.
- This script never touches `state.json`, `data/duplicate_history.json`, `.bak` files from `cleanup.py`, or anything under `cookies/`/`credentials.json` — those are out of scope for this skill.
