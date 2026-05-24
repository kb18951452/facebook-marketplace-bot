"""
image_pipeline_agent.py — Automated image harvest + AI verification pipeline.

Two-step process run daily (scheduled separately from the listing agent):
  1. Harvest: yt-dlp searches YouTube for job-site videos, extracts still frames,
              saves them to images/kx71/staging/ and images/svl75/staging/.
  2. Verify:  Claude Haiku vision classifies each staged frame. Frames showing
              the correct equipment are promoted to images/kx71/ or images/svl75/
              (the live library used by the listing bot). Bad frames are deleted.

Requirements:
  - ANTHROPIC_API_KEY env var
  - yt-dlp on PATH  (pip install yt-dlp)
  - ffmpeg on PATH  (https://ffmpeg.org)

Usage:
    python image_pipeline_agent.py
    python image_pipeline_agent.py --skip-harvest   # verify staged images only
"""

import argparse
import logging
import os
import sys

LOG_FILE = "image_harvester.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode="a"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

parser = argparse.ArgumentParser(description="Harvest and verify equipment images")
parser.add_argument("--skip-harvest", action="store_true",
                    help="Skip downloading new videos; verify/promote staged images only")
args = parser.parse_args()

# ── Step 1: Harvest ───────────────────────────────────────────────────────────
if not args.skip_harvest:
    log.info("=== image_pipeline_agent: Step 1 — Harvesting new frames ===")
    try:
        from image_harvester import harvest
        harvest()
    except FileNotFoundError as e:
        log.warning(f"Harvest tool not found (yt-dlp or ffmpeg missing?): {e} — continuing to verify.")
    except Exception as e:
        log.error(f"Harvest step failed: {e}", exc_info=True)
        # Continue to verification even if harvest fails
else:
    log.info("=== image_pipeline_agent: Harvest skipped (--skip-harvest) ===")

# ── Step 2: Verify and promote staged images ──────────────────────────────────
log.info("=== image_pipeline_agent: Step 2 — Verifying staged images ===")

if not os.environ.get("ANTHROPIC_API_KEY"):
    log.error(
        "ANTHROPIC_API_KEY not set — cannot verify images.\n"
        "Set it with:  $env:ANTHROPIC_API_KEY = 'sk-ant-...'\n"
        "Then re-run this script."
    )
    sys.exit(1)

try:
    import anthropic
    from image_filter import run_pass, EQUIPMENT_DIRS

    client = anthropic.Anthropic()
    total_promoted = 0
    total_deleted = 0

    for model_key, (equipment_name, staging_dir, final_dir) in EQUIPMENT_DIRS.items():
        if not staging_dir.exists():
            log.info(f"[{model_key}] Staging dir does not exist — skipping.")
            continue

        staged = [
            f for f in staging_dir.iterdir()
            if f.is_file() and f.suffix.lower() in {".png", ".jpg", ".jpeg"}
        ]
        if not staged:
            log.info(f"[{model_key}] No staged images to verify.")
            continue

        log.info(f"[{model_key}] Verifying {len(staged)} staged images in {staging_dir}...")
        stats = run_pass(
            client=client,
            model_key=model_key,
            equipment_name=equipment_name,
            img_dir=staging_dir,
            final_dir=final_dir,
            check_all=True,
            move=False,
            delete=True,
        )
        total_promoted += stats["kept"]
        total_deleted += stats["rejected"]
        log.info(
            f"[{model_key}] checked={stats['checked']}, "
            f"promoted={stats['kept']}, deleted={stats['rejected']}, errors={stats['errors']}"
        )

    log.info(
        f"=== image_pipeline_agent complete: "
        f"{total_promoted} images promoted to library, {total_deleted} rejected ==="
    )

except Exception as e:
    log.error(f"Verification step failed: {e}", exc_info=True)
    sys.exit(1)
