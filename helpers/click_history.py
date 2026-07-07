"""
Click History — how many clicks a Slot's current Listing has received over
time, and how that total carries forward across a Refresh or duplicate
removal so history survives a Listing being deleted and republished.

Every writer/reader of data/slot_metadata.json's click_snapshots array goes
through this module rather than re-deriving the trim/carry/window rules.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

SNAPSHOT_CAP = 200


def record_snapshot(
    metadata: dict,
    slot: str,
    clicks: Optional[int],
    ts: Optional[str] = None,
    skip_if_unchanged: bool = False,
) -> None:
    """Append a click-count snapshot for a slot, trimmed to the last
    SNAPSHOT_CAP entries. No-op if clicks is None (not reported this scan).
    With skip_if_unchanged, also no-op if clicks matches the last snapshot
    (used by the startup inventory scan to avoid padding history with
    unchanged counts; other callers record every scan unconditionally so a
    7-day delta is computable from any point)."""
    if clicks is None:
        return
    m = metadata.setdefault(slot, {})
    snaps = m.setdefault("click_snapshots", [])
    if skip_if_unchanged and snaps and snaps[-1]["clicks"] == clicks:
        return
    snaps.append({"ts": ts or datetime.now(timezone.utc).isoformat(), "clicks": clicks})
    if len(snaps) > SNAPSHOT_CAP:
        m["click_snapshots"] = snaps[-SNAPSHOT_CAP:]


def clicks_since_last(metadata: dict, slot: str, clicks: Optional[int]) -> int:
    """New clicks since the last recorded snapshot for this slot. A slot
    with no prior snapshot has an implicit baseline of 0, so its full
    current click count counts as new. Returns 0 if clicks is None."""
    if clicks is None:
        return 0
    snaps = metadata.get(slot, {}).get("click_snapshots", [])
    last = snaps[-1]["clicks"] if snaps else 0
    return max(0, clicks - last)


def carry_clicks(metadata: dict, slot: str, clicks: Optional[int]) -> None:
    """Fold a known click count into lifetime_clicks for a slot and clear
    its snapshot history, ready for a fresh Listing instance. No-op if
    clicks is None (nothing fresh to carry — leave history as-is)."""
    if clicks is None:
        return
    m = metadata.setdefault(slot, {})
    m["lifetime_clicks"] = m.get("lifetime_clicks", 0) + clicks
    m["click_snapshots"] = []


def carry_last_snapshot(metadata: dict, slot: str) -> None:
    """Fold the slot's last recorded snapshot into lifetime_clicks and
    clear its history. Use when there's no fresher click count on hand
    (e.g. a listing was just removed as a duplicate)."""
    m = metadata.get(slot)
    if not m:
        return
    snaps = m.get("click_snapshots", [])
    if snaps:
        carry_clicks(metadata, slot, snaps[-1]["clicks"])


def reset_for_new_listing(metadata: dict, slot: str) -> None:
    """Clear click_snapshots for a freshly published Listing instance.
    lifetime_clicks is left untouched — it already carries forward
    whatever the previous instance earned."""
    metadata.setdefault(slot, {})["click_snapshots"] = []


def lifetime_total(metadata: dict, slot: str) -> int:
    """Lifetime clicks across every Listing that has ever filled this slot,
    including the current instance's latest known count."""
    m = metadata.get(slot, {})
    snaps = m.get("click_snapshots", [])
    current = snaps[-1]["clicks"] if snaps else 0
    return (m.get("lifetime_clicks") or 0) + current


def seven_day_delta(snaps: list, published_at: Optional[str] = None) -> Optional[int]:
    """Delta clicks for the current listing instance over the last 7 days.

    Filters out snapshots older than published_at so a re-listed slot
    doesn't compute a negative delta against its previous life's high
    click count."""
    if not snaps:
        return None
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    pub_dt = None
    if published_at:
        try:
            pub_dt = datetime.fromisoformat(published_at)
            if pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    recent = []
    for s in snaps:
        try:
            ts = datetime.fromisoformat(s["ts"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff and (pub_dt is None or ts >= pub_dt):
                recent.append(s)
        except Exception:
            pass
    if not recent:
        return None
    if len(recent) == 1:
        return recent[-1]["clicks"]
    return recent[-1]["clicks"] - recent[0]["clicks"]
