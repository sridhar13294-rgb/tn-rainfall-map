# Observations into the model start (design note, 22 Oct 2026)

Goal: depend less on other centres' analyses by bringing observations in ourselves, in steps:
1. **now**: fetch open observations (`scripts/cyclone/obs_fetch.py`, RUN word `obs`) and correct the 4-centre consensus
   start with an optimal-interpolation (OI) analysis (`scripts/cyclone/mm/nudge.py`); nudge the first forecast hours
   toward observed rain (latent-heat nudging, LHN);
2. **next**: score each centre against the observations (`nudge.centre_fit`) and weight the consensus by it;
3. **later**: cycle our own 51-member ensemble and replace OI by an LETKF (section 6).

Honest limit up front: the four centres have already assimilated nearly all of these same GTS observations (plus
satellite radiances we do not have). With their consensus as the background, OI increments will mostly be small. The
real gains are (a) observations that arrive after the centres' cut-off, (b) Indian data a centre did not get or rejected,
(c) rain and lightning, which no centre's analysis uses this way, and (d) the step to cycling our own forecast, where the
background is ours and the observations do all the correcting.

## 1. Sources (all free; checked 22 Oct 2026)

| Source | What it adds | Access | Latency | Over India (expected per run time) |
|---|---|---|---|---|
| **SYNOP** (land) | surface pressure (-> MSLP the model's way), T, dew point, wind | NWS gateway raw GTS bulletins `https://tgftp.nws.noaa.gov/SL.us008001/DF.an/DC.sflnd/DS.synop/` (files `sn.0000-0300`, new one ~every 5 min, >= 24 h kept). Open | minutes | ~300-500 stations at main hours (IMD network on GTS); global set fetched too |
| **SHIP** | MSLP and wind over the sea | `.../DC.sfmar/DS.ships/`. Open | minutes | ~5-30 in the Bay / Arabian Sea |
| **TEMP** (radiosonde, part A) | T, humidity, wind, height on 1000-100 hPa | `.../DC.vsndn/DS.raobf/`. Open. Fallback for India: Univ. of Wyoming `https://weather.uwyo.edu/wsgi/sounding?datetime=YYYY-MM-DD%20HH:00:00&id=NNNNN&src=UNKNOWN&type=TEXT:LIST` (one request per station) | 1-3 h | ~30-40 stations at 00Z, ~25-35 at 12Z, ~none at 06/18Z |
| **METAR** | pressure (QNH -> station pressure -> MSLP), T, dew point, wind | NOAA AWC data API `https://aviationweather.gov/api/data/metar?bbox=lat0,lon0,lat1,lon1&format=json&hours=..&date=..` (max 400 rows/request, 100 requests/min; tiled). Open | minutes | ~100-130 airports |
| Station positions | lat/lon/height of WMO stations | `https://tgftp.nws.noaa.gov/data/nsd_bbsss.txt` (2016 list; missing new stations are dropped and counted) | - | - |
| **SYNOP fallback** | Indian SYNOPs if the gateway has < 50 | Ogimet `getsynop?begin=..&end=..&state=India` (one request; Ogimet limits queries per IP, so only as fallback) | ~1 h | - |
| **ASCAT-B/C winds** (25 km) | 10-m winds over the sea (cyclone circulation, monsoon flow) | KNMI Data Platform open-data API `https://api.dataplatform.knmi.nl/open-data/v1/datasets/osisaf_ascat_{b,c}_250/versions/nrt/files` with KNMI's published **anonymous key** (valid to 1 Aug 2027, shared quota 50 requests/min). Free registration gives a personal key (secret `KNMI_API_KEY`) | 1-3 h | 2 satellites x 2 passes/day; over India the passes are ~03-05 and ~15-17 UTC, so they fall in the **06Z and 18Z** windows, mostly outside 00Z/12Z |
| HY-2B/C winds | more scatterometer passes (06:00 LT orbit) | **registration needed** (OSI SAF / KNMI FTP `ftppro.knmi.nl`) - not used | 3-10 h | - |
| PO.DAAC (ASCAT, etc.) | same winds, archive | **Earthdata login needed** - not used | - | - |
| **CMORPH real time** (8 km, 30 min) | satellite rain for LHN | NOAA CPC `https://ftp.cpc.ncep.noaa.gov/precip/CMORPH_RT/GLOBE/data/YYYY/YYYYMM/`, grid from `.../GLOBE/CTL/*.ctl`. Open. *Not fully verified*: the data directory was last modified Jun 2026 (could be a re-sync or a stopped feed) - the first run's log will show which | ~2-4 h | all, 60S-60N |
| **PERSIANN-CCS** (0.04 deg) | rain fallback | CHRS UCI `https://persiann.eng.uci.edu/CHRSdata/PERSIANN-CCS/6hrly/rgccs6hYYDDDHH.bin.gz` (int16 big-endian, mm x 100, 3000x9000, 60N-60S) and `.../hrly/`. Open | ~1-2 h | all |
| GPM IMERG Early, GSMaP NRT | better satellite rain | **registration needed** (NASA PPS / Earthdata; JAXA G-Portal) | 4 h / 4 h | - |
| **Lightning** | where deep convection is now (LHN profile choice; rain where satellites miss) | this repo's `lightning-data` branch (from IMD lightning maps, every 15 min): `recent.json` keeps **only 2 h** of strike positions; `hist.jsonl` 3 days of movement vectors (used as a 6-h activity proxy). A 6-h strike total needs `lightning.py` (main) to keep 6 h (`2 * 3600` -> `6 * 3600`) - a main-branch change, Sridhar's call | 15 min | 62-96E, 2S-25N |
| NCEI ISD-lite / IGRA2 | archives for past-case tests (data denial) | open but **delayed** (days); IGRA2 `data-y2d` per-station year files | days | - |

Output `obs_<run>.npz` (uploaded to release `era5-cases`): one row per observed value - `type` (synop, metar, ship, temp,
scat), `sid`, `lat`, `lon` (0-360), `p` (hPa; station pressure for surface reports), `z` (station/level height, m),
`time` (unix s), `var` (mslp, ps [Pa]; t, td [K]; u, v [m/s]; z [m]), `value`, `err` (sigma_o); gridded `rain6` (mm in the
6 h before t0, 0.25 deg, 40S-40N 30-120E), `ltg6` (strike cells), `ltg_act6`; `counts` (JSON). Window t0-6 h to t0+3 h.
Scatterometer cells are averaged to 0.5 deg per pass at fetch time. Log: `data/cyclone/obs_log.txt` (counts per source,
India counts, rain source and hours, lightning maps).

## 2. Observation operator (`nudge.model_equivalents`, numpy or jax.numpy)
- Horizontal: bilinear on the Gaussian or regular grid (`HGrid`; layout `latlon` for pressure-level files, `lonlat` for
  mm2's nodal arrays), periodic in longitude.
- Vertical: linear in log p, from pressure levels or sigma x ps; no extrapolation.
- MSLP = ps exp(g zs / (Rd (T_low + 0.0065 zs/2))) - exactly mm2 `run.post()`. Observed MSLP is made the same way from
  station pressure, station height and observed T (METAR: QNH -> station pressure with the ICAO atmosphere first), so
  both sides use one reduction.
- Surface T/q/wind: lowest model level (sigma 0.99, ~85 m); T + 6.5 K/km x (model level height - station height);
  10-m wind = 0.85 x lowest-level wind.

## 3. OI analysis (`nudge.oi_analysis`, numpy, once per forecast before Model.init)
x_a = x_b + B H^T (H B H^T + R)^-1 (y - H x_b), univariate for T, q, u, v (13 pressure levels) and surface pressure, on
the 1.5-deg consensus grid. Local solves in 10 x 10 deg boxes, observations within box + 2.6 L.

| Setting | Value | Where it comes from |
|---|---|---|
| Horizontal correlation | Gaussian, L = 300 km near the ground (p/ps >= 0.9), 500 km aloft (<= 0.7), linear between; ps 300 km. Non-stationary Paciorek-Schervish form so it stays a valid covariance | the brief; typical of OI-era tropical scales (NMC/ECMWF OI used 300-600 km) |
| Vertical correlation | Gaussian in ln p, length 0.25 (T), 0.20 (q), 0.30 (u, v) (850-700 hPa ~0.75) | typical vertical correlations of forecast errors; to be fitted |
| sigma_b, background = consensus of analyses ('analysis' table) | T 0.9 K (1000) / 0.55 (500) / 0.9 (200) / 1.2 (50); wind 1.5 (1000) / 1.8 (500) / 2.6 (250-200); q 8 % of qsat; ps 0.6 hPa | analysis errors are ~0.6-0.7 of 6-h forecast errors; tropical O-B statistics of the big centres; **first guesses** |
| sigma_b, own 6-h forecast ('forecast6h') | T 1.2/0.8/1.2/1.5 K; wind 2.0/2.6/3.5 m/s; q 12 %; ps 1.0 hPa | same, forecast-error size |
| Flow dependence | sigma_b = max(table, spread among the 4 centres) (`sigma_b_from_spread`) - larger near a cyclone or a trough | consensus.py differences |
| sigma_o | SYNOP MSLP 1.0 hPa (+1 hPa per km of station height), METAR 1.2, ship 1.6; radiosonde T 1.3 (1000) - 0.9 (500) - 1.5 (100) K, wind 2.2-3.2 m/s, humidity 10 % of qsat; scatterometer 1.8 m/s; ship wind 2.6 m/s; plus time error (e.g. 0.5 m/s, 0.3 hPa per hour from t0) | rounded from the NCEP GSI and ECMWF conventional-data error tables (instrument + representativeness); to be tuned |
| Not used by default | land T2m (diurnal/inversion bias vs the 85 m level), land 10-m winds (as ECMWF), ship air T, humidity above 300 hPa, heights (monitored), station pressure when MSLP exists | |
| QC | reject \|O-B\| > 5 sqrt(sigma_o^2 + sigma_b^2) (a wind component takes its partner); stations whose height differs from model terrain > 600 m (T/q/wind) or > 800 m (pressure), stations above 1500 m for pressure; levels below ground; one report per station (nearest t0) | the brief + common practice |
| Thinning | superobs: surface data averaged in 1-deg boxes per type class and variable (error sigma_o^2 (0.5 + 0.5/n)); each radiosonde level kept; scatterometer pre-averaged at 0.5 deg | |
| Output | increments `{temperature, specific_humidity, u_component_of_wind, v_component_of_wind}` [lev, lat, lon] and dps [lat, lon]; `apply_increments` keeps 0 <= q <= qsat | |

Tests (`scripts/cyclone/mm/test_nudge.py`, synthetic truth/background/obs with the OI's own error statistics, 40
radiosondes, 250 SYNOPs, 500 scatterometer and 100 ship winds): within 250 km of a radiosonde the analysis error falls
25 % (T 0.70 -> 0.52 K), 20 % (wind 2.0 -> 1.6 m/s), 37 % (q); over the whole 30S-30N 45-110E box 6-18 %; a +25 K
radiosonde temperature and a +30 hPa pressure are rejected; O-A < O-B for every type. Runs in ~2 s for that region.

Limits of OI here: univariate (no geostrophic/hydrostatic coupling - a pressure increment brings no wind, so the mm2
digital filter (`M.dfi`) must stay on to remove the gravity-wave noise); fixed, isotropic correlations (a front or a
cyclone's structure is not followed, except through the spread-based sigma_b); errors of nearby observations assumed
independent (superobbing compensates); the 1.5-deg grid cannot hold detail finer than ~300 km; and the double counting of
observations the centres already used (keep sigma_b at the 'analysis' size, never smaller).

## 4. Latent-heat nudging (`nudge.lhn_*`; functions only, for the time loop)
Standard LHN (Jones & Macpherson 1997; Stephan et al. 2008):
- model rain >= 0.1 mm/h: latent-heating profile x (alpha - 1), alpha = observed/model rain clipped 0.3-3 (so where the
  model rains and nothing is observed, heating is cut by 70 %);
- model dry, rain observed: default convective profile (`default_heating_profile`: zero below sigma 0.95 and above 0.15,
  peak near 0.5) scaled so the column heating equals L_v x observed rain;
- humidity changed with the temperature to keep relative humidity (`dq = RH dqsat/dT dT`); rates capped at 3e-3 K/s;
- weight 1 for the first 3 h, down to 0 at 6 h (`lhn_weight`);
- observed rain: CMORPH (or PERSIANN-CCS) 6-h total before t0 as a rate (persistence over the first hours); where the
  satellite has nothing, lightning strike cells x a coefficient fitted on the same day where both exist
  (`lightning_rain_coef`, `merge_rain`); `regrid_mean` puts the 0.25-deg rain on the model grid.

## 5. Wiring (for the lead; live2.py and mm2.py are not changed here)
1. Order of jobs: RUN word `obs` (line 2 = run) after `oursm` for the same run, before MMLIVE.
2. `cyclone-mmlive.yml`, download step: `gh release download era5-cases -p obs_$R.npz -D /tmp/w || true`.
3. `live2.py run()`, right after the consensus block (after `if len(CN['used']) < 2: CN = None`):
   ```python
   import nudge as NG
   if CN is not None and C.get('obs', True):
       try:
           CN, OBREP = NG.analyse_consensus(CN, os.path.join(os.path.dirname(os.path.abspath(LIVEM)), f'obs_{t0:%Y%m%d%H}.npz'), t0,
                                            cfg=C.get('obs_cfg'))
       except Exception as e: print('obs analysis not used:', repr(e)[:200], flush=True)
   ```
   `member_start(CN, k)` then perturbs every member around the analysed mean; nothing else changes. Keep `M.dfi(st)`.
   (Without the consensus, the same increments can be added to `f3`/`psk` with `NG.oi_analysis` + `NG.apply_increments`.)
4. LHN in mm2 (needs two small mm2 changes by its owner): (a) `column()` returns the latent-heating profile
   `lh = dTc + LV/CP*(cond - evap)` (K/s) in `diag`; (b) the carry gets `rain_obs` (kg m-2 s-1 on the model grid, from
   `NG.regrid_mean(obs['rain6'], ...) / 21600`, NaN -> 0) and `rain_mean` (updated each step with `NG.running_rain`);
   in `Phys.explicit_terms` add `w = NG.lhn_weight(t_h, xp=jnp)`, `dT, dq = NG.lhn_tendency(lh, rain_mean, rain_obs, T, q,
   p, dsig, ps, sig, xp=jnp)` and `tend['T'] += w*dT; tend['q'] += w*dq`. Test first on past cases with CMORPH for the
   forecast hours (hindcast) - LHN can trigger spurious storms if the rain field is wrong.
5. `NG.centre_fit(CN, obs, t0)` gives each centre's normalised O-B; `consensus(..., weights={c: 1/fit[c]['all']**2})`
   is a cheap next step once a few weeks of scores agree.

## 6. Path to an LETKF with our 51-member ensemble
What it needs:
- **Ensemble background**: our own 6-h forecasts from the previous analysis (cycling 00/06/12/18Z). Start the cycle from
  consensus + centre differences + bred vectors (as live2), spin up ~1-2 weeks.
- **Observation operator**: done (`model_equivalents` runs on mm2's sigma grid, layout `lonlat`, under jax).
- **Localisation**: Gaspari-Cohn, ~500-800 km horizontally (tropics), ~0.5-1 in ln p vertically; R-localisation per grid
  column (each column solves its own 51 x 51 problem).
- **Inflation**: relaxation to prior spread (RTPS, factor ~0.8) or adaptive multiplicative inflation; 51 members under-
  sample errors, and our model's own errors (no radiances; simple physics) must be covered.
- **Satellite gap**: we will not have radiances, so in data-sparse oceans our analysis would drift from the centres'.
  Keep the consensus as a pseudo-observation (error = centre spread, thinned) in the LETKF - the dependence on other
  centres then shrinks to where we have no data of our own.
- **Cost** (Kaggle T4, from the benchmark T85 17 s and T170 2 min per 5-day member): 51 x 6-h forecasts ~45 s (T85) /
  ~5 min (T170); LETKF solve: 32 768 (T85) or 131 072 (T170) columns x (eigendecomposition of 51 x 51 + up to ~1000
  local obs) ~ 1e11-4e11 flops -> under a minute in jax on the GPU (batched `eigh`, ~0.3-1.4 GB); I/O and job start
  (~5-10 min per Kaggle session) dominate. Four cycles a day at T170 ~1 GPU-h/day (~7 of the 30 GPU-h weekly quota);
  at T85 ~2-3 GPU-h/week.
- **Before that**: 2-4 weeks of OI O-B logs to tune sigma_o, sigma_b and length scales (Desroziers diagnostics,
  Hollingsworth-Lonnberg fits) and to bias-correct station types; data-denial tests on past storms with archived
  observations (NCEI ISD surface, IGRA2 sondes; ASCAT via PO.DAAC needs an Earthdata login).
