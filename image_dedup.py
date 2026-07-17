"""
image_dedup.py — perceptual-hash deduplication for image galleries

Compares all images in images/kx71/ and images/svl75/ using perceptual hashing,
then removes the more-duplicate copies keeping the gallery diverse.

Usage:
    python image_dedup.py              # dry run — prints what would be removed
    python image_dedup.py --delete     # actually delete duplicates

Requires: pip install imagehash Pillow
"""

import argparse
import sys
from pathlib import Path
from collections import defaultdict

try:
    import imagehash
    from PIL import Image
except ImportError:
    print("Missing dependency. Run: pip install imagehash Pillow")
    sys.exit(1)

GALLERIES = [Path("images/kx71"), Path("images/svl75")]

# Hamming distance threshold — images within this distance are considered duplicates.
# 0 = identical, 10 = very similar, 20 = somewhat similar. Tune as needed.
SIMILARITY_THRESHOLD = 10


def hash_images(directory: Path) -> dict[str, Path]:
    """Return {hex_hash: path} for all PNGs in directory."""
    hashes = {}
    for img_path in sorted(directory.glob("*.png")):
        try:
            h = imagehash.phash(Image.open(img_path))
            hashes[str(h)] = img_path
        except Exception as e:
            print(f"  Could not hash {img_path.name}: {e}")
    return hashes


def find_duplicates(directory: Path) -> list[tuple[Path, Path, int]]:
    """Return list of (keep, remove, distance) pairs for near-duplicate images."""
    image_paths = sorted(directory.glob("*.png"))
    hashes: list[tuple] = []
    for p in image_paths:
        try:
            h = imagehash.phash(Image.open(p))
            hashes.append((h, p))
        except Exception:
            pass

    to_remove: set[Path] = set()
    duplicates: list[tuple[Path, Path, int]] = []

    for i in range(len(hashes)):
        h1, p1 = hashes[i]
        if p1 in to_remove:
            continue
        for j in range(i + 1, len(hashes)):
            h2, p2 = hashes[j]
            if p2 in to_remove:
                continue
            dist = h1 - h2
            if dist <= SIMILARITY_THRESHOLD:
                # Keep the one with the lower-numbered name (usually original source photo)
                keep, remove = (p1, p2) if p1.name < p2.name else (p2, p1)
                to_remove.add(remove)
                duplicates.append((keep, remove, dist))

    return duplicates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--delete", action="store_true", help="Delete duplicates (default: dry run)")
    args = parser.parse_args()

    total_removed = 0
    for gallery in GALLERIES:
        if not gallery.exists():
            print(f"Skipping {gallery} — not found")
            continue

        before = len(list(gallery.glob("*.png")))
        print(f"\n{gallery}  ({before} images)")
        duplicates = find_duplicates(gallery)

        if not duplicates:
            print("  No near-duplicates found.")
            continue

        for keep, remove, dist in duplicates:
            print(f"  dist={dist:2d}  keep={keep.name}  remove={remove.name}")
            if args.delete:
                remove.unlink()
                total_removed += 1

        after = before - len(duplicates)
        action = "Would remove" if not args.delete else "Removed"
        print(f"  {action} {len(duplicates)} duplicates — {after} images remain")

    if not args.delete:
        print(f"\nDry run complete. Run with --delete to remove {total_removed or 'the'} duplicates.")
    else:
        print(f"\nDone. Removed {total_removed} duplicate images total.")


if __name__ == "__main__":
    main()
