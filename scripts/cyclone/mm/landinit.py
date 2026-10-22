"""Starting land state for the moist model (mm2.Model.init): the soil-moisture bucket and the land temperature from analysed
fields instead of fixed guesses. numpy only (tested by test_land_init.py without JAX).
Field names follow ERA5 (cyc_libm.py; live_GFSM f2 from ours_fetch_m.py):
  volumetric_soil_water_layer_1  m3 m-3, top soil layer (ERA5 / ECMWF 0-7 cm, GFS 0-10 cm)
  soil_temperature_level_1       K, same layer
  skin_temperature               K
Mapping (land nodes only; sea, sea ice and land nodes with no valid value nearby keep the old guesses):
  bucket w  = clip(soil water / POROSITY, 0, 1) x bucket capacity (S['bucket'] m of water -> kg m-2)   [old: 60 % full]
  land tl   = skin temperature where valid, else top-soil temperature                                 [old: lowest model level]"""
import numpy as np
POROSITY = 0.45                                         # volumetric soil water at saturation (m3 m-3): a full bucket
NAMES = dict(soil_vol='volumetric_soil_water_layer_1', soil_t='soil_temperature_level_1', skin_t='skin_temperature')

def land_kwargs(f2, v2):
    """the optional Model.init keywords from one start's surface fields f2 [var, lat, lon] and their names v2 (a name that
    is absent or all-missing is left out, so old files give {} = the old behaviour)."""
    v2 = [str(v) for v in v2]; out = {}
    for k, n in NAMES.items():
        if n in v2:
            a = np.asarray(f2[v2.index(n)], float)
            if np.isfinite(a).any(): out[k] = a
    return out

def to_nodes_valid(N, x):
    """N (source grid -> model nodes, linear interpolation) applied to a field with gaps (NaN over sea, missing points):
    the weighted mean of the valid source points only, so a coastal land node is not lost to a sea neighbour's NaN;
    NaN where no valid point is near."""
    x = np.asarray(x, float); ok = np.isfinite(x)
    a = np.asarray(N(np.where(ok, x, 0.0)), float); c = np.asarray(N(ok.astype(float)), float)
    return np.where(c > 1e-3, a / np.where(c > 1e-3, c, 1.0), np.nan)

def land_start(N, t_low, land, bucket_m, soil_vol=None, soil_t=None, skin_t=None):
    """-> (tl, w) float32 on the model nodes. N: source grid -> nodes; t_low: lowest model-level temperature on the nodes (K);
    land: land mask on the nodes; bucket_m: bucket capacity (m of water). With no fields: exactly the old start
    (tl = t_low, w = 60 % of the bucket)."""
    tl = np.array(t_low, float); w = np.full(tl.shape, 0.6 * bucket_m * 1000.0); land = np.asarray(land, bool)
    if soil_vol is not None:
        v = to_nodes_valid(N, soil_vol); ok = land & np.isfinite(v)
        w = np.where(ok, np.clip(v / POROSITY, 0.0, 1.0) * bucket_m * 1000.0, w)
    for t in (soil_t, skin_t):                                   # skin last: it wins where both are valid
        if t is None: continue
        t = to_nodes_valid(N, t); ok = land & np.isfinite(t) & (t > 180.0) & (t < 350.0)
        tl = np.where(ok, t, tl)
    return tl.astype(np.float32), w.astype(np.float32)
