# Facebook Marketplace Bot

Automates the publishing and refreshing of heavy-equipment-rental classified ads across a large set of local markets, working around the marketplace platform's duplicate-listing detection to maintain broad, fresh coverage over time.

## Language

**Equipment**:
A rentable machine category offered for rent (currently Mini-Excavator and Skidsteer/Track Loader), each with its own Model, pricing tiers, and marketing blurb.
_Avoid_: equipment_type, item

**Service**:
A lead-generation listing category for repair or land work (small-engine repair by machine type, and Field Shredding) rather than a rentable machine — no Model, no real product photos, and a flat/quoted price instead of daily/weekly/monthly tiers. Restricted to whichever City it has launched in via its own City list, not the full City set every Equipment gets. Coded alongside Equipment in the same `_EQUIPMENT`/`TASK_VARIANTS` dicts, distinguished by `kind: "service"`.
_Avoid_: equipment_type (as a synonym — the field is shared code, not shared meaning)

**Text Card**:
The generated background photo for a Service listing — plain color card with short, thumbnail-readable text (e.g. "Weedeater Repair") in place of a real equipment photo. Run through the same rotate/crop/noise/phone-banner pipeline as a real photo so each listing still hashes unique.
_Avoid_: placeholder image

**Model**:
The specific machine designation used in marketing and photography for a piece of Equipment (e.g. KX71 for the Mini-Excavator, SVL75 for the Skidsteer).
_Avoid_: SKU

**City**:
A local market the business serves. Each City has a known distance from the depot and a computed Delivery Cost.
_Avoid_: location, market

**Delivery Cost**:
The delivery fee quoted for a City, based on its distance from the depot.
_Avoid_: estimated cost

**Task Variant**:
A customer-intent framing of a Listing for a given Equipment (e.g. drainage, site prep, tree work), each with its own pool of title and description templates. Multiple Task Variants let the same Equipment be listed several distinct ways within one City.
_Avoid_: task, template

**Language** (of a Listing):
The language a Listing is written in. Bilingual English/Spanish templates exist for every Equipment and Task Variant, though only English is currently in active rotation.
_Avoid_: locale

**Slot**:
The unit of publishing coverage — one specific combination of Equipment, City, Language, and Task Variant. A Slot is either open, filled by a live Listing, or Duplicate-Flagged.
_Avoid_: key, entry

**Listing**:
The classified ad actually posted to the marketplace to fill a Slot — its title, description, price, photos, and location. Deleting and republishing a Listing does not preserve its click history.
_Avoid_: ad, post

**Coverage**:
The state of every City having at least one live Listing. Gaining Coverage for an uncovered City takes priority over adding further Slots to a City that already has it.
_Avoid_: breadth

**Refresh**:
Replacing an existing, non-Duplicate-Flagged Listing with a newly generated one for the same Slot, to keep content from going stale. The lowest-priority activity — it only happens once new Coverage and restoring Duplicate-Flagged Slots have been handled.
_Avoid_: rotation, re-list

**Duplicate-Flagged**:
Describes a Slot whose Listing the marketplace platform has detected and removed as a duplicate. A Duplicate-Flagged Slot is restored (re-listed) after new Coverage is handled, but before any Refresh.
_Avoid_: banned, removed

**Click Snapshot**:
A point-in-time click count recorded for a Slot's current Listing.
_Avoid_: click count

**Lifetime Clicks**:
The accumulated click total for a Slot across every Listing that has ever filled it, carried forward whenever a Listing is deleted — so click history survives a Refresh or a duplicate removal.
_Avoid_: total clicks
