"""Ocean temperature (and salinity) profiles for the ocean mixed-layer columns of the moist model (scripts/cyclone/mm/ocean.py).
Runs on GitHub Actions (RUN word "ocean"); the sandbox cannot reach NOAA.

1. Climatology: NOAA World Ocean Atlas 2023 (WOA23), 1-degree monthly objectively analysed temperature t_an and salinity
   s_an, 1991-2020 normal (decav91C0; falls back to the all-decade average "decav", then to WOA18). Regridded by cell-
   overlap averaging to the 1.5-degree grid of libm_fields.npz (lat -90..90, lon 0..358.5 step 1.5), cropped to 40.5S-40.5N,
   30E-150E (the Indian Ocean and the western Pacific; model nodes outside get a generic profile), standard depths 0-325 m.
   Output /tmp/cyc_out/ocean_clim.npz: T, S [12 months, depth, lat, lon] (deg C, psu; NaN under the sea floor), depth,
   lat, lon, source.
2. Live (python cyc_ocean.py live, or after the climatology with "ocean"): NOAA RTOFS global 1/12-degree daily nowcast
   (rtofs_glo_3dz_n024_daily_3ztio.nc / 3zsio.nc) from NOMADS or the AWS open-data bucket, today or yesterday, bin-averaged
   onto the same grid and depths. Output /tmp/cyc_out/ocean_live.npz (same keys, one time; plus 'time'). If RTOFS is not
   available nothing is written and the model uses the climatology.
Log: data/cyclone/ocean_log.txt."""
import os, sys, datetime as dt, urllib.request, shutil, numpy as np
import netCDF4

OUT = '/tmp/cyc_out'; TMP = '/tmp/cyc_ocean_dl'; os.makedirs(OUT, exist_ok=True); os.makedirs(TMP, exist_ok=True)
os.makedirs('data/cyclone', exist_ok=True); LOGF = open('data/cyclone/ocean_log.txt', 'a')
def log(*a): print(*a, flush=True); print(*a, file=LOGF, flush=True)
LATS = np.arange(-40.5, 40.51, 1.5); LONS = np.arange(30.0, 150.01, 1.5)              # subset of the libm 1.5-deg grid
DEPTHS = np.array(list(range(0, 101, 5)) + list(range(125, 326, 25)), float)            # WOA standard depths to 325 m
WOA = [('decav91C0', 'https://www.ncei.noaa.gov/data/oceans/woa/WOA23/DATA/{var}/netcdf/decav91C0/1.00/woa23_decav91C0_{v}{m:02d}_01.nc'),
       ('decav91C0', 'https://www.ncei.noaa.gov/thredds-ocean/fileServer/woa23/DATA/{var}/netcdf/decav91C0/1.00/woa23_decav91C0_{v}{m:02d}_01.nc'),
       ('decav91C0', 'https://tds.gdex.ucar.edu/thredds/fileServer/files/d285000/woa23_netcdf/woa23_decav91C0_{v}{m:02d}_01.nc'),
       ('decav', 'https://www.ncei.noaa.gov/data/oceans/woa/WOA23/DATA/{var}/netcdf/decav/1.00/woa23_decav_{v}{m:02d}_01.nc'),
       ('decav', 'https://www.ncei.noaa.gov/thredds-ocean/fileServer/woa23/DATA/{var}/netcdf/decav/1.00/woa23_decav_{v}{m:02d}_01.nc'),
       ('woa18', 'https://www.ncei.noaa.gov/data/oceans/woa/WOA18/DATA/{var}/netcdf/decav/1.00/woa18_decav_{v}{m:02d}_01.nc')]
