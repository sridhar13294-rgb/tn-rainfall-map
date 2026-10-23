"""Observing-system simulation experiment (OSSE) for the LETKF with mm2 at T85 (identical twin, perfect model).
python osse.py LIBM_WX_NPZ OUT_JSON [CONFIG_JSON]        (Kaggle GPU; run from scripts/cyclone/mm)

Nature run: mm2 from the ERA5 start `start` (libm_wx2020_fields.npz), `days` long. Every 6 h synthetic observations of
the nature run at the network of network.py (real Indian station positions + plausible global network) with Gaussian
noise of the size of the observation errors.
Ensemble: K members started from nature + beta x (ERA5 at another date within +-window_days - ERA5 at the start), each
put through the digital filter. Their mean is off the truth by about half the day-to-day weather variability (like a
2-3 day old forecast), and the members are spread about as much - the truth is statistically one of them.
Free run: one forecast from the ensemble-mean start, no observations. Cycling: 6-h forecasts of every member -> LETKF
analysis (analysis.py) -> increments into each member's state.
Output (written every cycle): RMSE against the nature run of t850, z500, u850, v850, ps for the analysis mean, the
6-h background mean and the free run, by region; ensemble spread; O-B / O-A by observation type; timings."""
import sys, os, json, time, datetime as dt, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); MM = os.path.join(HERE, '..', 'cyclone', 'mm')
sys.path.insert(0, HERE); sys.path.insert(0, MM)
import jax, jax.numpy as jnp
import mm2, landinit
import mmstate as MS, analysis as AN, network as NW, obsop as OP

CFG = dict(start='2020-07-15T00', K=20, days=10, beta=0.5, window_days=60, seed=1, grid='T85', settings={'rad': 'radcloud', 'rad_every': 2},
           ana={}, cycles=None, dfi_after=False, label='osse')
REG = {'globe': lambda A, O: np.ones_like(A, bool), 'nh': lambda A, O: A >= 20, 'tropics': lambda A, O: np.abs(A) < 20,
       'sh': lambda A, O: A <= -20, 'india': lambda A, O: (A >= 5) & (A <= 35) & (O >= 65) & (O <= 100)}

