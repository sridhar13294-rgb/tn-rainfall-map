"""Which cloud part makes the radiation excess? (11 Nov) Radiation recomputed offline on the model state at hour 0 (ERA5 start after
DFI) and hour 24, global means: (a) as is, (b) no convective/anvil cloud, (c) cloud water x0.5, (d) clear sky.
References: atmospheric radiative heating ~-103 W/m2 (Wild 2013), SW CRE ~-47, LW CRE ~+26, OLR ~239, cover ~0.67 (CERES).
NOTE: set rad_dbg=1 (mm2 stores the radiation inputs on eager column() calls). python rad_parts.py LIB GRID STARTS"""
import sys, os, datetime as dt, numpy as np, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import mm2, landinit, radcloud as R
from dinosaur import primitive_equations
Z = dict(np.load(sys.argv[1])); TT=[str(t) for t in Z['times']]; V3=[str(v) for v in Z['v3']]; V2=[str(v) for v in Z['v2']]
GR = sys.argv[2]; KS = [int(x) for x in sys.argv[3].split(',')]
setx = {'rad':'radcloud','rad_every':1,'cmt_mf':1.0,'rd_si':1.0,'rad_dbg':1}; setx.update(__import__('json').loads(os.environ.get('EXTRA', '{}')))
M = mm2.Model(GR, 32, float(os.environ.get('DT', 20)), setx); W = np.cos(np.radians(np.asarray(M.LA)))
gm = lambda X: float((np.asarray(X) * W).sum() / W.sum())
acc = {}
for k in KS:
    t0 = dt.datetime.strptime(TT[k], '%Y-%m-%dT%H'); f2 = Z['f2'][k]; f3 = {v: np.array(Z['f3'][k, V3.index(v)]) for v in V3}
    st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')]/9.80616, f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
    M.build(t0); st = M.dfi(st); hor = M.coords.horizontal
    for h in (0, 24):
        if h: st, cr = mm2.integrate(M, st, cr, 24)
        aux = primitive_equations.compute_diagnostic_state_sigma(st.replace(tracers={}), M.coords)
        T = (aux.temperature_variation + M.ref_t[:, None, None]) / M.K; cl_ = hor.cos_lat
        u = aux.cos_lat_u[0]/cl_/M.MPS; v = aux.cos_lat_u[1]/cl_/M.MPS; q = st.tracers['specific_humidity']; ps = jnp.exp(hor.to_nodal(st.log_surface_pressure))[0]/M.PA
        crx = dict(cr, doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0)); M._carry = crx
        M.column(*(jnp.asarray(x, jnp.float32) for x in (T, q, u, v, ps)), crx, want_diag=True, div=hor.to_nodal(st.divergence)*M.SEC)
        I = {k_: np.asarray(v_, np.float64) if not isinstance(v_, dict) else v_ for k_, v_ in M._rad_in.items()}
        args = (I['T'], I['q'], I['p'], I['dp'], I['ps'])
        mass = I['dp'] / 9.80616; o3 = R.ozone_layer_mass(I['p'], I['dp'], np)
        def run(cm, scale):
            cl = R.clouds(*args, I['sea'].astype(bool), cm, I['Psrc'].sum(0) if cm is not None else None, I['Psrc'] if cm is not None else None, I['cond'], np, I['prm'])
            cl = dict(cl, lwp=cl['lwp'] * scale, iwp=cl['iwp'] * scale)
            lw = R.longwave(*args, I['Ts'], cl, np, I['prm'], o3); sw = R.shortwave(*args, I['sea'].astype(bool), I['mu0'], cl, np, I['prm'], o3, I['s0'])
            heat = ((lw['heating'] + sw['heating']) * 1004.6 * mass).sum(0)
            return dict(atm_rad=gm(heat), olr=gm(lw['olr']), sw_up=gm(sw['toa_up']), sw_up_clr=gm(sw['toa_up_clr']), sw_dn=gm(sw['toa_dn']),
                        cover=gm(cl['cover']), lwp=gm((cl['lwp'] * cl['c']).sum(0)) * 1000, iwp=gm((cl['iwp'] * cl['c']).sum(0)) * 1000,
                        sw_atm=gm((sw['heating'] * 1004.6 * mass).sum(0)), sw_sfc=gm(sw['net_sfc']))
        cm = I['cm'].astype(bool)
        for nm, (cmx, sc) in {'(a) as is': (cm, 1.0), '(b) no conv/anvil cloud': (None, 1.0), '(c) cloud water x0.5': (cm, 0.5), '(d) clouds off': (None, 0.0)}.items():
            r = run(cmx, sc); r['sw_cre'] = r['sw_up_clr'] - r['sw_up']; acc.setdefault((h, nm), []).append(r)
        print(TT[k], 'h', h, 'done', flush=True)
for (h, nm), rs in acc.items():
    m = {k_: np.mean([r[k_] for r in rs]) for k_ in rs[0]}
    print(f'h{h:2d} {nm:26s} atm rad {m["atm_rad"]:+7.1f} (ref -103) | SW atm {m["sw_atm"]:5.1f} (~79) sfc {m["sw_sfc"]:5.1f} (~161) | SW CRE {m["sw_cre"]:+6.1f} (-47) | OLR {m["olr"]:5.1f} (239) | cover {m["cover"]:.2f} (0.67) | LWP {m["lwp"]:5.0f} IWP {m["iwp"]:4.0f} g/m2 | TOA SW in {m["sw_dn"]:.0f}')
