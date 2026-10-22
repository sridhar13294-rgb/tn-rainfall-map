"""Checks of the starting land state (landinit.py, used by mm2.Model.init) on fake fields; numpy only.
python test_land_init.py   (or pytest)"""
import os, sys, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import landinit as L

LATS = np.arange(-30.0, 30.1, 10.0); LONS = np.arange(0.0, 360.0, 30.0)               # source grid [lat, lon] (7 x 12)
NLA = np.linspace(-30.0, 30.0, 13); NLO = np.arange(7.5, 360.0, 15.0)                # model nodes, twice as fine, off the source points, [lon, lat] as mm2
BUCKET = 0.15                                                                          # mm2 DEFAULTS['bucket'] (m)

def N(a):
    """bilinear source -> nodes (periodic in longitude), like mm2.Model.to_nodes."""
    a = np.asarray(a, float); lo = np.concatenate([LONS, [360.0]]); ext = np.concatenate([a, a[:, :1]], 1)
    rows = np.stack([np.interp(NLO, lo, r) for r in ext])                                # [lat, node lon]
    return np.stack([np.interp(NLA, LATS, rows[:, j]) for j in range(len(NLO))])        # [node lon, node lat]

def fake():
    """land in the east half (lon >= 180) plus a single-point island; sea temperatures irrelevant here."""
    lsm = np.zeros((len(LATS), len(LONS))); lsm[:, LONS >= 180] = 1.0
    tlow = 280.0 + 0.1 * np.arange(len(NLO))[:, None] + 0.0 * NLA[None, :]                # lowest model level (nodes)
    return lsm, tlow, N(lsm) > 0.5

def test_defaults_unchanged():
    lsm, tlow, land = fake()
    tl, w = L.land_start(N, tlow, land, BUCKET)
    assert tl.dtype == np.float32 and w.dtype == np.float32 and tl.shape == tlow.shape == w.shape
    assert np.array_equal(tl, tlow.astype(np.float32))                                   # old: lowest model level
    assert np.allclose(w, 0.6 * BUCKET * 1000)                                          # old: 60 % of the bucket (90 kg m-2)

def test_kwargs_from_files():
    old = ['surface_pressure', 'sea_surface_temperature', 'land_sea_mask', 'geopotential_at_surface']
    f2 = np.random.default_rng(0).random((len(old), len(LATS), len(LONS)))
    assert L.land_kwargs(f2, old) == {}                                                  # old libraries -> old behaviour
    new = old + ['volumetric_soil_water_layer_1', 'soil_temperature_level_1', 'skin_temperature', 'snow_depth']
    f2 = np.concatenate([f2, np.full((4, len(LATS), len(LONS)), 0.3)])
    f2[new.index('skin_temperature')] = np.nan                                           # all missing -> left out
    kw = L.land_kwargs(f2, np.array(new))
    assert sorted(kw) == ['soil_t', 'soil_vol'] and np.allclose(kw['soil_vol'], 0.3)

def test_bucket_mapping():
    lsm, tlow, land = fake(); sea = ~land
    for vol, frac in ((0.225, 0.5), (0.45, 1.0), (0.6, 1.0), (-0.1, 0.0), (0.09, 0.2)):
        f = np.where(lsm > 0.5, vol, np.nan)                                            # soil water over land only (NaN at sea)
        tl, w = L.land_start(N, tlow, land, BUCKET, soil_vol=f)
        assert np.allclose(w[land], frac * BUCKET * 1000, atol=1e-3), (vol, np.unique(w[land]))
        assert np.allclose(w[sea], 0.6 * BUCKET * 1000)                                  # sea / sea ice: unchanged
        assert np.array_equal(tl, tlow.astype(np.float32))                               # no temperature given: unchanged

def test_coast_nodes_use_land_values():
    lsm, tlow, land = fake()
    f = np.where(lsm > 0.5, 0.3, np.nan)
    v = L.to_nodes_valid(N, f)
    coast = land & (np.abs(NLO[:, None] - 180.0) < 16) & np.ones_like(tlow, bool)        # land nodes next to the sea
    assert coast.any() and np.allclose(v[coast], 0.3)                                    # a plain interpolation would give NaN there
    assert np.isnan(np.asarray(N(f))[coast]).any()

def test_temperature_mapping():
    lsm, tlow, land = fake(); sea = ~land
    soil = np.where(lsm > 0.5, 290.0, np.nan); skin = np.where(lsm > 0.5, 300.0, np.nan)
    tl, _ = L.land_start(N, tlow, land, BUCKET, soil_t=soil)
    assert np.allclose(tl[land], 290.0) and np.allclose(tl[sea], tlow[sea])
    tl, _ = L.land_start(N, tlow, land, BUCKET, soil_t=soil, skin_t=skin)
    assert np.allclose(tl[land], 300.0)                                                  # skin wins where both are valid
    skin2 = skin.copy(); skin2[:, LONS >= 270] = np.nan                                  # skin missing over part of the land
    tl, _ = L.land_start(N, tlow, land, BUCKET, soil_t=soil, skin_t=skin2)
    far = land & (NLO[:, None] >= 300) & np.ones_like(tlow, bool)
    near = land & (NLO[:, None] <= 240) & np.ones_like(tlow, bool)
    assert np.allclose(tl[far], 290.0) and np.allclose(tl[near], 300.0)                 # soil fills the gap
    bad = np.where(lsm > 0.5, 0.0, np.nan)                                               # a zero fill value is not a temperature
    tl, _ = L.land_start(N, tlow, land, BUCKET, skin_t=bad)
    assert np.array_equal(tl, tlow.astype(np.float32))

def test_land_only():
    """values present everywhere (ERA5 has soil water ~0 over sea): only land nodes change."""
    lsm, tlow, land = fake(); sea = ~land
    tl, w = L.land_start(N, tlow, land, BUCKET, soil_vol=np.zeros_like(lsm), skin_t=np.full_like(lsm, 250.0))
    assert np.allclose(w[land], 0.0) and np.allclose(w[sea], 90.0)
    assert np.allclose(tl[land], 250.0) and np.allclose(tl[sea], tlow[sea])

if __name__ == '__main__':
    for name, fn in [(k, v) for k, v in list(globals().items()) if k.startswith('test_')]:
        fn(); print(f'{name:<36} ok', flush=True)
