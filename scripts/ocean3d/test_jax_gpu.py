"""Stage 2 check: does our ocean (columns ocean.py + currents.py + reduced-gravity layer rgo.py) run under jax.jit on the
GPU, give the same answer as numpy, and how fast is it?  Kaggle: python test_jax_gpu.py OUT.json
  1. regional box 0-30N 40-105E, 10 days of ERA5 forcing from 15 May 2019: numpy (float64, CPU) vs jax.jit (GPU)
     -> max / RMS difference of the SST change and of the layer thickness, time per model day.
  2. global band 60S-60N (periodic), 30 days, jax only -> stays finite?, time per model day.
Forcing as era5_ocean_test.py (ERA5 fluxes + lam (SST_ERA5 - SST_model), lam = 30), but the 6-h mean short-wave is used
as it is (no diurnal shape) so that both paths get identical inputs and the correction is done inside the step."""
import os, sys, json, time, traceback, datetime as dt
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'cyclone', 'mm'))
import currents as cu, ocean as oc, rgo
import era5_ocean_test as E

LAM = 30.0; DT = 3600.0; NPER = 6


def windows(G, i0, i1):
    """Per 6-h window: taux, tauy, qns (ERA5, without the SST correction), sw, emp, sst_obs (0 where missing), obs mask."""
    nz = np.nan_to_num; W = []
    for n in range(i0, i1):
        tx, ty = E.fo.stress(nz(G['u10'][n]), nz(G['v10'][n]))
        qns = nz(G['slhf'][n] + G['sshf'][n] + G['lw'][n]); sw = nz(G['sw'][n])
        emp = -nz(G['slhf'][n]) / 2.5e6 - nz(G['tp'][n]) * 1000.0 / 21600.0
        so = G['sst'][n]; W.append((tx, ty, qns, sw, emp, nz(so), np.isfinite(so)))
    return W


def setup(G, clim, i0, periodic):
    LO, LA = np.meshgrid(G['lon'], G['lat'], indexing='ij'); sea = np.isfinite(G['sst'][i0])
    sst0 = np.where(sea, G['sst'][i0], 0.0)
    st = {k: np.asarray(v, float) for k, v in oc.profile_from_clim(clim, G['times'][i0], LA, LO, sst0, sea).items()}
    g = cu.make_geom(LA, LO, st['dz'], sea, periodic=periodic); rgg = rgo.make_geom(LA, LO, sea, periodic=periodic)
    rg = rgo.init_state(rgg, rgo.d20(st['T'], st['dz']))
    return st, rg, g, rgg, sea, sst0, LA, LO


def make_step(g, rgg, sea, prm, xp):
    f = g['f']
    def one(st, rg, tx, ty, qns, sw, emp, so, om):
        q = qns + xp.where(om, LAM * (so - st['T'][0]), 0.0)
        st, _ = oc.step(st, xp.where(sea, q, 0.0), xp.where(sea, sw, 0.0), tx, ty, f, DT, mask=sea, fw=xp.where(sea, emp, 0.0), xp=xp)
        rg = rgo.step(rg, tx, ty, rgg, DT, prm=prm, xp=xp)
        st = cu.step(st, tx, ty, f, g, DT, prm=prm, xp=xp, q=rgo.column_transports(rg, rgg, g, tx, ty, f, prm=prm, xp=xp))
        return st, rg
    return one


def run(st, rg, W, step, block=None):
    t = time.time()
    for w in W:
        for _ in range(NPER): st, rg = step(st, rg, *w)
    if block: block(st)
    return st, rg, time.time() - t