RTOFS = ['https://nomads.ncep.noaa.gov/pub/data/nccf/com/rtofs/prod/rtofs.{d}/rtofs_glo_3dz_n024_daily_{f}.nc',
         'https://noaa-nws-rtofs-pds.s3.amazonaws.com/rtofs.{d}/rtofs_glo_3dz_n024_daily_{f}.nc',
         'https://nomads.ncep.noaa.gov/pub/data/nccf/com/rtofs/prod/rtofs.{d}/rtofs_glo_3dz_f024_daily_{f}.nc',
         'https://noaa-nws-rtofs-pds.s3.amazonaws.com/rtofs.{d}/rtofs_glo_3dz_f024_daily_{f}.nc']


def fetch(url, path):
    req = urllib.request.Request(url, headers={'User-Agent': 'tn-rainfall-map cyclone study'})
    with urllib.request.urlopen(req, timeout=600) as r, open(path, 'wb') as fo: shutil.copyfileobj(r, fo, 1 << 22)
    return os.path.getsize(path)


def overlap_matrix(tgt, half_t, src, half_s, period=None):
    """weights W[t, s] = length of overlap of target cell [t-half_t, t+half_t] and source cell [s-half_s, s+half_s]."""
    d = tgt[:, None] - src[None, :]
    if period: d = (d + period / 2) % period - period / 2
    return np.clip(np.minimum(d + half_t, half_s) - np.maximum(d - half_t, -half_s), 0, None)


def regrid_woa(A, lat, lon):
    """A [depth, lat, lon] (NaN = no data) -> [depth, LATS, LONS] by overlap averaging of valid cells."""
    Wy = overlap_matrix(LATS, 0.75, lat, 0.5) * np.cos(np.radians(lat))[None]; Wx = overlap_matrix(LONS, 0.75, lon % 360, 0.5, 360.0)
    m = np.isfinite(A); A0 = np.where(m, A, 0.0)
    num = Wy @ A0 @ Wx.T; den = Wy @ m.astype(float) @ Wx.T
    full = Wy.sum(1)[:, None] * Wx.sum(1)[None, :]
    return np.where(den > 0.25 * full[None], num / np.maximum(den, 1e-12), np.nan)


def to_depths(A, z):
    """[nz, ...] on depths z -> DEPTHS (linear; NaN where a depth is below the deepest valid source level)."""
    out = np.full((len(DEPTHS),) + A.shape[1:], np.nan)
    for i, d in enumerate(DEPTHS):
        k = np.searchsorted(z, d)
        if k < len(z) and z[k] == d: out[i] = A[k]; continue
        if k == 0 or k >= len(z): continue
        w = (d - z[k - 1]) / (z[k] - z[k - 1]); out[i] = (1 - w) * A[k - 1] + w * A[k]       # NaN if either is NaN
    return out


def climatology():
    res = {}
    for var, v, key in (('temperature', 't', 'T'), ('salinity', 's', 'S')):
        months = None
        for name, pat in WOA:
            try:
                arr = []
                for m in range(1, 13):
                    url = pat.format(var=var, v=v, m=m); p = os.path.join(TMP, os.path.basename(url))
                    if not os.path.exists(p): log('get', url, fetch(url, p))
                    with netCDF4.Dataset(p) as ds:
                        z = np.asarray(ds['depth'][:], float); nk = int((z <= DEPTHS[-1] + 30).sum())
                        A = np.ma.filled(np.ma.asarray(ds[v + '_an'][0, :nk]).astype(float), np.nan)
                        arr.append(to_depths(regrid_woa(A, np.asarray(ds['lat'][:], float), np.asarray(ds['lon'][:], float)), z[:nk]))
                    os.remove(p)
                months = np.stack(arr); res['src_' + key] = name + ' ' + pat.split('/')[2]; break
            except Exception as e:
                log(var, name, 'failed:', repr(e)[:300])
        if months is None:
            if key == 'T': log('no WOA temperature: nothing written'); return
            continue
        res[key] = months.astype(np.float32); log(var, 'ok', months.shape, 'surface range', np.nanmin(months[:, 0]), np.nanmax(months[:, 0]))
    np.savez_compressed(OUT + '/ocean_clim.npz', T=res['T'], S=res.get('S', np.full_like(res['T'], 35.0)), depth=DEPTHS, lat=LATS, lon=LONS,
                        source=np.array('WOA monthly t_an/s_an: %s / %s' % (res.get('src_T'), res.get('src_S', 'none (35 psu)'))))
    log('saved ocean_clim.npz', os.path.getsize(OUT + '/ocean_clim.npz'))


