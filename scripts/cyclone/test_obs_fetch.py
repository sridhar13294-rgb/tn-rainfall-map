"""Offline tests for obs_fetch.py decoders (no network): SYNOP (FM-12), SHIP (FM-13) and TEMP part A (FM-35) bulletins in
the NWS gateway layout, the station list, directory listings, the CMORPH control file, regridding, the lightning
reader (reads this repository's lightning-data branch with git when it can), and records -> npz -> nudge OI.
python scripts/cyclone/test_obs_fetch.py"""
import os, sys, io, math, json, datetime as dt, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'mm'))
import obs_fetch as F
import nudge as N
UTC = dt.timezone.utc
T0 = dt.datetime(2026, 10, 22, 0, tzinfo=UTC)

NSD = """43;279;VOMM;Chennai / Minambakkam;;India;2;13-00N;080-11E;13-00N;080-11E;16;16;P
43;003;VABB;Mumbai / Santacruz;;India;2;19-07N;072-51E;;;14;;P
42;182;VIDP;New Delhi / Safdarjung;;India;2;28-35N;077-12E;28-35N;077-12E;216;216;P"""

SYNOP = ('\x01\r\r\n123 \r\r\nSMIN10 DEMS 220000\r\r\nAAXX 22001\r\r\n'
         '43279 32965 70510 10282 20241 30089 40108 52010 69901 72582 8552/ 333 20256=\r\r\n'
         '43003 NIL=\r\r\n'
         '42182 32970 00000 10215 29085 39816 40085 52004=\r\r\n\x03')
SHIP = ('\x01\r\r\n124 \r\r\nSMVD01 KWBC 220000\r\r\nBBXX\r\r\n'
        'WDE123 22004 99135 10850 41598 61812 10275 20250 40080 52005 22200 00280=\r\r\n\x03')
TEMP = ('\x01\r\r\n125 \r\r\nUSIN01 DEMS 220000\r\r\n'
        'TTAA 72001 43279 99008 26857 25010 00106 26458 26012 92796 22656 27015 85503 19656 28518 70142 08456 29020 '
        '50590 05960 30025 40762 16760 30530 30970 32560 31035 25092 41959 30540 20237 52358 31045 15421 66158 30050 '
        '10662 75756 27615 88115 77158 30045=\r\r\n\x03')

def stations():
    S = {}
    for line in NSD.splitlines():
        f = line.split(';'); num = lambda x: float(x) if x.strip() else None
        S[f[0] + f[1]] = dict(lat=F.dms(f[7]), lon=F.dms(f[8]), elev=num(f[11]), ualat=F.dms(f[9]), ualon=F.dms(f[10]), uaelev=num(f[12]), country=f[5], name=f[3])
    return S

def get(R, sid, var, p=None):
    v = [r for r in R.r if r[1] == sid and r[7] == var and ((p is None and r[0] != 'temp') or (p is not None and r[0] == 'temp' and r[4] == p))]
    assert len(v) == 1, (sid, var, p, v); return v[0]

