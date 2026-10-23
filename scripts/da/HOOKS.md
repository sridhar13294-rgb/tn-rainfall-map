# Hooks the LETKF needs outside scripts/da (proposed patches, not applied)

Everything in `scripts/da/` runs without changing any other file. These patches are for the owners of the files named,
when real-data cycling starts. None is needed for the OSSE.

## 1. `scripts/cyclone/mm/live2.py` - start the live ensemble from our own LETKF analysis

When a cycled analysis exists for the run time, members start from it instead of consensus + bred vectors. Right after
the consensus block in `run()` (after `if len(CN['used']) < 2: CN = None`):

```python
    DA = os.path.join(os.path.dirname(os.path.abspath(LIVEM)), f'letkf_{t0:%Y%m%d%H}.npz')    # scripts/da/cycle output
    if C.get('letkf', True) and os.path.exists(DA):
        sys.path.insert(0, os.path.join(HERE, '..', '..', 'da')); import mmstate as MSD
        DAZ = np.load(DA)                                            # t, q, u, v [K, L, X, Y]; ps [K, X, Y] on the T85 nodal grid
        print('LETKF start:', DAZ['t'].shape[0], 'analysis members', flush=True)
    else: DAZ = None
```

and, in the member loop, after `st, cr = M.init(...)` and `M.build(t0)` (replacing `st = M.dfi(st)` and the bred-vector
block when `DAZ` is set):

```python
            if DAZ is not None and grid == 'T85':
                j = k % DAZ['t'].shape[0]                            # member k <- analysis member j (k = 0: the analysis mean)
                Fb = MSD.nodal(M, st)
                Fa = {v: jnp.asarray(DAZ[v].mean(0) if k == 0 else DAZ[v][j]) for v in ('t', 'q', 'u', 'v', 'ps')}
                st = MSD.update(M, st, Fb, Fa)                       # whole state replaced by the analysis (same grid)
            else:
                st = M.dfi(st)
                ... (existing bred-vector code)
```

The land/sea state (`cr`) still comes from `M.init` (analysed soil fields), as now.

## 2. `scripts/cyclone/mm/mm2.py` - nothing required; two conveniences

- `Model.run_wx`'s `to_p` and `t_below` as module functions (scripts/da/mmstate.py has a copy to verify t850/z500).
- A batched member forecast (`jax.vmap` of `integrate` over states and carries) would cut the 6-h forecast cost of 20-50
  members (now a Python loop of jitted calls). Needs `M._carry` passed explicitly instead of set as an attribute inside
  the traced step (`Phys.explicit_terms` reads `M._carry`), which is the only obstacle to vmap.

## 3. `scripts/cyclone/obs_fetch.py` - global observations for cycling

The cycled analysis covers the whole globe; today's feed is regional (METAR 30-120E 40S-40N; SYNOP/TEMP effectively
India via Ogimet/Wyoming because the NWS gateway lists returned 0 bulletins on 22 Oct 12Z, see data/cyclone/obs_log.txt).
- a `region` argument (default the current box; `global` for DA): METAR tiles over the globe (~15-20 k reports per
  window, ~250 requests at 400 rows - inside the AWC 100/min limit with a pause), and the GTS SYNOP/TEMP/SHIP bulletins
  globally (the decoder already handles any WMO block; only the India filter has to go);
- keep ASCAT in every 6-h window (it is already fetched; passes over India fall at 06Z/18Z);
- write the analysis-time window as t0 - 3 h .. t0 + 3 h for cycling (now t0 - 6 h .. t0 + 3 h).

## 4. Workflow - a cycling job (new file `.github/workflows/cyclone-da.yml`, owner's call)

Every 6 h after `obs`: download the previous `letkf_<prev>.npz` (each member's full model state and carry as pytree
leaves - soil, sea-surface and radiation-cache fields must continue from the member's own forecast, not restart from
`M.init`), run `scripts/da/cycle.py` (to be written from osse.py: replace the nature
run by `obsop.prepare_real(nudge.load_obs(obs_<run>.npz))`), upload `letkf_<run>.npz` (K x 129 x 32768 float16 ~ 170 MB
for K = 20; or keep only mean + 20 members as float16) to the release.
