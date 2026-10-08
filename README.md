# Tamil Nadu Rainfall Grid Map

Live map: https://sridhar13294-rgb.github.io/tn-rainfall-map/

A 0.1° (~11 km) rainfall grid for Tamil Nadu, updated automatically every day.

## How it updates
A GitHub Action (`.github/workflows/daily.yml`) runs at 09:45 and 18:00 IST:
1. Downloads TN SMART's station-wise rainfall page (`scripts/update.py`): each gauge's name, district, latitude/longitude and the day's rainfall.
2. Saves the day to `data/daily/YYYY-MM-DD.json` and gauge positions to `data/stations.json`.
3. Adds the daily rain to the monthly totals from the TN SMART monthly report (`data/baseline.json`, made with `scripts/parse_report.py`).
4. Rebuilds the grid and publishes `site/index.html` to GitHub Pages.

`data/status.json` shows what the last run did. If TN SMART can't be reached, the map is rebuilt from saved data and the error is recorded there.

## Weather forecast page (experimental)
`forecast.html`, rebuilt 3 times a day (07:00, 15:00, 23:00 IST) by `.github/workflows/forecast.yml` running `scripts/forecast.py`:
- 6-hourly and daily rain, max/min temperature and max wind for a 0.25° Tamil Nadu grid, averaged across GFS (NOAA),
  ECMWF IFS and AIFS (ECMWF open data), ICON (DWD) and GEM (ECCC), read directly from the official open-data servers.
- Mean sea-level pressure averaged across the same models (with model spread), and GFS wind flow at 6 heights.
- `data/forecast_status.json` records which model runs were used and any download errors.
Experimental and non-commercial; not an official forecast.

## Fixing a station match
`data/match_report.json` lists how each report station was matched to a TN SMART gauge. To force a match, add
`"District|Station name": "TN SMART id"` (or `null` for no match) to `data/match_overrides.json`.

## New monthly report
`python scripts/parse_report.py REPORT.pdf YYYY-MM-DD` (the date the report is synced till) rewrites `data/baseline.json`.
