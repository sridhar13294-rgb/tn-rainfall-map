"""Checks of consensus.py on synthetic centres (numpy only, a few seconds):  python test_consensus.py   (or pytest)
Truth = smooth global fields on the live_GFSM grid (1.5 deg, 13 levels) with a 4 km plateau near 32N 88E; each centre = truth +
independent noise of a typical analysis size; then gross errors of the kinds a fetch can produce are planted and must be caught."""
import os, sys, tempfile, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import consensus as CS
LATS = np.arange(-90, 90.1, 1.5); LONS = np.arange(0, 360, 1.5)
LEVS = [50, 100, 150, 200, 250, 300, 400, 500, 600, 700, 850, 925, 1000]
G = CS.G; SIG = dict(temperature=0.5, specific_humidity=3e-4, u_component_of_wind=1.0, v_component_of_wind=1.0, geopotential=30.0)

def truth():
    LA, LO = np.meshgrid(np.radians(LATS), np.radians(LONS), indexing='ij'); c = np.cos(LA)
    zs = 4000.0 * G * np.exp(-((np.degrees(LA) - 32) ** 2 / 40 + (np.degrees(LO) - 88) ** 2 / 120))      # plateau (m2/s2)
    lsm = (zs > 50 * G).astype(float); lsm[(np.abs(np.degrees(LA) - 20) < 8) & (np.abs(np.degrees(LO) - 78) < 5)] = 1.0
    f3 = np.zeros((5, 13) + LA.shape)
    for k, p in enumerate(LEVS):
        s = p / 1000.0
        f3[0, k] = 288.0 - 0.0065 * min(CS.std_z(p), 11000) + 25 * (c - 0.7) + 2 * np.sin(3 * LO) * c
        f3[1, k] = 0.018 * s ** 3 * c ** 2 + 1e-6
        f3[2, k] = 25 * np.sin(2 * LA) * (1.2 - s) + 5 * np.cos(2 * LO) * c
        f3[3, k] = 6 * np.sin(2 * LO) * c * (1.2 - s)
        f3[4, k] = G * (CS.std_z(p) + 150 * (c - 0.7) + 40 * np.sin(2 * LO) * c)
    ps = 101300.0 * np.exp(-zs / (CS.RD * 280.0)) + 300 * np.sin(2 * LO) * c
    sst = np.where(lsm > 0.5, np.nan, 300.0 - 30 * np.sin(LA) ** 2)
    return dict(f3=f3, surface_pressure=ps, sea_surface_temperature=sst, land_sea_mask=lsm, geopotential_at_surface=zs)

def centre(T, seed, name, scale=1.0, f2=True):
    r = np.random.default_rng(seed); f3 = T['f3'].copy(); dps = 80 * scale * r.standard_normal(LATS.shape + LONS.shape)
    for i, v in enumerate(CS.V3): f3[i] += scale * SIG[v] * r.standard_normal(f3[i].shape)
    f3[4] += CS.RD * T['f3'][0] * (dps / T['surface_pressure'])[None]                          # geopotential consistent with its ps
    f3[1] = np.maximum(f3[1], 0)
    d = dict(f3=f3, v3=list(CS.V3), levs=list(LEVS), lats=LATS, lons=LONS, source=name, surface_pressure=T['surface_pressure'] + dps)
    if f2:
        d.update(sea_surface_temperature=T['sea_surface_temperature'] + 0.3 * r.standard_normal(LATS.shape + LONS.shape),
                 land_sea_mask=T['land_sea_mask'], geopotential_at_surface=T['geopotential_at_surface'])
    return d

def four(T):
    return {'GFSM': centre(T, 1, 'GFSM'), 'ECM': centre(T, 2, 'ECM', 0.7, f2=False), 'ICON': centre(T, 3, 'ICON'), 'CMC': centre(T, 4, 'CMC', 1.2)}

def rms(a, m=None):
    a = a if m is None else a[m]; return float(np.sqrt(np.nanmean(a ** 2)))

