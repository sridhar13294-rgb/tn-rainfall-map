import datetime as dt, numpy as np, re
IX = '/home/claude/tn-rainfall-map/data/cases/era5/indices/'
RMM = {}
for l in open(IX + 'rmm.txt').read().splitlines()[2:]:
    p = l.split()
    try: RMM[dt.date(int(p[0]), int(p[1]), int(p[2]))] = (float(p[3]), float(p[4]), int(p[5]), float(p[6]))
    except Exception: pass
OMI = {}
for l in open(IX + 'omi.txt'):
    p = l.split()
    if len(p) >= 6:
        pc1, pc2 = float(p[3]), float(p[4]); x, y = pc2, -pc1          # OMI drawn on RMM-like axes (Kiladis et al. 2014)
        ang = np.degrees(np.arctan2(y, x)) % 360; phase = int(((ang - 180) % 360) // 45) + 1
        OMI[dt.date(int(p[0]), int(p[1]), int(p[2]))] = (x, y, phase, float(p[5]))
ONI = {}
SEAS = ['DJF', 'JFM', 'FMA', 'MAM', 'AMJ', 'MJJ', 'JJA', 'JAS', 'ASO', 'SON', 'OND', 'NDJ']
for l in open(IX + 'oni.txt').read().splitlines()[1:]:
    p = l.split(); ONI[(int(p[1]), SEAS.index(p[0]) + 1)] = float(p[3])  # centre month = index+1 (DJF -> Jan)
DMI = {}
for l in open(IX + 'dmi_monthly.txt').read().splitlines()[1:]:
    p = l.split()
    if len(p) == 13 and p[0].isdigit():
        for m in range(12):
            v = float(p[m + 1])
            if v > -99: DMI[(int(p[0]), m + 1)] = v
def rmm_phase(x, y):
    ang = np.degrees(np.arctan2(y, x)) % 360; return int(((ang - 180) % 360) // 45) + 1
def mjo(d):
    r = RMM.get(d); o = OMI.get(d)
    return dict(rmm_phase=r[2] if r else None, rmm_amp=round(r[3], 2) if r else None, omi_phase=o[2] if o else None, omi_amp=round(o[3], 2) if o else None)
def enso(d):
    m = d.month; return ONI.get((d.year, m - 1 if m > 1 else 1)) if False else ONI.get((d.year, m))
def iod(d):
    return DMI.get((d.year, d.month)) or DMI.get((d.year, d.month - 1))
if __name__ == '__main__':
    print(len(RMM), max(RMM), len(OMI), max(OMI))
    # check OMI phase vs RMM phase agreement where amplitude > 1
    agree = [abs(RMM[d][2] - OMI[d][2]) % 8 <= 1 or abs(RMM[d][2] - OMI[d][2]) % 8 == 7 for d in RMM if d in OMI and RMM[d][3] > 1 and OMI[d][3] > 1 and d.year >= 2000]
    print('OMI vs RMM phase within one:', round(np.mean(agree), 2), len(agree))
    for d in [dt.date(2015, 12, 1), dt.date(2023, 12, 17)]: print(d, mjo(d), enso(d), iod(d))
