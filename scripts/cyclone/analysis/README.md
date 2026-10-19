# Bay of Bengal cyclone: analogues and our track model

These scripts produced the doc "Next Bay of Bengal cyclone (late Oct 2026): analogues and our track forecast".

Run them from a work folder that has a `data/` folder holding:

- `ibtracs_bob.json` and `steering_era5.json`, made by `scripts/cyclone/cyc_hist.py` (also in `data/cyclone/`)
- `fc_<SOURCE>_<RUN>.npz` forecast files, made by `scripts/cyclone/cyc_fetch.py` (in the `era5-cases` release)

Order:

1. `steer.py`, then `steer_eval.py`: fit the steering model on past storms and test it, leaving out one year at a time. This writes `steer_model_h.pkl` and `steer_multi.json`.
2. `track_all.py`: find and follow the Bay low in every forecast member. This writes `tracks.json`.
3. `run_ours.py`: run our track model from each member's forming point on that member's winds. This writes `ours.json`.
4. `consensus.py`: work out the forming time and place, the landfall shares, the middle track and the strength. This writes `consensus.json`. Run it with `TZ=UTC`.
5. `run_analogs.py`: score every Bay storm since 1980 on timing, forming place, track, strength, MJO, IOD and El Niño. This writes `analogs.json`.
6. `maps.py`: draw `map_ours.png` and `map_analogs.png`.

`cyc.py` holds the shared helpers: the forecast loader, the land mask (`data/cyclone/land.json`; small islands count as sea), the tracker and the landfall check. `analogs.py` holds the scoring. The past MJO, El Niño and IOD values come from `scripts/case_analysis/indices.py`.
