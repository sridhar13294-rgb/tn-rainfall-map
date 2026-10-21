"""Barotropic vorticity model of the steering flow (our own, no forecast model involved).
The deep-layer mean wind (850/700/500/200 hPa, weights 0.3/0.3/0.25/0.15) is turned into vorticity and stepped forward
with  d(zeta + f)/dt = -J(psi, zeta + f)  on a Mercator grid (1 deg), so ridges, troughs, highs and other circulations
move and change by themselves: they are carried by the flow and drift west-northwest under the beta effect.
Boundaries keep their starting stream function; a sponge near the edges and weak diffusion keep it stable.
This is the classic barotropic track-model idea (BAM / VICBAR family); it has no heating, friction or vertical structure."""
import math, numpy as np
from scipy.fft import dstn, idstn
from scipy.interpolate import RegularGridInterpolator as RGI
A = 6.371e6; OM = 7.292e-5; WTS = {850: 0.3, 700: 0.3, 500: 0.25, 200: 0.15}
class BVE:
    def __init__(self, lat0, lat1, lon0, lon1, res=1.0):
        d = math.radians(res); self.lon = np.arange(lon0, lon1 + 1e-6, res)
        y0, y1 = [math.log(math.tan(math.pi / 4 + math.radians(p) / 2)) for p in (lat0, lat1)]
        self.y = np.arange(y0, y1 + 1e-9, d); self.lat = np.degrees(2 * np.arctan(np.exp(self.y)) - math.pi / 2)
        self.h = A * d                                               # grid step in Mercator metres (same in x and y)
        self.LAT, self.LON = np.meshgrid(self.lat, self.lon, indexing='ij'); self.m = 1 / np.cos(np.radians(self.LAT))
        self.f = 2 * OM * np.sin(np.radians(self.LAT)); ny, nx = self.LAT.shape
        k = np.arange(1, ny - 1); l = np.arange(1, nx - 1)
        self.eig = ((2 * np.cos(np.pi * k / (ny - 1)) - 2)[:, None] + (2 * np.cos(np.pi * l / (nx - 1)) - 2)[None, :]) / self.h ** 2
        J, I = np.meshgrid(np.arange(ny), np.arange(nx), indexing='ij'); dist = np.minimum.reduce([J, ny - 1 - J, I, nx - 1 - I]); w = 6
        e = np.clip((w - dist) / w, 0, 1)
        self.sponge = e / (2 * 86400)                                 # relax to the start near the edges (2-day time scale)
    def regrid(self, field, lats, lons):
        f = RGI((lats, lons), field, bounds_error=False, fill_value=None)
        return f(np.stack([self.LAT.ravel(), self.LON.ravel()], -1)).reshape(self.LAT.shape)
    def dx(self, a): g = np.zeros_like(a); g[:, 1:-1] = (a[:, 2:] - a[:, :-2]) / (2 * self.h); g[:, 0] = (a[:, 1] - a[:, 0]) / self.h; g[:, -1] = (a[:, -1] - a[:, -2]) / self.h; return g
    def dy(self, a): g = np.zeros_like(a); g[1:-1] = (a[2:] - a[:-2]) / (2 * self.h); g[0] = (a[1] - a[0]) / self.h; g[-1] = (a[-1] - a[-2]) / self.h; return g
    def vort(self, u, v):
        m = self.m; return m * m * (self.dx(v / m) - self.dy(u / m))
    def boundary_psi(self, u, v):
        """stream function on the edge from the wind across it (psi_x = v/m, psi_y = -u/m); any net inflow is spread evenly."""
        m = self.m; ny, nx = u.shape; h = self.h
        s = np.concatenate([[0], np.cumsum(0.5 * (v[0, 1:] + v[0, :-1]) / (0.5 * (m[0, 1:] + m[0, :-1])) * h)])        # south, west -> east
        e = s[-1] + np.concatenate([[0], np.cumsum(-0.5 * (u[1:, -1] + u[:-1, -1]) / (0.5 * (m[1:, -1] + m[:-1, -1])) * h)])   # east, south -> north
        n = e[-1] - np.concatenate([[0], np.cumsum(0.5 * (v[-1, ::-1][1:] + v[-1, ::-1][:-1]) / (0.5 * (m[-1, ::-1][1:] + m[-1, ::-1][:-1])) * h)])  # north, east -> west
        w = n[-1] - np.concatenate([[0], np.cumsum(-0.5 * (u[::-1, 0][1:] + u[::-1, 0][:-1]) / (0.5 * (m[::-1, 0][1:] + m[::-1, 0][:-1])) * h)])  # west, north -> south
        per = np.concatenate([s, e[1:], n[1:], w[1:]]); gap = per[-1] - per[0]; per = per - gap * np.arange(len(per)) / (len(per) - 1)
        P = np.zeros((ny, nx)); i = 0
        P[0, :] = per[i:i + nx]; i += nx - 1
        P[:, -1] = per[i:i + ny]; i += ny - 1
        P[-1, ::-1] = per[i:i + nx]; i += nx - 1
        P[::-1, 0] = per[i:i + ny]
        return P
    def poisson(self, zeta, Pb):
        rhs = zeta / self.m ** 2; h2 = self.h ** 2; r = rhs[1:-1, 1:-1].copy()
        r[0, :] -= Pb[0, 1:-1] / h2; r[-1, :] -= Pb[-1, 1:-1] / h2; r[:, 0] -= Pb[1:-1, 0] / h2; r[:, -1] -= Pb[1:-1, -1] / h2
        P = Pb.copy(); P[1:-1, 1:-1] = idstn(dstn(r, type=1) / self.eig, type=1); return P
    def jac(self, p, q):
        """Arakawa (1966) Jacobian on the interior, Mercator x/y."""
        J = np.zeros_like(p); h = self.h
        pp, qq = p, q
        a = (pp[1:-1, 2:] - pp[1:-1, :-2]) * (qq[2:, 1:-1] - qq[:-2, 1:-1]) - (pp[2:, 1:-1] - pp[:-2, 1:-1]) * (qq[1:-1, 2:] - qq[1:-1, :-2])
        b = pp[1:-1, 2:] * (qq[2:, 2:] - qq[:-2, 2:]) - pp[1:-1, :-2] * (qq[2:, :-2] - qq[:-2, :-2]) - pp[2:, 1:-1] * (qq[2:, 2:] - qq[2:, :-2]) + pp[:-2, 1:-1] * (qq[:-2, 2:] - qq[:-2, :-2])
        c = qq[2:, 1:-1] * (pp[2:, 2:] - pp[2:, :-2]) - qq[:-2, 1:-1] * (pp[:-2, 2:] - pp[:-2, :-2]) - qq[1:-1, 2:] * (pp[2:, 2:] - pp[:-2, 2:]) + qq[1:-1, :-2] * (pp[2:, :-2] - pp[:-2, :-2])
        J[1:-1, 1:-1] = (a + b + c) / (12 * h * h); return J
    def winds(self, P):
        m = self.m; return -m * self.dy(P), m * self.dx(P)
    def run(self, u0, v0, hours, every=6, dt=900.0, nu=2.0e4, robert=0.1):
        """u0, v0 on this grid (m/s). Returns list of (hour, u, v) every `every` hours, starting at 0."""
        z0 = self.vort(u0, v0); Pb = self.boundary_psi(u0, v0); P = self.poisson(z0, Pb)
        q_old = z0 + self.f; q = q_old.copy(); out = [(0, *self.winds(P))]; nstep = int(round(hours * 3600 / dt)); per = int(round(every * 3600 / dt))
        lap = lambda a: self.m ** 2 * ((np.roll(a, 1, 1) + np.roll(a, -1, 1) + np.roll(a, 1, 0) + np.roll(a, -1, 0) - 4 * a) / self.h ** 2)
        for n in range(1, nstep + 1):
            z = q - self.f
            tend = -self.m ** 2 * self.jac(P, q) + nu * lap(z) - self.sponge * (z - z0)
            tend[0, :] = tend[-1, :] = tend[:, 0] = tend[:, -1] = 0
            if n == 1: q_new = q + dt * tend
            else: q_new = q_old + 2 * dt * tend
            q_f = q + robert * (q_new - 2 * q + q_old) if n > 1 else q
            q_old, q = q_f, q_new
            P = self.poisson(q - self.f, Pb)
            if n % per == 0: out.append((n * dt / 3600, *self.winds(P)))
        return out
