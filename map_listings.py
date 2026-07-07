"""
map_listings.py — Generate listings_map.html, an interactive Leaflet map.

Usage:
    python map_listings.py          # writes listings_map.html
    python map_listings.py --open   # writes and opens in default browser

Click the legend items to toggle layer visibility.
"""

import argparse
import json
import math
import os
import subprocess
import webbrowser
from collections import defaultdict
from datetime import datetime, timezone

from helpers.slot import parse as parse_slot, build as build_slot
from helpers.click_history import seven_day_delta, lifetime_total
from helpers.ads import get_equipment, get_locations, TASK_VARIANTS

# ── Load data ─────────────────────────────────────────────────────────────────
def _load(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}

cities_raw   = _load("data/cities_data.json")
state        = _load("state.json")
metadata     = _load("data/slot_metadata.json")
competitors  = _load("data/competitors.json").get("sellers", {})
dupe_history = _load("data/duplicate_history.json")

city_lookup = {c["city"]: c for c in (cities_raw if isinstance(cities_raw, list) else [])}

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

def _get_schedule_info():
    """Query Windows Task Scheduler for next/last FacebookMarketplaceBot run times."""
    try:
        r = subprocess.run(
            ["schtasks", "/query", "/fo", "LIST", "/v"],
            capture_output=True, text=True, timeout=15,
            encoding="utf-8", errors="replace"
        )
        now = datetime.now()
        soonest = None
        latest_last = None
        cur = {}
        for line in r.stdout.splitlines():
            line = line.strip()
            if line.startswith("TaskName:"):
                name = line.split(":", 1)[1].strip()
                cur = {"name": name} if ("FacebookMarketplaceBot" in name and "_Run" in name) else {}
            elif cur:
                if line.startswith("Next Run Time:"):
                    val = line.split(":", 1)[1].strip()
                    if val and "N/A" not in val:
                        try:
                            dt = datetime.strptime(val, "%m/%d/%Y %I:%M:%S %p")
                            if dt > now and (soonest is None or dt < soonest):
                                soonest = dt
                        except Exception:
                            pass
                elif line.startswith("Last Run Time:"):
                    val = line.split(":", 1)[1].strip()
                    if val and "N/A" not in val:
                        try:
                            dt = datetime.strptime(val, "%m/%d/%Y %I:%M:%S %p")
                            if latest_last is None or dt > latest_last:
                                latest_last = dt
                        except Exception:
                            pass
        next_str = soonest.strftime("%a %m/%d %I:%M %p") if soonest else "—"
        last_str = latest_last.strftime("%a %m/%d %I:%M %p") if latest_last else "—"
        return next_str, last_str
    except Exception:
        return "—", "—"


# ── Build markers (active listings only) ──────────────────────────────────────
markers = []

for slot in state.keys():
    parsed = parse_slot(slot)
    if not parsed:
        continue
    equip = parsed.equipment_type
    city  = parsed.city

    geo = city_lookup.get(city)
    if not geo or not geo.get("lat") or not geo.get("lng"):
        continue

    meta   = metadata.get(slot, {})
    snaps  = meta.get("click_snapshots", [])
    pub_at = meta.get("published_at")

    current_clicks  = snaps[-1]["clicks"] if snaps else None
    seven_day       = seven_day_delta(snaps, pub_at)
    lifetime_clicks = lifetime_total(metadata, slot)

    markers.append({
        "slot":            slot,
        "city":            city,
        "equip":           equip,
        "lat":             float(geo["lat"]),
        "lng":             float(geo["lng"]),
        "title":           state.get(slot, ""),
        "published_at":    pub_at,
        "age_days":        _age_days(pub_at),
        "current_clicks":  current_clicks,
        "seven_day":       seven_day,
        "lifetime_clicks": lifetime_clicks,
        "radius":          5,  # filled in below
    })

# ── Pending markers: per (city, equipment) aggregate of missing task variants ──
# One marker per equipment type per city that isn't fully covered — not one per
# task variant, to keep density comparable to the active-listing markers.
active_slots = set(state.keys())
pending_markers = []

