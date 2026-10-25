"""One forecast saved for the MEGAM map viewer: every 6 h to 10 days, whole globe, on the model grid.
python maps_run.py LIBM_WX_NPZ START(YYYY-MM-DDTHH or 'near:YYYY-MM-DD') OUT_NPZ [HOURS] [SETTINGS_JSON]"""
import sys, os, json, time, datetime as dt, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import mm2, landinit
LIB, START, OUT = sys.argv[1], sys.argv[2], sys.argv[3]; HOURS = int(sys.argv[4]) if len(sys.argv) > 4 else 240
SET = json.loads(sys.argv[5]) if len(sys.argv) > 5 else {}
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
if START.startswith('near:'):                                                                    # the last start on or before that day
    want = dt.datetime.strptime(START[5:], '%Y-%m-%d'); START = max([t for t in TT if dt.datetime.strptime(t, '%Y-%m-%dT%H') <= want] or TT[:1])
print('start', START, 'available', TT[:3], '...', flush=True)
t0 = dt.datetime.strptime(START, '%Y-%m-%dT%H'); k = TT.index(START); f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}
M = mm2.Model('T85', 32, None, dict(SET, map_out=True, map_snd=True)); t = time.time()
st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], Z['f2'][k, V2.index('surface_pressure')], Z['f2'][k, V2.index('geopotential_at_surface')] / 9.80616,
                Z['f2'][k, V2.index('sea_surface_temperature')], Z['f2'][k, V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(Z['f2'][k], V2))
M.build(t0); st = M.dfi(st); out = M.run_wx(st, cr, HOURS, 6)
print('ran', round(time.time() - t), 's; fields', sorted(out), flush=True)
if not np.isfinite(out['mslp']).all(): raise SystemExit('model blew up')
BOX = (40.0, 120.0, -20.0, 40.0)                                                                 # soundings kept for this lon/lat box
ix = np.where((M.lon >= BOX[0]) & (M.lon <= BOX[1]))[0]; iy = np.where((M.lat >= BOX[2]) & (M.lat <= BOX[3]))[0]
save = {kk: np.asarray(v, np.float32).astype(np.float16) for kk, v in out.items() if kk != 't2_old' and not kk.startswith('snd_')}
for kk, v in out.items():
    if kk.startswith('snd_'): save[kk] = np.asarray(v, np.float32)[:, ix][:, :, iy].astype(np.float16)
save['snd_lon'] = np.asarray(M.lon[ix], np.float32); save['snd_lat'] = np.asarray(M.lat[iy], np.float32)
save['mslp'] = (np.asarray(out['mslp']) / 100.0).astype(np.float32)                               # hPa, kept in float32 for isobars
np.savez_compressed(OUT, lon=np.asarray(M.lon, np.float32), lat=np.asarray(M.lat, np.float32), land=np.asarray(M.land, np.uint8),
                    init=START, hours=np.arange(0, HOURS + 1, 6), **save)
print('saved', OUT, os.path.getsize(OUT) // 1024, 'KB', flush=True)
