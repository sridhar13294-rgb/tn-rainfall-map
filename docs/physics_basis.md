# MEGAM physics basis register (equation-driven, not parameter-driven)
Rule (Sridhar, 30 Oct): for every process - governing law -> derived equation -> assumptions -> units and signs -> conservation -> limiting cases -> literature -> status. A simplified rule is replaced only when the physics and the evidence justify it; every replacement is derived and checked offline before any GPU test (as done for mass-flux CMT, scratchpad deriv/cmt.py -> scripts/cyclone/mm/cmt_derivation.py).

| Process | Governing law / reference | Current implementation | Basis status | Action |
| --- | --- | --- | --- | --- |
| Dynamics | Hydrostatic primitive equations (Dinosaur, semi-Lagrangian semi-implicit) | library | derived (library) | A-A2 limiter: horizontal-only as IFS |
| Surface fluxes | Monin-Obukhov bulk formulas (Louis 1979 stability), Charnock | bulk formulas | VERIFIED (audit 30 Oct) | - |
| Boundary layer | K-profile (Troen & Mahrt 1986, Hong & Pan 1996) | old velocity scale (pbl_tm 0) | DEFECT: velocity scale ~2.3x too small (B-L1) | pbl_tm 1 (derived form exists) |
| Cloud-top mixing | Radiatively driven entrainment (Lock et al. 2000; IFS) | absent | MISSING (B-L3) | derive + implement |
| Shallow convection | Mass-flux (Siebesma et al. 2003; IFS) | MSE relaxation to column mean, tau 1 h | NOT physically based (B-C2): implied flux 10-40x observed | sh_mflux interim; mass-flux shallow plume as final |
| Shallow/deep decision | One plume, cloud depth (IFS) | two parcels | inconsistent (B-C1) | single plume decision |
| Deep convection | Entraining mass-flux plume, CAPE closure (Tiedtke 1989, Bechtold 2008) | conv_mf | VERIFIED by reading (flux form, condensation sink correct) | B-C3 source layer, B-C4 cap |
| Momentum transport | Mass-flux CMT (Gregory et al. 1997) | relaxation tau 6 h | NOT physically based (B-M1): offline derivation shows shear erased +50..+80 m/s/day | cmt_mf implemented + derived; testing |
| Grid-scale condensation | Saturation adjustment + sub-grid cloud fraction (Sundqvist 1989 / Tiedtke 1993) | 100% RH, instant rain-out | inconsistent with radiation clouds (B-G1) | consistent cloud fraction (F6) |
| Rain evaporation | Kessler-type, IFS form | tuned k_evap | basis unclear (B-G2) | derive dimensionally |
| Radiation | 2-stream LW/SW, diagnostic clouds | radcloud | heating conversion VERIFIED; cloud threshold inconsistent (B-R1) | F6 |
| Inserted vortex | Gradient-wind + hydrostatic balance (Holland 1980) | bogus() | balance VERIFIED; moisture profile assumed (A-B4) | use analysed / observed humidity |
| Ocean mixed layer | Slab + wind cooling | simple | simplified (Stage 2 replaces) | Stage 2 |
| Drag | Lott & Miller 1997 | gwd_tend (new) | derived, offline-checked | score winds |
