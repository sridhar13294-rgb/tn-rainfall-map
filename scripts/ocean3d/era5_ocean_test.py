"""Ocean-only test with real ERA5 forcing (runs on Kaggle: needs internet for the WeatherBench2 ERA5 archive, and
Veros + a GPU for the Veros part):  python era5_ocean_test.py OUT.json [veros] [year]

Period: summer monsoon of YEAR (default 2019): spin-up 15 Mar - 15 May, scored 15 May - 15 Aug (92 days).
Forcing (6-hourly ERA5 at 1.5 degrees, WeatherBench2 240x121 archive): 10 m wind -> stress (forcing.stress, Large & Pond),
  mean surface latent / sensible / net long-wave / net short-wave fluxes (W m-2, downward positive), 6-h precipitation
  and evaporation (= -latent / Lv). Heat flux into the model sea: Q = Q_ERA5 + lam (SST_ERA5 - SST_model), the usual
  flux-forcing correction that stands in for the dependence of the real fluxes on the model's own SST (lam = 30 W m-2
  K-1, and 0 for the column runs as a check).
Models: (1) the columns alone, (2) columns + reduced-gravity layer (rgo.py), both on the 1.5-degree grid 0-30N 40-105E
  (edges walls; scored 3-25N), from WOA23 (ocean_clim.npz, in the job's working directory) shifted to the ERA5 SST of
  15 May; (3) Veros 2-degree global (veros_coupled.VerosOcean), spun up by the same ERA5 forcing from 15 Mar (Veros'
  own start: annual-mean climatology at rest).
Scores: as skill_monsoon.py (pattern correlation, RMS, box means of the SST change 15 May -> 15 Aug, against ERA5)."""
import os, sys, json, time, datetime as dt
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'cyclone', 'mm'))
import currents as cu, ocean as oc, rgo, forcing as fo
from skill_monsoon import scores
ERA = 'gs://weatherbench2/datasets/era5/1959-2023_01_10-6h-240x121_equiangular_with_poles_conservative.zarr'
VARS = dict(u10='10m_u_component_of_wind', v10='10m_v_component_of_wind', slhf='mean_surface_latent_heat_flux',
            sshf='mean_surface_sensible_heat_flux', lw='mean_surface_net_long_wave_radiation_flux',
            sw='mean_surface_net_short_wave_radiation_flux', tp='total_precipitation_6hr', sst='sea_surface_temperature')


def get_era5(t0, t1):
    import xarray as xr
    ds = xr.open_zarr(ERA, storage_options={'token': 'anon'}, chunks=None).sel(time=slice(np.datetime64(t0), np.datetime64(t1)))
    out = {}
    for k, v in VARS.items():
        x = ds[v]; x = x.sortby('latitude').transpose('time', 'longitude', 'latitude'); out[k] = x.values.astype(np.float32); print('era5', k, out[k].shape, flush=True)
    out['lat'] = ds['latitude'].sortby('latitude').values.astype(float); out['lon'] = ds['longitude'].values.astype(float)
    out['times'] = [dt.datetime.utcfromtimestamp(int(t) / 1e9) for t in ds['time'].values.astype('datetime64[ns]').astype(np.int64)]
    return out


def box(F, la0, la1, lo0, lo1):
    J = np.where((F['lat'] >= la0) & (F['lat'] <= la1))[0]; I = np.where((F['lon'] >= lo0) & (F['lon'] <= lo1))[0]
    G = {k: F[k][:, I][:, :, J] for k in VARS}; G['lat'] = F['lat'][J]; G['lon'] = F['lon'][I]; G['times'] = F['times']; return G


def forcing_at(F, n, Ts, lam):
    nz = np.nan_to_num; U, V = nz(F['u10'][n]), nz(F['v10'][n]); tx, ty = fo.stress(U, V)
    qns = nz(F['slhf'][n] + F['sshf'][n] + F['lw'][n]); sw = nz(F['sw'][n])
    sst = F['sst'][n]; qns = qns + np.where(np.isfinite(sst), lam * (nz(sst) - Ts), 0.0)
    emp = -nz(F['slhf'][n]) / 2.5e6 - nz(F['tp'][n]) * 1000.0 / 21600.0
    return tx, ty, qns, sw, emp


