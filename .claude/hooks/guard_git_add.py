"""
PreToolUse hook (Bash matcher): stop `git add` from staging secrets or the
bulk debug artifacts (screenshots, .bak files, logs) that accumulate
untracked in this repo's working tree.
"""

import json
import re
import sys

data = json.load(sys.stdin)
command = data.get("tool_input", {}).get("command", "")

if "git add" not in command:
    sys.exit(0)

BROAD_ADD = re.compile(r"git add\s+(-A\b|--all\b|\.(?:\s|$))")
SENSITIVE = re.compile(r"credentials\.json|cookies[/\\]|\.bak\b|screenshot_\S*\.png|\.log\b")


def deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))


def ask(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }
    }))


if BROAD_ADD.search(command):
    ask(
        "This stages everything, including untracked debug screenshots, "
        "listing_progress.log, and .bak files sitting in the working tree. "
        "Add specific files instead, or confirm you want a broad add."
    )
elif SENSITIVE.search(command):
    deny(
        "Blocked: this references credentials.json, cookies/, a .bak file, "
        "a debug screenshot, or a log file. These should not be committed."
    )

sys.exit(0)
