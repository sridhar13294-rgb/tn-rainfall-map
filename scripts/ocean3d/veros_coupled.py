"""Stage 2, step B: a Veros ocean that takes its surface forcing from outside (the atmosphere model, or ERA5 for an
ocean-only run) and hands back SST and surface currents. NOT YET RUN: needs `pip install veros` and a GPU (Kaggle);
the container this was written in cannot install Veros. See docs/stage2_ocean.md for the speed verdict.

COUPLING INTERFACE (one call per coupling step, every 1-3 h of model time; all fields on the atmosphere grid [X, Y],
X = longitude, Y = latitude, as mm2.py's nodes; regridding to/from Veros is done here, bilinear, numpy):
  atmosphere -> ocean (means over the coupling interval)
     taux, tauy   N m-2      wind stress on the sea
     qns          W m-2      non-solar heat flux INTO the sea: LW down - sigma SST^4 - sensible - latent
     sw           W m-2      net shortwave entering the sea (absorbed with depth, Jerlov I two-band, as ocean.py)
     emp          kg m-2 s-1 evaporation minus precipitation (virtual salt flux S (E - P) / rho0)
  ocean -> atmosphere (at the end of the interval)
     sst          K          top-level temperature (Veros top level ~10 m thick at 1-2 degrees: a bulk SST)
     usfc, vsfc   m s-1      top-level current (optional: relative-wind stress, advection of the 1-D columns)
  the atmosphere keeps its own 1-D columns where Veros has no ocean (marginal seas Veros removes, lakes).

  usage:   oc = VerosOcean(lat2d, lon2d, sea, nx=180, ny=80, nz=40, dt=1800.0)       # once (set-up, spin-up below)
           oc.spin_up(days)                                                           # Veros' own climatological forcing
           sst, us, vs = oc.couple(taux, tauy, qns, sw, emp, seconds=3600.0)          # each coupling step

INITIAL STATE: Veros' global_flexible setup starts from its annual-mean climatology at rest; currents need months to
years of spin-up (geostrophic adjustment of the upper ocean takes weeks, the gyres years). Plan: a one-off spin-up run
(climatological forcing, 2-5 model years, saved with Veros' restart files to a release asset), then for each forecast
nudge the top 300 m to WOA23/RTOFS for the start month for a few days (t_star/s_star restoring). Not done yet."""
import numpy as np


def bilinear(src_lat, src_lon, A, dst_lat, dst_lon):
    """A [len(src_lon), len(src_lat)] on a regular lon/lat grid (lon periodic) -> points dst (2-D arrays)."""
    from scipy.interpolate import RegularGridInterpolator as RGI
    lo = np.concatenate([src_lon, [src_lon[0] + 360.0]]); Ae = np.concatenate([A, A[:1]], 0)
    la = np.asarray(src_lat); o = np.argsort(la); la = la[o]; Ae = Ae[:, o]
    f = RGI((lo, la), Ae, bounds_error=False, fill_value=None)
    return f(np.stack([(np.asarray(dst_lon) - lo[0]) % 360.0 + lo[0], np.asarray(dst_lat)], -1))


class VerosOcean:
    def __init__(self, lat2d, lon2d, sea, nx=180, ny=80, nz=40, dt=1800.0):
        from veros import veros_routine, veros_kernel, KernelOutput
        from veros.core.operators import numpy as npx, update, at
        from veros.setups.global_flexible import GlobalFlexibleResolutionSetup as Base
        from veros.setups.global_flexible.global_flexible import set_forcing_kernel
        outer = self; self.LA, self.LO = np.asarray(lat2d, float), np.asarray(lon2d, float); self.sea = np.asarray(sea, bool)
        self.ext = None                                                              # None: climatological forcing

        class Coupled(Base):
            @veros_routine
            def set_forcing(self, state):          # Veros needs the first argument to be called "self"
                vs = state.variables
                if outer.ext is None: vs.update(set_forcing_kernel(state)); return
                s = state.settings; cp0 = 3991.86795711963; F = outer.ext
                vs.surface_taux = update(vs.surface_taux, at[2:-2, 2:-2], F['taux'])
                vs.surface_tauy = update(vs.surface_tauy, at[2:-2, 2:-2], F['tauy'])
                if s.enable_tke:
                    vs.forc_tke_surface = update(vs.forc_tke_surface, at[2:-2, 2:-2], (np.hypot(F['taux'], F['tauy']) / s.rho_0) ** 1.5)
                m = vs.maskT[2:-2, 2:-2, -1]
                vs.forc_temp_surface = update(vs.forc_temp_surface, at[2:-2, 2:-2], F['qns'] * m / cp0 / s.rho_0)
                S0 = vs.salt[2:-2, 2:-2, -1, vs.tau]
                vs.forc_salt_surface = update(vs.forc_salt_surface, at[2:-2, 2:-2], S0 * F['emp'] / s.rho_0 * m)
                if s.enable_tempsalt_sources:
                    vs.temp_source = update(vs.temp_source, at[2:-2, 2:-2, :], F['sw'][..., None] * vs.divpen_shortwave[None, None, :]
                                            * vs.maskT[2:-2, 2:-2, :] / cp0 / s.rho_0)

        self.sim = Coupled(override=dict(nx=nx, ny=ny, nz=nz, dt_mom=dt, dt_tracer=dt, runlen=0.0))
        self.sim.setup(); st = self.sim.state; vs = st.variables
        self.xt = np.asarray(vs.xt[2:-2]); self.yt = np.asarray(vs.yt[2:-2]); self.dt = dt
        XT, YT = np.meshgrid(self.xt, self.yt, indexing='ij'); self.XT, self.YT = XT, YT
        self.wet = np.asarray(vs.maskT[2:-2, 2:-2, -1]) > 0
        self.has_ocean = (bilinear(self.yt, self.xt, self.wet.astype(float), self.LA, self.LO) > 0.5) & self.sea

    def _to_veros(self, A):                                                           # atmosphere grid -> Veros t grid
        lon = self.LO[:, 0]; lat = self.LA[0]; return bilinear(lat, lon, np.nan_to_num(A), self.YT, self.XT)

    def spin_up(self, days):
        self.ext = None; n = int(round(days * 86400 / self.dt))
        for _ in range(n): self.sim.step(self.sim.state)

    def couple(self, taux, tauy, qns, sw, emp, seconds):
        self.ext = {k: self._to_veros(v) for k, v in dict(taux=taux, tauy=tauy, qns=qns, sw=sw, emp=emp).items()}
        for _ in range(max(1, int(round(seconds / self.dt)))): self.sim.step(self.sim.state)
        vs = self.sim.state.variables; T = np.asarray(vs.temp[2:-2, 2:-2, -1, vs.tau]) + 273.15
        U = np.asarray(vs.u[2:-2, 2:-2, -1, vs.tau]); V = np.asarray(vs.v[2:-2, 2:-2, -1, vs.tau])
        back = lambda A: bilinear(self.yt, self.xt, np.where(self.wet, A, np.nan), self.LA, self.LO)
        T = np.where(self.wet, T, np.nan)
        # fill land of the Veros grid from the nearest sea so that bilinear values at the coast stay sensible
        from scipy import ndimage as ndi
        _, idx = ndi.distance_transform_edt(~self.wet, return_indices=True)
        fill = lambda A: A[tuple(idx)]
        return (bilinear(self.yt, self.xt, fill(T), self.LA, self.LO), bilinear(self.yt, self.xt, fill(U), self.LA, self.LO),
                bilinear(self.yt, self.xt, fill(V), self.LA, self.LO))
