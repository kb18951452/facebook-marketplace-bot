"""
map_listings.py — Generate listings_map.html, an interactive Leaflet map.

Usage:
    python map_listings.py          # writes listings_map.html
    python map_listings.py --open   # writes and opens in default browser

Click the legend items to toggle layer visibility.
"""

import argparse
import json
import os
import webbrowser
from datetime import datetime, timedelta, timezone

# ── Load data ─────────────────────────────────────────────────────────────────
def _load(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}

cities_raw   = _load("data/cities_data.json")
state        = _load("state.json")
dupe_history = _load("data/duplicate_history.json")
metadata     = _load("data/slot_metadata.json")

city_lookup  = {c["city"]: c for c in (cities_raw if isinstance(cities_raw, list) else [])}

# ── Helpers ───────────────────────────────────────────────────────────────────
def _age_days(iso_str):
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return round((datetime.now(timezone.utc) - dt).total_seconds() / 86400, 1)
    except Exception:
        return None

def _seven_day_clicks(snaps):
    """Delta clicks within the current listing instance over the last 7 days."""
    if not snaps:
        return None
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    recent = []
    for s in snaps:
        try:
            ts = datetime.fromisoformat(s["ts"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                recent.append(s)
        except Exception:
            pass
    if not recent:
        return None
    # If only one snapshot use its full value (listing is < 1 day old in the window)
    if len(recent) == 1:
        return recent[-1]["clicks"]
    return recent[-1]["clicks"] - recent[0]["clicks"]

# ── Build markers ─────────────────────────────────────────────────────────────
all_slots = set(state.keys()) | set(dupe_history.keys())
markers   = []

for slot in all_slots:
    parts = slot.split("_")
    if len(parts) < 3:
        continue
    equip = parts[0]
    city  = "_".join(parts[1:-1])

    geo = city_lookup.get(city)
    if not geo or not geo.get("lat") or not geo.get("lng"):
        continue

    lat = float(geo["lat"]) + (0.004 if equip == "mini-ex" else -0.004)
    lng = float(geo["lng"])

    meta   = metadata.get(slot, {})
    snaps  = meta.get("click_snapshots", [])
    status = "active" if slot in state else "duplicate"

    current_clicks  = snaps[-1]["clicks"] if snaps else None
    seven_day       = _seven_day_clicks(snaps)
    lifetime_clicks = meta.get("lifetime_clicks", 0) + (current_clicks or 0)
    title           = state.get(slot) or meta.get("title") or ""

    markers.append({
        "slot":            slot,
        "city":            city,
        "equip":           equip,
        "status":          status,
        "lat":             lat,
        "lng":             lng,
        "title":           title,
        "published_at":    meta.get("published_at"),
        "age_days":        _age_days(meta.get("published_at")),
        "current_clicks":  current_clicks,
        "seven_day":       seven_day,
        "lifetime_clicks": lifetime_clicks,
        "dupe_since":      dupe_history.get(slot),
        "dupe_age_days":   _age_days(dupe_history.get(slot)),
    })

# ── Uncovered cities ──────────────────────────────────────────────────────────
covered = {m["city"] for m in markers}
uncovered = [
    {"city": c["city"], "lat": float(c["lat"]), "lng": float(c["lng"])}
    for c in city_lookup.values()
    if c["city"] not in covered and c.get("lat") and c.get("lng")
]

# ── Stats ─────────────────────────────────────────────────────────────────────
active_m  = [m for m in markers if m["status"] == "active"]
dupe_m    = [m for m in markers if m["status"] == "duplicate"]
mini_m    = [m for m in active_m if m["equip"] == "mini-ex"]
track_m   = [m for m in active_m if m["equip"] == "trackloader"]
cities_active = len({m["city"] for m in active_m})

known_clicks = [m["current_clicks"] for m in active_m if m["current_clicks"] is not None]
avg_clicks   = round(sum(known_clicks) / len(known_clicks), 1) if known_clicks else None

known_7d     = [m["seven_day"] for m in active_m if m["seven_day"] is not None]
avg_7d       = round(sum(known_7d) / len(known_7d), 1) if known_7d else None

stats = {
    "active_total":   len(active_m),
    "active_mini_ex": len(mini_m),
    "active_track":   len(track_m),
    "dupe_queue":     len(dupe_m),
    "uncovered":      len(uncovered),
    "cities_active":  cities_active,
    "cities_total":   len(city_lookup),
    "avg_clicks":     avg_clicks,
    "avg_7d":         avg_7d,
    "generated_at":   datetime.now().strftime("%Y-%m-%d %H:%M"),
}

# ── Center ────────────────────────────────────────────────────────────────────
if markers:
    clat = sum(m["lat"] for m in markers) / len(markers)
    clng = sum(m["lng"] for m in markers) / len(markers)
else:
    clat, clng = 31.5, -97.1

# ── HTML ──────────────────────────────────────────────────────────────────────
MJ = json.dumps(markers,   ensure_ascii=False)
UJ = json.dumps(uncovered, ensure_ascii=False)
SJ = json.dumps(stats,     ensure_ascii=False)

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>FB Marketplace Listings</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background:#f3f4f6; }}
#map {{ height: 100vh; width: 100%; }}

/* ── Panel ── */
#panel {{
  position:absolute; top:12px; right:12px; z-index:1000;
  background:white; border-radius:12px;
  box-shadow:0 4px 20px rgba(0,0,0,.18);
  padding:16px 18px; min-width:230px;
}}
#panel h2 {{ font-size:14px; font-weight:700; color:#111; margin-bottom:12px; }}
.section {{ margin-bottom:12px; }}
.section-title {{ font-size:10px; font-weight:700; text-transform:uppercase;
                  letter-spacing:.07em; color:#9ca3af; margin-bottom:6px; }}
.row {{ display:flex; justify-content:space-between; align-items:center;
        font-size:13px; padding:2px 0; color:#374151; }}
.row .val {{ font-weight:700; color:#111; }}
.divider {{ border:none; border-top:1px solid #f3f4f6; margin:10px 0; }}
#ts {{ font-size:10px; color:#9ca3af; margin-top:8px; }}

/* ── Legend (toggleable) ── */
#legend {{
  position:absolute; bottom:28px; left:12px; z-index:1000;
  background:white; border-radius:10px;
  box-shadow:0 2px 10px rgba(0,0,0,.18);
  padding:10px 14px; user-select:none;
}}
#legend b {{ display:block; font-size:10px; font-weight:700; text-transform:uppercase;
             letter-spacing:.07em; color:#9ca3af; margin-bottom:6px; }}
.leg-row {{
  display:flex; align-items:center; gap:8px;
  font-size:12px; color:#374151; padding:3px 0;
  cursor:pointer; border-radius:4px; padding:4px 6px; margin:-4px -6px;
  transition:background .15s;
}}
.leg-row:hover {{ background:#f9fafb; }}
.leg-row.off {{ opacity:.35; }}
.dot {{ width:12px; height:12px; border-radius:50%; flex-shrink:0;
        border:1.5px solid rgba(0,0,0,.15); }}
.green  {{ background:#22c55e; }}
.blue   {{ background:#3b82f6; }}
.orange {{ background:#f97316; }}
.gray   {{ background:#d1d5db; }}

/* ── Popup ── */
.lf-popup {{ font-size:13px; line-height:1.65; min-width:190px; }}
.lf-popup .city {{ font-size:15px; font-weight:700; margin-bottom:2px; }}
.lf-popup .sub  {{ color:#6b7280; font-size:12px; margin-bottom:6px; }}
.lf-popup hr    {{ border:none; border-top:1px solid #f3f4f6; margin:6px 0; }}
.lf-popup .stat-row {{ display:flex; justify-content:space-between; }}
.lf-popup .stat-row span:last-child {{ font-weight:600; }}
</style>
</head>
<body>
<div id="map"></div>

<div id="panel">
  <h2>📍 Listings Overview</h2>
  <div class="section">
    <div class="section-title">Active</div>
    <div class="row"><span>Mini-Excavator</span><span class="val" id="s-mini"></span></div>
    <div class="row"><span>Track Loader</span><span class="val" id="s-track"></span></div>
    <div class="row" style="color:#9ca3af"><span>Total</span><span class="val" id="s-total"></span></div>
  </div>
  <hr class="divider"/>
  <div class="section">
    <div class="section-title">Coverage</div>
    <div class="row"><span>Cities active</span><span class="val" id="s-cities"></span></div>
    <div class="row"><span>Cities total</span><span class="val" id="s-ctotal"></span></div>
    <div class="row"><span>Dupe queue</span><span class="val" id="s-dupe"></span></div>
    <div class="row"><span>Not yet listed</span><span class="val" id="s-unc"></span></div>
  </div>
  <hr class="divider"/>
  <div class="section">
    <div class="section-title">Clicks</div>
    <div class="row"><span>Avg current</span><span class="val" id="s-avg"></span></div>
    <div class="row"><span>Avg 7-day delta</span><span class="val" id="s-7d"></span></div>
  </div>
  <div id="ts"></div>
</div>

<div id="legend">
  <b>Legend — click to toggle</b>
  <div class="leg-row" id="leg-mini"  onclick="toggle('mini')">
    <span class="dot green"></span>Active mini-excavator
  </div>
  <div class="leg-row" id="leg-track" onclick="toggle('track')">
    <span class="dot blue"></span>Active track loader
  </div>
  <div class="leg-row" id="leg-dupe"  onclick="toggle('dupe')">
    <span class="dot orange"></span>Duplicate-removed (queued)
  </div>
  <div class="leg-row" id="leg-unc"   onclick="toggle('unc')">
    <span class="dot gray"></span>Not yet listed
  </div>
</div>

<script>
const MARKERS   = {MJ};
const UNCOVERED = {UJ};
const STATS     = {SJ};

// ── Panel ────────────────────────────────────────────────────────────────────
document.getElementById('s-mini').textContent  = STATS.active_mini_ex;
document.getElementById('s-track').textContent = STATS.active_track;
document.getElementById('s-total').textContent = STATS.active_total;
document.getElementById('s-cities').textContent= STATS.cities_active;
document.getElementById('s-ctotal').textContent= STATS.cities_total;
document.getElementById('s-dupe').textContent  = STATS.dupe_queue;
document.getElementById('s-unc').textContent   = STATS.uncovered;
document.getElementById('s-avg').textContent   = STATS.avg_clicks != null ? STATS.avg_clicks : '—';
document.getElementById('s-7d').textContent    = STATS.avg_7d    != null ? STATS.avg_7d     : '—';
document.getElementById('ts').textContent      = 'Updated ' + STATS.generated_at;

// ── Map ───────────────────────────────────────────────────────────────────────
const map = L.map('map').setView([{clat:.5f}, {clng:.5f}], 10);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  attribution: '© <a href="https://openstreetmap.org/copyright">OpenStreetMap</a>',
  maxZoom: 18
}}).addTo(map);

// ── Layer groups ──────────────────────────────────────────────────────────────
const layers = {{
  mini:  L.layerGroup().addTo(map),
  track: L.layerGroup().addTo(map),
  dupe:  L.layerGroup().addTo(map),
  unc:   L.layerGroup().addTo(map),
}};
const visible = {{ mini: true, track: true, dupe: true, unc: true }};

function toggle(key) {{
  visible[key] = !visible[key];
  if (visible[key]) {{ layers[key].addTo(map); }}
  else              {{ map.removeLayer(layers[key]); }}
  document.getElementById('leg-' + key).classList.toggle('off', !visible[key]);
}}

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmtDays(d) {{
  if (d === null || d === undefined) return '—';
  if (d < 1) return 'Today';
  return Math.floor(d) + 'd';
}}
function fmtClicks(n) {{
  return (n !== null && n !== undefined) ? n : '—';
}}

// ── Uncovered ─────────────────────────────────────────────────────────────────
UNCOVERED.forEach(function(c) {{
  L.circleMarker([c.lat, c.lng], {{
    radius: 5, color: '#9ca3af', fillColor: '#d1d5db', fillOpacity: 0.5, weight: 1
  }}).bindPopup(
    '<div class="lf-popup"><div class="city">' + c.city + ', TX</div>' +
    '<div class="sub">Not yet listed</div></div>'
  ).addTo(layers.unc);
}});

// ── Listing markers ───────────────────────────────────────────────────────────
MARKERS.forEach(function(m) {{
  var layerKey, color, fill;
  if (m.status === 'duplicate') {{
    layerKey = 'dupe'; color = '#c2410c'; fill = '#f97316';
  }} else if (m.equip === 'mini-ex') {{
    layerKey = 'mini'; color = '#15803d'; fill = '#22c55e';
  }} else {{
    layerKey = 'track'; color = '#1d4ed8'; fill = '#3b82f6';
  }}

  var equipLabel = m.equip === 'mini-ex' ? 'Mini-Excavator' : 'Track Loader';
  var statusBadge = m.status === 'active'
    ? '<span style="color:#15803d;font-weight:600">● Active</span>'
    : '<span style="color:#c2410c;font-weight:600">● Duplicate queue</span>';

  var popup =
    '<div class="lf-popup">' +
    '<div class="city">' + m.city + ', TX</div>' +
    '<div class="sub">' + equipLabel + ' &nbsp;·&nbsp; ' + statusBadge + '</div>';

  if (m.title) {{
    popup += '<div style="font-size:11px;color:#6b7280;margin-bottom:4px">' + m.title + '</div>';
  }}
  popup += '<hr/>';

  popup +=
    '<div class="stat-row"><span>📅 Age</span><span>' + fmtDays(m.age_days) + '</span></div>' +
    '<div class="stat-row"><span>👆 Current clicks</span><span>' + fmtClicks(m.current_clicks) + '</span></div>' +
    '<div class="stat-row"><span>📈 7-day delta</span><span>' + fmtClicks(m.seven_day) + '</span></div>' +
    '<div class="stat-row"><span>🏆 Lifetime clicks</span><span>' + (m.lifetime_clicks > 0 ? m.lifetime_clicks : '—') + '</span></div>';

  if (m.status === 'duplicate' && m.dupe_age_days !== null) {{
    popup += '<div class="stat-row"><span>🗑️ In queue</span><span>' + fmtDays(m.dupe_age_days) + '</span></div>';
  }}

  popup += '</div>';

  L.circleMarker([m.lat, m.lng], {{
    radius: m.status === 'active' ? 8 : 7,
    color: color, fillColor: fill, fillOpacity: 0.85, weight: 1.5
  }}).bindPopup(popup).addTo(layers[layerKey]);
}});
</script>
</body>
</html>
"""

OUT = "listings_map.html"
with open(OUT, "w", encoding="utf-8") as f:
    f.write(HTML)

print(f"Map written to {OUT}")
print(f"  Active     : {stats['active_total']}  ({stats['active_mini_ex']} mini-ex, {stats['active_track']} track)")
print(f"  Dupe queue : {stats['dupe_queue']}")
print(f"  Uncovered  : {stats['uncovered']} / {stats['cities_total']} cities")
print(f"  Avg clicks : {stats['avg_clicks'] or 'n/a'}  |  7-day avg delta: {stats['avg_7d'] or 'n/a'}")

parser = argparse.ArgumentParser()
parser.add_argument("--open", action="store_true")
args, _ = parser.parse_known_args()
if args.open:
    webbrowser.open(os.path.abspath(OUT))
