"""How each member of the hemispheric physics ensemble differs (shared by the past-storm test and the live run).
No storylines: members differ only where the starting data and the model are genuinely uncertain."""
import numpy as np
from scipy import ndimage as nd
from ours_live_s import halton
def perturb(U, V, LAg, LOg, LEVS, k, amp_ic=1.0):
    """member k's starting winds: (1) mid-latitude waves (deviation from the zonal mean north of 25N) 80-120% as strong
    and shifted up to 3 deg east/west - a trough's depth and position are the least certain part of any analysis;
    (2) smooth random rotational wind errors of 1 m/s low down and 2 m/s aloft, on 1,500-4,000 km scales."""
    h = lambda b: halton(k, b)
    res = float(abs(LOg[0, 1] - LOg[0, 0]))
    sc = 0.8 + 0.4 * h(2); sh = (h(3) - 0.5) * 6.0; wm = np.clip((LAg - 25) / 10, 0, 1)
    rs = np.random.default_rng(500 + k)
    Kx = rs.uniform(2 * np.pi / 40, 2 * np.pi / 13, 8); Ky = rs.uniform(2 * np.pi / 40, 2 * np.pi / 13, 8) * rs.choice([-1, 1], 8); ph = rs.uniform(0, 2 * np.pi, 8)
    psi = sum(np.sin(Kx[i] * LOg + Ky[i] * LAg + ph[i]) for i in range(8))
    du = -np.gradient(psi, axis=0); dv = np.gradient(psi, axis=1); nrm = np.sqrt((du ** 2 + dv ** 2).mean()); du, dv = du / nrm, dv / nrm
    Uo, Vo = [], []
    for l in range(len(LEVS)):
        a = amp_ic * (1.0 if LEVS[l] >= 700 else 2.0)
        for X, dX, dst in ((U[l], du, Uo), (V[l], dv, Vo)):
            zm = X.mean(1, keepdims=True); dev = nd.shift(X - zm, (0, sh / res), order=1, mode='nearest')
            dst.append(X + wm * (zm + sc * dev - X) + a * dX)
    return Uo, Vo
def phys(k):
    """member k's model settings, spread evenly (Halton) over realistic ranges."""
    h = lambda b: halton(k, b)
    return dict(trough_scale=0.8 + 0.4 * h(2), trough_shift=(h(3) - 0.5) * 6.0, Ld15=0.9e6 + 0.6e6 * h(5), tau_v=3 + 6 * h(7), xo=0.4 + 0.2 * h(11),
                heat_f=0.5 + h(13), sppt=0.25 * h(17), dla=(h(29) - 0.5) * 1.0, dlo=(h(31) - 0.5) * 1.0, rate=h(37), gen=h(41), prec=h(43))
