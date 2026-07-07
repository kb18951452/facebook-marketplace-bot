"""
Slot — the unit of publishing coverage: one combination of Equipment, City,
Language, and (for current listings) Task Variant, encoded as the single
string key used across state.json, data/duplicate_history.json, and
data/slot_metadata.json.

This is the one place that format is built or parsed. Everything else
(daily_agent.py, main.py, map_listings.py, cleanup scripts) should go through
build()/from_listing()/parse() rather than re-deriving the key shape.

state.json holds a mix of two eras: current keys carry a Task Variant
(equip_city_lang_task), legacy keys predate Task Variants and don't
(equip_city_lang). parse() understands both; build() only produces current
keys, since every listing generated today has a Task Variant.
"""

import re
from typing import NamedTuple, Optional

from helpers.ads import get_equipment

_LANGUAGES = ("eng", "spa")


class Slot(NamedTuple):
    equipment_type: str
    city: str
    lang: str
    task_slug: Optional[str] = None

    def key(self) -> str:
        base = f"{self.equipment_type}_{self.city}_{self.lang}"
        return f"{base}_{self.task_slug}" if self.task_slug else base


def _equip_lang_patterns() -> "tuple[re.Pattern, re.Pattern]":
    equip_alt = "|".join(re.escape(e) for e in get_equipment())
    lang_alt = "|".join(_LANGUAGES)
    current = re.compile(rf"^({equip_alt})_(.+)_({lang_alt})_(.+)$")
    legacy = re.compile(rf"^({equip_alt})_(.+)_({lang_alt})$")
    return current, legacy


def build(equipment_type: str, city: str, lang: str, task_slug: str) -> str:
    """Build a current-format Slot key. Raises ValueError without a
    task_slug — every listing generated today has one; a caller without
    one is working from stale/incomplete data."""
    if not task_slug:
        raise ValueError(f"build() requires a task_slug (got {task_slug!r} for {equipment_type}/{city}/{lang})")
    return Slot(equipment_type, city, lang, task_slug).key()


def from_listing(listable) -> str:
    """Build a Slot key from a ListingData (or anything with the same shape:
    .equipment_type, .location ("City, TX"), .lang, .task_slug)."""
    city = listable.location.split(", ")[0]
    return build(listable.equipment_type, city, listable.lang, listable.task_slug)


def parse(slot_key: str) -> Optional[Slot]:
    """Parse a Slot key back into its parts, current or legacy format.
    Returns None if the key doesn't match either shape."""
    current, legacy = _equip_lang_patterns()

    m = current.match(slot_key)
    if m:
        equip, city, lang, task_slug = m.groups()
        return Slot(equip, city, lang, task_slug)

    m = legacy.match(slot_key)
    if m:
        equip, city, lang = m.groups()
        return Slot(equip, city, lang, None)

    return None
