"""Hour-0 surface-pressure split over the tropical ocean (10 Nov, P5). Over the sea ERA5 terrain = 0, so model surface
pressure can be compared with ERA5 surface pressure directly (no sea-level reduction involved). Steps:
(a) init: model ps right after M.init (vertical interpolation of ERA5 pressure-level fields to model sigma levels)
(b) DFI: model ps after M.dfi (as in every forecast). Also the NE-Bay box (land) for (a)/(b) in MSLP terms via run_wx hour 0.
python h0_split.py LIB GRID [N]"""
import sys, os, datetime as dt, numpy as np, jax.numpy as jnp
sys.path.insert(0, '.'); import mm2, landinit
LIB, GR = sys.argv[1], sys.argv[2]; N = int(sys.argv[3]) if len(sys.argv) > 3 else 12
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
la = np.asarray(Z['lats'], float); lo = np.asarray(Z['lons'], float)
starts = [k for k, t in enumerate(TT) if t[5:7] in ('10', '11') and t.endswith('T00')][:N]
M = mm2.Model(GR, 32, None, {'rad': 'radcloud', 'rad_every': 2, 'cmt_mf': 1, 'rd_si': 1})
def g(F):
    F = np.asarray(F); mla, mlo = np.asarray(M.lat), np.asarray(M.lon)
    ii = np.abs(mla[None, :] - la[:, None]).argmin(1); jj = np.abs(mlo[None, :] - lo[:, None]).argmin(1)
    return F[np.ix_(jj, ii)].T
lsm_all = Z['f2'][0][V2.index('land_sea_mask')]
ocean = (lsm_all < 0.01) & ((la >= 3) & (la <= 15))[:, None] & ((lo >= 60) & (lo <= 100))[None, :]
gocean = (lsm_all < 0.01) & ((la >= -30) & (la <= 30))[:, None]
R = []
for k in starts:
    t0 = dt.datetime.strptime(TT[k], '%Y-%m-%dT%H'); f2 = Z['f2'][k]; f3 = {v: np.array(Z['f3'][k, V3.index(v)]) for v in V3}
    era = f2[V2.index('surface_pressure')] / 100.0
    st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / 9.80616,
                    f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
    M.build(t0); hor = M.coords.horizontal
    ps = lambda s: g(np.asarray(jnp.exp(hor.to_nodal(s.log_surface_pressure))[0]) / M.PA) / 100.0
    a = ps(st) - era; st2 = M.dfi(st); b = ps(st2) - era
    R.append([np.nanmean(a[ocean]), np.nanmean(b[ocean]), np.nanmean(a[gocean]), np.nanmean(b[gocean])])
    print(TT[k], 'ocean 3-15N 60-100E: init %+.2f after DFI %+.2f | tropical ocean 30S-30N: init %+.2f after DFI %+.2f hPa' % tuple(R[-1]), flush=True)
m = np.mean(R, 0); print('MEAN %d starts %s: ocean 3-15N 60-100E init %+.2f -> DFI %+.2f | tropical ocean init %+.2f -> DFI %+.2f hPa' % (len(R), GR, *m))
