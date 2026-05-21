"""
map_listings.py — Generate listings_map.html, an interactive Leaflet map of all
FB Marketplace slots (active, duplicate-queued, and uncovered cities).

Usage:
    python map_listings.py              # writes listings_map.html
    python map_listings.py --open       # writes and opens in default browser

Reads:
    data/cities_data.json       city coordinates
    state.json                  active slots  {slot: title}
    data/duplicate_history.json duplicate-removed slots  {slot: iso_timestamp}
    data/slot_metadata.json     per-slot stats  {slot: {published_at, last_clicks, ...}}
"""

import argparse
import json
import math
import os
import webbrowser
from datetime import datetime, timezone

# ── Load data files ────────────────────────────────────────────────────────────
def _load(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}

cities_raw   = _load("data/cities_data.json")
state        = _load("state.json")
dupe_history = _load("data/duplicate_history.json")
metadata     = _load("data/slot_metadata.json")

city_lookup = {c["city"]: c for c in (cities_raw if isinstance(cities_raw, list) else [])}

# ── Build marker list ──────────────────────────────────────────────────────────
def _age_days(iso_str):
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        return round(delta.total_seconds() / 86400, 1)
    except Exception:
        return None

# Collect all known slots across both active and duplicate states
all_slots = set(state.keys()) | set(dupe_history.keys())

markers = []
for slot in all_slots:
    parts = slot.split("_")
    if len(parts) < 3:
        continue
    equip = parts[0]
    city  = "_".join(parts[1:-1])
    lang  = parts[-1]

    geo = city_lookup.get(city)
    if not geo or not geo.get("lat") or not geo.get("lng"):
        continue

    lat = float(geo["lat"])
    lng = float(geo["lng"])

    # Offset so mini-ex and trackloader don't overlap exactly
    lat += 0.004 if equip == "mini-ex" else -0.004

    is_active = slot in state
    is_dupe   = slot in dupe_history

    meta = metadata.get(slot, {})
    published_at   = meta.get("published_at") or (None if is_dupe else None)
    last_clicks    = meta.get("last_clicks")
    last_clicks_at = meta.get("last_clicks_at")
    title          = state.get(slot) or meta.get("title") or ""
    dupe_since     = dupe_history.get(slot)

    age_days       = _age_days(published_at)
    clicks_age     = _age_days(last_clicks_at)

    status = "active" if is_active else "duplicate"

    markers.append({
        "slot":          slot,
        "city":          city,
        "equip":         equip,
        "lang":          lang,
        "status":        status,
        "lat":           lat,
        "lng":           lng,
        "title":         title,
        "published_at":  published_at,
        "age_days":      age_days,
        "last_clicks":   last_clicks,
        "last_clicks_at":last_clicks_at,
        "clicks_age":    clicks_age,
        "dupe_since":    dupe_since,
    })

# ── Uncovered cities (no active or dupe slot) ──────────────────────────────────
covered_cities = {m["city"] for m in markers}
uncovered = []
for c in city_lookup.values():
    if c["city"] not in covered_cities and c.get("lat") and c.get("lng"):
        uncovered.append({
            "city": c["city"],
            "lat":  float(c["lat"]),
            "lng":  float(c["lng"]),
        })

# ── Summary stats ──────────────────────────────────────────────────────────────
active_markers    = [m for m in markers if m["status"] == "active"]
dupe_markers      = [m for m in markers if m["status"] == "duplicate"]
active_mini       = [m for m in active_markers if m["equip"] == "mini-ex"]
active_track      = [m for m in active_markers if m["equip"] == "trackloader"]
cities_active     = len({m["city"] for m in active_markers})
clicks_known      = [m["last_clicks"] for m in active_markers if m["last_clicks"] is not None]
avg_clicks        = round(sum(clicks_known) / len(clicks_known), 1) if clicks_known else None

stats = {
    "active_total":    len(active_markers),
    "active_mini_ex":  len(active_mini),
    "active_track":    len(active_track),
    "dupe_queue":      len(dupe_markers),
    "cities_active":   cities_active,
    "cities_total":    len(city_lookup),
    "avg_clicks":      avg_clicks,
    "generated_at":    datetime.now().strftime("%Y-%m-%d %H:%M"),
}

# ── Map center ────────────────────────────────────────────────────────────────
if markers:
    center_lat = sum(m["lat"] for m in markers) / len(markers)
    center_lng = sum(m["lng"] for m in markers) / len(markers)
else:
    center_lat, center_lng = 31.5, -97.1