def bad(CN, kinds=('outlier', 'bounds', 'nan')): return [d for d in CN['dropped'] if d[3] in kinds]

def test_clean():
    T = truth(); C = four(T); CN = CS.consensus(C)
    assert not bad(CN), bad(CN)
    assert CN['used'] == ['GFSM', 'ECM', 'ICON', 'CMC'] and CN['holes'] == 0
    for i, v in enumerate(CS.V3):
        e = rms(CN['f3'][v] - T['f3'][i]); single = min(rms(C[n]['f3'][i] - T['f3'][i]) for n in C)
        assert e < single, (v, e, single)                                                     # the mean beats every single centre
        s = sum(CN['diffs'][n][v] for n in CN['diffs']); assert np.abs(s).max() < 1e-3 * max(SIG[v], 1e-3) * 50, v   # equal weights: diffs sum to 0
    zs = [z for z in CN['z'].values()]; assert max(zs) < 2.0, max(zs)                        # honest centres score ~1
    row = next(r for r in CN['report']['rows'] if r['var'] == 'temperature' and r['lev'] == 500)
    assert 0.3 < row['spread'] < 0.9 and row['n'] == 4, row
    ps = CN['f2']['surface_pressure']; assert rms(ps - T['surface_pressure']) < 80, rms(ps - T['surface_pressure'])
    assert CN['f2']['land_sea_mask'] is C['GFSM']['land_sea_mask']
    sea = np.isfinite(T['sea_surface_temperature']); assert np.isfinite(CN['f2']['sea_surface_temperature'][sea]).all()
    return CN

def test_gross_errors():
    T = truth(); C = four(T); iT, iQ, iU, iZ = 0, 1, 2, 4; k = LEVS.index
    C['ICON']['f3'][iT, k(500)] -= 273.15                                                     # Celsius instead of Kelvin -> bounds
    C['CMC']['f3'][iZ, k(300)] = T['f3'][iZ, k(250)] + 30 * np.random.default_rng(9).standard_normal(LATS.shape + LONS.shape)   # wrong level
    C['ECM']['f3'][iU, k(850)] = C['ECM']['f3'][iU, k(850)][::-1]                              # latitudes flipped
    C['GFSM']['f3'][iQ, k(1000)][:40] = np.nan                                               # a third of the field missing
    C['CMC']['f3'][iT, k(700)] += 2.5                                                        # biased by 5 sigma everywhere
    CN = CS.consensus(C); got = {(d[0], d[1], d[2], d[3]) for d in bad(CN)}
    want = {('ICON', 'temperature', 500, 'bounds'), ('CMC', 'geopotential', 300, 'outlier'), ('ECM', 'u_component_of_wind', 850, 'outlier'),
            ('GFSM', 'specific_humidity', 1000, 'nan'), ('CMC', 'temperature', 700, 'outlier')}
    assert got == want, (got ^ want)
    for (n, v, lev, _) in want:                                                              # dropped fields do not touch the mean
        i = CS.V3.index(v); e = rms(CN['f3'][v][k(lev)] - T['f3'][i, k(lev)])
        assert e < 1.2 * SIG[v], (n, v, lev, e)
        assert np.all(CN['diffs'][n][v][k(lev)] == 0)
    return CN

def test_three_centres_one_bad():
    T = truth(); C = four(T); del C['ICON']
    C['CMC']['f3'][3, LEVS.index(200)] *= -1                                                 # v with the wrong sign
    C['ECM']['f3'][4, LEVS.index(500)] /= G                                                  # height (m) instead of geopotential
    CN = CS.consensus(C)
    got = {(d[0], d[1], d[2]) for d in bad(CN)}
    assert ('CMC', 'v_component_of_wind', 200) in got, got
    assert ('ECM', 'geopotential', 500) in got, got                                          # out of bounds
    assert len(got) == 2, got
    return CN