for loc in get_locations():
    city = loc.get("city")
    geo = city_lookup.get(city)
    if not geo or not geo.get("lat") or not geo.get("lng"):
        continue
    for equip in get_equipment():
        tasks = TASK_VARIANTS.get(equip, [])
        if not tasks:
            continue
        missing_tasks = []
        duplicate_count = 0
        for task in tasks:
            slot = build_slot(equip, city, "eng", task["slug"])
            if slot in active_slots:
                continue
            missing_tasks.append(task["slug"])
            if slot in dupe_history:
                duplicate_count += 1
        if not missing_tasks:
            continue
        pending_markers.append({
            "slot":            f"{equip}_pending",  # synthetic, for stable jitter ordering only
            "city":            city,
            "equip":           equip,
            "lat":             float(geo["lat"]),
            "lng":             float(geo["lng"]),
            "missing_count":   len(missing_tasks),
            "total_count":     len(tasks),
            "missing_tasks":   missing_tasks,
            "duplicate_count": duplicate_count,
        })

# ── Jitter: spread same-city markers so bubbles never overlap ─────────────────
# Sort within each city by slot name for stable placement across reloads.
# Spread in a circle; longitude scaled by ~cos(31°N) so the circle looks round.
# Active and pending markers jitter together so a city's full picture clusters
# in one place on the map.
JITTER_R = 0.004
city_groups = defaultdict(list)
for m in markers:
    city_groups[m["city"]].append(m)
for m in pending_markers:
    city_groups[m["city"]].append(m)

for group in city_groups.values():
    n = len(group)
    if n == 1:
        continue
    group.sort(key=lambda m: m["slot"])
    for i, m in enumerate(group):
        angle = 2 * math.pi * i / n
        m["lat"] += JITTER_R * math.cos(angle)
        m["lng"] += JITTER_R * math.sin(angle) * 0.82

# ── Bubble radius: scale by current click count ───────────────────────────────
MIN_R, MAX_R = 5, 22
all_clicks = [m["current_clicks"] for m in markers if m["current_clicks"] and m["current_clicks"] > 0]
max_clicks = max(all_clicks) if all_clicks else 1
for m in markers:
    c = m["current_clicks"]
    if c and c > 0:
        m["radius"] = round(MIN_R + (c / max_clicks) * (MAX_R - MIN_R), 1)
    else:
        m["radius"] = MIN_R

# ── Uncovered cities (no active listing, regardless of past dupe history) ─────
covered = {m["city"] for m in markers}
uncovered = [
    {"city": c["city"], "lat": float(c["lat"]), "lng": float(c["lng"])}
    for c in city_lookup.values()
    if c["city"] not in covered and c.get("lat") and c.get("lng")
]

# ── Stats ─────────────────────────────────────────────────────────────────────
mini_m  = [m for m in markers if m["equip"] == "mini-ex"]
track_m = [m for m in markers if m["equip"] == "trackloader"]
cities_active = len({m["city"] for m in markers})

known_clicks = [m["current_clicks"] for m in markers if m["current_clicks"] is not None]
avg_clicks   = round(sum(known_clicks) / len(known_clicks), 1) if known_clicks else None

known_7d = [m["seven_day"] for m in markers if m["seven_day"] is not None]
avg_7d   = round(sum(known_7d) / len(known_7d), 1) if known_7d else None

next_run_str, last_run_str = _get_schedule_info()

stats = {
    "active_total":   len(markers),
    "active_mini_ex": len(mini_m),
    "active_track":   len(track_m),
    "uncovered":      len(uncovered),
    "cities_active":  cities_active,
    "cities_total":   len(city_lookup),
    "avg_clicks":     avg_clicks,
    "avg_7d":         avg_7d,
    "pending_total":  sum(p["missing_count"] for p in pending_markers),
    "next_run":       next_run_str,
    "last_run":       last_run_str,
    "generated_at":   datetime.now().strftime("%Y-%m-%d %H:%M"),
}

# ── Center ────────────────────────────────────────────────────────────────────
if markers:
    clat = sum(m["lat"] for m in markers) / len(markers)
    clng = sum(m["lng"] for m in markers) / len(markers)
else:
    clat, clng = 31.5, -97.1

