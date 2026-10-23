"""Simple bulk surface forcing for the ocean-only tests (skill_wake.py, skill_monsoon.py): the project's ERA5 files have
winds, SST, 925 hPa temperature/humidity and OLR or rain, but no surface fluxes. Same formulas for every run, so the
differences between runs are what the ocean physics adds.
  stress   rho_a Cd |U| U, Large & Pond (1981): Cd = 1.2e-3 below 11 m/s, (0.49 + 0.065 |U|) 1e-3 above, capped at
           2.4e-3 (saturation in strong winds), |U| + 0.5 m/s
  latent   rho_a Lv Ce |U| (qs(SST) - qa), Ce = 1.2e-3, qa = q925 + 2 g/kg
  sensible rho_a cp Ch |U| (SST - Ta), Ch = 1.1e-3, Ta = t925 + 5 K (~750 m at a moist-adiabatic lapse rate)
  shortwave daily-mean insolation x 0.72 (clear sky) x (1 - 0.7 c) x 0.94 (sea albedo), with the diurnal cycle
  longwave  -55 (1 - 0.6 c) W m-2;  c = cloud fraction given by the caller."""
import math, numpy as np


def qsat(Tk, p=101000.0):
    es = 611.2 * np.exp(17.67 * (Tk - 273.15) / (Tk - 29.65)); return 0.622 * es / (p - 0.378 * es) * 0.98   # x0.98 salt water


def stress(U, V, mult=1.0):
    S = np.hypot(U, V) + 0.5; cd = np.minimum(np.where(S < 11.0, 1.2e-3, (0.49 + 0.065 * S) * 1e-3), 2.4e-3) * mult
    return 1.2 * cd * S * U, 1.2 * cd * S * V


def fluxes(Ts, U, V, qa925, ta925, cloud, LA, LO, when):
    """Qns (W m-2, into the sea; latent + sensible + net longwave) and net shortwave entering the sea."""
    S = np.hypot(U, V) + 0.5; qa = qa925 + 0.002; Ta = ta925 + 5.0
    lat_f = 1.2 * 2.5e6 * 1.2e-3 * S * np.maximum(qsat(Ts) - qa, 0.0); sen = 1.2 * 1004.0 * 1.1e-3 * S * (Ts - Ta)
    hr = when.hour + when.minute / 60.0 + LO / 15.0
    doy = when.timetuple().tm_yday; decl = math.radians(23.44) * math.sin(2 * math.pi * (284 + doy) / 365.0)
    phi = np.radians(LA)
    cz = np.maximum(np.sin(phi) * math.sin(decl) + np.cos(phi) * math.cos(decl) * np.cos(np.radians(15 * (hr - 12))), 0)
    hs = np.arccos(np.clip(-np.tan(phi) * math.tan(decl), -1, 1))
    czm = (hs * np.sin(phi) * math.sin(decl) + np.cos(phi) * math.cos(decl) * np.sin(hs)) / math.pi
    daily = 1361.0 * czm
    sw = 0.72 * daily * (1 - 0.7 * cloud) * cz / np.maximum(czm, 1e-3) * 0.94
    return -55.0 * (1 - 0.6 * cloud) - lat_f - sen, sw