def test_decoders():
    S = stations(); assert abs(S['43279']['lat'] - 13.0) < 1e-9 and abs(S['43279']['lon'] - (80 + 11 / 60)) < 1e-9
    R = F.Recs(); st = {}
    for raw in (SYNOP, SHIP, TEMP):
        for tt, cccc, yyg, text in F.bulletins(raw.encode('latin-1')):
            if tt[:2] == 'SM' and 'BBXX' not in text: F.decode_synops(text, S, T0, R, st)
            elif 'BBXX' in text: F.decode_ships(text, T0, R, st)
            elif tt[:2] == 'US': F.decode_temps(text, S, T0, R, st)
    # SYNOP Chennai: T 28.2 C, Td 24.1 C, station 1008.9 hPa, MSLP reduced the model's way, wind 050 deg 10 m/s
    r = get(R, '43279', 't'); assert abs(r[8] - 301.35) < 1e-9 and r[6] == F.unix(T0)
    assert abs(get(R, '43279', 'td')[8] - 297.25) < 1e-9 and abs(get(R, '43279', 'ps')[8] - 100890.0) < 1e-6
    ms = get(R, '43279', 'mslp')[8] / 100; want = 1008.9 * math.exp(N.G * 16 / (N.RD * (301.35 + 0.0065 * 8)))
    assert abs(ms - want) < 1e-6 and abs(ms - 1010.8) < 0.3, ms                   # close to the reported 4PPPP 1010.8
    u, v = get(R, '43279', 'u')[8], get(R, '43279', 'v')[8]
    assert abs(u + 10 * math.sin(math.radians(50))) < 1e-9 and abs(v + 10 * math.cos(math.radians(50))) < 1e-9
    # Delhi: calm wind, humidity as RH 85 % (29UUU) -> dew point
    assert get(R, '42182', 'u')[8] == 0 and abs(F.td_from_rh(294.65, 0.85) - get(R, '42182', 'td')[8]) < 1e-9
    assert not [x for x in R.r if x[1] == '43003']                               # NIL report
    # SHIP: 13.5N 85.0E, 180 deg 12 kt, MSLP 1008.0
    s = get(R, 'WDE123', 'mslp'); assert abs(s[2] - 13.5) < 1e-6 and abs(s[3] - 85.0) < 1e-6 and abs(s[8] - 100800) < 1e-6
    assert abs(get(R, 'WDE123', 'v')[8] - 12 * F.KT) < 1e-9 and abs(get(R, 'WDE123', 'u')[8]) < 1e-9
    assert abs(get(R, 'WDE123', 't')[8] - 300.65) < 1e-9
    # TEMP: heights, signs, dew points, knots, the hundreds of knots in ddd
    exp = {1000: (106, 26.4, 18.4), 925: (796, 22.6, 16.6), 850: (1503, 19.6, 13.6), 700: (3142, 8.4, 2.4), 500: (5900, -5.9, -15.9),
           400: (7620, -16.7, -26.7), 300: (9700, -32.5, -42.5), 250: (10920, -41.9, None), 200: (12370, -52.3, None),   # no humidity above 300 hPa
           150: (14210, -66.1, None), 100: (16620, -75.7, None)}
    for p, (z, t, td) in exp.items():
        assert abs(get(R, '43279', 'z', p)[8] - z) < 1e-9, (p, get(R, '43279', 'z', p))
        assert abs(get(R, '43279', 't', p)[8] - (t + 273.15)) < 1e-9, p
        if td is not None: assert abs(get(R, '43279', 'td', p)[8] - (td + 273.15)) < 1e-9, p
    u100, v100 = get(R, '43279', 'u', 100)[8], get(R, '43279', 'v', 100)[8]
    assert abs(math.hypot(u100, v100) - 115 * F.KT) < 1e-9                      # 27615 -> 275 deg 115 kt
    assert abs(get(R, '43279', 'u', 850)[8] + 18 * F.KT * math.sin(math.radians(285))) < 1e-9
    print('decoders: SYNOP, SHIP, TEMP part A - ok;', st)
    return R

