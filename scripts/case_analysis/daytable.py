import json, sys, datetime as dt, numpy as np
sys.path.insert(0, '.')
from lib import *
import indices
COMP = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
def frm(deg_to):                                           # direction the wind comes FROM, 8 points
    return COMP[int(((deg_to + 180) % 360 + 22.5) // 45) % 8]
def table(name, day, lags=(-7, -6, -5, -4, -3, -2, -1, 0, 1)):
    d = json.load(open(f'out/{name}/diag.json')); rows = d['rows']; P = d['summary']['target']
    E = Event(name, day); OT = origin_track(E, P)
    out = []
    for n in lags:
        D = E.day + dt.timedelta(days=n); rs = [r for r in rows if r['t'].startswith(D.isoformat())]
        if not rs: continue
        m = lambda k: float(np.nanmean([r[k] for r in rs if r.get(k) is not None]))
        u = np.nanmean([np.sin(np.radians(r['wind925_to'])) * r['wind925_kmh'] for r in rs]); v = np.nanmean([np.cos(np.radians(r['wind925_to'])) * r['wind925_kmh'] for r in rs])
        k0 = [k for k in OT if E.times[k].date() == D and E.times[k].hour == 0]
        cen = OT[k0[0]] if k0 else None
        dist = None
        if cen: dist = float(np.hypot((cen[0] - P['lat']) * 110.6, (cen[1] - P['lon']) * 111.3 * np.cos(np.radians(P['lat']))))
        st = [r['steer_mid_kmh'] for r in rs if r.get('steer_mid_kmh') is not None]
        mj = indices.mjo(D)
        out.append(dict(day=D.isoformat(), lag=n, pw=round(m('pw')), pw_anom=round(m('pw_anom')), wind=round(float(np.hypot(u, v))), wind_from=frm(np.degrees(np.arctan2(u, v)) % 360),
                        rise=round(-m('w500') * 100) / 100, div200=round(m('div200'), 1), olr=round(m('olr')), cape=round(m('cape')), rh700=round(m('rh700')),
                        centre=(round(cen[0], 1), round(cen[1], 1), round(cen[2], 1)) if cen else None, dist=round(dist) if dist else None,
                        steer_mid=round(float(np.mean(st))) if st else None, mjo=(mj['rmm_phase'], mj['rmm_amp']) if mj['rmm_phase'] else (mj['omi_phase'], mj['omi_amp']),
                        wd_lon=round(m('wd_anom_lon')), wd_anom=round(m('wd_anom_min')), jet=round(m('jet_max')), wedge200=round(m('westerly_edge200'), 1) if any(r.get('westerly_edge200') for r in rs) else None,
                        wedge500=round(m('westerly_edge500'), 1) if any(r.get('westerly_edge500') for r in rs) else None, uswbay=round(m('u850_swbay'), 1), sst=round(m('sst'), 1), sst_anom=round(m('sst_anom'), 1)))
    return out
if __name__ == '__main__':
    for r in table(sys.argv[1], sys.argv[2]): print(r)
