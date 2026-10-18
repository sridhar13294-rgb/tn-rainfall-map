"""Shared helpers for the ERA5 case-study downloads (Copernicus Climate Data Store, same ECMWF account as ECDS)."""
import json, os, time, datetime as dt
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'cases', 'era5'); os.makedirs(OUT, exist_ok=True)
KEY = (os.environ.get('CDS_KEY') or os.environ.get('ECMWF_DS_KEY') or '').strip()
AREA = [40, 50, 0, 110]                     # N, W, S, E: Arabian Sea to the South China Sea, tropics to the westerlies
GRID = [0.5, 0.5]
LEVELS = ['200', '300', '500', '700', '850', '925']
PL_VARS = ['u_component_of_wind', 'v_component_of_wind', 'geopotential', 'specific_humidity', 'temperature',
           'vertical_velocity', 'vorticity', 'divergence', 'relative_humidity']
SL_VARS = ['mean_sea_level_pressure', 'total_column_water_vapour', 'sea_surface_temperature', '10m_u_component_of_wind',
           '10m_v_component_of_wind', 'convective_available_potential_energy', 'top_net_thermal_radiation',
           'vertical_integral_of_eastward_water_vapour_flux', 'vertical_integral_of_northward_water_vapour_flux']
SHORT = {'10u': 'u10', '10v': 'v10', 'p71.162': 'ivtu', 'p72.162': 'ivtv', 'viwve': 'ivtu', 'viwvn': 'ivtv'}
def scale(name, v):
    """Convert ERA5 units to the ones we talk in: hPa, gpm, g/kg, deg C, 1e-5/s, W/m2 outgoing longwave."""
    base = ''.join(c for c in name if not c.isdigit())
    if base == 'z': return v / 9.80665
    if base == 'q': return v * 1000
    if base in ('vo', 'd'): return v * 1e5
    if name == 'msl': return v / 100
    if name == 'sst': return v - 273.15
    if name == 'ttr': return -v / 3600          # hourly accumulation (J/m2) -> mean outgoing longwave (W/m2)
    if name == 'tp': return v * 1000
    return v
def client():
    import cdsapi
    return cdsapi.Client(url='https://cds.climate.copernicus.eu/api', key=KEY, quiet=True, timeout=900, retry_max=30, sleep_max=60)
def month_groups(d0, d1):
    """Split a date range into (year, month, [days]) groups, since CDS requests take a product of year x month x day."""
    g = {}; d = d0
    while d <= d1:
        g.setdefault((d.year, d.month), []).append(d.day); d += dt.timedelta(days=1)
    return [(y, m, ds) for (y, m), ds in sorted(g.items())]
def pack(a):
    """float array -> int16 with per-array scale/offset (NaN kept as -32768): 2 bytes a value, ~0.002% precision."""
    a = np.asarray(a, np.float64); ok = np.isfinite(a)
    if not ok.any(): return np.full(a.shape, -32768, np.int16), 0.0, 1.0
    lo, hi = float(a[ok].min()), float(a[ok].max()); s = (hi - lo) / 65000 or 1.0
    q = np.full(a.shape, -32768, np.int16); q[ok] = np.round((a[ok] - lo) / s - 32500).astype(np.int16)
    return q, lo + 32500 * s, s
def read_grib(fn, fields, keyf):
    import pygrib
    g = pygrib.open(fn); lat = lon = None
    for m in g:
        if lat is None:
            la, lo = m.latlons(); lat, lon = la[:, 0], lo[0, :]
        name = SHORT.get(m.shortName, m.shortName)
        k = name + (str(m.level) if m.typeOfLevel == 'isobaricInhPa' else '')
        v = m.values; v = np.where(np.ma.getmaskarray(v), np.nan, np.ma.getdata(v)).astype(np.float64)
        fields.setdefault(k, {})[keyf(m)] = scale(name, v)
    g.close()
    return lat, lon