def main(out):
    import jax, jax.numpy as jnp
    R = dict(devices=str(jax.devices()), x64=bool(jax.config.read('jax_enable_x64')))
    def save(): json.dump(R, open(out, 'w'), indent=1)
    clim = dict(np.load('ocean_clim.npz')) if os.path.exists('ocean_clim.npz') else dict(np.load(os.path.join(HERE, 'ocean_clim.npz')))
    prm = dict(r_ek=1.0)                                                          # the recommended setting (no Ekman shear)
    t0, t1 = dt.datetime(2019, 5, 15), dt.datetime(2019, 6, 14)
    F = E.get_era5(t0, t1); ix = {t: i for i, t in enumerate(F['times'])}
    tojax = lambda d: jax.tree_util.tree_map(jnp.asarray, d)
    block = lambda s: jax.block_until_ready(s)
    # 1. regional: numpy vs jax
    try:
        G = E.box(F, 0.0, 30.0, 40.0, 105.0); i0 = ix[t0]; i1 = ix[t0 + dt.timedelta(days=10)]
        st, rg, g, rgg, sea, sst0, LA, LO = setup(G, clim, i0, False); W = windows(G, i0, i1)
        stn, rgn, tn = run(st, rg, W, make_step(g, rgg, sea, prm, np))
        R['regional'] = dict(grid=list(sea.shape), days=10, numpy_s_per_day=round(tn / 10, 2)); save(); print(R, flush=True)
        stepj = jax.jit(make_step(g, rgg, jnp.asarray(sea), prm, jnp)); Wj = [tuple(jnp.asarray(a) for a in w) for w in W]
        tc = time.time(); s1, r1 = stepj(tojax(st), tojax(rg), *Wj[0]); block(s1); R['regional']['jax_compile_s'] = round(time.time() - tc, 1)
        stj, rgj, tj = run(tojax(st), tojax(rg), Wj, stepj, block)
        dn = np.where(sea, stn['T'][0] - sst0, 0.0); dj = np.where(sea, np.asarray(stj['T'][0]) - sst0, 0.0); d = (dj - dn)[sea]
        hd = np.asarray(rgj['h']) - np.asarray(rgn['h'])
        R['regional'].update(jax_s_per_day=round(tj / 10, 3), speedup=round(tn / max(tj, 1e-9), 1), finite=bool(np.isfinite(dj).all()),
                             dsst_numpy_mean=round(float(dn[sea].mean()), 3), dsst_jax_mean=round(float(dj[sea].mean()), 3),
                             dsst_diff_max=round(float(np.abs(d).max()), 4), dsst_diff_rms=round(float(np.sqrt((d ** 2).mean())), 4),
                             h_diff_max_m=round(float(np.nanmax(np.abs(hd))), 3))
    except Exception:
        R['regional_error'] = traceback.format_exc()[-3000:]
    save(); print(R, flush=True)
    # 2. global band, jax only, 30 days
    try:
        G = E.box(F, -60.0, 60.0, 0.0, 360.0); i0 = ix[t0]; i1 = ix[t1]
        st, rg, g, rgg, sea, sst0, LA, LO = setup(G, clim, i0, True); W = [tuple(jnp.asarray(a) for a in w) for w in windows(G, i0, i1)]
        stepj = jax.jit(make_step(g, rgg, jnp.asarray(sea), prm, jnp))
        tc = time.time(); s1, r1 = stepj(tojax(st), tojax(rg), *W[0]); block(s1); comp = time.time() - tc
        stj, rgj, tj = run(tojax(st), tojax(rg), W, stepj, block); days = (i1 - i0) / 4.0
        dj = np.where(sea, np.asarray(stj['T'][0]) - sst0, 0.0); do = np.nan_to_num(G['sst'][i1 - 1] - G['sst'][i0])
        ok = sea & np.isfinite(G['sst'][i1 - 1]); h = np.asarray(rgj['h'])
        R['global'] = dict(grid=list(sea.shape), days=days, jax_compile_s=round(comp, 1), jax_s_per_day=round(tj / days, 3),
                           s_per_10day_forecast=round(tj / days * 10, 1), finite=bool(np.isfinite(dj).all() and np.isfinite(h).all()),
                           dsst_mean=round(float(dj[ok].mean()), 3), dsst_era5_mean=round(float(do[ok].mean()), 3),
                           dsst_corr_vs_era5=round(float(np.corrcoef(dj[ok], do[ok])[0, 1]), 3),
                           h_min_max_m=[round(float(np.nanmin(h)), 1), round(float(np.nanmax(h)), 1)])
    except Exception:
        R['global_error'] = traceback.format_exc()[-3000:]
    save(); print(R, flush=True)


if __name__ == '__main__':
    main(sys.argv[1])
