"""Ocean-only skill test of the column ocean with and without currents (currents.py): the summer-monsoon cooling of the
north Indian Ocean.

python3 skill_monsoon.py ERA5_CLIM_DAILY.npz OCEAN_CLIM.npz OUT.json [days]

Start 15 May from the WOA23 May/June profiles (shifted to the ERA5 SST of that day), force with the ERA5 1990-2019
daily-climatology 10 m wind for 92 days (to 15 August) and compare the SST change with the ERA5 climatological change.
Stress and heat flux from forcing.py (bulk formulas: 925 hPa temperature and humidity, cloud from the daily rain,
c = 0.15 + rain/15 mm, stress x1.1 for the day-to-day wind variance a climatological daily mean does not have); the
same formulas for every run, so the differences between runs are what the currents add. A second set of runs has no
surface heat flux at all (only mixing and currents change the SST).
Grid: the ERA5 climatology's 1.5-degree box (0-39N, 51-109.5E); its edges are walls (the 51E edge lies on/near the
Somali coast; the 0N wall stops cross-equator transport, so rows south of 3N are left out of the scores).
Scores (sea points 3-25N): pattern correlation and RMS difference of the SST change; box means for the upwelling
regions (Somalia 5-11N 51-55E, Oman 16-22N 56-60E, south-west India 7-13N 73-77E, Sri Lanka dome 6-10N 82-87E) and the
central Bay (12-18N 85-92E)."""
import os, sys, json, math, datetime as dt, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'cyclone', 'mm'))
import currents as cu, ocean as oc, rgo, forcing as fo

BOX = dict(somalia=(5, 11, 51, 55), oman=(16, 22, 56, 60), sw_india=(7, 13, 73, 77), sl_dome=(6, 10, 82, 87), central_bay=(12, 18, 85, 92))


def run(E, clim, d0, days, lam, use_cur, prm=None, dt_s=3600.0, gust=1.1):
    lat = np.asarray(E['lat'], float); lon = np.asarray(E['lon'], float)
    LO, LA = np.meshgrid(lon, lat, indexing='ij')
    sstE = np.asarray(E['sst'], float)                                                     # [doy, lon, lat] K
    sea = np.isfinite(sstE[d0]) & (sstE[d0] > 270)
    sst0 = np.where(sea, sstE[d0], 0.0)
    st = oc.profile_from_clim(clim, dt.datetime(2001, 1, 1) + dt.timedelta(days=d0), LA, LO, sst0, sea)
    st = {k: v.astype(float) for k, v in st.items()}
    g = cu.make_geom(LA, LO, st['dz'], sea, periodic=False); f = g['f']
    if use_cur == 'rgo': rgg = rgo.make_geom(LA, LO, sea, periodic=False); rg = rgo.init_state(rgg, rgo.d20(st['T'], st['dz']))
    nper = int(86400 / dt_s); z = np.zeros_like(LA); t0 = dt.datetime(2001, 1, 1) + dt.timedelta(days=d0)
    nz = lambda A: np.nan_to_num(np.asarray(A, float))
    for d in range(days):
        a = d0 + d; u, v = nz(E['u10'][a]), nz(E['v10'][a])
        tx, ty = fo.stress(u, v, mult=gust); tgt = nz(sstE[a + 1])
        cl = np.clip(0.15 + nz(E['tp24'][a]) * (1000.0 if np.nanmax(E['tp24'][a]) < 1 else 1.0) / 15.0, 0, 0.95)
        for i in range(nper):
            if lam is None:
                Qns, sw = fo.fluxes(st['T'][0], u, v, nz(E['q925'][a]) / (1000.0 if np.nanmax(E['q925'][a]) > 1 else 1.0), nz(E['t925'][a]), cl, LA, LO,
                                    t0 + dt.timedelta(days=d, seconds=(i + 0.5) * dt_s))
            else: Qns, sw = lam * (tgt - st['T'][0]), z
            Qns, sw = np.where(sea, Qns, 0.0), np.where(sea, sw, 0.0)
            st, _ = oc.step(st, Qns, sw, tx, ty, f, dt_s, mask=sea)
            if use_cur == 'rgo':
                rg = rgo.step(rg, tx, ty, rgg, dt_s, prm=prm)
                st = cu.step(st, tx, ty, f, g, dt_s, q=rgo.column_transports(rg, rgg, g, tx, ty, f, prm=prm))
            elif use_cur: st = cu.step(st, tx, ty, f, g, dt_s, prm=prm)
    return st['T'][0] - st['T'][0] * 0 - sst0, sea, LA, LO, g


def scores(dm, do, sea, LA, LO):
    m = sea & (LA >= 3) & (LA <= 25)
    a, b = dm[m], do[m]
    r = float(np.corrcoef(a, b)[0, 1]); rms = float(np.sqrt(np.mean((a - b) ** 2)))
    out = dict(corr=round(r, 3), rms=round(rms, 3), bias=round(float(np.mean(a - b)), 3))
    for k, (y0, y1, x0, x1) in BOX.items():
        mm = sea & (LA >= y0) & (LA <= y1) & (LO >= x0) & (LO <= x1)
        out[k] = round(float(dm[mm].mean()), 2) if mm.any() else None
    return out


if __name__ == '__main__':
    E = dict(np.load(sys.argv[1])); clim = dict(np.load(sys.argv[2])); out = sys.argv[3]; days = int(sys.argv[4]) if len(sys.argv) > 4 else 92
    d0 = 134                                                                               # 15 May (index = doy - 1)
    sstE = np.asarray(E['sst'], float); dobs = sstE[d0 + days] - sstE[d0]
    R = dict(start='15 May', days=days, runs={})
    lat = np.asarray(E['lat'], float); lon = np.asarray(E['lon'], float); LO, LA = np.meshgrid(lon, lat, indexing='ij')
    sea = np.isfinite(sstE[d0]) & (sstE[d0] > 270)
    R['era5'] = scores(np.where(sea, dobs, 0), np.where(sea, dobs, 0), sea, LA, LO)
    for lam in (None,):
        for name, uc, prm in (('column', False, None), ('column+ekman', True, dict(geo=0)), ('column+ekman+geo', True, None), ('column+rgo', 'rgo', None)):
            t0 = time.time(); dm, sea, LA, LO, g = run(E, clim, d0, days, lam, uc, prm)
            key = '%s %s' % (name, 'bulk flux' if lam is None else 'no flux'); R['runs'][key] = scores(dm, np.where(sea, dobs, 0), sea, LA, LO)
            R['runs'][key]['cpu_s'] = round(time.time() - t0, 1); print(key, R['runs'][key], flush=True)
            np.savez_compressed(os.path.join(os.path.dirname(os.path.abspath(out)), 'monsoon_%s_%s.npz' % (name.replace('+', '_'), 'bulk' if lam is None else 'noflux')), dsst=dm.astype(np.float32), obs=dobs.astype(np.float32), lat=lat, lon=lon)
    print('era5', R['era5']); json.dump(R, open(out, 'w'), indent=1)
