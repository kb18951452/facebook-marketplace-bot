"""
PreToolUse hook (Edit|Write matcher): ask for confirmation before direct
edits to production slot-tracking state (state.json, data/slot_metadata.json).
These should only change through the bot's normal publish flow.
"""

import json
import sys
from pathlib import Path

data = json.load(sys.stdin)
file_path = data.get("tool_input", {}).get("file_path", "")
name = Path(file_path).name

GUARDED = {"state.json", "slot_metadata.json"}

if name in GUARDED:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": (
                f"{name} is production slot-tracking state. It should only change "
                "through the bot's normal publish flow (daily_agent.py / main.py), "
                "not a direct edit. Confirm this is intentional."
            ),
        }
    }))

sys.exit(0)