# ── HTML template ──────────────────────────────────────────────────────────────
MARKERS_JSON  = json.dumps(markers,   ensure_ascii=False)
UNCOVERED_JSON = json.dumps(uncovered, ensure_ascii=False)
STATS_JSON    = json.dumps(stats,     ensure_ascii=False)

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>FB Marketplace Listings Map</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
  #map {{ height: 100vh; width: 100%; }}

  #panel {{
    position: absolute; top: 12px; right: 12px; z-index: 1000;
    background: white; border-radius: 10px;
    box-shadow: 0 3px 14px rgba(0,0,0,0.25);
    padding: 16px 18px; min-width: 230px; max-width: 260px;
  }}
  #panel h2 {{ font-size: 14px; font-weight: 700; margin-bottom: 12px; color: #111; }}
  .section {{ margin-bottom: 12px; }}
  .section-title {{ font-size: 11px; font-weight: 600; text-transform: uppercase;
                    letter-spacing: .05em; color: #888; margin-bottom: 6px; }}
  .row {{ display: flex; justify-content: space-between; align-items: center;
          font-size: 13px; padding: 2px 0; }}
  .row .label {{ display: flex; align-items: center; gap: 6px; color: #333; }}
  .row .val   {{ font-weight: 600; color: #111; }}
  .dot {{ width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }}
  .green  {{ background: #22c55e; }}
  .blue   {{ background: #3b82f6; }}
  .orange {{ background: #f97316; }}
  .gray   {{ background: #d1d5db; }}
  .divider {{ border: none; border-top: 1px solid #f0f0f0; margin: 10px 0; }}
  #ts {{ font-size: 10px; color: #aaa; margin-top: 10px; }}

  #legend {{
    position: absolute; bottom: 28px; left: 12px; z-index: 1000;
    background: white; border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    padding: 10px 14px; font-size: 12px; line-height: 1.8;
  }}
  #legend b {{ display: block; font-size: 11px; font-weight: 700;
               text-transform: uppercase; letter-spacing:.05em;
               color: #888; margin-bottom: 4px; }}
  .leg-row {{ display: flex; align-items: center; gap: 8px; color: #333; }}
</style>
</head>
<body>
<div id="map"></div>

<div id="panel">
  <h2>📍 Listings Overview</h2>

  <div class="section">
    <div class="section-title">Active listings</div>
    <div class="row">
      <span class="label"><span class="dot green"></span>Mini-Excavator</span>
      <span class="val" id="s-mini"></span>
    </div>
    <div class="row">
      <span class="label"><span class="dot blue"></span>Track Loader</span>
      <span class="val" id="s-track"></span>
    </div>
    <div class="row">
      <span class="label" style="padding-left:16px;color:#666">Total active</span>
      <span class="val" id="s-total"></span>
    </div>
  </div>

  <hr class="divider"/>

  <div class="section">
    <div class="section-title">Coverage</div>
    <div class="row">
      <span class="label">Cities active</span>
      <span class="val" id="s-cities"></span>
    </div>
    <div class="row">
      <span class="label">Cities total</span>
      <span class="val" id="s-cities-total"></span>
    </div>
    <div class="row">
      <span class="label"><span class="dot orange"></span>Dupe queue</span>
      <span class="val" id="s-dupe"></span>
    </div>
    <div class="row">
      <span class="label"><span class="dot gray"></span>Uncovered</span>
      <span class="val" id="s-uncovered"></span>
    </div>
  </div>

  <hr class="divider"/>

  <div class="section">
    <div class="section-title">Engagement</div>
    <div class="row">
      <span class="label">Avg clicks</span>
      <span class="val" id="s-clicks"></span>
    </div>
  </div>

  <div id="ts"></div>
</div>

<div id="legend">
  <b>Legend</b>
  <div class="leg-row"><span class="dot green"></span> Active mini-excavator</div>
  <div class="leg-row"><span class="dot blue"></span> Active track loader</div>
  <div class="leg-row"><span class="dot orange"></span> Duplicate-removed (queued)</div>
  <div class="leg-row"><span class="dot gray"></span> Not yet listed</div>
</div>

<script>
const MARKERS   = {MARKERS_JSON};
const UNCOVERED = {UNCOVERED_JSON};
const STATS     = {STATS_JSON};

// ── Panel stats ────────────────────────────────────────────────────────────
document.getElementById('s-mini').textContent         = STATS.active_mini_ex;
document.getElementById('s-track').textContent        = STATS.active_track;
document.getElementById('s-total').textContent        = STATS.active_total;
document.getElementById('s-cities').textContent       = STATS.cities_active;
document.getElementById('s-cities-total').textContent = STATS.cities_total;
document.getElementById('s-dupe').textContent         = STATS.dupe_queue;
document.getElementById('s-uncovered').textContent    = UNCOVERED.length;
document.getElementById('s-clicks').textContent       = STATS.avg_clicks != null ? STATS.avg_clicks : '—';
document.getElementById('ts').textContent             = 'Updated ' + STATS.generated_at;

// ── Map ────────────────────────────────────────────────────────────────────
const map = L.map('map').setView([{center_lat:.5f}, {center_lng:.5f}], 10);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  maxZoom: 18
}}).addTo(map);

// ── Uncovered cities (gray, small, behind everything) ─────────────────────
UNCOVERED.forEach(function(c) {{
  L.circleMarker([c.lat, c.lng], {{
    radius: 5, color: '#9ca3af', fillColor: '#d1d5db',
    fillOpacity: 0.5, weight: 1
  }}).bindPopup('<b>' + c.city + ', TX</b><br><i style="color:#888">Not yet listed</i>').addTo(map);
}});

// ── Listing markers ────────────────────────────────────────────────────────
function fmtAge(days) {{
  if (days === null || days === undefined) return '—';
  if (days < 1) return 'Today';
  if (days < 2) return '1 day';
  return Math.floor(days) + ' days';
}}

MARKERS.forEach(function(m) {{
  var color, fillColor;
  if (m.status === 'duplicate') {{
    color = '#c2410c'; fillColor = '#f97316';
  }} else if (m.equip === 'mini-ex') {{
    color = '#15803d'; fillColor = '#22c55e';
  }} else {{
    color = '#1d4ed8'; fillColor = '#3b82f6';
  }}

  var equipLabel = m.equip === 'mini-ex' ? 'Mini-Excavator' : 'Track Loader';
  var statusLabel = m.status === 'active' ? '✅ Active' : '🟠 Duplicate queue';

  var popup = '<div style="font-size:13px;line-height:1.6;min-width:180px">';
  popup += '<b style="font-size:14px">' + m.city + ', TX</b><br>';
  popup += '<span style="color:#555">' + equipLabel + '</span><br>';
  popup += '<hr style="margin:4px 0;border:none;border-top:1px solid #eee"/>';
  popup += statusLabel + '<br>';
  if (m.title) popup += '<span style="font-size:11px;color:#666">' + m.title + '</span><br>';
  popup += '<hr style="margin:4px 0;border:none;border-top:1px solid #eee"/>';
  popup += '📅 Age: <b>' + fmtAge(m.age_days) + '</b><br>';
  popup += '👆 Clicks: <b>' + (m.last_clicks !== null && m.last_clicks !== undefined ? m.last_clicks : '—') + '</b>';
  if (m.clicks_age !== null && m.clicks_age !== undefined) {{
    popup += ' <span style="font-size:11px;color:#888">(' + fmtAge(m.clicks_age) + ' ago)</span>';
  }}
  if (m.status === 'duplicate' && m.dupe_since) {{
    popup += '<br>🗑️ Removed: <b>' + fmtAge(m.age_days !== null ? null : null) + '</b>';
    try {{
      var ds = new Date(m.dupe_since);
      var diffDays = Math.floor((Date.now() - ds) / 86400000);
      popup += '<br>🗑️ In queue: <b>' + (diffDays < 1 ? 'Today' : diffDays + ' days') + '</b>';
    }} catch(e) {{}}
  }}
  popup += '</div>';

  L.circleMarker([m.lat, m.lng], {{
    radius: m.status === 'active' ? 8 : 7,
    color: color, fillColor: fillColor,
    fillOpacity: 0.85, weight: 1.5
  }}).bindPopup(popup).addTo(map);
}});
</script>
</body>
</html>
"""

# ── Write output ───────────────────────────────────────────────────────────────
OUT = "listings_map.html"
with open(OUT, "w", encoding="utf-8") as f:
    f.write(HTML)

print(f"Map written to {OUT}")
print(f"  Active listings : {stats['active_total']}  ({stats['active_mini_ex']} mini-ex, {stats['active_track']} trackloader)")
print(f"  Duplicate queue : {stats['dupe_queue']}")
print(f"  Cities covered  : {stats['cities_active']} / {stats['cities_total']}")
print(f"  Avg clicks      : {stats['avg_clicks'] or '—'}")

if __name__ == "__main__" or True:
    parser = argparse.ArgumentParser()
    parser.add_argument("--open", action="store_true", help="Open map in browser after generating")
    args, _ = parser.parse_known_args()
    if args.open:
        webbrowser.open(os.path.abspath(OUT))
