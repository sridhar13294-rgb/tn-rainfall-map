# MEGAM formulation revision history (Stage 1)

Baseline: `MEGAM_physics_equations.md` (31 Oct 2026) = the formulation of the CONTROL. This file records every change since:
what the equation is, whether it is a coding fix or a new option, its status, and the evidence. All options are default OFF
unless marked ADOPTED. Details and registered gates: docs/rootcause.md.

| Option (mm2) | Process | Kind | Formulation | Since | Status | Key evidence |
|---|---|---|---|---|---|---|
| pbl_tm 1 | BL (Troen-Mahrt) | option | ws = (u*^3 + 7 eps kappa w*^3)^1/3, counter-gradient flux | 25 Oct | F2 dropped 4 Nov; to be re-tested alone with bl_lcl (D-F2e) | F2 = pbl_tm + sh_mflux |
| (bug fix) pbl_tm counter-gradient | BL | CODING BUG FIX | F = rho K_bl gamma (was rho max(K_bl, K_free) gamma) | 3 Nov | ADOPTED (code) | flux was up to 18.6x surface flux; 75 L blow-up; no effect at 32 L |
| sh_mflux 0.03 | shallow | option | MSE/q relaxation time = layer mass / (2 Mb) | 29 Oct | F2 dropped 4 Nov; to be re-tested alone on the base (D-F2a) | P1 cold 850, P4 coastal convection |
| evap_ifs 1 | rain evaporation | option | IFS Kessler form, convective rain below cloud base | 30 Oct | REJECTED | fails exam, genesis, TN rain alone |
| rad_prm lw_cnt 0.667 | LW continuum | option | continuum x1.0 (was x1.5) | 30 Oct | on hold | passes exam/genesis alone, TN rain 1.60 |
| ck_z 1 | surface exchange | option | ck brought from 10 m to the lowest level (log law) | 30 Oct | on hold | exam +2.7 % alone |
| cld_pdf | cloud | option | uniform total-water PDF (D1) | 30 Oct | not adopted | |
| ent_top | BL | option | cloud-top entrainment (D2) | 30 Oct | REJECTED | |
| shallow 'mf' + sh_trig + sh_clos 0.6 | shallow | option | non-raining mass-flux plume, IFS-type closure | 25 Oct / 3 Nov | REJECTED | 850 -2.0 K, TN rain 1.91, genesis 12 % (3 Nov) |
| sfc_imp 1 | surface coupling | NUMERICAL fix (option) | implicit surface heat/moisture flux + implicit land skin T | 4 Nov | candidate | 75 L: all 19 exam starts complete; 32 L neutral; Andes h_bl 361 > 300 K/day |
| bl_lcl 1 | BL depth | option | K-profile depth <= LCL of lowest-level air | 4 Nov | candidate | P1 gates pass; genesis 14 % (with F2); q850 now -0.7 g/kg |
| cmt_mf 1 | momentum transport | option | Gregory 1997 / ECMWF mass-flux CMT, du/dt = g d/dp [M (u_u - u)], C_u 0.7 | 30 Oct (code unchanged since commit 601c27c2) | candidate | P3 gates pass alone (4 Nov); genesis 31 % = control; 30 Oct rejection on tracks (+17/+34 %) now under re-diagnosis |
| BASE1 = control + cmt_mf | base | ADOPTED AS BASE 4 Nov 19:23 (Sridhar; condition: F2's disadvantages D-F2a..f addressed, HANDOFF) | | 4 Nov | full suite: PASS 1,5,7,8a; FAIL 2 (= control), 3 (Vardah -5.7, Michaung +7.4 hPa), 4 (+9 %), 6 (TN rain 1.81) | control re-run on current code pending (TN rain 1.43 suspect) |
| PKG = F2 + bl_lcl + cmt_mf | combined | candidate | | 4 Nov | REJECTED (track 72 h +31 %) | easterly bias larger; southern-lows hypothesis under test |

Control formulations that are known weak (not yet replaced): shallow MSE/q relaxation (tau 1 h, exchange mass flux 0.3-0.9 vs observed
0.02-0.03 kg m-2 s-1); CMT relaxation to the cloud-layer mean with tau_cmt 6 h (~8x too fast); saturation adjustment with no stored
cloud water (all condensate rains in the step); explicit surface coupling (unstable on thin layers); sequential process split
(order: surface -> BL -> deep -> shallow -> CMT -> condensation/rain -> radiation), which couples every fix to the processes after it.
