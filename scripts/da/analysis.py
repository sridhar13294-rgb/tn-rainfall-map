"""One LETKF analysis of mm2's nodal fields (T, q, u, v on sigma levels, surface pressure), model-independent: it takes
and returns plain arrays, so it is tested on the CPU without the model (test_analysis.py) and runs on the GPU with jax.

Fields: dict t, q, u, v [K, L, X, Y] and ps [K, X, Y] (Pa); static: lon [X], lat [Y], sig [L] (top -> bottom), zs and
land [X, Y]. Observations: records (type, sid, lat, lon, p, z, var) + value + err (sigma_o).

Steps: H(x_k) for every member -> QC against the ensemble mean -> for each of G vertical groups (sigma levels where the
weights are computed), the local observations of every grid column (Gaspari-Cohn in great-circle distance and in
ln sigma) -> K x K weights per column and group -> each model level gets the weights blended linearly in ln sigma
between its two groups -> analysis ensemble -> RTPS -> q kept >= 0."""
import math, numpy as np
import letkf as LK, obsop as OP

DEFAULTS = dict(
    c_h=700.0,                        # horizontal Gaspari-Cohn half-width (km): weight 0.21 at c, 0 beyond 2c
    c_h_top=900.0,                    # ... at the top group (linear in ln sigma between); wider aloft where obs are sparse
    c_v=0.6,                          # vertical half-width in ln sigma (~ln p): 0.6 -> from 1000 hPa the support reaches ~300 hPa
    groups=(0.985, 0.93, 0.85, 0.72, 0.58, 0.45, 0.33, 0.22, 0.13, 0.06),     # sigma of the weight levels
    pmax=400,                         # at most this many observations per local problem (nearest first)
    rho=1.0,                          # multiplicative prior inflation inside the solve
    rtps=0.8,                         # relaxation to prior spread
    adaptive=False,                   # global adaptive multiplicative inflation (rho updated each cycle)
    chunk=4096,                       # columns per solver call (GPU memory)
    qc=None,                          # obsop.quality_control settings
    q_max=0.04)

def flat(F):
    """[..., X, Y] -> [..., X*Y]."""
    return F.reshape(F.shape[:-2] + (-1,))

def obs_stats(why, hx_mean, y, typ, var, sprd=None, hxa_mean=None):
    """O-B (and O-A) rms / mean, spread and counts by type:variable."""
    out = {}
    for key in sorted(set(zip(typ, var))):
        m = (typ == key[0]) & (var == key[1]); u = m & (why == '')
        r = dict(n=int(m.sum()), used=int(u.sum()), rejected={w: int(((why == w) & m).sum()) for w in set(why[m]) if w})
        if u.any():
            d = y[u] - hx_mean[u]; r.update(omb_rms=float(np.sqrt((d ** 2).mean())), omb_mean=float(d.mean()))
            if sprd is not None: r['spread'] = float(np.sqrt((sprd[u] ** 2).mean()))
            if hxa_mean is not None: da = y[u] - hxa_mean[u]; r.update(oma_rms=float(np.sqrt((da ** 2).mean())))
        out[f'{key[0]}:{key[1]}'] = r
    return out

class Analysis:
    def __init__(self, static, cfg=None, xp=np):
        self.c = dict(DEFAULTS, **(cfg or {})); self.xp = xp; self.st = static
        LO, LA = np.meshgrid(np.asarray(static['lon'], float), np.asarray(static['lat'], float), indexing='ij')
        self.glat, self.glon = LA.ravel(), LO.ravel()
        self.sig = np.asarray(static['sig'], float); self.B = LK.vertical_blend(self.sig, self.c['groups'])
        self.solver = LK.Solver(xp, self.c['chunk']); self.rho = float(self.c['rho'])

    def __call__(self, Fb, obs):
        xp, c = self.xp, self.c; info = {}
        op = OP.Operator(self.st, obs)
        HX, vert = op(Fb, xp)                                                              # [K, n]
        HX = np.asarray(HX, np.float64); vert = np.asarray(vert).mean(0)
        K = HX.shape[0]; hm = HX.mean(0); sprd = HX.std(0, ddof=1)
        y = np.asarray(obs['value'], float); so = np.asarray(obs['err'], float); d = y - hm
        ok, why = OP.quality_control(op, obs, d, so, np.nan_to_num(sprd), c['qc'])
        typ, var = op.type, op.var
        Yp = (HX[:, ok] - hm[ok]).astype(np.float32); dd = d[ok].astype(np.float32); rinv = (1.0 / so[ok] ** 2).astype(np.float32)
        olat = np.asarray(obs['lat'], float)[ok]; olon = np.asarray(obs['lon'], float)[ok]; ov = vert[ok]
        if c['adaptive']: self.rho = LK.adaptive_inflation(dd, Yp, rinv, prev=self.rho)
        info['rho'] = self.rho; info['n_used'] = int(ok.sum()); info['n_obs'] = int(len(ok))
        # weights per vertical group
        lg = np.log(np.asarray(c['groups'], float)); top, bot = lg.min(), lg.max(); Tg = []; nloc = []
        for g, l in enumerate(lg):
            a = (bot - l) / max(bot - top, 1e-9); ch = c['c_h'] + a * (c['c_h_top'] - c['c_h'])
            idx, loc = LK.local_obs_sphere(self.glat, self.glon, olat, olon, ch, c['pmax'], overt=ov, gvert=l, c_v=c['c_v'])
            nloc.append(float((loc > 0.01).sum(1).mean()))
            Tg.append(self.solver.weights(xp.asarray(Yp), xp.asarray(dd), xp.asarray(rinv), idx, loc, self.rho))
        Tg = xp.stack(Tg); info['mean_local_obs'] = [round(x, 1) for x in nloc]
        # apply, level by level
        B = self.B; V = ('t', 'q', 'u', 'v'); Xbf = {k: flat(Fb[k]) for k in V}; lev = {k: [] for k in V}; L = len(self.sig)
        for l in range(L):
            Tl = sum(float(B[l, g]) * Tg[g] for g in range(len(lg)) if B[l, g] > 0)
            for k in V:
                xa = LK.apply_weights(Xbf[k][:, l], Tl, xp); lev[k].append(LK.rtps(Xbf[k][:, l], xa, c['rtps'], xp))
            if l == L - 1:                                                                  # surface pressure: lowest level's weights
                Xb = flat(Fb['ps']); psa = LK.rtps(Xb, LK.apply_weights(Xb, Tl, xp), c['rtps'], xp).reshape(Fb['ps'].shape)
        Fa = {k: xp.stack(lev[k], 1).reshape(Fb[k].shape) for k in V}; Fa['ps'] = psa
        Fa['q'] = xp.clip(Fa['q'], 0.0, c['q_max'])
        HA, _ = op(Fa, xp); ham = np.asarray(HA, np.float64).mean(0)
        info['obs'] = obs_stats(why, hm, y, typ, var, sprd, ham)
        return Fa, info
