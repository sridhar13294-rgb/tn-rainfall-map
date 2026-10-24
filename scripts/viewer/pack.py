"""Pack one MEGAM forecast (maps_run.py npz) into compact files for the map viewer.
python pack.py FORECAST_NPZ OUT_DIR
Each field becomes field_<name>.bin: uint8 or uint16, [time, lat, lon] with lat north->south and lon 0..360,
plus meta.json with the grid, times and per-field scaling (value = offset + scale * code)."""
import sys, os, json, datetime as dt, numpy as np
SRC, OUT = sys.argv[1], sys.argv[2]; os.makedirs(OUT, exist_ok=True)
Z = np.load(SRC); lon = Z['lon'].astype(float); lat = Z['lat'].astype(float); hours = Z['hours'].tolist()
init = str(Z['init']); order = np.argsort(-lat)                                                   # north to south
def grid(a): a = np.asarray(a, np.float32); return np.transpose(a, (0, 2, 1))[:, order, :]        # model [t, lon, lat] -> [t, lat, lon]
F = {}
def add(name, arr, lo, hi, bits=8, unit='', label=''):
    arr = np.clip(arr, lo, hi); n = 255 if bits == 8 else 65535; sc = (hi - lo) / n
    code = np.round((arr - lo) / sc).astype(np.uint8 if bits == 8 else np.uint16)
    code.tofile(os.path.join(OUT, f'field_{name}.bin')); F[name] = dict(offset=lo, scale=sc, bits=bits, unit=unit, label=label)
kt = 1 / 0.5144
add('mslp', grid(Z['mslp']), 940, 1060, 16, 'hPa', 'Sea-level pressure')
add('z500', grid(Z['z500']) / 10, 500, 610, 16, 'dam', '500 hPa height')
add('z850', grid(Z['z850']) / 10, 100, 170, 16, 'dam', '850 hPa height')
for lev in ('850', '500', '200'):
    if f'u{lev}' in Z:
        add(f'u{lev}', grid(Z[f'u{lev}']) * kt, -160, 160, 8, 'kt'); add(f'v{lev}', grid(Z[f'v{lev}']) * kt, -160, 160, 8, 'kt')
add('u10', grid(Z['u10']) * kt, -120, 120, 8, 'kt'); add('v10', grid(Z['v10']) * kt, -120, 120, 8, 'kt')
add('t2', grid(Z['t2']) - 273.15, -50, 55, 8, '°C', '2 m temperature')
add('t850', grid(Z['t850']) - 273.15, -40, 40, 8, '°C', '850 hPa temperature')
if 't500' in Z: add('t500', grid(Z['t500']) - 273.15, -50, 5, 8, '°C', '500 hPa temperature')
for lev in ('850', '700', '500'):
    if f'rh{lev}' in Z: add(f'rh{lev}', np.clip(grid(Z[f'rh{lev}']) * 100, 0, 100), 0, 100, 8, '%', f'{lev} hPa relative humidity')
add('tcw', grid(Z['tcw']), 0, 80, 8, 'mm', 'Precipitable water')
rain = grid(Z['rain']); r6 = np.concatenate([np.zeros_like(rain[:1]), np.diff(rain, axis=0)], 0).clip(0)
add('rain6', r6, 0, 255, 16, 'mm', '6-h rain'); add('raintot', rain.clip(0), 0, 2000, 16, 'mm', 'Total rain since start')
r24 = np.stack([rain[i] - rain[max(0, i - 4)] for i in range(len(hours))]).clip(0); add('rain24', r24, 0, 600, 16, 'mm', '24-h rain')
land = np.asarray(Z['land'], np.uint8).T[order, :]; land.tofile(os.path.join(OUT, 'land.bin'))
meta = dict(model='MEGAM', grid='T85 (~140 km)', init=init, hours=hours, nlat=len(lat), nlon=len(lon), lat=[round(x, 4) for x in lat[order]],
            lon0=float(lon[0]), dlon=float(lon[1] - lon[0]), fields=F)
json.dump(meta, open(os.path.join(OUT, 'meta.json'), 'w'))
print('packed', init, len(hours), 'times', sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT)) // 1024, 'KB')