def main(LIB, OUT, cfgp=None):
    C = dict(CFG); C.update(json.load(open(cfgp)) if cfgp and os.path.exists(cfgp) else (json.loads(cfgp) if cfgp else {}))
    T_all = time.time(); rs = np.random.default_rng(C['seed']); log = lambda *a: print(*a, flush=True)
    Z = np.load(LIB); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
    tt = [dt.datetime.strptime(t, '%Y-%m-%dT%H') for t in TT]; t_s = dt.datetime.strptime(C['start'], '%Y-%m-%dT%H')
    k0 = int(np.argmin([abs((t - t_s).total_seconds()) for t in tt])); t0 = tt[k0]
    win = C['window_days']
    while True:
        others = [k for k, t in enumerate(tt) if k != k0 and abs((t - t0).days) <= win]
        if len(others) >= C['K'] or win > 200: break
        win += 15
    pick = list(rs.choice(others, C['K'], replace=len(others) < C['K']))
    log('start', t0, 'members from', [TT[k] for k in pick])
    M = mm2.Model(C['grid'], 32, None, dict(C['settings']))
    f2 = Z['f2']; f3 = Z['f3']
    def init(k):
        F3 = {v: f3[k, V3.index(v)] for v in V3}
        return M.init(F3, Z['levs'], Z['lats'], Z['lons'], f2[k, V2.index('surface_pressure')], f2[k, V2.index('geopotential_at_surface')] / 9.80616,
                      f2[k, V2.index('sea_surface_temperature')], f2[k, V2.index('land_sea_mask')], when=tt[k], **landinit.land_kwargs(f2[k], V2))
    raw = {}
    for k in sorted(set(pick)): raw[k] = init(k)[0]
    s0, cr0 = init(k0); M.build(t0)
    t = time.time(); nat = M.dfi(s0); log('nature start ready %.0fs' % (time.time() - t))
    mem = []
    for j, k in enumerate(pick):
        mem.append(M.dfi(MS.combine(s0, raw[k], s0, C['beta'])))
    raw = None; free = MS.mean_state(mem)
    log('members ready %.0fs' % (time.time() - T_all))
    cr_n = cr0; cr_f = cr0; cr_m = [cr0] * C['K']
    LA = np.asarray(M.LA); LO = np.asarray(M.LO); W = np.cos(np.radians(LA))
    static = dict(lon=np.asarray(M.lon), lat=np.asarray(M.lat), sig=np.asarray(M.sig), zs=np.asarray(M.zs), land=np.asarray(M.land).astype(np.float32))
    net = NW.build(static['lon'], static['lat'], static['land'], static['zs'], seed=7)
    A = AN.Analysis(static, C['ana'], xp=jnp)
    def scores(fields, truth):
        out = {}
        for v in truth:
            e = (np.asarray(fields[v]) - np.asarray(truth[v])) ** 2
            out[v] = {r: round(float(np.sqrt((e * W * f(LA, LO)).sum() / (W * f(LA, LO)).sum())), 3) for r, f in REG.items()}
        return out
    def ens_verif(sts):
        Vs = [MS.verif(M, s) for s in sts]; mean = {v: np.mean([np.asarray(x[v]) for x in Vs], 0) for v in Vs[0]}
        spread = {v: round(float(np.sqrt((np.var([np.asarray(x[v]) for x in Vs], 0, ddof=1) * W).sum() / W.sum())), 3) for v in Vs[0]}
        return mean, spread
    res = dict(config=C, start=str(t0), members_from=[TT[k] for k in pick], network={k: int(len(v['lat'])) for k, v in net.items()}, cycles=[])
    tv = MS.verif(M, nat); m0, sp0 = ens_verif(mem)
    res['cycles'].append(dict(h=0, ana=scores(m0, tv), free=scores(MS.verif(M, free), tv), spread_ana=sp0))
    log('h 0 initial error', {v: res['cycles'][0]['ana'][v]['globe'] for v in tv}, 'spread', sp0)
    ncyc = C['cycles'] or int(C['days'] * 4)
    for c in range(1, ncyc + 1):
        tc = time.time(); h = 6 * c
        nat, cr_n = mm2.integrate(M, nat, cr_n, 6); free, cr_f = mm2.integrate(M, free, cr_f, 6)
        for j in range(C['K']): mem[j], cr_m[j] = mm2.integrate(M, mem[j], cr_m[j], 6)
        jax.block_until_ready(mem[-1].vorticity); t_fc = time.time() - tc
        # observations of the nature run
        tc2 = time.time(); Ft = MS.nodal(M, nat)
        obs = NW.records(net, (t0.hour + h) % 24, static['lon'], static['lat'], static['land'], c)
        op = OP.Operator(static, obs); hx = np.asarray(op(Ft, jnp)[0], float)
        tob = dict(obs, var=np.where(obs['var'] == 'q', 't', obs['var'])); tq = np.asarray(OP.Operator(static, tob)(Ft, jnp)[0], float)
        pob = np.where(op.upper, op.pobs, np.asarray(OP.Operator(static, dict(obs, var=np.full(len(hx), 'ps')))(Ft, jnp)[0], float))
        ok = np.isfinite(hx) & np.isfinite(tq) & np.isfinite(pob)
        obs = {k: v[ok] for k, v in obs.items()}; hx = hx[ok]
        obs['err'] = OP.obs_errors(obs, qs_ref=OP.NG.qsat(tq[ok], pob[ok])); obs['value'] = hx + rs.standard_normal(len(hx)) * obs['err']
        # analysis
        Fb = MS.stack([MS.nodal(M, s) for s in mem]); bgm, bsp = ens_verif(mem)
        Fa, info = A(Fb, obs)
        mem = [MS.update(M, mem[j], MS.member(Fb, j), MS.member(Fa, j)) for j in range(C['K'])]
        if C['dfi_after']: mem = [M.dfi(s) for s in mem]
        jax.block_until_ready(mem[-1].vorticity); t_an = time.time() - tc2
        tv = MS.verif(M, nat); am, asp = ens_verif(mem)
        row = dict(h=h, ana=scores(am, tv), bg=scores(bgm, tv), free=scores(MS.verif(M, free), tv), spread_ana=asp, spread_bg=bsp,
                   n_obs=info['n_obs'], n_used=info['n_used'], rho=info['rho'], local_obs=info['mean_local_obs'],
                   obs={k: {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in r.items()} for k, r in info['obs'].items()},
                   t_forecast_s=round(t_fc, 1), t_analysis_s=round(time.time() - tc2, 1))
        res['cycles'].append(row); json.dump(res, open(OUT, 'w'), default=str)
        g = lambda key: {v: row[key][v]['globe'] for v in row[key]}
        log('h %3d ana %s | bg %s | free %s | spread %s | obs %d/%d | fc %.0fs an %.0fs' % (h, g('ana'), g('bg'), g('free'), asp, info['n_used'], info['n_obs'], t_fc, t_an))
        if not all(np.isfinite(row['ana'][v]['globe']) for v in row['ana']): log('non-finite analysis: stop'); break
    res['total_s'] = round(time.time() - T_all); json.dump(res, open(OUT, 'w'), default=str); log('done %.0fs' % (time.time() - T_all))

if __name__ == '__main__':
    main(*sys.argv[1:4])
