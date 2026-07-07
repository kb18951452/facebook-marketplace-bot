"""
run_session.py — Supervisor for one scheduled listing session.

Owns a single wall-clock window (default 3h45m) and keeps the listing agent
alive inside it:

  * Launches daily_agent.py with --no-jitter and a --budget-min equal to the
    time left in the window.
  * If the agent crashes or hits a fatal Chrome-session error (exit code 1 or
    any unexpected non-zero), it is relaunched and resumes from state.json,
    after a short backoff — until the window closes.
  * A clean completion (exit 0) ends the session early; there is no more work
    to do this window.
  * A login give-up (exit 2 — e.g. 2FA/checkpoint needs a human) ends the
    session; blindly retrying a blocked login risks locking the account.

Windows Task Scheduler invokes this once at 08:00 and once at 13:00 via
run_daily_agent.bat. MultipleInstances=IgnoreNew prevents overlap.
"""

import logging
import subprocess
import sys
import time

# ── Config ──────────────────────────────────────────────────────────────────
SESSION_MINUTES = 225          # length of the scheduled window (+25% over the original 180)
MIN_BUDGET_MIN = 8             # don't bother launching with less runway than this
RESTART_BACKOFF_SEC = 30       # pause between a crash and the next relaunch
LOG_FILE = "listing_progress.log"

# Exit codes from daily_agent.py
EXIT_CLEAN = 0                 # finished all work within budget — stop
EXIT_FATAL = 1                 # mid-run Chrome/session death — restart & resume
EXIT_LOGIN_BLOCKED = 2         # login needs a human (2FA/checkpoint) — stop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, mode="a")],
)
logger = logging.getLogger("run_session")


def main() -> int:
    deadline = time.time() + SESSION_MINUTES * 60
    logger.info(
        f"=== Session supervisor started — {SESSION_MINUTES} min window, "
        f"deadline {time.strftime('%H:%M:%S', time.localtime(deadline))} ==="
    )

    attempt = 0
    while True:
        remaining_min = (deadline - time.time()) / 60
        if remaining_min < MIN_BUDGET_MIN:
            logger.info(f"Session window closing ({remaining_min:.1f} min left) — done.")
            return 0

        attempt += 1
        logger.info(
            f"Launching agent (attempt {attempt}) with {remaining_min:.1f} min budget."
        )
        try:
            result = subprocess.run(
                [sys.executable, "daily_agent.py",
                 "--no-jitter", "--budget-min", f"{remaining_min:.1f}"],
            )
            code = result.returncode
        except Exception as e:  # supervisor must never crash on a launch failure
            logger.error(f"Failed to launch agent: {e}")
            code = EXIT_FATAL

        if code == EXIT_CLEAN:
            logger.info("Agent finished cleanly — no more work this session.")
            return 0
        if code == EXIT_LOGIN_BLOCKED:
            logger.error("Agent could not log in (human action needed) — ending session.")
            return 2

        # Any other exit (fatal session death, crash) → restart and resume.
        logger.warning(
            f"Agent exited with code {code}. Restarting to resume from state.json "
            f"after {RESTART_BACKOFF_SEC}s backoff."
        )
        if (deadline - time.time()) <= RESTART_BACKOFF_SEC:
            logger.info("Not enough window left to back off and retry — done.")
            return code
        time.sleep(RESTART_BACKOFF_SEC)


if __name__ == "__main__":
    sys.exit(main())