def run_columns(G, clim, i0, i1, lam, mode, dt_s=3600.0):
    LO, LA = np.meshgrid(G['lon'], G['lat'], indexing='ij'); sst = G['sst']
    sea = np.isfinite(sst[i0:i1 + 1]).all(0); sst0 = np.where(sea, sst[i0], 0.0)
    st = {k: v.astype(float) for k, v in oc.profile_from_clim(clim, G['times'][i0], LA, LO, sst0, sea).items()}
    g = cu.make_geom(LA, LO, st['dz'], sea, periodic=False); f = g['f']
    if mode == 'rgo': rgg = rgo.make_geom(LA, LO, sea, periodic=False); rg = rgo.init_state(rgg, rgo.d20(st['T'], st['dz']))
    nper = int(round(6 * 3600 / dt_s))
    for n in range(i0, i1):
        for i in range(nper):
            tx, ty, qns, sw, emp = forcing_at(G, n, st['T'][0], lam)
            # ERA5 net short-wave is a 6-h mean: give it the diurnal shape of the sun, normalised over the 6 h
            when = G['times'][n] + dt.timedelta(seconds=(i + 0.5) * dt_s)
            shp = fo.diurnal(LA, LO, when)[0]
            mean6 = np.mean([fo.diurnal(LA, LO, G['times'][n] + dt.timedelta(seconds=(j + 0.5) * dt_s))[0] for j in range(nper)], 0)
            sw = np.where(mean6 > 1e-3, sw * shp / np.maximum(mean6, 1e-3), sw)
            st, _ = oc.step(st, np.where(sea, qns, 0), np.where(sea, sw, 0), tx, ty, f, dt_s, mask=sea, fw=np.where(sea, emp, 0))
            if mode == 'rgo':
                rg = rgo.step(rg, tx, ty, rgg, dt_s); st = cu.step(st, tx, ty, f, g, dt_s, q=rgo.column_transports(rg, rgg, g, tx, ty, f))
    return np.where(sea, st['T'][0] - sst0, 0.0), sea, LA, LO


def run_veros(F, i_spin, i0, i1, lam):
    from veros_coupled import VerosOcean
    LO, LA = np.meshgrid(F['lon'], F['lat'], indexing='ij'); sea = np.isfinite(F['sst'][i0])
    t0 = time.time(); oc_ = VerosOcean(LA, LO, sea, nx=180, ny=80, nz=40, dt=1800.0); info = dict(setup_s=round(time.time() - t0, 1))
    sstm = np.nan_to_num(F['sst'][i_spin]); t0 = time.time(); keep = None
    for n in range(i_spin, i1):
        tx, ty, qns, sw, emp = forcing_at(F, n, sstm, lam)
        sstm, us, vs = oc_.couple(tx, ty, qns, sw, emp, 6 * 3600.0)
        if n + 1 == i0: keep = sstm.copy()
    info['run_s'] = round(time.time() - t0, 1); info['days'] = (i1 - i_spin) / 4.0
    return sstm - keep, info


if __name__ == '__main__':
    out = sys.argv[1]; year = int([a for a in sys.argv[2:] if a.isdigit()][0]) if any(a.isdigit() for a in sys.argv[2:]) else 2019
    t_spin, t0, t1 = dt.datetime(year, 3, 15), dt.datetime(year, 5, 15), dt.datetime(year, 8, 15)
    F = get_era5(t_spin, t1); ix = {t: i for i, t in enumerate(F['times'])}; i_spin, i0, i1 = ix[t_spin], ix[t0], ix[t1]
    clim = dict(np.load('ocean_clim.npz')) if os.path.exists('ocean_clim.npz') else dict(np.load(os.path.join(HERE, 'ocean_clim.npz')))
    G = box(F, 0.0, 30.0, 40.0, 105.0); LO, LA = np.meshgrid(G['lon'], G['lat'], indexing='ij')
    dobs = np.nan_to_num(G['sst'][i1] - G['sst'][i0]); R = dict(year=year, runs={})
    sea0 = np.isfinite(G['sst'][i0:i1 + 1]).all(0); R['era5'] = scores(np.where(sea0, dobs, 0), np.where(sea0, dobs, 0), sea0, LA, LO)
    for mode in ('column', 'rgo'):
        for lam in (30.0, 0.0):
            t = time.time(); dm, sea, LA, LO = run_columns(G, clim, i0, i1, lam, mode)
            k = '%s lam=%g' % (mode, lam); R['runs'][k] = scores(dm, np.where(sea, dobs, 0), sea, LA, LO); R['runs'][k]['cpu_s'] = round(time.time() - t, 1)
            print(k, R['runs'][k], flush=True); json.dump(R, open(out, 'w'), indent=1)
    if 'veros' in sys.argv[2:]:
        try:
            d, info = run_veros(F, i_spin, i0, i1, 30.0)
            J = np.where((F['lat'] >= 0) & (F['lat'] <= 30))[0]; I = np.where((F['lon'] >= 40) & (F['lon'] <= 105))[0]
            dv = np.asarray(d)[I][:, J]; ok = sea0 & np.isfinite(dv)
            R['runs']['veros2deg lam=30'] = dict(scores(np.where(ok, dv, 0), np.where(ok, dobs, 0), ok, LA, LO), **info)
        except Exception as e:
            import traceback; R['runs']['veros2deg lam=30'] = dict(error=traceback.format_exc()[-2000:])
        print('veros', R['runs']['veros2deg lam=30'], flush=True)
    print('era5', R['era5']); json.dump(R, open(out, 'w'), indent=1)
