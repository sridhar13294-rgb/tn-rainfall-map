"""Standard weather-centre scores on the 1.5-degree ERA5 grid (121 latitudes -90..90, 240 longitudes 0..358.5), the same
way for our model and for ECMWF, so the numbers compare directly (WMO / WeatherBench2 style).
- RMSE: area-weighted (cos latitude) root-mean-square error against ERA5.
- ACC: anomaly correlation, forecast and truth both minus the ERA5 1990-2019 climate for that day; 1 = perfect,
  0.6 is the usual 'still useful' line for 500 hPa height.
- bias: mean forecast minus truth.
Regions: globe, northern / southern extratropics (20-90), tropics (20S-20N), India (5-35N, 65-100E), Tamil Nadu (8-14N, 76-81E)."""
import numpy as np
LATS = np.linspace(-90, 90, 121); LONS = np.arange(0, 360, 1.5)
LA, LO = np.meshgrid(LATS, LONS, indexing='ij')
REGIONS = {'globe': np.ones_like(LA, bool), 'n_extratropics': LA >= 20, 's_extratropics': LA <= -20, 'tropics': np.abs(LA) < 20,
           'india': (LA >= 5) & (LA <= 35) & (LO >= 65) & (LO <= 100), 'tamil_nadu': (LA >= 8) & (LA <= 14) & (LO >= 76) & (LO <= 81),
           # Indian rain regions (boxes close to IMD's homogeneous regions) so a rain fix is judged across all India, not only TN
           'india_nw': (LA >= 22) & (LA <= 35) & (LO >= 68) & (LO <= 80), 'india_central': (LA >= 18) & (LA < 26) & (LO > 73) & (LO <= 86),
           'india_ne': (LA >= 22) & (LA <= 29) & (LO >= 88) & (LO <= 97), 'india_south': (LA >= 8) & (LA < 18) & (LO >= 74) & (LO <= 84),
           'west_coast': (LA >= 8) & (LA <= 20) & (LO >= 72) & (LO < 76)}
W = np.cos(np.radians(LA)); W[np.abs(LA) > 89.9] = 0.0
def scores(f, o, c=None):
    """f, o (and climate c): [121, 240] arrays. Returns {region: {rmse, bias, acc}}."""
    out = {}
    for name, m in REGIONS.items():
        w = W * m * np.isfinite(f) * np.isfinite(o); sw = w.sum()
        if sw <= 0: continue
        d = np.nan_to_num(f - o); r = dict(rmse=float(np.sqrt((w * d ** 2).sum() / sw)), bias=float((w * d).sum() / sw))
        if c is not None:
            fa = np.nan_to_num(f - c); oa = np.nan_to_num(o - c); fa = fa - (w * fa).sum() / sw; oa = oa - (w * oa).sum() / sw
            den = np.sqrt((w * fa ** 2).sum() * (w * oa ** 2).sum()); r['acc'] = float((w * fa * oa).sum() / den) if den > 0 else None
        out[name] = r
    return out
def to_grid(field, lon, lat):
    """model field [lon, lat] on its own grid -> [121, 240] ERA5 1.5-degree grid (bilinear, periodic in longitude)."""
    from scipy.interpolate import RegularGridInterpolator as RGI
    la = np.asarray(lat); lo = np.asarray(lon); F = np.asarray(field, float).T                   # [lat, lon]
    if la[0] > la[-1]: la = la[::-1]; F = F[::-1]
    lo2 = np.concatenate([lo[-1:] - 360, lo, lo[:1] + 360]); F2 = np.concatenate([F[:, -1:], F, F[:, :1]], 1)
    la2 = np.concatenate([[-90.0], la, [90.0]]); F2 = np.concatenate([F2[:1], F2, F2[-1:]], 0)
    return RGI((la2, lo2), F2, bounds_error=False, fill_value=None)(np.stack([LA.ravel(), LO.ravel()], -1)).reshape(LA.shape)