def test_listing_ctl_grid():
    html = ('<tr><td><a href="sn.0001">sn.0001</a></td><td align="right">22-Oct-2026 15:20  </td><td align="right"> 12K</td></tr>\n'
            '<a href="sn.0002">sn.0002</a>                22-Oct-2026 15:25   14K\n<a href="?C=M;O=A">Last modified</a>\n<a href="2026/">2026/</a>  12-Jun-2026 15:24    -')
    F.http = lambda url, **k: html.encode()
    L = F.listing('x'); d = dict(L)
    assert d['sn.0001'] == dt.datetime(2026, 10, 22, 15, 20, tzinfo=UTC) and d['sn.0002'] == dt.datetime(2026, 10, 22, 15, 25, tzinfo=UTC) and '2026/' in d
    ctl = F.parse_ctl('DSET ^../data/%y4/%y4%m2/CMORPH_V0.x_RT_8km-30min_%y4%m2%d2%h2\nOPTIONS little_endian template\nUNDEF -999.0\n'
                      'XDEF 4948 LINEAR 0.0363783345 0.072756669\nYDEF 1649 LINEAR -59.963614312 0.072771376\nTDEF 99999 LINEAR 00:00z01jan2018 30mn\nVARS 1\n')
    assert ctl['nx'] == 4948 and ctl['ny'] == 1649 and ctl['order'] == '<' and ctl['dt_min'] == 30.0
    la = np.arange(-59.98, 60, 0.04); lo = np.arange(0.02, 360, 0.04); A = np.full((len(la), len(lo)), 2.5)
    G = F.to_grid(A, la, lo); assert G.shape == (320, 360) and np.allclose(G, 2.5)
    print('listing, CMORPH ctl, regridding - ok')

def test_lightning():
    t0 = None
    try:
        import subprocess
        txt = subprocess.run(['git', '-C', F.ROOT, 'show', 'origin/lightning-data:recent.json'], capture_output=True, check=True).stdout
        t_end = max(dt.datetime.fromisoformat(r['t_end']) for r in json.loads(txt)); t0 = t_end + dt.timedelta(minutes=5)
    except Exception as e:
        print('lightning: no local lightning-data branch, skipped', repr(e)[:80]); return
    G, A, hrs, maps, nh = F.lightning(t0)
    print(f'lightning at {t0:%Y-%m-%d %H:%M}: {maps} maps ({hrs:.1f} h), {G.sum():.0f} strike cells (India box {G[np.ix_((F.RLAT >= 6) & (F.RLAT <= 37.5), (F.RLON >= 68) & (F.RLON <= 98))].sum():.0f}), activity records {nh}')
    assert maps >= 1 and G.sum() > 0

def test_end_to_end(R):
    """decoded records -> npz -> nudge.oi_analysis on a smooth background."""
    import tempfile
    A = R.arrays(); fn = os.path.join(tempfile.mkdtemp(), 'obs_test.npz'); np.savez_compressed(fn, **A)
    ob = N.load_obs(fn)
    lats = np.arange(-90, 90.1, 1.5); lons = np.arange(0, 360, 1.5); levs = np.array([50, 100, 150, 200, 250, 300, 400, 500, 600, 700, 850, 925, 1000.])
    Tm = np.interp(np.log(levs), np.log([50, 100, 200, 300, 500, 700, 850, 1000]), [210, 195, 218, 241, 268, 283, 292, 300])
    sh = (len(levs), len(lats), len(lons)); f3 = dict(temperature=Tm[:, None, None] * np.ones(sh), u_component_of_wind=np.zeros(sh), v_component_of_wind=np.zeros(sh),
                                                      specific_humidity=0.7 * N.qsat(Tm[:, None, None] * np.ones(sh), levs[:, None, None] * 100) * (levs[:, None, None] >= 300))
    ps = np.full(sh[1:], 101000.0); zs = np.zeros(sh[1:])
    inc, dps, rep = N.oi_analysis(f3, levs, lats, lons, ps, zs, ob, t0_unix=F.unix(T0), cfg=dict(region=(0, 35, 65, 100)))
    print(N.report_text(rep))
    j, i = np.abs(lats - 13.5).argmin(), np.abs(lons - 79.5).argmin()
    assert dps[j, i] != 0 and np.abs(inc['temperature'][:, j, i]).max() > 0
    print('end to end: records -> npz -> OI increments - ok')

if __name__ == '__main__':
    R = test_decoders(); test_end_to_end(R); test_listing_ctl_grid(); test_lightning(); print('all obs_fetch tests passed')
