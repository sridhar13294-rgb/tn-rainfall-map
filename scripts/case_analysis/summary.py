"""One row per event: system, track, steering, ingredients on the rain day, western disturbance and background."""
import json, os, sys, datetime as dt, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
import indices
HERE = os.path.dirname(os.path.abspath(__file__))
from run import META, DAYS
def dist(a, b, c, d): return float(np.hypot((a - c) * 110.6, (b - d) * 111.3 * np.cos(np.radians(a))))
rows = []
for name, day in DAYS.items():
    D = dt.date.fromisoformat(day); dj = json.load(open(os.path.join(HERE, 'out', name, 'diag.json'))); S = dj['summary']; R = dj['rows']; P = S['target']
    E = Event(name, D); OT = origin_track(E, P); ks = sorted(OT)
    first = ks[0]; k0 = [k for k in ks if E.times[k].date() == D and E.times[k].hour == 0]
    cen = OT[k0[0]] if k0 else None
    # motion over the 24 h before the rain day 00 UTC
    kprev = [k for k in ks if (dt.datetime(D.year, D.month, D.day) - E.times[k]).total_seconds() == 86400]
    speed = dist(OT[kprev[0]][0], OT[kprev[0]][1], cen[0], cen[1]) / 24 if (kprev and cen) else None
    day_rows = [r for r in R if r['t'].startswith(D.isoformat())]
    mean = lambda k: float(np.nanmean([r[k] for r in day_rows if r.get(k) is not None])) if any(r.get(k) is not None for r in day_rows) else None
    wd = [(r['wd_anom_min'], r['lag_h'], r['wd_anom_lon']) for r in R if r.get('wd_anom_min') is not None and -7 * 24 - 12 <= r['lag_h'] <= 12]
    wdmin = min(wd) if wd else None
    k_msl = [r for r in day_rows if r.get('msl_min') is not None]
    m = indices.mjo(D); ph, amp = (m['rmm_phase'], m['rmm_amp']) if m['rmm_phase'] else (m['omi_phase'], m['omi_amp'])
    rows.append(dict(name=name, label=META.get(name, {}).get('label', name), day=day, top=P['top'], max=P['max'], lat=P['lat'], lon=P['lon'],
                     kind=S['kind'], msl_min=round(min(r['msl_min'] for r in k_msl), 1) if k_msl else None,
                     deficit=round(max(r['msl_deficit'] for r in k_msl), 1) if k_msl else None,
                     origin=(round(OT[first][0], 1), round(OT[first][1], 1), E.times[first].strftime('%d %b'), round((E.times[first] - dt.datetime(D.year, D.month, D.day)).total_seconds() / 86400, 1)),
                     centre=(round(cen[0], 1), round(cen[1], 1)) if cen else None, dist_km=round(dist(P['lat'], P['lon'], cen[0], cen[1])) if cen else None,
                     speed_kmh=round(speed, 1) if speed is not None else None, steer_mid=mean('steer_mid_kmh'),
                     pw=mean('pw'), pw_anom=mean('pw_anom'), wind850=mean('wind850_kmh'), wind925=mean('wind925_kmh'), div200=mean('div200'), rise=-mean('w500'), conv925=mean('conv925'),
                     cape=mean('cape'), olr=mean('olr'), shear=mean('shear_kmh'), sst=mean('sst'), sst_anom=mean('sst_anom'),
                     wd_min=round(wdmin[0]) if wdmin else None, wd_lag_d=round(wdmin[1] / 24, 1) if wdmin else None, wd_lon=round(wdmin[2]) if wdmin else None,
                     wd_on_day=mean('wd_anom_min'), wd_lon_on_day=mean('wd_anom_lon'), wedge200=mean('westerly_edge200'), wedge500=mean('westerly_edge500'), u200s=mean('u200_south'),
                     jet=mean('jet_max'), uswbay=mean('u850_swbay'), uswbay_anom=mean('u850_swbay_anom'), mjo_phase=ph, mjo_amp=amp, oni=indices.enso(D), dmi=indices.iod(D),
                     pw_d3=S['lags']['-3']['pw_anom'], pw_d1=S['lags']['-1']['pw_anom']))
    print(name, flush=True)
json.dump(rows, open(os.path.join(HERE, 'summary.json'), 'w'), indent=1, default=float)