def rtofs_field(path, want):
    """bin-average an RTOFS 3-D z-level file onto LATS x LONS for each of its depths, then onto DEPTHS."""
    with netCDF4.Dataset(path) as ds:
        names = {n.lower(): n for n in ds.variables}
        vname = next(names[n] for n in names if n.startswith(want))
        la = np.asarray(ds[names['latitude']][:], float); lo = np.asarray(ds[names['longitude']][:], float) % 360
        z = np.asarray(ds[names['depth']][:], float)
        if la.ndim == 1: la, lo = np.meshgrid(la, lo, indexing='ij')
        rows = np.where(((la >= LATS[0] - 1) & (la <= LATS[-1] + 1)).any(1))[0]; r0, r1 = rows.min(), rows.max() + 1
        la, lo = la[r0:r1], lo[r0:r1]
        iy = np.rint((la - LATS[0]) / 1.5).astype(int); ix = np.rint(((lo - LONS[0]) % 360) / 1.5).astype(int)
        ok = (iy >= 0) & (iy < len(LATS)) & (ix >= 0) & (ix < len(LONS)); cell = np.where(ok, iy * len(LONS) + ix, 0)
        kz = np.where(z <= DEPTHS[-1] + 60)[0]; out = np.full((len(kz), len(LATS), len(LONS)), np.nan)
        for j, k in enumerate(kz):
            a = ds[vname][0, k, r0:r1, :]; v = np.ma.filled(np.ma.asarray(a).astype(float), np.nan); m = ok & np.isfinite(v) & (np.abs(v) < 1e3)
            s = np.bincount(cell[m], v[m], len(LATS) * len(LONS)); c = np.bincount(cell[m], None, len(LATS) * len(LONS))
            out[j] = np.where(c > 0, s / np.maximum(c, 1), np.nan).reshape(len(LATS), len(LONS))
        return to_depths(out, z[kz])


def live():
    today = dt.datetime.utcnow().date()
    for back in (0, 1):
        d = (today - dt.timedelta(days=back)).strftime('%Y%m%d'); got = {}
        for f, want, key in (('3ztio', 'temp', 'T'), ('3zsio', 'sal', 'S')):
            for pat in RTOFS:
                url = pat.format(d=d, f=f); p = os.path.join(TMP, os.path.basename(url))
                try:
                    log('get', url, fetch(url, p)); got[key] = rtofs_field(p, want); os.remove(p); break
                except Exception as e:
                    log('  failed:', repr(e)[:200])
                    if os.path.exists(p): os.remove(p)
            if 'T' not in got: break
        if 'T' in got:
            T = got['T'][None].astype(np.float32); S = got.get('S', np.full(got['T'].shape, 35.0))[None].astype(np.float32)
            np.savez_compressed(OUT + '/ocean_live.npz', T=T, S=S, depth=DEPTHS, lat=LATS, lon=LONS, time=np.array(d),
                                source=np.array('RTOFS global nowcast ' + d))
            log('saved ocean_live.npz', d, 'surface range', np.nanmin(T[0, 0]), np.nanmax(T[0, 0])); return
    log('RTOFS not available: the model falls back to the climatology')


if __name__ == '__main__':
    log('cyc_ocean', dt.datetime.utcnow().isoformat(timespec='minutes'), sys.argv[1:])
    if 'live' not in sys.argv[1:]: climatology()
    if 'clim' not in sys.argv[1:]: live()