# ── HTML ──────────────────────────────────────────────────────────────────────
MJ = json.dumps(markers,         ensure_ascii=False)
UJ = json.dumps(uncovered,       ensure_ascii=False)
PJ = json.dumps(pending_markers, ensure_ascii=False)
SJ = json.dumps(stats,           ensure_ascii=False)
CJ = json.dumps(competitors,     ensure_ascii=False)

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
  font-size:12px; color:#374151;
  cursor:pointer; border-radius:4px; padding:4px 6px; margin:-4px -6px;
  transition:background .15s;
}}
.leg-row:hover {{ background:#f9fafb; }}
.leg-row.off {{ opacity:.35; }}
.dot {{ width:12px; height:12px; border-radius:50%; flex-shrink:0;
        border:1.5px solid rgba(0,0,0,.15); }}
.green  {{ background:#22c55e; }}
.blue   {{ background:#3b82f6; }}
.gray   {{ background:#d1d5db; }}
.purple {{ background:#8b5cf6; }}
.hollow {{ background:transparent; border:1.5px dashed #6b7280; }}

select.comp-sel {{
  width:100%; font-size:12px; padding:4px 6px; margin-top:5px;
  border:1px solid #e5e7eb; border-radius:6px; color:#374151; background:white;
}}

@keyframes livepulse {{
  0%, 100% {{ opacity:1; }}
  50%       {{ opacity:.3; }}
}}
@keyframes newmarker {{
  0%   {{ stroke-width:6; stroke-opacity:.8; }}
  100% {{ stroke-width:1.5; stroke-opacity:0; }}
}}

/* ── Bubble legend ── */
#bubble-legend {{
  position:absolute; bottom:28px; left:160px; z-index:1000;
  background:white; border-radius:10px;
  box-shadow:0 2px 10px rgba(0,0,0,.18);
  padding:10px 14px; user-select:none;
}}
#bubble-legend b {{ display:block; font-size:10px; font-weight:700; text-transform:uppercase;
                    letter-spacing:.07em; color:#9ca3af; margin-bottom:8px; }}
.bubble-row {{ display:flex; align-items:center; gap:8px; font-size:12px; color:#374151; padding:2px 0; }}
.bubble-circle {{ border-radius:50%; background:rgba(100,100,100,.25);
                  border:1.5px solid rgba(0,0,0,.2); flex-shrink:0; }}

/* ── Popup ── */
.lf-popup {{ font-size:13px; line-height:1.65; min-width:190px; }}
.lf-popup .city {{ font-size:15px; font-weight:700; margin-bottom:2px; }}
.lf-popup .sub  {{ color:#6b7280; font-size:12px; margin-bottom:6px; }}
.lf-popup hr    {{ border:none; border-top:1px solid #f3f4f6; margin:6px 0; }}
.lf-popup .stat-row {{ display:flex; justify-content:space-between; }}
.lf-popup .stat-row span:last-child {{ font-weight:600; }}

/* ── Action buttons ── */
.action-btn {{
  display:block; width:100%; padding:7px 12px; border:none; border-radius:8px;
  font-size:12px; font-weight:600; cursor:pointer;
  background:#2563eb; color:white; transition:background .15s;
}}
.action-btn:hover:not(:disabled) {{ background:#1d4ed8; }}
.action-btn.secondary {{ background:#f3f4f6; color:#374151; border:1px solid #e5e7eb; }}
.action-btn.secondary:hover:not(:disabled) {{ background:#e5e7eb; }}
.action-btn:disabled {{ opacity:.5; cursor:not-allowed; }}
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
    <div class="row"><span>Not yet listed</span><span class="val" id="s-unc"></span></div>
    <div class="row"><span>Pending slots</span><span class="val" id="s-pending"></span></div>
  </div>
  <hr class="divider"/>
  <div class="section">
    <div class="section-title">Clicks</div>
    <div class="row"><span>Avg current</span><span class="val" id="s-avg"></span></div>
    <div class="row"><span>Avg 7-day delta</span><span class="val" id="s-7d"></span></div>
  </div>
  <hr class="divider"/>
  <div class="section" id="comp-panel" style="display:none">
    <div class="section-title">Competition</div>
    <div class="row"><span>Sellers</span><span class="val" id="s-comp-sellers">—</span></div>
    <div class="row"><span>Listings</span><span class="val" id="s-comp-listings">—</span></div>
    <select class="comp-sel" id="comp-select" onchange="filterCompetitors(this.value)">
      <option value="all">All sellers</option>
      <option value="none">Hide all</option>
    </select>
  </div>
  <hr class="divider" id="comp-divider" style="display:none"/>
  <div class="section">
    <div class="section-title">Agent</div>
    <div class="row"><span>Status</span><span class="val" id="s-bot-status"><span style="color:#6b7280">&#9679; Idle</span></span></div>
    <div class="row"><span>Next run</span><span class="val" id="s-next-run">—</span></div>
    <div class="row"><span>Last run</span><span class="val" id="s-last-run">—</span></div>
  </div>
  <div id="live-section" style="display:none">
    <hr class="divider"/>
    <div class="section-title" style="display:flex;align-items:center;gap:6px">
      <span style="width:7px;height:7px;border-radius:50%;background:#22c55e;display:inline-block;animation:livepulse 1.2s ease-in-out infinite"></span>
      Live
    </div>
    <div id="live-now" style="font-size:12px;color:#374151;line-height:1.5;margin-bottom:6px"></div>
    <div id="live-recent" style="font-size:11px;color:#6b7280;line-height:1.6"></div>
  </div>
  <hr class="divider"/>
  <div style="margin-top:4px">
    <button class="action-btn" id="btn-agent" onclick="triggerRun('agent')">&#9654; Run Agent Now</button>
    <button class="action-btn secondary" id="btn-stats" onclick="triggerRun('stats')" style="margin-top:6px">&#8635; Refresh Stats</button>
  </div>
  <div id="s-last-log" style="font-size:9px;color:#9ca3af;margin-top:8px;line-height:1.4;word-break:break-all"></div>
  <div id="ts"></div>
</div>

<div id="legend">
  <b>Legend — click to toggle</b>
  <div class="leg-row" id="leg-mini" onclick="toggle('mini')">
    <span class="dot green"></span>Active mini-excavator
  </div>
  <div class="leg-row" id="leg-track" onclick="toggle('track')">
    <span class="dot blue"></span>Active track loader
  </div>
  <div class="leg-row" id="leg-unc" onclick="toggle('unc')">
    <span class="dot gray"></span>Not yet listed
  </div>
  <div class="leg-row" id="leg-pending" onclick="toggle('pending')">
    <span class="dot hollow"></span>Pending (green/blue outline = equipment)
  </div>
  <div class="leg-row" id="leg-comp" onclick="toggleComp()" style="display:none">
    <span class="dot purple"></span>Competitor listing
  </div>
</div>

<div id="bubble-legend">
  <b>Bubble = clicks</b>
  <div class="bubble-row">
    <span class="bubble-circle" style="width:10px;height:10px"></span>
    <span>Few / none</span>
  </div>
  <div class="bubble-row">
    <span class="bubble-circle" style="width:16px;height:16px"></span>
    <span>Some</span>
  </div>
  <div class="bubble-row">
    <span class="bubble-circle" style="width:24px;height:24px"></span>
    <span>Many clicks</span>
  </div>
  <div style="font-size:10px;color:#9ca3af;margin-top:4px">hover for 7-day delta</div>
</div>

<script>
const MARKERS      = {MJ};
const UNCOVERED    = {UJ};
const PENDING      = {PJ};
const STATS        = {SJ};
const COMPETITORS  = {CJ};

// ── Panel ────────────────────────────────────────────────────────────────────
document.getElementById('s-mini').textContent   = STATS.active_mini_ex;
document.getElementById('s-track').textContent  = STATS.active_track;
document.getElementById('s-total').textContent  = STATS.active_total;
document.getElementById('s-cities').textContent = STATS.cities_active;
document.getElementById('s-ctotal').textContent = STATS.cities_total;
document.getElementById('s-unc').textContent    = STATS.uncovered;
document.getElementById('s-pending').textContent = STATS.pending_total;
document.getElementById('s-avg').textContent    = STATS.avg_clicks != null ? STATS.avg_clicks : '—';
document.getElementById('s-7d').textContent     = STATS.avg_7d    != null ? STATS.avg_7d     : '—';
document.getElementById('ts').textContent       = 'Updated ' + STATS.generated_at;

// ── Map ───────────────────────────────────────────────────────────────────────
const map = L.map('map').setView([{clat:.5f}, {clng:.5f}], 10);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  attribution: '© <a href="https://openstreetmap.org/copyright">OpenStreetMap</a>',
  maxZoom: 18
}}).addTo(map);

// ── Layer groups ──────────────────────────────────────────────────────────────
const layers = {{
  mini:    L.layerGroup().addTo(map),
  track:   L.layerGroup().addTo(map),
  unc:     L.layerGroup().addTo(map),
  pending: L.layerGroup().addTo(map),
}};
const visible = {{ mini: true, track: true, unc: true, pending: true }};

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
function buildPopup(m) {{
  var equipLabel = m.equip === 'mini-ex' ? 'Mini-Excavator' : 'Track Loader';
  var p = '<div class="lf-popup"><div class="city">' + m.city + ', TX</div>' +
    '<div class="sub">' + equipLabel + '</div>';
  if (m.title) p += '<div style="font-size:11px;color:#6b7280;margin-bottom:4px">' + m.title + '</div>';
  p += '<hr/>' +
    '<div class="stat-row"><span>📅 Age</span><span>' + fmtDays(m.age_days) + '</span></div>' +
    '<div class="stat-row"><span>👆 Current clicks</span><span>' + fmtClicks(m.current_clicks) + '</span></div>' +
    '<div class="stat-row"><span>📈 7-day delta</span><span>' + fmtClicks(m.seven_day) + '</span></div>' +
    '<div class="stat-row"><span>🏆 Lifetime clicks</span><span>' + (m.lifetime_clicks > 0 ? m.lifetime_clicks : '—') + '</span></div>' +
    '</div>';
  return p;
}}
function fmtTaskSlug(s) {{
  return s.split('_').map(function(w) {{ return w.charAt(0).toUpperCase() + w.slice(1); }}).join(' ');
}}
function buildPendingPopup(m) {{
  var equipLabel = m.equip === 'mini-ex' ? 'Mini-Excavator' : 'Track Loader';
  var p = '<div class="lf-popup"><div class="city">' + m.city + ', TX</div>' +
    '<div class="sub">' + equipLabel + ' — pending</div><hr/>' +
    '<div class="stat-row"><span>Missing task variants</span><span>' + m.missing_count + ' / ' + m.total_count + '</span></div>';
  if (m.duplicate_count > 0) {{
    p += '<div class="stat-row"><span>⚠️ Duplicate-queued</span><span>' + m.duplicate_count + '</span></div>';
  }}
  p += '<hr/><div style="font-size:11px;color:#374151;line-height:1.6">' +
    m.missing_tasks.map(fmtTaskSlug).join('<br>') + '</div></div>';
  return p;
}}
function updateStats(s) {{
  document.getElementById('s-mini').textContent   = s.active_mini_ex;
  document.getElementById('s-track').textContent  = s.active_track;
  document.getElementById('s-total').textContent  = s.active_total;
  document.getElementById('s-cities').textContent = s.cities_active;
  document.getElementById('s-ctotal').textContent = s.cities_total;
  document.getElementById('s-unc').textContent    = s.uncovered;
  document.getElementById('s-pending').textContent = s.pending_total;
  document.getElementById('s-avg').textContent    = s.avg_clicks != null ? s.avg_clicks : '—';
  document.getElementById('s-7d').textContent     = s.avg_7d    != null ? s.avg_7d     : '—';
  if (s.next_run) document.getElementById('s-next-run').textContent = s.next_run;
  if (s.last_run) document.getElementById('s-last-run').textContent = s.last_run;
  document.getElementById('ts').textContent = 'Updated ' + s.generated_at;
}}

// ── Layer renderer (called on initial load and on every /api/markers refresh) ─
var knownSlots = new Set(MARKERS.map(function(m) {{ return m.slot; }}));

function renderLayers(markersArr, uncoveredArr, pendingArr) {{
  layers.mini.clearLayers();
  layers.track.clearLayers();
  layers.unc.clearLayers();
  layers.pending.clearLayers();

  uncoveredArr.forEach(function(c) {{
    L.circleMarker([c.lat, c.lng], {{
      radius: 5, color: '#9ca3af', fillColor: '#d1d5db', fillOpacity: 0.5, weight: 1
    }}).bindPopup(
      '<div class="lf-popup"><div class="city">' + c.city + ', TX</div><div class="sub">Not yet listed</div></div>'
    ).addTo(layers.unc);
  }});

  (pendingArr || []).forEach(function(m) {{
    var color = m.equip === 'mini-ex' ? '#22c55e' : '#3b82f6';
    L.circleMarker([m.lat, m.lng], {{
      radius: 6, color: color, fillColor: color, fillOpacity: 0.08,
      weight: 1.5, dashArray: '3,3',
    }}).bindPopup(buildPendingPopup(m)).addTo(layers.pending);
  }});

  var newSlots = new Set(markersArr.map(function(m) {{ return m.slot; }}));
  markersArr.forEach(function(m) {{
    var layerKey = m.equip === 'mini-ex' ? 'mini' : 'track';
    var color    = m.equip === 'mini-ex' ? '#15803d' : '#1d4ed8';
    var fill     = m.equip === 'mini-ex' ? '#22c55e' : '#3b82f6';
    var isNew    = !knownSlots.has(m.slot);
    var marker = L.circleMarker([m.lat, m.lng], {{
      radius: m.radius,
      color: isNew ? '#ffffff' : color,
      fillColor: fill, fillOpacity: 0.85,
      weight: isNew ? 3 : 1.5,
    }}).bindPopup(buildPopup(m)).addTo(layers[layerKey]);
    if (isNew) {{
      setTimeout(function() {{ marker.setStyle({{color: color, weight: 1.5}}); }}, 4000);
    }}
  }});
  knownSlots = newSlots;
}}

// Initial render from baked-in data
renderLayers(MARKERS, UNCOVERED, PENDING);

// ── Bot status controls ───────────────────────────────────────────────────────
const SERVER_MODE = window.location.protocol !== 'file:';

document.getElementById('s-next-run').textContent = STATS.next_run || '—';
document.getElementById('s-last-run').textContent  = STATS.last_run  || '—';

function setAgentStatus(running) {{
  document.getElementById('s-bot-status').innerHTML = running
    ? '<span style="color:#15803d;font-weight:600">&#9679; Running</span>'
    : '<span style="color:#6b7280">&#9679; Idle</span>';
  document.getElementById('btn-agent').disabled = running;
  document.getElementById('btn-stats').disabled = running;
}}

// ── Live feed: polls /api/live every 5 s ──────────────────────────────────────
function refreshLive() {{
  fetch('/api/live')
    .then(function(r) {{ return r.json(); }})
    .then(function(d) {{
      setAgentStatus(d.running);
      var sec = document.getElementById('live-section');
      sec.style.display = (d.running && d.publishing) ? '' : 'none';

      if (d.publishing) {{
        var p = d.publishing;
        var dot = p.equip === 'mini-ex' ? '🟢' : '🔵';
        document.getElementById('live-now').innerHTML =
          '<strong>' + dot + ' ' + p.city + ', TX</strong><br>' +
          '<span style="color:#6b7280">' + p.title.slice(0, 55) + (p.title.length > 55 ? '…' : '') + '</span>';
      }}

      if (d.recent && d.recent.length) {{
        var html = d.recent.slice().reverse().map(function(r) {{
          return '✓ ' + r.city + ' <span style="color:#d1d5db">·</span> ' + r.ts;
        }}).join('<br>');
        document.getElementById('live-recent').innerHTML = html;
      }}
    }})
    .catch(function() {{}});
}}

// ── Marker refresh: polls /api/markers every 30 s ─────────────────────────────
function refreshMarkers() {{
  fetch('/api/markers')
    .then(function(r) {{ return r.json(); }})
    .then(function(d) {{
      if (d.markers)   renderLayers(d.markers, d.uncovered || [], d.pending || []);
      if (d.stats)     updateStats(d.stats);
    }})
    .catch(function() {{}});
}}

function triggerRun(type) {{
  if (!SERVER_MODE) {{
    alert('Open http://localhost:8080 via map_server.py to use this button.');
    return;
  }}
  var btn = document.getElementById(type === 'agent' ? 'btn-agent' : 'btn-stats');
  btn.disabled = true;
  btn.textContent = '⏳ Starting…';
  fetch('/api/run/' + type, {{method: 'POST'}})
    .then(function(r) {{ return r.json(); }})
    .then(function(d) {{
      btn.textContent = d.ok ? '✓ Started' : '✗ Error';
      setTimeout(refreshLive, 2000);
      setTimeout(function() {{
        btn.textContent = type === 'agent' ? '▶ Run Agent Now' : '⟳ Refresh Stats';
        refreshLive();
      }}, 8000);
    }})
    .catch(function() {{ btn.textContent = '✗ Error'; }});
}}

if (SERVER_MODE) {{
  refreshLive();
  setInterval(refreshLive, 5000);
  setInterval(refreshMarkers, 30000);
}}

// ── Competitor layer ──────────────────────────────────────────────────────────
var compLayer = L.layerGroup().addTo(map);
var compVisible = true;

function _djitter(seed, scale) {{
  var h = 0;
  for (var i = 0; i < seed.length; i++) {{ h = Math.imul(31, h) + seed.charCodeAt(i) | 0; }}
  return ((h >>> 0) % 10000) / 10000 * scale - scale / 2;
}}

function renderCompetitors(filterSellerId) {{
  compLayer.clearLayers();
  if (filterSellerId === 'none') return;
  Object.keys(COMPETITORS).forEach(function(sid) {{
    if (filterSellerId !== 'all' && filterSellerId !== sid) return;
    var seller = COMPETITORS[sid];
    seller.listings.forEach(function(listing) {{
      var lat = listing.lat + _djitter(listing.url + 'lat', 0.005);
      var lng = listing.lng + _djitter(listing.url + 'lng', 0.005) * 0.82;
      var popup =
        '<div class="lf-popup">' +
        '<div class="city">' + listing.location + '</div>' +
        '<div class="sub" style="color:#7c3aed">🟣 ' + (seller.name || sid) + '</div>' +
        (listing.title ? '<div style="font-size:11px;color:#374151;margin:4px 0">' + listing.title + '</div>' : '') +
        '<hr/>' +
        '<div class="stat-row"><span>💰 Price</span><span>' + (listing.price || '—') + '</span></div>' +
        (listing.url ? '<div style="margin-top:6px"><a href="' + listing.url + '" target="_blank" style="color:#2563eb;font-size:11px">View listing ↗</a></div>' : '') +
        '</div>';
      L.circleMarker([lat, lng], {{
        radius: 8, color: '#6d28d9', fillColor: '#8b5cf6', fillOpacity: 0.85, weight: 1.5,
      }}).bindPopup(popup).addTo(compLayer);
    }});
  }});
}}

function filterCompetitors(val) {{
  renderCompetitors(val);
  if (val !== 'none') {{
    if (!map.hasLayer(compLayer)) map.addLayer(compLayer);
  }}
}}

function toggleComp() {{
  compVisible = !compVisible;
  if (compVisible) {{ map.addLayer(compLayer); }} else {{ map.removeLayer(compLayer); }}
  document.getElementById('leg-comp').classList.toggle('off', !compVisible);
}}

// Initialise competitor panel
(function() {{
  var sel = document.getElementById('comp-select');
  var totalListings = 0;
  var sellerCount   = 0;
  Object.keys(COMPETITORS).forEach(function(sid) {{
    sellerCount++;
    var seller = COMPETITORS[sid];
    totalListings += seller.listings.length;
    var opt = document.createElement('option');
    opt.value       = sid;
    opt.textContent = (seller.name || sid) + ' (' + seller.listings.length + ')';
    sel.appendChild(opt);
  }});
  if (sellerCount > 0) {{
    document.getElementById('s-comp-sellers').textContent  = sellerCount;
    document.getElementById('s-comp-listings').textContent = totalListings;
    document.getElementById('comp-panel').style.display    = '';
    document.getElementById('comp-divider').style.display  = '';
    document.getElementById('leg-comp').style.display      = '';
    renderCompetitors('all');
  }}
}})();
</script>
</body>
</html>
"""

OUT = "listings_map.html"
with open(OUT, "w", encoding="utf-8") as f:
    f.write(HTML)

# Also write raw data so map_server /api/markers can serve it without re-parsing HTML
with open("listings_data.json", "w", encoding="utf-8") as f:
    json.dump({"markers": markers, "uncovered": uncovered, "pending": pending_markers, "stats": stats},
              f, ensure_ascii=False)

print(f"Map written to {OUT}")
print(f"  Active     : {stats['active_total']}  ({stats['active_mini_ex']} mini-ex, {stats['active_track']} track)")
print(f"  Uncovered  : {stats['uncovered']} / {stats['cities_total']} cities")
print(f"  Pending    : {stats['pending_total']} task-variant slots across {len(pending_markers)} city/equipment pairs")
print(f"  Avg clicks : {stats['avg_clicks'] or 'n/a'}  |  7-day avg delta: {stats['avg_7d'] or 'n/a'}")

parser = argparse.ArgumentParser()
parser.add_argument("--open", action="store_true")
args, _ = parser.parse_known_args()
if args.open:
    webbrowser.open(os.path.abspath(OUT))
