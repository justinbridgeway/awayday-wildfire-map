#!/usr/bin/env python3
"""
Awayday Colorado Wildfire Map — Auto-Update Script
Runs on a schedule via GitHub Actions.
Fetches latest fire data from InciWeb (NIFC) public API,
updates fire sizes, containment and timestamps in index.html,
then commits the changes back to the repo.
"""

import urllib.request
import urllib.error
import json
import re
import os
import datetime

# ─────────────────────────────────────────────
# CONFIGURATION — edit these if needed
# ─────────────────────────────────────────────

HTML_FILE = "index.html"

# Fire names as they appear in InciWeb data → mapped to our internal names
FIRE_NAME_MAP = {
    "Fishhook": "Fishhook Fire",
    "Green Ridge": "Green Ridge Fire",
    "Gold Mountain": "Gold Mountain Fire",
    "Ferris": "Ferris Fire",
    "Aspen Acres": "Aspen Acres Fire",
    "Willow": "Willow Fire",
    "Snyder": "Snyder Fire",
    "Big Sheep": "Big Sheep Fire",
}

# ─────────────────────────────────────────────
# FETCH LIVE FIRE DATA FROM NIFC PUBLIC API
# ─────────────────────────────────────────────

def fetch_nifc_fires():
    """
    Fetch active Colorado incidents from the NIFC (National Interagency
    Fire Center) public ArcGIS REST API. No API key required.
    Returns a list of fire dicts with name, acres, containment, updated.
    """
    # NIFC public ArcGIS endpoint — active incidents layer
    url = (
        "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/"
        "Active_Fires/FeatureServer/0/query"
        "?where=POOState%3D'US-CO'"
        "&outFields=IncidentName,DailyAcres,PercentContained,ModifiedOnDateTime_dt"
        "&f=json"
        "&resultRecordCount=50"
    )

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "awayday-fire-tracker/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())

        fires = []
        for feature in data.get("features", []):
            attrs = feature.get("attributes", {})
            name = attrs.get("IncidentName", "")
            acres = attrs.get("DailyAcres") or 0
            contained = attrs.get("PercentContained") or 0
            modified = attrs.get("ModifiedOnDateTime_dt", 0)

            # Convert epoch ms to readable date
            if modified:
                dt = datetime.datetime.utcfromtimestamp(modified / 1000)
                updated = dt.strftime("%b %d, %Y %H:%M UTC")
            else:
                updated = "Unknown"

            fires.append({
                "name": name.strip(),
                "acres": int(acres),
                "contained": int(contained),
                "updated": updated,
            })

        print(f"  NIFC returned {len(fires)} Colorado incidents")
        return fires

    except Exception as e:
        print(f"  WARNING: NIFC fetch failed: {e}")
        return []


# ─────────────────────────────────────────────
# MATCH NIFC DATA TO OUR KNOWN FIRES
# ─────────────────────────────────────────────

def match_fires(nifc_fires):
    """
    Match NIFC fire records to our internal fire names.
    Returns dict: {internal_name: {acres, contained, updated}}
    """
    matched = {}
    for nifc in nifc_fires:
        nifc_name_upper = nifc["name"].upper()
        for key, internal_name in FIRE_NAME_MAP.items():
            if key.upper() in nifc_name_upper:
                matched[internal_name] = {
                    "acres": nifc["acres"],
                    "contained": nifc["contained"],
                    "updated": nifc["updated"],
                }
                print(f"  Matched: '{nifc['name']}' → {internal_name} | {nifc['acres']:,} acres | {nifc['contained']}% contained")
                break
    return matched


# ─────────────────────────────────────────────
# UPDATE STAT BAR IN HTML
# ─────────────────────────────────────────────

def update_stat_bar(html, fire_data):
    """
    Update the top stat bar chips with latest acres and containment.
    Looks for patterns like: 98,100 ac · 25%  followed by fire name.
    """
    stat_updates = {
        "Aspen Acres": "Aspen Acres",
        "Ferris": "Ferris",
        "Gold Mountain": "Gold Mtn",
        "Willow": "Willow",
        "Snyder": "Snyder",
        "Fishhook": "Fishhook",
        "Green Ridge": "Green Ridge",
    }

    for fire_key, display_name in stat_updates.items():
        for internal_name, info in fire_data.items():
            if fire_key.upper() in internal_name.upper():
                acres_str = f"{info['acres']:,}"
                cont_str = str(info["contained"])
                # Replace pattern: digits,digits ac · digits% followed by the display name
                pattern = r'(<strong>)[^<]*?(</strong>\s*' + re.escape(display_name) + r')'
                replacement = r'\g<1>' + acres_str + ' ac &middot; ' + cont_str + r'%\2'
                html, count = re.subn(pattern, replacement, html)
                if count:
                    print(f"  Stat bar updated for {display_name}: {acres_str} ac / {cont_str}%")
    return html


# ─────────────────────────────────────────────
# UPDATE TABLE CONTAINMENT BARS IN HTML
# ─────────────────────────────────────────────

