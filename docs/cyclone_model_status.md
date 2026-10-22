# Cyclone model (v2) — status and handoff (22 Oct 2026, 18:30 IST)

Owner: Sridhar (works from a phone; wants plain language, honest pushback, fact-checks). Goal: our own multi-level model as
close to ECMWF as possible; products (website Cyclone tab, rain, strike maps) only AFTER the model is complete. "Go live"
(main/website changes) only when everything is complete and tested on branch `cases`, and only on Sridhar's word.
Claude usage is limited (resets Mon 26 Oct 22:30 IST): no helper agents, few short messages, batch GPU tests.

## Rules
- Branch `cases` only. Commit trailer: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` +
  `Claude-Session: https://claude.ai/code/session_01AXxjaemsi36VrJDzeKZ8zA`. Git identity Claude <noreply@anthropic.com>.
- Secrets live only in GitHub secrets (ECMWF_DS_KEY/CDS_KEY, KAGGLE_USERNAME/KAGGLE_API_TOKEN, KAGGLE2_*, later KAGGLE3/4_*). Never paste.
- Stopped on request: all 6-hourly live ensembles, TN cyclone watch. Website Cyclone tab hidden (main). Only scheduled task kept:
  daily rain skill check 10:30 IST. Don't restart cycles.
- GitHub has 20 job slots; model workflows capped (max-parallel 6, live 11) so the site's jobs run.

## Model: scripts/cyclone/mm/mm2.py (Dinosaur spectral core, JAX)
Switches (Model(grid, 32, dt_min=None -> per-grid max step DT_MAX, set_)):
- conv='bmj' (old adjustment) | 'mf' (new mass-flux: entraining plume, entr x (1.3-RH), CAPE closure, energy/water exact)
- rad='gray' | 'radcloud' (radcloud.py: diagnostic clouds + 4-band LW / 7-term SW; rad_every for hourly refresh) — NOT yet run on GPU
- ocean: pass init(..., ocean=<ocean_clim.npz or ocean_live.npz>, when=start) -> ocean.py 24-level mixed layer (cold wake); else old slab
- SPPT capped/tapered (sppt_on=True to compile it; member settings in carry['prm'], compile once per start: with_params)
- track(), track_from_peak(), track_all() (multi-system + mergers); live2.py scenario counts
- Multi-centre start (not yet wired into live2): scripts/cyclone/centres_m.py (ICON, CMC fetch, inside ours_fetch_m.py "oursm"),
  scripts/cyclone/vitals.py (tcvitals/JTWC), scripts/cyclone/mm/consensus.py (outlier-checked mean + centre differences).
  live2.py integration snippet: see the commit message / agent report (consensus mean = control; members = mean + mix of
  centre differences; vitals for storm insertion; cyclone-mmlive.yml must download live_ICON/live_CMC).

## GPU (Kaggle) jobs: .github/workflows/cyclone-kaggle.yml
Write data/cyclone/KAGGLE: line1 slug, line2 release files (comma), line3 command run in repo/scripts/cyclone/mm, line4
accelerator (NvidiaTeslaT4), line5 account 1-4. Results -> data/cyclone/kaggle/<slug>/ (json + logs, ~at end).
Two GPUs: `bash ../kaggle/par.sh <driver.py> /kaggle/working/<lib> ../../../data/cyclone/kaggle_cfg/<cfg>.json /kaggle/working/<prefix>`.
Account needs phone verification (else no internet). Benchmark (T4): T85 17 s / 5-day member, T170 (~80 km) 2 min, 1.9 GB;
T213 killed (host RAM). Weekly quota 30 GPU-h per account.
Drivers: hind2.py (single runs, variants), hindens2.py (ensembles), genesis2.py (start 48 h before formation; lib libm48_fields.npz),
test_mm2.py (budgets + 48-h variant runs: argv4 'name:conv=mf;rad=radcloud,...', argv5 ocean file), gpu_bench.py.
Config key "ocean": "/kaggle/working/ocean_clim.npz" (add ocean_clim.npz to line 2).

## Running at handoff (check data/cyclone/kaggle/<slug>/)
- tn-mm2-t170 (acct 1): T170 control, 84 storms -> score vs T85 (v2 bogus auto: 149/199/374/408 km at 24-96 h).
- tn-mm2-gen-mf (acct 1): genesis test bmj vs mf (+entr 1e-4, 2.5e-4, slow) — key result for convection.
- tn-mm2-ens-stab (acct 2): 10 members x 84 storms, stability (live 06Z test: 51/51 stable).
- GitHub MM.json gen48_v2 (CPU): genesis bmj variants (rh_deep, tau_deep, ck).
- RUN=ocean fetch: ocean_clim.npz / ocean_live.npz (check data/cyclone/ocean_log.txt; URLs unverified).
Scorers: scratchpad ana_*.py (lost if container restarts) — simple to redo: track error vs `real` at 24/48/72/96 h.

## Next steps (in order)
1. Read results above. Pick conv (mf if it forms depressions closer/more often), grid (T170 if better).
2. GPU check of radcloud (test_mm2 variants) + ocean (needs ocean_clim.npz); fix any JAX issues.
3. Past-storm tests of each switch vs the same baseline; then combined version; tune entr/tau/ck.
4. Ensemble spread (#8) with hindens2; wire consensus + vitals into live2; ECMWF-relative scores (TIGGE: data/cyclone/tigge_tracks.json;
   ECMWF ENS mean 73/85/142/208 km, HRES 92/113/155/175 at 1-4 d on the same storms).
5. Only then: products and go-live request.
Timeline promised: all 11 fixes ~31 Oct - 1 Nov.