def test_two_centres():
    T = truth(); C = {'GFSM': centre(T, 1, 'GFSM'), 'ICON': centre(T, 3, 'ICON')}
    C['ICON']['f3'][0, LEVS.index(850)] += 6.0                                               # cannot tell which of two is wrong ...
    C['ICON']['f3'][2, LEVS.index(250)][60:70, 50:60] = 1e20                                 # ... but impossible values are removed
    CN = CS.consensus(C); assert not [d for d in bad(CN) if d[3] == 'outlier']
    assert np.nanmax(CN['f3']['u_component_of_wind'][LEVS.index(250)]) < 150
    assert np.isfinite(CN['f3']['u_component_of_wind']).all()
    return CN

def test_below_ground_and_weights():
    T = truth(); C = four(T); k = LEVS.index(1000); hi = T['geopotential_at_surface'] > 1500 * G
    C['CMC']['f3'][0, k][hi] += 40.0                                                          # wild extrapolation under the plateau only
    CN = CS.consensus(C); assert not bad(CN), bad(CN)
    CW = CS.consensus(four(T), weights={'ECM': 3.0})
    e_eq = rms(CN['f3']['temperature'] - T['f3'][0]); e_w = rms(CW['f3']['temperature'] - T['f3'][0])
    assert e_w < e_eq, (e_w, e_eq)                                                            # ECM is the least noisy centre here
    s = sum(CW['weights'][n] * CW['diffs'][n]['temperature'] for n in CW['diffs']); assert np.abs(s).max() < 1e-3
    return CW

def test_ps_terrain():
    T = truth(); C = four(T); C['ICON']['geopotential_at_surface'] = T['geopotential_at_surface'] + 300 * G   # ICON's mountains higher ...
    C['ICON']['surface_pressure'] = C['ICON']['surface_pressure'] * np.exp(-300 * G / (CS.RD * T['f3'][0, -1]))   # ... and its ps lower
    CN = CS.consensus(C)
    assert rms(CN['ps_diffs']['ICON']) < 150, rms(CN['ps_diffs']['ICON'])                    # compared on the same (GFS) terrain
    assert not [d for d in bad(CN) if d[1] == 'surface_pressure']
    return CN

def test_members():
    T = truth(); CN = CS.consensus(four(T))
    f0, p0 = CS.member_start(CN, 0); assert all(np.array_equal(f0[v], CN['f3'][v]) for v in f0)
    P = np.stack([CS.member_start(CN, k)[0]['temperature'][LEVS.index(500)] - f0['temperature'][LEVS.index(500)] for k in range(1, 41)])
    sp = rms(P); want = np.sqrt(np.mean(sum(CN['diffs'][n]['temperature'][LEVS.index(500)] ** 2 for n in CN['diffs']) / 3))
    assert 0.7 * want < sp < 1.3 * want, (sp, want)                                           # members spread like the centres
    f1, _ = CS.member_start(CN, 1); f1b, _ = CS.member_start(CN, 1); assert np.array_equal(f1['u_component_of_wind'], f1b['u_component_of_wind'])
    assert all((CS.member_start(CN, k, scale=3.0)[0]['specific_humidity'] >= 0).all() for k in (1, 2, 3))
    fc, pc = CS.centre_start(CN, 'ICON', 1.0); C4 = four(T)
    assert np.allclose(fc['temperature'], C4['ICON']['f3'][0], atol=1e-3)                    # a = 1: that centre's own fields
    return CN

