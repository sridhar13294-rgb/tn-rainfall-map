"""Stage 2: multi-year spin-up of the 2-degree Veros ocean with real ERA5 forcing, then the same monsoon-2019 score as
era5_ocean_test.py (whose Veros run had only 2 months of spin-up: correlation 0.87, RMS 0.84).
Kaggle: VEROS_BACKEND=jax VEROS_DEVICE=gpu VEROS_FLOAT_TYPE=float32 python veros_spin.py OUT.json [START=2017-01-01]
  - forcing: 6-hourly ERA5 (WeatherBench2), fetched one month at a time, lam = 30 W m-2 K-1 flux correction
  - every month: drift check of Veros SST against ERA5 SST (Indian Ocean box 30S-30N 40-110E and the whole sea)
  - at 15 May 2019 the Veros state is saved to /kaggle/working/veros_state_20190515.npz (kept as Kaggle output,
    for later forecast starts), then scored over 15 May - 15 Aug 2019 like the earlier test."""
import os, sys, json, time, traceback, datetime as dt
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'cyclone', 'mm'))
import era5_ocean_test as E
from skill_monsoon import scores

LAM = 30.0; SIX = dt.timedelta(hours=6)


def next_month(t):
    return dt.datetime(t.year + (t.month == 12), t.month % 12 + 1, 1)


def save_state(oc_, path):
    vs = oc_.sim.state.variables; D = {}
    names = list(vs.fields()) if hasattr(vs, 'fields') else ['temp', 'salt', 'u', 'v', 'w', 'psi', 'dpsi', 'tke', 'surface_taux', 'surface_tauy']
    for k in names:
        try:
            a = np.asarray(getattr(vs, k))
            if a.dtype.kind in 'fiub' and a.size > 1: D[k] = a
        except Exception:
            pass
    np.savez_compressed(path, **D); return sorted(D)


def main(out, start):
    from veros_coupled import VerosOcean
    t_spin = dt.datetime.strptime(start, '%Y-%m-%d'); t0, t1 = dt.datetime(2019, 5, 15), dt.datetime(2019, 8, 15)
    R = dict(start=start, months=[]); save = lambda: json.dump(R, open(out, 'w'), indent=1)
    F = E.get_era5(t_spin, t_spin); LO, LA = np.meshgrid(F['lon'], F['lat'], indexing='ij'); sea = np.isfinite(F['sst'][0])
    io = sea & (LA >= -30) & (LA <= 30) & (LO >= 40) & (LO <= 110)
    tt = time.time(); oc_ = VerosOcean(LA, LO, sea, nx=180, ny=80, nz=40, dt=1800.0); R['setup_s'] = round(time.time() - tt, 1)
    sstm = np.nan_to_num(F['sst'][0]); keep = None; t = t_spin; trun = 0.0; tget = 0.0
    while t < t1:
        tn = min(next_month(t), t1); tg = time.time(); F = E.get_era5(t, tn - SIX); tget += time.time() - tg
        tr = time.time()
        for n, when in enumerate(F['times']):
            tx, ty, qns, sw, emp = E.forcing_at(F, n, sstm, LAM)
            sstm, us, vs = oc_.couple(tx, ty, qns, sw, emp, 6 * 3600.0)
            if when + SIX == t0:
                keep = np.asarray(sstm).copy()
                try: R['state_saved'] = save_state(oc_, '/kaggle/working/veros_state_20190515.npz')[:40]
                except Exception: R['state_save_error'] = traceback.format_exc()[-1500:]
        trun += time.time() - tr
        so = F['sst'][-1]; ok = np.isfinite(so) & np.isfinite(sstm); d = np.where(ok, sstm - np.nan_to_num(so), np.nan)
        m = dict(month=t.strftime('%Y-%m'), bias_io=round(float(np.nanmean(d[io & ok])), 3), rms_io=round(float(np.sqrt(np.nanmean(d[io & ok] ** 2))), 3),
                 bias_all=round(float(np.nanmean(d[sea & ok])), 3), rms_all=round(float(np.sqrt(np.nanmean(d[sea & ok] ** 2))), 3),
                 finite=bool(np.isfinite(sstm[sea]).all()))
        R['months'].append(m); R.update(run_s=round(trun), era5_fetch_s=round(tget)); save(); print(m, flush=True)
        if not m['finite']: R['stopped'] = 'non-finite SST'; save(); return
        t = tn
    # score 15 May -> 15 Aug 2019, as era5_ocean_test.py
    Fs = E.get_era5(t0, t0); Fe = E.get_era5(t1 - SIX, t1 - SIX)
    J = np.where((F['lat'] >= 0) & (F['lat'] <= 30))[0]; I = np.where((F['lon'] >= 40) & (F['lon'] <= 105))[0]
    lo, la = F['lon'][I], F['lat'][J]; LOb, LAb = np.meshgrid(lo, la, indexing='ij')
    so0, so1 = Fs['sst'][0][I][:, J], Fe['sst'][0][I][:, J]; sea0 = np.isfinite(so0) & np.isfinite(so1)
    dobs = np.nan_to_num(so1 - so0); dv = (np.asarray(sstm) - keep)[I][:, J]; ok = sea0 & np.isfinite(dv)
    R['score_monsoon2019'] = scores(np.where(ok, dv, 0), np.where(ok, dobs, 0), ok, LAb, LOb)
    R['era5'] = scores(np.where(sea0, dobs, 0), np.where(sea0, dobs, 0), sea0, LAb, LOb)
    R['before_2month_spinup'] = dict(corr=0.871, rms_anom=0.836, somalia=-4.28, oman=-4.48, sl_dome=-0.63, central_bay=-0.98)
    save(); print(R['score_monsoon2019'], flush=True)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '2017-01-01')
