# Awayday Colorado Wildfire Map

Live wildfire threat map for Awayday brand locations across Colorado.

## How it works

- **`index.html`** — the shareable map file, hosted via Netlify
- **`update_fire_map.py`** — auto-update script that fetches live fire data
- **`.github/workflows/update_fire_map.yml`** — runs the script every 6 hours automatically

## What auto-updates

Every 6 hours, GitHub Actions:
1. Fetches the latest fire data from the NIFC (National Interagency Fire Center) public API
2. Updates fire acreage, containment percentages, and containment bar widths in the map
3. Updates the timestamp
4. Commits the changes — Netlify detects this and redeploys within seconds

The NASA FIRMS satellite hotspot layer on the map also updates automatically every 3 hours whenever someone opens the file.

## What still needs manual updates

- Evacuation zone details (narrative text)
- New fires that spring up (add to `update_fire_map.py` FIRE_NAME_MAP)
- Threat level assessments for Awayday locations
- Air quality advisories

For significant developments, ask Claude to update the full file and push the new version.

## Triggering a manual update

Go to **Actions → Update Wildfire Map → Run workflow** in GitHub to trigger an immediate update outside the 6-hour schedule.

## Files

| File | Purpose |
|------|---------|
| `index.html` | The wildfire map (auto-updated) |
| `update_fire_map.py` | Python update script |
| `.github/workflows/update_fire_map.yml` | GitHub Actions schedule |

## Data sources

- **NIFC Active Fires API** — fire size and containment (auto)
- **NASA FIRMS VIIRS** — satellite hotspots (auto, on page open)
- **Colorado Sun / CPR News / InciWeb** — narrative details (manual)
