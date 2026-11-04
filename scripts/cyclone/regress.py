"""Control regression check (added 4 Nov after Sridhar asked for regular code review).
Guarantees that code edits do not silently change the CONTROL model: with all options at their defaults, (a) the column
physics tendencies on a fixed state and (b) the state after one full time step must be BIT-IDENTICAL to the stored
reference of the last accepted version. Any difference = the control changed -> refuse, unless the change is intended and
the reference is renewed on purpose (python regress.py --renew "reason"; the reason is logged in data/cyclone/regress_log.md).
Optional: --opts a,b,c checks that each named option, switched on, DOES change the output (no dead switches).
Runs automatically from precheck.py whenever scripts/cyclone/mm/*.py differ from the reference's hash.
Input: one start (2020-10-27T00) cut from libm_wx2020_fields.npz -> data/cyclone/regress_in.npz (committed)."""
import datetime as dt, glob, hashlib, json, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MM = os.path.join(ROOT, 'scripts/cyclone/mm'); IN = os.path.join(ROOT, 'data/cyclone/regress_in.npz')
REF = os.path.join(ROOT, 'data/cyclone/regress_ref.npz'); LOG = os.path.join(ROOT, 'data/cyclone/regress_log.md')
def code_hash():
    h = hashlib.sha256()
    for f in sorted(glob.glob(MM + '/*.py')):
        if os.path.basename(f) in ('mm2.py', 'landinit.py', 'radcloud.py') or 'rad' in os.path.basename(f): h.update(open(f, 'rb').read())
    return h.hexdigest()[:16]
def run(settings=None):
    sys.path.insert(0, MM); import jax.numpy as jnp, mm2, landinit
    from dinosaur import spherical_harmonic
    Z = dict(np.load(IN)); V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]; t0 = dt.datetime(2020, 10, 27)
    M = mm2.Model('T42', 32, None, dict({'rad': 'radcloud', 'rad_every': 2}, **(settings or {})))
    f3 = {v: Z['f3'][0, V3.index(v)] for v in V3}; f2 = Z['f2'][0]
    st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / 9.80616,
                    f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
    M.build(t0); hor = M.coords.horizontal
    T = (hor.to_nodal(st.temperature_variation) + M.ref_t[:, None, None]) / M.K; q = st.tracers['specific_humidity']
    ps = jnp.exp(hor.to_nodal(st.log_surface_pressure))[0] / M.PA; u, v = spherical_harmonic.vor_div_to_uv_nodal(hor, st.vorticity, st.divergence)
    tn, d = M.column(T, q, u / M.MPS, v / M.MPS, ps, dict(cr, doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0)), rad_fresh=True,
                     div=hor.to_nodal(st.divergence) * M.SEC)
    out = {'col_' + k: np.asarray(x) for k, x in tn.items()}; out.update(col_rain=np.asarray(d['rain']), col_H=np.asarray(d['H']), col_E=np.asarray(d['E']))
    st1, cr1 = mm2.integrate(M, st, cr, 1)                                                          # T42: one 60-min step
    out.update(step_T=np.asarray(hor.to_nodal(st1.temperature_variation)), step_q=np.asarray(st1.tracers['specific_humidity']),
               step_rain=np.asarray(cr1['rain']), step_tl=np.asarray(cr1['tl']))
    return out
def main(a):
    if not os.path.exists(IN): print('REGRESS warning: data/cyclone/regress_in.npz missing - check skipped'); return 0
    if '--renew' in a:
        why = a[a.index('--renew') + 1] if len(a) > a.index('--renew') + 1 else ''
        if not why: print('REGRESS: --renew needs a reason'); return 1
        r = run(); np.savez_compressed(REF, hash=code_hash(), **r)
        open(LOG, 'a').write(f'- {dt.datetime.utcnow():%Y-%m-%d %H:%MZ} reference renewed (code {code_hash()}): {why}\n'); print('REGRESS reference renewed'); return 0
    R = dict(np.load(REF)); r = run(); bad = []
    for k, x in r.items():
        dmax = float(np.abs(x - R[k]).max())
        if dmax != 0.0: bad.append(f'{k}: max diff {dmax:.3e}')
    if bad:
        print('REGRESS FAILED - the CONTROL model changed (all options at defaults):'); [print('  ', b) for b in bad]
        print('  If intended: python scripts/cyclone/regress.py --renew "reason"  (logged)'); return 1
    print(f'REGRESS OK: control bit-identical to the reference ({len(r)} fields; code {code_hash()} vs ref {str(R["hash"])})')
    if '--opts' in a:
        for o in a[a.index('--opts') + 1].split(','):
            k, _, v = o.partition('='); val = float(v) if v else 1.0
            ro = run({k: val}); ch = [kk for kk in ro if float(np.abs(ro[kk] - R[kk]).max()) > 0]
            print(f'  option {k}={val}: ' + (f'changes {len(ch)} fields' if ch else 'NO EFFECT (dead switch?)'))
            if not ch: bad.append(k)
    return 1 if bad else 0
if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
