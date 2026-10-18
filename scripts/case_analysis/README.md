# Big-rain case studies: analysis code

Run in this order, from this folder:
- `run.py all` downloads each event's ERA5 file from the `era5-cases` release, then writes diagnostics and figures to `out/<event>/`.
- `summary.py` writes one row per event (`summary.json`).
- `composite.py` draws the average of the Oct–Dec events at 7, 5, 3 and 1 day before and on the rain day.
- `days_features.py` measures the warning signs on every day (needs `days_YYYY.npz` from the release in `days/`).
- `test_signs.py` tests the signs on every Oct–Dec day (set `THR=150` or `THR=200`).

Paths at the top of `lib.py` point to the session where this was built; change `HIST` (TN SMART history from the
train-data branch) and `LAND` (coastline rings) before running elsewhere.
