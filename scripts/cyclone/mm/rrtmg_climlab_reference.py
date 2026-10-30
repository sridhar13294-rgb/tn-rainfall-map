"""Independent clear-sky LW reference (RRTMG_LW via climlab, Mlawer et al. 1997 / Iacono et al. 2008; ~1 W/m2, ~0.1 K/day vs
LBLRTM) for the same column as lw_column.json. Installs micromamba + conda-forge climlab when missing (Kaggle).
python rrtmg_climlab_reference.py"""
import sys, os, json, subprocess, numpy as np
H = os.path.dirname(os.path.abspath(__file__))
try:
    import climlab
except ImportError:
    if os.environ.get('RRTMG_CHILD'): raise
    sh = ('cd /tmp && curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xj bin/micromamba && '
          '/tmp/bin/micromamba create -y -q -p /tmp/cl -c conda-forge python=3.12 climlab numpy > /tmp/mm.log 2>&1; tail -3 /tmp/mm.log')
    subprocess.run(sh, shell=True)
    r = subprocess.run(['/tmp/cl/bin/python', os.path.abspath(__file__)], env=dict(os.environ, RRTMG_CHILD='1')); sys.exit(r.returncode)
C = json.load(open(os.path.join(H, 'lw_column.json')))
p, dp, T, q = (np.array(C[k]) for k in ('p', 'dp', 'T', 'q')); Ts = C['Ts']
lev = p / 100.0
o3 = np.interp(np.log(p), np.log([1e2, 1e3, 3e3, 1e4, 3e4, 1e5]), [1e-6, 8e-6, 8e-6, 2e-7, 5e-8, 3e-8])
state = climlab.column_state(lev=lev); state['Tatm'][:] = T; state['Ts'][:] = Ts
res = {}
for lab, gases in (('h2o+co2', dict(CO2=420e-6, O3=0.0, CH4=0.0, N2O=0.0)), ('all', dict(CO2=420e-6, O3=o3, CH4=1.9e-6, N2O=0.33e-6))):
    absorb = dict(CFC11=0., CFC12=0., CFC22=0., CCL4=0., O2=0.209); absorb.update(gases)
    rad = climlab.radiation.RRTMG_LW(state=state, specific_humidity=q, absorber_vmr=absorb, emissivity=1.0)
    rad.compute_diagnostics()
    hr = np.asarray(rad.TdotLW_clr if hasattr(rad, 'TdotLW_clr') else rad.TdotLW).ravel()
    dg = rad.diagnostics; print(lab, 'diagnostics:', sorted(dg.keys()))
    g = lambda *ks: next((np.asarray(dg[k]).ravel() for k in ks if k in dg), np.array([np.nan]))
    dn = g('LW_flux_down_clr', 'LW_flux_down'); olr = g('OLRclr', 'OLR')
    res[lab] = (hr, float(olr[0]), float(dn[-1]))
fit = np.array(C['fitted']); s15 = np.array(C['ssm15']); s10 = np.array(C['ssm10'])
sig = p / C['ps']; m8 = sig >= 0.79; mm = lambda h: float((h * dp * m8).sum() / (dp * m8).sum())
m83 = (p >= 30000) & (p <= 80000); m3 = lambda h: float((h * dp * m83).sum() / (dp * m83).sum())
for lab, (hr, olr, dn) in res.items(): print(f'RRTMG {lab}: OLR {olr:.1f}  surface down {dn:.1f}')
print(f'MEGAM: OLR 285.6 surface down 411.5 (fitted scheme; gases H2O, CO2, O3)')
print(f'{"hPa":>6s} {"RRTMG all":>10s} {"RRTMG h2o+co2":>14s} {"MEGAM":>8s} {"SSMx1.5":>8s} {"SSMx1.0":>8s}  K/day')
for k in range(10, len(p)): print(f'{p[k]/100:6.0f} {res["all"][0][k]:+10.2f} {res["h2o+co2"][0][k]:+14.2f} {fit[k]:+8.2f} {s15[k]:+8.2f} {s10[k]:+8.2f}')
print(f'800-1000 hPa mass-mean: RRTMG all {mm(res["all"][0]):+.2f}  h2o+co2 {mm(res["h2o+co2"][0]):+.2f}  MEGAM {mm(fit):+.2f}  SSMx1.5 {mm(s15):+.2f}  SSMx1.0 {mm(s10):+.2f}')
print(f'300-800 hPa mass-mean:  RRTMG all {m3(res["all"][0]):+.2f}  h2o+co2 {m3(res["h2o+co2"][0]):+.2f}  MEGAM {m3(fit):+.2f}')
d = mm(fit) - mm(res['all'][0]); print(f'MEGAM minus RRTMG, 800-1000 hPa: {d:+.2f} K/day = {d * 1004.6 * 20000 / 9.80616 / 86400:+.1f} W/m2 (negative = MEGAM cools more)')
