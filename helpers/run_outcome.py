"""
run_outcome.py — structured outcome ledger for scheduled scripts.

Motivating gap: a scheduled run can exit 0 while accomplishing nothing (0
published, 0 matched, price fetch silently degraded), and two of the three
scheduled scripts (stats_tracker.py, fuel_price_agent.py) are launched by
Task Scheduler via pythonw.exe with no console attached — an uncaught
exception's traceback has nowhere to print to and is lost entirely, leaving
only a bare non-zero exit code in Task Scheduler's history.

Every scheduled entry point should call install_crash_logger() once at
startup (right after logging is configured) and record_run() at every exit
path, so both silent crashes and silent no-op runs land in one queryable
place (data/run_history.json) instead of requiring someone to notice a
pattern by re-reading logs by hand.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone

HISTORY_FILE = "data/run_history.json"
HISTORY_LEN = 50  # per-script rolling window


def _load() -> dict:
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def record_run(script: str, status: str, metrics: dict = None, note: str = None) -> None:
    """Append one outcome entry for `script` (e.g. 'daily_agent', 'stats_tracker',
    'fuel_price_agent'). status is 'success', 'no-op' (ran fine, accomplished
    nothing), 'blocked' (needs a human), or 'fatal' (crashed). metrics is
    whatever numbers matter for that script's goal (published count, matched
    count, price delta, ...)."""
    data = _load()
    history = data.setdefault(script, [])
    history.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "metrics": metrics or {},
        "note": note,
    })
    data[script] = history[-HISTORY_LEN:]
    _save(data)


def install_crash_logger(script: str) -> None:
    """Install a sys.excepthook that logs any uncaught exception's full
    traceback and records it as a 'fatal' run before the process dies.
    Without this, pythonw.exe-launched scripts (no console) lose the
    traceback entirely — Task Scheduler shows only a bare exit code."""
    logger = logging.getLogger(script)

    def _hook(exc_type, exc_value, tb):
        logger.error("Uncaught exception — process is about to die:",
                     exc_info=(exc_type, exc_value, tb))
        record_run(script, "fatal", note=f"{exc_type.__name__}: {exc_value}")
        sys.__excepthook__(exc_type, exc_value, tb)

    sys.excepthook = _hook
