"""
repo_cleanup.py — Purge stale debug screenshots and rotate listing_progress.log.

These are working-tree artifacts (none are committed/gitignored), but they
accumulate fast: debug screenshots are written on every publish-flow anomaly,
and listing_progress.log is appended to on every run with no rotation.

Defaults to a dry run — prints what would change without touching anything.
Pass --apply to actually delete/rotate.

Run from repo root:
    python .claude/skills/repo-cleanup/repo_cleanup.py                # dry run
    python .claude/skills/repo-cleanup/repo_cleanup.py --apply        # do it
    python .claude/skills/repo-cleanup/repo_cleanup.py --apply --keep-days 7 --log-threshold-mb 10
"""

import argparse
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

SCREENSHOT_PATTERNS = [
    "screenshot_after_next_*.png",
    "screenshot_category_debug_*.png",
    "screenshot_category_missing_*.png",
    "screenshot_location_missing_*.png",
    "screenshot_publish_missing_*.png",
]

LOG_FILE = ROOT / "listing_progress.log"


def find_stale_screenshots(keep_days: int):
    cutoff = time.time() - keep_days * 86400
    stale = []
    for pattern in SCREENSHOT_PATTERNS:
        for path in ROOT.glob(pattern):
            if path.stat().st_mtime < cutoff:
                stale.append(path)
    return stale


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually delete/rotate (default: dry run)")
    parser.add_argument("--keep-days", type=int, default=3, help="Delete debug screenshots older than this many days (default: 3)")
    parser.add_argument("--log-threshold-mb", type=float, default=20.0, help="Rotate listing_progress.log if it exceeds this size in MB (default: 20)")
    args = parser.parse_args()

    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"=== repo cleanup ({mode}) ===")

    stale = find_stale_screenshots(args.keep_days)
    total_bytes = sum(p.stat().st_size for p in stale)
    print(f"Debug screenshots older than {args.keep_days}d: {len(stale)} files, {human_size(total_bytes)}")
    if args.apply:
        for path in stale:
            path.unlink()
        print(f"  deleted {len(stale)} files")
    elif stale:
        print("  (dry run — re-run with --apply to delete)")

    if LOG_FILE.exists():
        size = LOG_FILE.stat().st_size
        threshold = args.log_threshold_mb * 1024 * 1024
        print(f"listing_progress.log: {human_size(size)} (threshold {args.log_threshold_mb}MB)")
        if size > threshold:
            archive_name = LOG_FILE.with_name(
                f"listing_progress.log.{time.strftime('%Y%m%d-%H%M%S')}.bak"
            )
            if args.apply:
                try:
                    LOG_FILE.rename(archive_name)
                    LOG_FILE.touch()
                    print(f"  rotated -> {archive_name.name} (fresh empty log created)")
                except OSError as e:
                    print(f"  could not rotate — file may be in use by a running agent: {e}")
            else:
                print(f"  over threshold — would rotate to {archive_name.name} (dry run — re-run with --apply)")
        else:
            print("  under threshold — no rotation needed")
    else:
        print("listing_progress.log: not found")


if __name__ == "__main__":
    main()
