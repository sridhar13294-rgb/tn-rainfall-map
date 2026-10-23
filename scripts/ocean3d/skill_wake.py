"""Ocean-only skill test: SST change in the Bay of Bengal over the ~11 days of a post-monsoon cyclone case, column ocean
with and without currents (currents.py), against ERA5 SST (which follows the OSTIA analysis: it sees cold wakes, though
smoothed and somewhat weakened).

python3 skill_wake.py OUT.json OCEAN_CLIM.npz CASE.npz [CASE.npz ...]

Case files: the project's ERA5 case archives (era5-cases release: nivar_2020.npz ...; 6-hourly, 0.5 degree, 0-40N
50-110E; sst, u10, v10, q925, t925, ttr). Run domain 0-30N, 60-105E (its edges are walls, far from the scored box); scored: the Bay, 5-23N 77-95E. Start profile: WOA23 for the
date shifted to the first ERA5 SST (ocean.profile_from_clim).
Forcing: forcing.py (bulk formulas, the same for every run; cloud c = clip((270 - OLR) / 100, 0, 1)).
Scores (sea points): pattern correlation and RMS difference of (SST end - SST start); mean change over the points that
ERA5 cools by more than 1 K (the wake), and the coolest 2 % of points."""
import os, sys, json, math, datetime as dt, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'cyclone', 'mm'))
import currents as cu, ocean as oc, rgo, forcing as fo
BAY = (5.0, 23.0, 77.0, 95.0)                                                                  # scored box
DOM = (0.0, 30.0, 60.0, 105.0)                                                                 # run domain (edges are walls)


def dec(d, k):
    a = d[k]; v = a.astype(float) * float(d[k + '__scale']) + float(d[k + '__off']); return np.where(a == -32768, np.nan, v)


def run_case(path, clim, use_cur, prm=None, dt_s=1800.0):
    d = np.load(path); la = np.asarray(d['lat'], float); lo = np.asarray(d['lon'], float)
    J = np.where((la >= DOM[0]) & (la <= DOM[1]))[0]; I = np.where((lo >= DOM[2]) & (lo <= DOM[3]))[0]
    cut = lambda A: A[:, J][:, :, I].transpose(0, 2, 1)                                       # -> [t, lon, lat]
    sst = cut(dec(d, 'sst')) + 273.15; u = cut(dec(d, 'u10')); v = cut(dec(d, 'v10'))
    q925 = cut(dec(d, 'q925')) / 1000.0; t925 = cut(dec(d, 't925')); olr = np.abs(cut(dec(d, 'ttr')))
    times = [dt.datetime.strptime(t, '%Y%m%d%H') for t in d['times']]
    lat, lon = la[J], lo[I]; LO, LA = np.meshgrid(lon, lat, indexing='ij')
    sea = np.isfinite(sst).all(0)
    sst0 = np.where(sea, sst[0], 0.0)
    st = {k: v_.astype(float) for k, v_ in oc.profile_from_clim(clim, times[0], LA, LO, sst0, sea).items()}
    g = cu.make_geom(LA, LO, st['dz'], sea, periodic=False); f = g['f']
    if use_cur == 'rgo': rgg = rgo.make_geom(LA, LO, sea, periodic=False); rg = rgo.init_state(rgg, rgo.d20(st['T'], st['dz']))
    nper = int(round((times[1] - times[0]).total_seconds() / dt_s)); z = np.zeros_like(LA)
    for n in range(len(times) - 1):
        for i in range(nper):
            w = (i + 0.5) / nper; lin = lambda A: np.nan_to_num((1 - w) * A[n] + w * A[n + 1])
            U, V = lin(u), lin(v); tx, ty = fo.stress(U, V)
            c = np.clip((270.0 - lin(olr)) / 100.0, 0, 1)
            when = times[n] + dt.timedelta(seconds=(i + 0.5) * dt_s)
            Qns, sw = fo.fluxes(st['T'][0], U, V, lin(q925), lin(t925), c, LA, LO, when)
            Qns, sw = np.where(sea, Qns, 0.0), np.where(sea, sw, 0.0)
            st, _ = oc.step(st, Qns, sw, tx, ty, f, dt_s, mask=sea)
            if use_cur == 'rgo':
                rg = rgo.step(rg, tx, ty, rgg, dt_s, prm=prm)
                st = cu.step(st, tx, ty, f, g, dt_s, q=rgo.column_transports(rg, rgg, g, tx, ty, f, prm=prm))
            elif use_cur: st = cu.step(st, tx, ty, f, g, dt_s, prm=prm)
    dm = np.where(sea, st['T'][0] - sst0, np.nan); do = np.where(sea, sst[-1] - sst[0], np.nan)
    box = (LA >= BAY[0]) & (LA <= BAY[1]) & (LO >= BAY[2]) & (LO <= BAY[3])
    if os.environ.get('WAKE_SAVE'): np.savez_compressed(os.environ['WAKE_SAVE'], dm=dm, do=do, lat=lat, lon=lon)
    return dm, do, sea & box


def scores(dm, do, sea):
    m = sea & np.isfinite(dm) & np.isfinite(do); a, b = dm[m], do[m]
    wk = b < -1.0; c2 = b <= np.percentile(b, 2)
    return dict(corr=round(float(np.corrcoef(a, b)[0, 1]), 3), rms=round(float(np.sqrt(np.mean((a - b) ** 2))), 3),
                mean_model=round(float(a.mean()), 2), mean_era5=round(float(b.mean()), 2),
                wake_model=round(float(a[wk].mean()), 2) if wk.any() else None, wake_era5=round(float(b[wk].mean()), 2) if wk.any() else None,
                coolest2_model=round(float(a[c2].mean()), 2), coolest2_era5=round(float(b[c2].mean()), 2), min_model=round(float(a.min()), 2), min_era5=round(float(b.min()), 2))


if __name__ == '__main__':
    out = sys.argv[1]; clim = dict(np.load(sys.argv[2])); R = {}
    for path in sys.argv[3:]:
        name = os.path.basename(path).replace('.npz', ''); R[name] = {}
        for key, uc, prm in (('column', False, None), ('column+ekman', True, dict(geo=0)), ('column+ekman+geo', True, None), ('column+slab', True, dict(mode='slab', geo=0)), ('column+rgo', 'rgo', None)):
            t0 = time.time(); dm, do, sea = run_case(path, clim, uc, prm); R[name][key] = scores(dm, do, sea)
            R[name][key]['cpu_s'] = round(time.time() - t0, 1); print(name, key, R[name][key], flush=True)
        json.dump(R, open(out, 'w'), indent=1)
    keys = list(next(iter(R.values())).keys())
    R['mean'] = {k: {s: round(float(np.mean([R[c][k][s] for c in R if c != 'mean'])), 3) for s in ('corr', 'rms', 'wake_model', 'coolest2_model', 'coolest2_era5', 'wake_era5')} for k in keys}
    print('mean', json.dumps(R['mean'], indent=1)); json.dump(R, open(out, 'w'), indent=1)
