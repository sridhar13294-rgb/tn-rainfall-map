# Hook for the moist model (scripts/cyclone/mm/mm2.py) - to be applied by the atmosphere engineer

Adds currents and upwelling (step A, `currents.py`) or the reduced-gravity layer (step B prototype, `rgo.py`) to the
existing 1-D ocean columns. Off by default; switched on with the setting `ocean3d`:

* `ocean3d=None` (default): unchanged behaviour.
* `ocean3d='ekman'`: Ekman drift + return flow + baroclinic geostrophic current (diagnostic, from the stress and the
  columns' density), 3-D upwind advection of the columns' T and S.
* `ocean3d='rgo'`: prognostic 1.5-layer reduced-gravity layer (thermocline depth h, currents u, v; Kelvin/Rossby waves)
  carrying the columns (Ekman shear off by default: `rgo.PRM['shear']`). Recommended (docs/stage2_ocean.md, ERA5 2019
  monsoon test).

Line numbers refer to mm2.py at commit 35e24ce9 / ca2942a3 (cases).

## 1. import (after line 19 `from ocean import step as ocean_step, profile_from_clim`)

```python
import os, sys                                                                # mm2.py does not import them yet
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'ocean3d'))
import currents as ocur, rgo as orgo                                          # stage 2 ocean (scripts/ocean3d)
```

## 2. setting (in `DEFAULTS`, line 39)

add `ocean3d=None,` to the dict (it is a structural switch, not in `DYN`).

## 3. Model.init (replace line 120)

```python
        if ocean is not None:                                                                       # 1-D ocean column under every sea point (ocean.py)
            oc0 = profile_from_clim(ocean, when, self.LA, self.LO, sst, sst > 0)
            carry['ocean'] = {k: jnp.asarray(v, jnp.float32) for k, v in oc0.items()}
            if self.S.get('ocean3d'):                                                               # stage 2: currents / reduced-gravity layer
                self.ocg = ocur.make_geom(self.LA, self.LO, oc0['dz'], sst > 0)
                if self.S['ocean3d'] == 'rgo':
                    self.rgg = orgo.make_geom(self.LA, self.LO, sst > 0)
                    rg0 = orgo.init_state(self.rgg, orgo.d20(oc0['T'].astype(float), oc0['dz'].astype(float)))
                    carry['rgo'] = {k: jnp.asarray(v, jnp.float32) for k, v in rg0.items()}
```

## 4. Model.surface (after line 503 `sst = jnp.where(sea, sst_o, cr['sst'])`)

```python
            if self.S.get('ocean3d'):                                                               # stage 2: currents, upwelling, thermocline waves
                tx, ty = kt * u[-1], kt * v[-1]; q = None
                if self.S['ocean3d'] == 'rgo':
                    rg = orgo.step(cr['rgo'], tx, ty, self.rgg, dt, xp=jnp)
                    q = orgo.column_transports(rg, self.rgg, self.ocg, tx, ty, self.fcor, xp=jnp)
                ocn = ocur.step(ocn, tx, ty, self.fcor, self.ocg, dt, xp=jnp, q=q)
                sst = jnp.where(sea, ocn['T'][0], cr['sst'])
```

## 5. Model.surface output (line 512)

```python
        if 'ocean' in cr: out['ocean'] = ocn
        if 'rgo' in cr: out['rgo'] = rg
```

## Notes

* Cost: currents.step is ~10 element-wise operations per ocean level (24) plus 6 rolls; rgo.step ~40 operations on
  2-D fields. Both are negligible next to the column physics. They may also be called every n-th step with dt*n
  (stable up to dt = 2 h at T170 for rgo; currents.step limits its own Courant number).
* The geometry (`self.ocg`, `self.rgg`) is numpy and becomes jit constants; it depends on the coast (sst > 0 at the
  start), so a different start date with a different sea-ice edge recompiles (as the land mask already does).
* The ocean grid poleward of 60 degrees: the rgo layer is held at rest there (lat_max); currents.py still applies
  Ekman drift there, with a Courant limiter. Sea ice is not treated (columns with sst = 0 are land for the ocean).
* float32: T is carried in K; per-step advective increments are 1e-4 to 1e-2 K, above float32 resolution at 300 K
  (3e-5 K). If needed, carry T - 273.15 instead.
* Not tested inside mm2.py / under jit in this container (no JAX here). The functions use only xp operations that
  ocean.py already uses under jit, plus `xp.roll` and `xp.stack`. The numpy path is tested by
  scripts/ocean3d/test_currents.py and test_rgo.py (test_currents.py checks jax == numpy when JAX is installed).
