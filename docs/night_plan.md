# Night work plan (from 23 Oct 00:30 IST) — hourly work cycle, status to Sridhar every 3 hours

State file (scratchpad, not in repo): /tmp/claude-0/-home-claude/2c3b34a9-cc00-53e0-8864-49737f9cdb93/scratchpad/cycle_state.json
{"last_status_utc": "...", "notes": [...]}. Status due when >= 3 h since last_status_utc.

Rules: decisions on settings are made by the exams (no need to ask). Never change main/website. New convection scheme
(conv='mf') must be FIXED until it works (Sridhar, 23 Oct): never fall back to the old scheme; old = yardstick only.
Commit from the main clone if clean, else the worktree scratchpad/wt-cases. Update the live doc (change log + test table)
when a result changes a decision. Use quick tests ("every": 3) for iteration; full sets to confirm.

Queue, in priority order (tick off in cycle_state notes):
1. tn-wx-diag4: hour-0 z500 vs ERA5 must be < ~15 m. If yes: rerun general exam (wx_base config: base, rad) and the
   ECMWF scores (data/cyclone/wx/hres_2020_scores.json must be non-empty; else fix cyc_wx.py selection). If not: keep
   diagnosing (region/band breakdown is in wx_diag.py).
2. Rerun storm baselines with the terrain fix: base (T85), T170, Arabian Sea, South Indian Ocean (quick: every 2).
3. Convection (mass flux) repair, one change at a time, genesis quick test (libm48, every 3, 28 storms; target >= old scheme's
   23-30% formed and vorticity ~7) then track test:
   a) trigger: parcel temperature/moisture kick from surface fluxes (Bechtold/ECMWF: dT = c*H/(rho cp w*), dq similar);
   b) organised entrainment decreasing with height + turbulent part; detrainment above level of max buoyancy;
   c) closure time scale tau = min(3600, depth / w_up) with resolution scaling;
   d) downdrafts (saturated, evaporatively driven, from level of free sink, mass flux 0.3*Mb);
   e) check heating profile shape (peak 400-500 hPa).
4. Ensemble spread +25% (bred amp 1.0 -> 1.25-1.5, SPPT range), hindens2 quick test; target spread/error ~1, truth in 90% circle ~90%.
5. UK Met Office: build geopotential hydrostatically from T, q, surface pressure and orography; GEOS: use newest run <= start
   (lagged forecast). Then a fetch test (RUN oursm).
6. Wire OI observations (nudge.analyse_consensus) into live2 per docs/obs_assimilation.md section 5 (no live runs now).