def test_point_mask_and_region():
    T = truth(); C = four(T); ia, io = np.argmin(np.abs(LATS - 15)), np.argmin(np.abs(LONS - 88))
    C['GFSM']['f3'][2, LEVS.index(850)][ia, io] += 60.0                                        # one bad point in the Bay
    CN = CS.consensus(C, z_point=15)
    assert any(d[3] == 'points' and d[0] == 'GFSM' and d[2] == 850 for d in CN['dropped'])
    assert abs(CN['f3']['u_component_of_wind'][LEVS.index(850)][ia, io] - T['f3'][2, LEVS.index(850)][ia, io]) < 3
    C2 = four(T); C2['CMC']['f3'][0, LEVS.index(300)][LATS > 45] += 1.0                         # differs only outside 0-30N
    a = next(r for r in CS.consensus(four(T))['report']['rows'] if r['var'] == 'temperature' and r['lev'] == 300)
    b = next(r for r in CS.consensus(C2)['report']['rows'] if r['var'] == 'temperature' and r['lev'] == 300)
    assert abs(a['spread'] - b['spread']) < 1e-6, (a, b)
    return CN

def test_files_roundtrip():
    T = truth(); C = four(T); run = '2026102206'
    with tempfile.TemporaryDirectory() as d:
        for n, x in C.items():
            if n == 'ECM': np.savez_compressed(f'{d}/live_ECM_{run}.npz', f3=x['f3'][None].astype(np.float32), sp=x['surface_pressure'][None].astype(np.float32),
                                               source='2026102200+6h', lats=LATS, lons=LONS, v3=np.array(CS.V3[::-1]), levs=np.array(LEVS))
            else:
                f3 = x['f3'] if n != 'ICON' else x['f3'][:, ::-1]                                # ICON written with levels reversed
                f2 = np.stack([x[v] if not (n == 'CMC' and v == 'sea_surface_temperature') else C['GFSM'][v] for v in CS.V2])   # CMC: GFS sea temperature
                np.savez_compressed(f'{d}/live_{n}_{run}.npz', f3=f3[None].astype(np.float32), f2=f2[None].astype(np.float32),
                                    times=np.array(['2026-10-22T06']), lats=LATS, lons=LONS, v3=np.array(CS.V3), v2=np.array(CS.V2),
                                    levs=np.array(LEVS if n != 'ICON' else LEVS[::-1]),
                                    **({} if n == 'GFSM' else dict(notes=np.array(['sea_surface_temperature from GFS' if n == 'CMC' else 'q from RH (over water)']))))
        # ECM's file above has its variables listed in reverse but its array in V3 order: rewrite it consistently
        np.savez_compressed(f'{d}/live_ECM_{run}.npz', f3=C['ECM']['f3'][::-1][None].astype(np.float32), sp=C['ECM']['surface_pressure'][None].astype(np.float32),
                            source='2026102200+6h', lats=LATS, lons=LONS, v3=np.array(CS.V3[::-1]), levs=np.array(LEVS))
        L = CS.load_centres(d, run); assert list(L) == ['GFSM', 'ECM', 'ICON', 'CMC']
        assert L['CMC']['sea_surface_temperature'] is None and L['CMC']['substituted'] == ['sea_surface_temperature']   # not counted twice
        assert L['ICON']['sea_surface_temperature'] is not None
        assert np.allclose(L['ICON']['f3'], C['ICON']['f3'], atol=1e-3) and np.allclose(L['ECM']['f3'], C['ECM']['f3'], atol=1e-2)
        CN = CS.consensus(L); assert not bad(CN), bad(CN)
        out = CS.save_livem(CN, f'{d}/live_CONS_{run}.npz'); Z = np.load(out); G0 = np.load(f'{d}/live_GFSM_{run}.npz')
        assert set(G0.files) <= set(Z.files) and Z['f3'].shape == G0['f3'].shape and Z['f2'].shape == G0['f2'].shape
        assert str(Z['times'][0]) == '2026-10-22T06' and list(Z['v2']) == list(G0['v2'])
    return CN

if __name__ == '__main__':
    import time
    for name, fn in [(k, v) for k, v in list(globals().items()) if k.startswith('test_')]:
        t = time.time(); CN = fn(); print(f'{name:<32} ok  {time.time() - t:5.1f}s  used {CN["used"]}  not used {[d[:4] for d in bad(CN)]}', flush=True)
    print(); print(CS.report_text(test_clean()['report']))
