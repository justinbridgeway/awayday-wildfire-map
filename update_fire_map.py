#!/usr/bin/env python3
"""
Awayday Colorado Wildfire Map — Auto-Update Script
Fetches latest fire data from NIFC public API and updates index.html
"""

import urllib.request
import json
import re
import os
import datetime
import glob
import sys

# ─────────────────────────────────────────────
# FIND THE HTML FILE (handles different filenames)
# ─────────────────────────────────────────────

def find_html_file():
    """Find the map HTML file — tries common names."""
    candidates = [
        "index.html",
        "awayday_colorado_wildfire_map.html",
        "wildfire_map.html",
        "map.html",
    ]
    # Also search for any .html file in the root
    all_html = glob.glob("*.html")
    
    for name in candidates:
        if os.path.exists(name):
            print(f"  Found HTML file: {name}")
            return name
    
    if all_html:
        print(f"  Found HTML file: {all_html[0]}")
        return all_html[0]
    
    print("  ERROR: No HTML file found in repository root.")
    print(f"  Files in current directory: {os.listdir('.')}")
    return None

# ─────────────────────────────────────────────
# FIRE NAME MAPPING
# ─────────────────────────────────────────────

FIRE_NAME_MAP = {
    "Fishhook":     "Fishhook Fire",
    "Green Ridge":  "Green Ridge Fire",
    "Gold Mountain":"Gold Mountain Fire",
    "Ferris":       "Ferris Fire",
    "Aspen Acres":  "Aspen Acres Fire",
    "Willow":       "Willow Fire",
    "Snyder":       "Snyder Fire",
    "Big Sheep":    "Big Sheep Fire",
}

# ─────────────────────────────────────────────
# FETCH LIVE FIRE DATA FROM NIFC
# ─────────────────────────────────────────────

def fetch_nifc_fires():
    """Fetch active Colorado incidents from NIFC public ArcGIS API."""
    url = (
        "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/"
        "Active_Fires/FeatureServer/0/query"
        "?where=POOState%3D'US-CO'"
        "&outFields=IncidentName,DailyAcres,PercentContained,ModifiedOnDateTime_dt"
        "&f=json"
        "&resultRecordCount=50"
    )
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "awayday-fire-tracker/1.0"}
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())

        fires = []
        for feature in data.get("features", []):
            attrs = feature.get("attributes", {})
            name     = (attrs.get("IncidentName") or "").strip()
            acres    = int(attrs.get("DailyAcres") or 0)
            contained= int(attrs.get("PercentContained") or 0)
            modified = attrs.get("ModifiedOnDateTime_dt", 0)

            if modified:
                dt = datetime.datetime.utcfromtimestamp(modified / 1000)
                updated = dt.strftime("%b %d %H:%M UTC")
            else:
                updated = "Unknown"

            if name:
                fires.append({"name": name, "acres": acres,
                               "contained": contained, "updated": updated})

        print(f"  NIFC returned {len(fires)} Colorado incident(s)")
        for f in fires:
            print(f"    - {f['name']}: {f['acres']:,} ac / {f['contained']}%")
        return fires

    except Exception as e:
        print(f"  WARNING: NIFC fetch failed ({e}) — skipping fire data update")
        return []

# ─────────────────────────────────────────────
# MATCH + UPDATE HTML
# ─────────────────────────────────────────────

def match_and_update(html, nifc_fires):
    """Match NIFC fires to our map and update key figures."""
    changes = 0
    for nifc in nifc_fires:
        name_upper = nifc["name"].upper()
        for key, internal in FIRE_NAME_MAP.items():
            if key.upper() in name_upper:
                acres     = f"{nifc['acres']:,}"
                contained = str(nifc["contained"])
                short     = internal.replace(" Fire", "")

                # 1. Update containment bar width
                pattern = (
                    r'(<strong>' + re.escape(short) + r'</strong>'
                    r'.*?<div class="cfill[^"]*" style="width:)\d+(%">)'
                )
                new_html, n = re.subn(
                    pattern, r'\g<1>' + contained + r'\2',
                    html, flags=re.DOTALL
                )
                if n:
                    html = new_html
                    changes += 1

                # 2. Update acreage
                pattern2 = (
                    r'(<strong>' + re.escape(short) + r'</strong>'
                    r'.*?<strong>)[\d,]+( ac</strong>)'
                )
                new_html2, n2 = re.subn(
                    pattern2, r'\g<1>' + acres + r'\2',
                    html, flags=re.DOTALL
                )
                if n2:
                    html = new_html2
                    changes += 1

                # 3. Update stat bar chips  e.g.  98,100 ac · 25%
                pattern3 = (
                    r'(<strong>)[\d,]+ ac &middot; \d+(%</strong>\s*'
                    + re.escape(internal.split()[0]) + r')'
                )
                new_html3, n3 = re.subn(
                    pattern3,
                    r'\g<1>' + acres + ' ac &middot; ' + contained + r'\2',
                    html
                )
                if n3:
                    html = new_html3
                    changes += 1

                if n or n2 or n3:
                    print(f"  Updated {internal}: {acres} ac / {contained}%")
                break

    return html, changes

# ─────────────────────────────────────────────
# UPDATE TIMESTAMP
# ─────────────────────────────────────────────

def update_timestamp(html):
    now      = datetime.datetime.utcnow()
    date_str = now.strftime("%B %d, %Y")

    # Green updated bar
    html = re.sub(
        r'(&#10003; Updated )[A-Za-z]+ \d+, \d{4}',
        r'\g<1>' + date_str,
        html
    )
    # Header meta line
    html = re.sub(
        r'(Updated )[A-Za-z]+ \d+, \d{4}( &nbsp;&middot;&nbsp; Sources)',
        r'\g<1>' + date_str + r'\2',
        html
    )
    # Footer
    html = re.sub(
        r'(Updated )[A-Za-z]+ \d+, \d{4}(</span>)',
        r'\g<1>' + date_str + r'\2',
        html
    )
    print(f"  Timestamp set to: {date_str}")
    return html

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print("=" * 55)
    print("Awayday Wildfire Map — Auto-Updater")
    print(f"Run: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 55)

    # 1. Find HTML file
    html_file = find_html_file()
    if not html_file:
        sys.exit(1)

    with open(html_file, "r", encoding="utf-8") as f:
        html = f.read()
    print(f"  Read {len(html):,} bytes from {html_file}")

    # 2. Fetch NIFC data
    print("\n[1/3] Fetching NIFC fire data...")
    nifc_fires = fetch_nifc_fires()

    # 3. Update HTML
    print("\n[2/3] Applying updates...")
    if nifc_fires:
        html, changes = match_and_update(html, nifc_fires)
        print(f"  {changes} field(s) updated from NIFC data")
    else:
        print("  No NIFC data — skipping fire figures (timestamp still updated)")

    html = update_timestamp(html)

    # 4. Write back
    print(f"\n[3/3] Writing {html_file}...")
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Done — {os.path.getsize(html_file)/1024:.1f} KB written")
    print("\nAuto-update complete.")

if __name__ == "__main__":
    main()