def update_table_rows(html, fire_data):
    """
    Update the containment bar widths and acreage figures in the fire table.
    """
    for internal_name, info in fire_data.items():
        acres = info["acres"]
        contained = info["contained"]
        acres_str = f"{acres:,}"
        cont_str = str(contained)

        # Update containment bar width: style="width:XX%"
        # We target the cfill div that follows the fire name in the table
        # Strategy: find the fire name cell and update the next cbar width

        # Pattern: <strong>FIRENAME</strong> ... width:OLD%
        short_name = internal_name.replace(" Fire", "")
        pattern = (
            r'(<strong>' + re.escape(short_name) + r'</strong>'
            r'.*?<div class="cfill[^"]*" style="width:)'
            r'\d+'
            r'(%">)'
        )
        replacement = r'\g<1>' + cont_str + r'\2'
        html, count = re.subn(pattern, replacement, html, flags=re.DOTALL)
        if count:
            print(f"  Table containment bar updated for {short_name}: {cont_str}%")

        # Update acreage display: <strong>XX,XXX ac</strong>
        pattern2 = (
            r'(<strong>' + re.escape(short_name) + r'</strong>'
            r'.*?<strong>)'
            r'[\d,]+'
            r'( ac</strong>)'
        )
        replacement2 = r'\g<1>' + acres_str + r'\2'
        html, count2 = re.subn(pattern2, replacement2, html, flags=re.DOTALL)
        if count2:
            print(f"  Table acreage updated for {short_name}: {acres_str} ac")

    return html


# ─────────────────────────────────────────────
# UPDATE TIMESTAMP IN HTML
# ─────────────────────────────────────────────

def update_timestamp(html):
    """Replace the last-updated date string in the HTML."""
    now = datetime.datetime.utcnow()
    date_str = now.strftime("%B %d, %Y at %H:%M UTC")

    # Update the green updated-bar div
    pattern = r'(&#10003; Updated )[\w\s,]+(&mdash;)'
    replacement = r'\g<1>' + now.strftime("%B %d, %Y") + r' \2'
    html, count = re.subn(pattern, replacement, html)
    if count:
        print(f"  Timestamp updated to: {date_str}")

    # Update the footer date
    pattern2 = r'(Updated )[\w\s,]+(\d{4})(</span>)'
    replacement2 = r'\g<1>' + now.strftime("%B %d, %Y") + r'\3'
    html, count2 = re.subn(pattern2, replacement2, html)

    # Update the header meta line
    pattern3 = r'(Updated )\w+ \d+, \d{4}( &nbsp;&middot;&nbsp; Sources)'
    replacement3 = r'\g<1>' + now.strftime("%B %d, %Y") + r'\2'
    html, count3 = re.subn(pattern3, replacement3, html)

    return html


# ─────────────────────────────────────────────
# UPDATE THREAT LEVEL FOR STEAMBOAT
# ─────────────────────────────────────────────

def update_threat_levels(html, fire_data):
    """
    Automatically adjust Steamboat Springs threat level based on
    whether Fishhook/Green Ridge fires are still active.
    """
    fishhook = fire_data.get("Fishhook Fire")
    green_ridge = fire_data.get("Green Ridge Fire")

    # If both new Steamboat fires are gone from NIFC (fully contained/closed),
    # downgrade Steamboat back to low risk
    if not fishhook and not green_ridge:
        print("  INFO: Fishhook and Green Ridge no longer in NIFC data — fires may be contained")
        # We leave the HTML as-is and let the human reviewer decide
        # rather than automatically downgrading (safety-first approach)

    return html


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print("=" * 50)
    print("Awayday Wildfire Map Auto-Updater")
    print(f"Run time: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 50)

    # Read the current HTML file
    if not os.path.exists(HTML_FILE):
        print(f"ERROR: {HTML_FILE} not found. Make sure the script runs from the repo root.")
        return False

    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()
    print(f"  Read {HTML_FILE} ({len(html):,} bytes)")

    # Fetch live fire data
    print("\n[1/4] Fetching live fire data from NIFC...")
    nifc_fires = fetch_nifc_fires()

    # Match to our known fires
    print("\n[2/4] Matching fires to map locations...")
    fire_data = match_fires(nifc_fires)

    if not fire_data:
        print("  WARNING: No fires matched. HTML will not be updated with new fire data.")
        print("  Timestamp will still be updated.")

    # Apply updates
    print("\n[3/4] Updating HTML...")
    if fire_data:
        html = update_stat_bar(html, fire_data)
        html = update_table_rows(html, fire_data)
        html = update_threat_levels(html, fire_data)

    html = update_timestamp(html)

    # Write updated HTML
    print("\n[4/4] Writing updated HTML file...")
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = os.path.getsize(HTML_FILE) / 1024
    print(f"  Wrote {HTML_FILE} ({size_kb:.1f} KB)")
    print("\nUpdate complete.")
    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

