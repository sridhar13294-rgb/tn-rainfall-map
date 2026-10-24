"""Open observations for the start of our model, for one run time t0 (runs on GitHub Actions: RUN word "obs").

python obs_fetch.py [run] YYYYMMDDHH | latest          (latest = the last 00/06/12/18 UTC at least 3 h ago)
Window: t0 - 6 h ... t0 + 3 h (not past now). Output /tmp/cyc_out/obs_<run>.npz, log data/cyclone/obs_log.txt.

Sources (all free, no login, checked Oct 2026; see docs/obs_assimilation.md):
  SYNOP, SHIP, TEMP  NOAA NWS Telecommunication Gateway raw GTS bulletins, https://tgftp.nws.noaa.gov/SL.us008001/DF.an/
                     DC.sflnd/DS.synop, DC.sfmar/DS.ships, DC.vsndn/DS.raobf (files sn.0000-sn.0300, a new one every ~5 min,
                     >= 24 h kept); station positions from https://tgftp.nws.noaa.gov/data/nsd_bbsss.txt. Global (cheap).
                     Fallbacks for India only: Ogimet getsynop (one request; Ogimet limits queries per IP) and the
                     University of Wyoming sounding service (weather.uwyo.edu/wsgi/sounding, one request per station).
  METAR              NOAA Aviation Weather Center data API https://aviationweather.gov/api/data/metar (JSON; <= 400 rows
                     per request, 100 requests/min - the domain is tiled, tiles split when full).
  Scatterometer      ASCAT-B and ASCAT-C 25-km winds (EUMETSAT OSI SAF, processed by KNMI) from the KNMI Data Platform
                     open-data API with KNMI's published anonymous key (shared quota 50 requests/min; set KNMI_API_KEY for
                     a registered key). HY-2B/C winds need OSI SAF registration; PO.DAAC needs an Earthdata login.
  Satellite rain     NOAA CPC CMORPH real-time 8 km / 30 min (https://ftp.cpc.ncep.noaa.gov/precip/CMORPH_RT/GLOBE/), the
                     grid read from its GrADS control file; fallback CHRS PERSIANN-CCS 0.04 deg (6-hourly, else hourly).
                     6-h accumulation ending at t0 on 0.25 deg. (GPM IMERG and GSMaP need registration.)
  Lightning          this repository's lightning reference (lightning-data branch, from IMD lightning maps): strike
                     cells (0.05 deg, 20-min maps every 15 min) counted on 0.25 deg; the branch keeps only 2 h of positions,
                     so a 6-h total needs lightning.py to keep 6 h (a main-branch change). Plus a 6-h activity proxy from
                     the 3-day movement-vector history.
Record format (npz arrays, one row per observed value): type (synop, metar, ship, temp, scat), sid, lat, lon (0-360),
p (hPa; NaN for surface reports - station pressure where known), z (station height / level height, m), time (unix s),
var (mslp, ps [Pa]; t, td [K]; u, v [m/s]; z [m]), value, err (error estimate, same units; nudge.obs_error).
Gridded: rain6 [lat, lon] mm (NaN = no data), rain_lat, rain_lon, rain_src, rain_hours; ltg6, ltg_act6, ltg_hours."""
import os, sys, re, io, gzip, bz2, json, math, time, calendar, subprocess, urllib.request, urllib.parse, datetime as dt
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import socket
_gai = socket.getaddrinfo
socket.getaddrinfo = lambda h, *a, **k: [x for x in _gai(h, *a, **k) if x[0] == socket.AF_INET] or _gai(h, *a, **k)   # GitHub runners: no IPv6 route
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, 'mm'))
import nudge as NG

OUT = '/tmp/cyc_out'; ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
LOGF = os.path.join(ROOT, 'data', 'cyclone', 'obs_log.txt')
DOM = dict(lat0=-40.0, lat1=40.0, lon0=30.0, lon1=120.0)                 # domain for the per-request sources
INDIA = (6.0, 37.5, 68.0, 98.0)                                           # lat0, lat1, lon0, lon1 (for counts)
UA = 'tn-rainfall-map cyclone study (github.com/sridhar13294-rgb/tn-rainfall-map)'
UTC = dt.timezone.utc
TG = 'https://tgftp.nws.noaa.gov/SL.us008001/DF.an/'
NSD = 'https://tgftp.nws.noaa.gov/data/nsd_bbsss.txt'
AWC = 'https://aviationweather.gov/api/data/metar'
KNMI = 'https://api.dataplatform.knmi.nl/open-data/v1/datasets/{ds}/versions/{ver}/files'
# KNMI's anonymous key, published for everyone on developer.dataplatform.knmi.nl/open-data-api (valid to 1 Aug 2027)
KNMI_ANON = 'eyJvcmciOiI1ZTU1NGUxOTI3NGE5NjAwMDEyYTNlYjEiLCJpZCI6IjUzYTg1ZDBhMmQ5YzRkYzJiYWNlNzQ4NTQ2Zjk4ODExIiwiaCI6Im11cm11cjEyOCJ9'
SCAT_SETS = [('osisaf_ascat_b_250', 'nrt', 'metopb'), ('osisaf_ascat_c_250', 'nrt', 'metopc')]
CMORPH = 'https://ftp.cpc.ncep.noaa.gov/precip/CMORPH_RT/GLOBE/'
PCCS = 'https://persiann.eng.uci.edu/CHRSdata/PERSIANN-CCS/'
STD = (1000, 925, 850, 700, 500, 400, 300, 250, 200, 150, 100)
KT = 0.514444

_log = []
def log(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); _log.append(s)

def http(url, timeout=60, tries=3, headers=None, quiet=False):
    """GET -> bytes (None for 204/404). Retries on network errors and 429/5xx."""
    h = {'User-Agent': UA}; h.update(headers or {}); err = None
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
                return r.read() if r.status != 204 else None
        except urllib.error.HTTPError as e:
            if e.code in (404, 410): return None
            err = e
            if e.code not in (429, 500, 502, 503, 504): break
        except Exception as e:
            err = e
        time.sleep(2 + 4 * k)
    if not quiet: log('  http failed', url[:150], repr(err)[:120])
    raise IOError(f'{url}: {err!r}')

def unpack(buf):
    if buf[:2] == b'\x1f\x8b': return gzip.decompress(buf)
    if buf[:3] == b'BZh': return bz2.decompress(buf)
    return buf

def listing(url):
    """names linked from an Apache/nginx directory index, with their modification time when shown."""
    html = http(url, timeout=60).decode('latin-1', 'replace'); out = []
    for line in html.splitlines():
        for m in re.finditer(r'href="([^"?]+)"[^>]*>[^<]*</a>(?:</td><td[^>]*>)?\s*(\d{1,2}-[A-Za-z]{3}-\d{4} \d{2}:\d{2}|\d{4}-\d{2}-\d{2} \d{2}:\d{2})?', line):
            name, ts = m.group(1), m.group(2); t = None
            if ts:
                for fmt in ('%d-%b-%Y %H:%M', '%Y-%m-%d %H:%M'):
                    try: t = dt.datetime.strptime(ts, fmt).replace(tzinfo=UTC); break
                    except ValueError: pass
            out.append((name, t))
    return out

# ================================================================================================ records
class Recs:
    def __init__(self): self.r = []
    def add(self, typ, sid, lat, lon, p, z, t, var, val, err=None):
        if val is None or not np.isfinite(val) or lat is None or lon is None: return
        if not (-90 <= lat <= 90): return
        if err is None: err = NG.obs_error(typ, var, p, z)
        self.r.append((typ, str(sid)[:12], float(lat), float(lon) % 360.0, np.nan if p is None else float(p), np.nan if z is None else float(z),
                       int(t), var, float(val), float(err)))
    def wind(self, typ, sid, lat, lon, p, z, t, ddeg, spd):
        if ddeg is None or spd is None: return
        u = -spd * math.sin(math.radians(ddeg)); v = -spd * math.cos(math.radians(ddeg))
        self.add(typ, sid, lat, lon, p, z, t, 'u', u); self.add(typ, sid, lat, lon, p, z, t, 'v', v)
    def arrays(self):
        """record arrays; a report received more than once (re-sent, corrected) is kept once - the last one received."""
        u = {}
        for x in self.r: u[(x[0], x[1], round(x[2], 3), round(x[3], 3), None if x[4] != x[4] else round(x[4], 1), x[6], x[7])] = x
        self.r = list(u.values())
        if not self.r:
            return dict(type=np.zeros(0, '<U5'), sid=np.zeros(0, '<U12'), lat=np.zeros(0, np.float32), lon=np.zeros(0, np.float32),
                        p=np.zeros(0, np.float32), z=np.zeros(0, np.float32), time=np.zeros(0, np.int64), var=np.zeros(0, '<U4'),
                        value=np.zeros(0), err=np.zeros(0, np.float32))
        c = list(zip(*self.r))
        return dict(type=np.array(c[0], '<U5'), sid=np.array(c[1], '<U12'), lat=np.array(c[2], np.float32), lon=np.array(c[3], np.float32),
                    p=np.array(c[4], np.float32), z=np.array(c[5], np.float32), time=np.array(c[6], np.int64), var=np.array(c[7], '<U4'),
                    value=np.array(c[8], np.float64), err=np.array(c[9], np.float32))

def unix(t): return calendar.timegm(t.utctimetuple())

def obs_time(day, hour, t0, minute=0):
    """the datetime with this day-of-month and hour closest to t0 (bulletins carry no month/year)."""
    best = None
    for dm in (-1, 0, 1):
        y, m = t0.year, t0.month + dm
        if m == 0: y, m = y - 1, 12
        if m == 13: y, m = y + 1, 1
        try: c = dt.datetime(y, m, day, hour, minute, tzinfo=UTC)
        except ValueError: continue
        if best is None or abs(c - t0) < abs(best - t0): best = c
    return best if best is not None and abs(best - t0) <= dt.timedelta(days=2) else None

def mslp_reduce(p_stn_hpa, z, T_k):
    """station pressure -> MSLP the way the model does it (mm2 post(): mean column temperature T + 0.0065 z / 2)."""
    return p_stn_hpa * math.exp(NG.G * z / (NG.RD * (T_k + 0.0065 * z / 2)))

def td_from_rh(T, rh):
    e = rh * 611.2 * math.exp(17.67 * (T - 273.15) / (T - 29.65)); x = math.log(max(e, 1e-3) / 611.2)
    return 273.15 + 243.5 * x / (17.67 - x)

# ================================================================================================ stations
def dms(s):
    s = s.strip()
    m = re.fullmatch(r'(\d+)-(\d+)(?:-(\d+))?([NSEW])', s)
    if not m: return None
    v = int(m.group(1)) + int(m.group(2)) / 60 + (int(m.group(3) or 0)) / 3600
    return -v if m.group(4) in 'SW' else v

def stations():
    txt = http(NSD, timeout=120).decode('latin-1'); S = {}
    for line in txt.splitlines():
        f = line.split(';')
        if len(f) < 12: continue
        wmo = f[0].strip() + f[1].strip()
        if not re.fullmatch(r'\d{5}', wmo): continue
        la, lo = dms(f[7]), dms(f[8]); ula, ulo = dms(f[9]), dms(f[10])
        num = lambda x: float(x) if re.fullmatch(r'-?\d+(\.\d+)?', x.strip() or 'x') else None
        S[wmo] = dict(lat=la, lon=lo, elev=num(f[11]), ualat=ula, ualon=ulo, uaelev=num(f[12]) if len(f) > 12 else None, country=f[5], name=f[3])
    return S

# ================================================================================================ GTS bulletins (NWS TGFTP)
HEAD = re.compile(r'^([A-Z]{4}\d{2})\s+([A-Z]{4})\s+(\d{6})(?:\s+[A-Z]{3})?\s*$')
def bulletins(raw):
    txt = raw.decode('latin-1').replace('\r', '')
    for chunk in re.split(r'[\x01\x03]', txt):
        lines = [l.strip() for l in chunk.split('\n') if l.strip()]
        for k, l in enumerate(lines[:3]):
            m = HEAD.match(l)
            if m: yield m.group(1), m.group(2), m.group(3), ' '.join(lines[k + 1:]); break

def tg_files(sub, t_from, now):
    """recent sn.* files of a TGFTP directory (by modification time; the server's clock offset is taken from the newest
    file). Falls back to all 301 names."""
    try:
        L = [(n, t) for n, t in listing(TG + sub + '/') if re.fullmatch(r'sn\.\d{4}', n) and t is not None]
        if L:
            newest = max(t for _, t in L); off = dt.timedelta(hours=round((now - newest).total_seconds() / 3600.0))
            return sorted(n for n, t in L if t + off >= t_from - dt.timedelta(hours=1))
    except Exception as e:
        log('  listing failed', sub, repr(e)[:100])
    return [f'sn.{k:04d}' for k in range(301)]

def tg_fetch(sub, t_from, now):
    names = tg_files(sub, t_from, now); out = []
    def one(n):
        try: return http(TG + sub + '/' + n, timeout=60, tries=2, quiet=True) or b''
        except Exception as e:
            if n.endswith('0000') or n == names[0]: log('  tg', sub, n, 'failed', repr(e)[:150])
            return b''
    with ThreadPoolExecutor(8) as ex:
        for b in ex.map(one, names): out.append(b)
    log(f'  {sub}: {len(names)} files, {sum(len(b) for b in out) / 1e6:.1f} MB')
    return out

def wind_dd(dd, ff, units):
    if '/' in dd + ff or units is None: return None, None
    d = int(dd) * 10; f = int(ff) * units
    if dd == '00' and int(ff) == 0: return 0.0, 0.0
    if d > 360: return None, None                                      # 99 = variable
    return float(d), f

def synop_section1(g):
    """groups after iRixhVV Nddff [00fff] -> {1: '1snTTT', 2: ..., ...} in increasing order until another section."""
    vals = {}; last = 0
    for x in g:
        if len(x) != 5 or not x[0].isdigit(): break
        k = int(x[0])
        if k <= last or k == 0: break
        if k == 2 and x[1] not in '019/': break                          # '222Dv' = ship section 2
        vals[k] = x; last = k
    return vals

def t_val(x):
    if x is None or '/' in x[2:] or x[1] not in '01': return None
    v = int(x[2:]) / 10.0; return 273.15 + (-v if x[1] == '1' else v)

def p_val(x):
    if x is None or '/' in x[1:]: return None
    v = int(x[1:]) / 10.0
    return v + 1000.0 if v < 100 else v

def decode_land_like(R, typ, sid, la, lo, z, t, iw, g, stats):
    """iRixhVV Nddff [00fff] section-1 groups -> records (surface)."""
    if len(g) < 2: return
    units = KT if iw in '34' else (1.0 if iw in '01' else None)
    w = g[1]; rest = g[2:]
    if len(w) != 5: return
    dd, ff = w[1:3], w[3:5]
    if ff == '99' and rest and rest[0].startswith('00') and len(rest[0]) == 5: ff = rest[0][2:]; rest = rest[1:]
    sec = synop_section1(rest); ts = unix(t)
    T = t_val(sec.get(1)); Td = None
    x2 = sec.get(2)
    if x2 and '/' not in x2[2:]:
        if x2[1] == '9':
            if T is not None and 0 < int(x2[2:]) <= 100: Td = td_from_rh(T, int(x2[2:]) / 100.0)
        else: Td = t_val(x2)
    pst = p_val(sec.get(3)); x4 = sec.get(4); pm = p_val(x4) if (x4 and x4[1] in '09') else None
    if T is not None and 180 < T < 335: R.add(typ, sid, la, lo, pst, z, ts, 't', T)
    if Td is not None and T is not None and 180 < Td <= T + 0.5: R.add(typ, sid, la, lo, pst, z, ts, 'td', min(Td, T))
    if pst is not None and 400 < pst < 1090: R.add(typ, sid, la, lo, pst, z, ts, 'ps', pst * 100.0)
    ms = None
    if pst is not None and z is not None and T is not None and 400 < pst < 1090 and z <= 2000: ms = mslp_reduce(pst, z, T)
    elif pm is not None: ms = pm
    if ms is not None and 870 < ms < 1090:
        e = NG.obs_error(typ, 'mslp', None, z) + (0.0 if (pst is not None and z is not None and T is not None) or (z or 0) < 300 else 100.0)
        R.add(typ, sid, la, lo, pst, z, ts, 'mslp', ms * 100.0, e)
    d, f = wind_dd(dd, ff, units)
    if d is not None and f is not None and f < 90: R.wind(typ, sid, la, lo, pst, z, ts, d, f)
    stats[typ] = stats.get(typ, 0) + 1

def decode_synops(text, S, t0, R, stats, src='tg'):
    yyggi = None
    for rep in text.split('='):
        tk = rep.split()
        if not tk: continue
        if tk[0] == 'AAXX':
            if len(tk) < 2: continue
            yyggi = tk[1]; tk = tk[2:]
        if not tk or yyggi is None or len(yyggi) != 5 or not yyggi[:4].isdigit(): continue
        if not re.fullmatch(r'\d{5}', tk[0]) or 'NIL' in tk[1:3]: continue
        st = S.get(tk[0])
        if not st or st['lat'] is None or st['lon'] is None: stats['no_station'] = stats.get('no_station', 0) + 1; continue
        t = obs_time(int(yyggi[:2]), int(yyggi[2:4]), t0)
        if t is None: continue
        decode_land_like(R, 'synop', tk[0], st['lat'], st['lon'], st['elev'], t, yyggi[4], tk[1:], stats)

def decode_ships(text, t0, R, stats):
    for rep in text.split('='):
        tk = rep.split()
        if tk and tk[0] == 'BBXX': tk = tk[1:]
        if len(tk) < 6 or not re.fullmatch(r'\d{4}[\d/]', tk[1]) or not re.fullmatch(r'99\d{3}', tk[2]) or not re.fullmatch(r'[1357]\d{4}', tk[3]): continue
        la = int(tk[2][2:]) / 10.0; q = tk[3][0]; lo = int(tk[3][1:]) / 10.0
        if la > 90 or lo > 180: continue
        la = -la if q in '35' else la; lo = -lo if q in '57' else lo
        t = obs_time(int(tk[1][:2]), int(tk[1][2:4]), t0)
        if t is None: continue
        decode_land_like(R, 'ship', tk[0], la, lo, 0.0, t, tk[1][4], tk[4:], stats)

STDCODE = {'00': 1000, '92': 925, '85': 850, '70': 700, '50': 500, '40': 400, '30': 300, '25': 250, '20': 200, '15': 150, '10': 100}
ZREF = {1000: 110, 925: 790, 850: 1500, 700: 3120, 500: 5850, 400: 7550, 300: 9650, 250: 10900, 200: 12400, 150: 14200, 100: 16600}
def temp_height(p, hhh):
    if '/' in hhh: return None
    h = int(hhh)
    if p == 1000: return float(-(h - 500) if h >= 500 else h)
    unit, base = (1, 1000) if p >= 700 else (10, 10000)
    cands = [h * unit + k * base for k in range(0, 4)]                   # e.g. 700 hPa '142' -> 3142 m, 250 hPa '092' -> 10920 m
    return float(min(cands, key=lambda c: abs(c - ZREF[p])))

def temp_tt(x):
    """TTTaDD -> (T K, Td K)."""
    if x is None or len(x) != 5 or '/' in x[:3]: return None, None
    v = int(x[:3]) / 10.0; T = 273.15 + (-v if int(x[2]) % 2 else v)
    dd = x[3:]
    if '/' in dd: return T, None
    k = int(dd)
    dep = k / 10.0 if k <= 50 else (k - 50.0 if k >= 56 else None)
    return T, (T - dep if dep is not None else None)

def temp_wind(x, units):
    if x is None or len(x) != 5 or '/' in x: return None, None
    d = int(x[:3]); f = int(x[3:])
    f += 100 * (d % 5); d -= d % 5
    if d > 360: return None, None
    return float(d), f * units

def decode_temps(text, S, t0, R, stats):
    for rep in text.split('='):
        tk = rep.split()
        if len(tk) < 4 or tk[0] != 'TTAA' or not re.fullmatch(r'\d{4}[\d/]', tk[1]) or not re.fullmatch(r'\d{5}', tk[2]): continue
        yy, gg, idw = int(tk[1][:2]), int(tk[1][2:4]), tk[1][4]
        units = KT if yy > 50 else 1.0; day = yy - 50 if yy > 50 else yy
        t = obs_time(day, gg, t0)
        st = S.get(tk[2])
        if t is None: continue
        if not st: stats['temp_no_station'] = stats.get('temp_no_station', 0) + 1; continue
        la = st['ualat'] if st.get('ualat') is not None else st['lat']; lo = st['ualon'] if st.get('ualon') is not None else st['lon']
        if la is None or lo is None: continue
        plast = None
        if idw.isdigit():
            d = int(idw); cand = [p for p in STD if (p // 100) % 10 == d] if d else [1000]
            plast = min(cand) if cand else None
        ts = unix(t); i = 3; nlev = 0; g = tk
        while i < len(g):
            x = g[i]
            if len(x) != 5: break
            if x[:2] == '99' and i == 3:                                 # surface: 99PPP TTTDD [dddff]
                i += 2 + (1 if plast is not None else 0); continue
            if x[:2] in ('88', '77', '66') or x in ('31313', '51515', '21212', '41414'): break
            if x[:2] not in STDCODE: break
            p = STDCODE[x[:2]]; z = temp_height(p, x[2:])
            T, Td = temp_tt(g[i + 1] if i + 1 < len(g) else None)
            haswind = plast is not None and p >= plast
            wd, ws = temp_wind(g[i + 2] if haswind and i + 2 < len(g) else None, units)
            i += 2 + (1 if haswind else 0)
            if T is not None and 170 < T < 330: R.add('temp', tk[2], la, lo, p, z, ts, 't', T); nlev += 1
            if Td is not None and T is not None and p >= 300: R.add('temp', tk[2], la, lo, p, z, ts, 'td', Td)
            if wd is not None and ws < 150: R.wind('temp', tk[2], la, lo, p, z, ts, wd, ws)
            if z is not None and T is not None: R.add('temp', tk[2], la, lo, p, z, ts, 'z', z)
        if nlev: stats['temp'] = stats.get('temp', 0) + 1; stats.setdefault('temp_sids', set()).add(tk[2])

def gts(t0, t_from, t_to, now, S, R):
    stats = {}
    for sub, kind in (('DC.sflnd/DS.synop', 'synop'), ('DC.sfmar/DS.ships', 'ship'), ('DC.vsndn/DS.raobf', 'temp')):
        try:
            for raw in tg_fetch(sub, t_from, now):
                for tt, cccc, yygggg, text in bulletins(raw):
                    if kind == 'synop' and tt[:2] in ('SM', 'SI', 'SN') and 'BBXX' not in text: decode_synops(text, S, t0, R, stats)
                    elif kind == 'ship' and 'BBXX' in text: decode_ships(text, t0, R, stats)
                    elif kind == 'temp' and tt[:2] == 'US': decode_temps(text, S, t0, R, stats)
        except Exception as e:
            log('  GTS', sub, 'failed:', repr(e)[:200])
    return stats

# ================================================================================================ fallbacks (India)
def ogimet_india(t_from, t_to, S, t0, R):
    q = f'getsynop?begin={t_from:%Y%m%d%H%M}&end={t_to:%Y%m%d%H%M}&state=India'
    for base in ('https://www.ogimet.com/cgi-bin/', 'http://www.ogimet.com/cgi-bin/'):
        try:
            txt = (http(base + q, timeout=120, tries=1) or b'').decode('latin-1'); break
        except Exception: txt = ''
    stats = {}
    for line in txt.splitlines():
        parts = line.split(',', 6)
        if len(parts) == 7 and parts[6].startswith('AAXX'): decode_synops(parts[6], S, t0, R, stats)
    return stats.get('synop', 0)

def wyoming(S, t0, R, sids):
    n = 0
    for sid in sids:
        url = f'https://weather.uwyo.edu/wsgi/sounding?datetime={t0:%Y-%m-%d}%20{t0:%H}:00:00&id={sid}&src=UNKNOWN&type=TEXT:LIST'
        try: html = (http(url, timeout=60, tries=1, quiet=True) or b'').decode('latin-1', 'replace')
        except Exception: html = ''
        time.sleep(2.0)
        pre = re.findall(r'<pre[^>]*>(.*?)</pre>', html, re.S | re.I)
        if not pre: continue
        lines = pre[0].splitlines(); hi = next((k for k, l in enumerate(lines) if 'PRES' in l and 'HGHT' in l), None)
        if hi is None: continue
        names = lines[hi].split(); st = S.get(sid, {})
        mla = re.search(r'Station latitude:\s*(-?[\d.]+)', html); mlo = re.search(r'Station longitude:\s*(-?[\d.]+)', html)
        la = float(mla.group(1)) if mla else (st.get('ualat') or st.get('lat')); lo = float(mlo.group(1)) if mlo else (st.get('ualon') or st.get('lon'))
        if la is None or lo is None: continue
        ts = unix(t0); got = 0
        for l in lines[hi + 1:]:
            if not l.strip() or set(l.strip()) <= set('-'): continue
            vals = [l[k * 7:(k + 1) * 7].strip() for k in range(len(names))]; row = dict(zip(names, vals))
            try: p = float(row.get('PRES', ''))
            except ValueError: continue
            if int(round(p)) not in STD or abs(p - round(p)) > 0.01: continue
            p = int(round(p)); f = lambda k: float(row[k]) if row.get(k, '') not in ('', None) else None
            try: z, T, Td, dd, ff = f('HGHT'), f('TEMP'), f('DWPT'), f('DRCT'), f('SKNT')
            except ValueError: continue
            if T is not None: R.add('temp', sid, la, lo, p, z, ts, 't', T + 273.15); got += 1
            if Td is not None and T is not None and p >= 300: R.add('temp', sid, la, lo, p, z, ts, 'td', Td + 273.15)
            if dd is not None and ff is not None: R.wind('temp', sid, la, lo, p, z, ts, dd, ff * KT)
            if z is not None: R.add('temp', sid, la, lo, p, z, ts, 'z', z)
        n += got > 0
    return n

# ================================================================================================ METAR (AWC)
def metars(t_from, t_to, R):
    hours = max(1, int(math.ceil((t_to - t_from).total_seconds() / 3600.0)))
    date = t_to.strftime('%Y%m%d_%H%M'); seen = set(); nreq = [0]; n = [0]
    def q(b, depth):
        url = f'{AWC}?bbox={b[0]:g},{b[1]:g},{b[2]:g},{b[3]:g}&format=json&hours={hours}&date={date}'
        try: raw = http(url, timeout=90)
        except Exception: return
        nreq[0] += 1; time.sleep(0.7)
        data = json.loads(raw) if raw else []
        if isinstance(data, dict): data = data.get('data') or data.get('features') or []
        if len(data) >= 400 and depth < 4:
            ml, mo = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
            for bb in ((b[0], b[1], ml, mo), (b[0], mo, ml, b[3]), (ml, b[1], b[2], mo), (ml, mo, b[2], b[3])): q(bb, depth + 1)
            return
        for m in data:
            try:
                key = (m.get('icaoId'), m.get('obsTime'))
                if key in seen or m.get('lat') is None: continue
                seen.add(key); ts = int(m['obsTime'])
                if not (unix(t_from) <= ts <= unix(t_to)): continue
                la, lo, z = float(m['lat']), float(m['lon']), float(m.get('elev') or 0.0); sid = m.get('icaoId', '')
                T = m.get('temp'); Td = m.get('dewp'); T = None if T is None else float(T) + 273.15; Td = None if Td is None else float(Td) + 273.15
                pst = None; qnh = m.get('altim')
                if qnh not in (None, ''):
                    qnh = float(qnh)
                    if 850 < qnh < 1090: pst = qnh * (1 - 2.25577e-5 * z) ** 5.25588          # QNH -> station pressure (ICAO atmosphere)
                if T is not None and 180 < T < 335: R.add('metar', sid, la, lo, pst, z, ts, 't', T)
                if Td is not None and T is not None and 180 < Td <= T + 0.5: R.add('metar', sid, la, lo, pst, z, ts, 'td', min(Td, T))
                if pst is not None:
                    R.add('metar', sid, la, lo, pst, z, ts, 'ps', pst * 100.0)
                    if T is not None and z <= 2000: R.add('metar', sid, la, lo, pst, z, ts, 'mslp', mslp_reduce(pst, z, T) * 100.0)
                    elif z < 300: R.add('metar', sid, la, lo, pst, z, ts, 'mslp', qnh * 100.0, NG.obs_error('metar', 'mslp', None, z) + 100.0)
                elif m.get('slp') not in (None, ''): R.add('metar', sid, la, lo, None, z, ts, 'mslp', float(m['slp']) * 100.0)
                wd, ws = m.get('wdir'), m.get('wspd')
                if isinstance(wd, (int, float)) and ws is not None and float(ws) < 150:
                    if float(ws) == 0: R.wind('metar', sid, la, lo, pst, z, ts, 0.0, 0.0)
                    elif 0 < float(wd) <= 360: R.wind('metar', sid, la, lo, pst, z, ts, float(wd), float(ws) * KT)
                n[0] += 1
            except Exception:
                continue
    for la in np.arange(DOM['lat0'], DOM['lat1'], 10.0):
        for lo in np.arange(DOM['lon0'], DOM['lon1'], 10.0): q((la, lo, la + 10, lo + 10), 0)
    return n[0], nreq[0]

# ================================================================================================ scatterometer (KNMI)
def scat(t_from, t_to, R):
    key = os.environ.get('KNMI_API_KEY') or KNMI_ANON; H = {'Authorization': key}; tot = {}
    try: import netCDF4
    except ImportError: log('  scat: netCDF4 not installed'); return tot
    for ds, ver, sat in SCAT_SETS:
        try:
            js = json.loads(http(KNMI.format(ds=ds, ver=ver) + '?maxKeys=500&orderBy=created&sorting=desc', headers=H, timeout=60))
        except Exception as e:
            log('  scat', ds, 'list failed', repr(e)[:120]); continue
        files = []
        for f in js.get('files', []):
            m = re.search(r'(20\d{6})_(\d{6})', f.get('filename', ''))
            if not m: continue
            ts = dt.datetime.strptime(m.group(1) + m.group(2), '%Y%m%d%H%M%S').replace(tzinfo=UTC)
            if t_from - dt.timedelta(hours=2) <= ts <= t_to: files.append((abs((ts - t0_of(t_from)).total_seconds()), f['filename']))
        files = [fn for _, fn in sorted(files)[:120]]                     # whole orbits or short granules: at most 120, nearest t0 first
        n = 0
        for fn in sorted(files):
            try:
                time.sleep(1.3)
                u = json.loads(http(KNMI.format(ds=ds, ver=ver) + '/' + urllib.parse.quote(fn) + '/url', headers=H))['temporaryDownloadUrl']
                buf = unpack(http(u, timeout=300)); time.sleep(1.3)
                n += read_scat(netCDF4.Dataset('mem.nc', memory=buf), sat, t_from, t_to, R)
            except Exception as e:
                log('  scat', fn, 'failed', repr(e)[:150])
        tot[sat] = n; log(f'  scat {ds}: {len(files)} files in window, {n} superobs')
    return tot

def scat_eumetsat(t_from, t_to, R, cid='EO:EUM:DAT:METOP:OSI-104'):
    """ASCAT 12.5-km coastal winds (OSI SAF) from the EUMETSAT Data Store with our own key (EUMETSAT_KEY/SECRET secrets)."""
    import base64, zipfile
    k, sec = os.environ.get('EUMETSAT_KEY', ''), os.environ.get('EUMETSAT_SECRET', ''); tot = {}
    if not (k and sec): return tot
    try: import netCDF4
    except ImportError: log('  scat (EUMETSAT): netCDF4 not installed'); return tot
    try:
        req = urllib.request.Request('https://api.eumetsat.int/token', data=b'grant_type=client_credentials',
                                     headers={'Authorization': 'Basic ' + base64.b64encode(f'{k}:{sec}'.encode()).decode()})
        tok = json.loads(urllib.request.urlopen(req, timeout=60).read())['access_token']; H = {'Authorization': 'Bearer ' + tok}
        q = urllib.parse.urlencode({'format': 'json', 'pi': cid, 'dtstart': (t_from - dt.timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                                    'dtend': t_to.strftime('%Y-%m-%dT%H:%M:%SZ'), 'c': 100})
        feats = json.loads(http('https://api.eumetsat.int/data/search-products/1.0.0/os?' + q, headers=H)).get('features', [])
    except Exception as e:
        log('  scat (EUMETSAT) search failed', repr(e)[:150]); return tot
    for f in feats:
        pid = f.get('id', ''); sat = 'metopb' if 'metopb' in pid else 'metopc' if 'metopc' in pid else 'metop'
        try:
            buf = http('https://api.eumetsat.int/data/download/1.0.0/collections/' + urllib.parse.quote(cid) + '/products/' + urllib.parse.quote(pid), headers=H, timeout=300)
            if buf[:2] == b'PK':
                z = zipfile.ZipFile(io.BytesIO(buf)); nm = [n for n in z.namelist() if '.nc' in n or n.endswith('.l2')] or z.namelist(); buf = z.read(nm[0])
            buf = unpack(buf)
            tot[sat] = tot.get(sat, 0) + read_scat(netCDF4.Dataset('mem.nc', memory=buf), sat, t_from, t_to, R)
        except Exception as e:
            log('  scat (EUMETSAT)', pid[:60], 'failed', repr(e)[:150])
    log(f'  scat EUMETSAT {cid}: {len(feats)} files in window, superobs {tot}')
    return tot

def t0_of(t_from): return t_from + dt.timedelta(hours=6)                 # the window starts 6 h before t0

def read_scat(D, sat, t_from, t_to, R, box=0.5):
    """one KNMI L2 wind file -> 0.5-deg superobs (vector mean of the good cells of this pass) inside the domain."""
    V = D.variables; g = lambda k: np.ma.filled(np.ma.asarray(V[k][:]).astype(float), np.nan)
    lat, lon, spd, wdir = g('lat'), g('lon') % 360, g('wind_speed'), g('wind_dir')
    tv = V['time']; tt = np.ma.filled(np.ma.asarray(tv[:]).astype(float), np.nan)
    mu = re.match(r'(\w+) since (\d{4}-\d{2}-\d{2})[ T]?(\d{2}:\d{2}:\d{2})?', getattr(tv, 'units', 'seconds since 1990-01-01 00:00:00'))
    ref = dt.datetime.strptime(mu.group(2) + ' ' + (mu.group(3) or '00:00:00'), '%Y-%m-%d %H:%M:%S').replace(tzinfo=UTC)
    fac = {'seconds': 1, 'minutes': 60, 'hours': 3600, 'days': 86400}.get(mu.group(1), 1)
    ts = unix(ref) + tt * fac
    if ts.shape != lat.shape: ts = np.broadcast_to(ts.reshape(ts.shape + (1,) * (lat.ndim - ts.ndim)), lat.shape)
    ok = np.isfinite(lat) & np.isfinite(spd) & np.isfinite(wdir) & np.isfinite(ts)
    if 'wvc_quality_flag' in V:
        fv = V['wvc_quality_flag']; fl = np.ma.filled(np.ma.asarray(fv[:]), 0).astype(np.int64)
        masks = np.atleast_1d(getattr(fv, 'flag_masks', [])); names = str(getattr(fv, 'flag_meanings', '')).split()
        BAD = ('not_enough', 'poor_azimuth', 'over_land', 'over_ice', 'inversion_not_successful', 'quality_control_fail', 'monitoring_not_used', 'not_usable')
        bad = 0
        for mk, nm in zip(masks, names):
            if any(b in nm for b in BAD): bad |= int(mk)
        ok &= (fl & bad) == 0
    a = getattr(V['wind_dir'], 'standard_name', '') + ' ' + getattr(V['wind_dir'], 'long_name', '') + ' ' + getattr(V['wind_dir'], 'comment', '')
    toward = ('to_direction' in a) or ('oceanographic' in a.lower()) or ('from' not in a.lower())
    sgn = 1.0 if toward else -1.0
    u = sgn * spd * np.sin(np.radians(wdir)); v = sgn * spd * np.cos(np.radians(wdir))
    ok &= (lat >= DOM['lat0']) & (lat <= DOM['lat1']) & (lon >= DOM['lon0']) & (lon <= DOM['lon1']) & (ts >= unix(t_from)) & (ts <= unix(t_to))
    if not ok.any(): return 0
    la, lo, uu, vv, tt = lat[ok], lon[ok], u[ok], v[ok], ts[ok]
    kj = np.floor((la + 90) / box).astype(int) * 10000 + np.floor(lo / box).astype(int)
    keys, inv, cnt = np.unique(kj, return_inverse=True, return_counts=True)
    S = lambda x: np.bincount(inv, x) / cnt
    mla, mlo, mu_, mv, mt = S(la), S(lo), S(uu), S(vv), S(tt)
    for k in range(len(keys)):
        if cnt[k] < 2: continue
        R.add('scat', sat, mla[k], mlo[k], None, 10.0, int(mt[k]), 'u', mu_[k]); R.add('scat', sat, mla[k], mlo[k], None, 10.0, int(mt[k]), 'v', mv[k])
    return int((cnt >= 2).sum())

# ================================================================================================ satellite rain
RLAT = np.arange(DOM['lat0'] + 0.125, DOM['lat1'], 0.25); RLON = np.arange(DOM['lon0'] + 0.125, DOM['lon1'], 0.25)
def to_grid(A, la, lo):
    """fine regular field A [lat, lon] (NaN = missing) with 1-D axes -> mean on the 0.25-deg domain grid (NaN where under
    half of the fine cells are valid)."""
    lo = lo % 360; jy = np.floor((la - DOM['lat0']) / 0.25).astype(int); ix = np.floor((lo - DOM['lon0']) / 0.25).astype(int)
    oky = (jy >= 0) & (jy < len(RLAT)); okx = (ix >= 0) & (ix < len(RLON))
    B = A[np.ix_(oky, okx)]; J, I = np.meshgrid(jy[oky], ix[okx], indexing='ij'); flat = J * len(RLON) + I
    v = np.isfinite(B); n = len(RLAT) * len(RLON)
    s = np.bincount(flat[v], B[v], minlength=n); c = np.bincount(flat[v], minlength=n); a = np.bincount(flat.ravel(), minlength=n)
    return np.where(c >= 0.5 * np.maximum(a, 1), s / np.maximum(c, 1), np.nan).reshape(len(RLAT), len(RLON))

CMORPH_DEFAULT = dict(nx=4948, x0=0.0363783345, dx=0.072756669, ny=1649, y0=-59.963614312, dy=0.072771376, order='<', undef=-999.0,
                      dt_min=30.0, assumed=True)
def parse_ctl(txt):
    c = dict(CMORPH_DEFAULT, assumed=False)
    for line in txt.splitlines():
        w = line.split()
        if not w: continue
        k = w[0].lower()
        if k == 'dset': c['dset'] = w[1]
        elif k == 'options':
            o = ' '.join(w[1:]).lower(); c['order'] = '>' if 'big_endian' in o else '<'; c['yrev'] = 'yrev' in o
        elif k == 'undef': c['undef'] = float(w[1])
        elif k == 'xdef' and len(w) >= 5 and w[2].lower() == 'linear': c['nx'], c['x0'], c['dx'] = int(w[1]), float(w[3]), float(w[4])
        elif k == 'ydef' and len(w) >= 5 and w[2].lower() == 'linear': c['ny'], c['y0'], c['dy'] = int(w[1]), float(w[3]), float(w[4])
        elif k == 'tdef' and len(w) >= 5:
            m = re.match(r'(\d+)(mn|hr)', w[4].lower()); c['dt_min'] = float(m.group(1)) * (60 if m.group(2) == 'hr' else 1) if m else 30.0
        elif k == 'dtype': c['dtype'] = w[1].lower()
        elif k == 'vars': c['nvars'] = int(w[1])
    return c

def cmorph(t_end, hours=6):
    """6-h accumulation (mm) ending at t_end from CMORPH real time; (grid, hours found, note)."""
    ctl = None
    try:
        names = [n for n, _ in listing(CMORPH + 'CTL/') if n.lower().endswith('.ctl')]
        pick = sorted(names, key=lambda n: (('8km' not in n.lower()) + ('30min' not in n.lower()), n))
        if pick: ctl = parse_ctl(http(CMORPH + 'CTL/' + pick[0]).decode('latin-1')); log('  CMORPH ctl', pick[0], {k: ctl[k] for k in ('nx', 'ny', 'x0', 'y0', 'dx', 'dy', 'order', 'dt_min') if k in ctl}, ctl.get('dset', ''))
    except Exception as e:
        log('  CMORPH ctl not read', repr(e)[:120])
    c = ctl or dict(CMORPH_DEFAULT)
    lon = c['x0'] + c['dx'] * np.arange(c['nx']); lat = c['y0'] + c['dy'] * np.arange(c['ny'])
    acc = np.zeros((len(RLAT), len(RLON))); miss = np.zeros(acc.shape, bool); got = 0.0; dirs = {}; note = ''
    def one_file(buf, name):
        """one data file -> accumulation (mm) on the 0.25-deg grid over the time it covers, or None."""
        nonlocal note
        if buf[:3] == b'CDF' or buf[:4] == b'\x89HDF':
            r = cmorph_nc(buf)
            if r is None: note = 'netCDF not understood'; return None
            return to_grid(r[0], r[1], r[2])
        nv = int(c.get('nvars', 1) or 1); nrec = len(buf) / (4 * c['nx'] * c['ny'])
        if nrec != int(nrec) or nrec < 1: note = f'unexpected size {len(buf)}'; log('  CMORPH', name, note); return None
        R_ = np.frombuffer(buf, c['order'] + 'f4').reshape(int(nrec), c['ny'], c['nx']).astype(float)
        if nv > 1 and int(nrec) % nv == 0: R_ = R_[0::nv]                  # first variable of each time
        R_ = np.where((R_ < 0) | (R_ == c['undef']) | (R_ > 500), np.nan, R_)
        if c.get('yrev'): R_ = R_[:, ::-1]
        R_ = R_[:max(1, int(round(60.0 / c['dt_min'])))]                    # at most one hour of records per file
        A = np.nansum(R_, 0) * c['dt_min'] / 60.0                           # records are rates (mm/h) over dt_min each
        A[np.all(~np.isfinite(R_), 0)] = np.nan
        return to_grid(A, lat, lon)
    for k in range(hours, 0, -1):
        h = t_end - dt.timedelta(hours=k); tag = f'{h:%Y%m%d%H}'
        d = CMORPH + f'data/{h:%Y}/{h:%Y%m}/'
        if d not in dirs:
            try: dirs[d] = [n for n, _ in listing(d)]
            except Exception as e: dirs[d] = []; log('  CMORPH listing failed', d, repr(e)[:100])
        cand = {}
        for n in dirs[d]:
            m = re.search(r'(\d{10,12})', n)
            if m and m.group(1).startswith(tag) and not n.endswith('/'): cand.setdefault(m.group(1), n)   # hourly file, or the :00 and :30 files
        if not cand: continue
        acc_h = None
        for stamp, n in sorted(cand.items()):
            try: a = one_file(unpack(http(d + n, timeout=180)), n)
            except Exception: a = None
            if a is None: acc_h = None; break
            acc_h = a if acc_h is None else acc_h + a
        if acc_h is None: continue
        acc = acc + np.nan_to_num(acc_h); miss |= ~np.isfinite(acc_h); got += 1.0
    if got == 0: return None, 0.0, note or 'no files'
    acc = acc * hours / got; acc[miss] = np.nan
    if dirs and got < hours: log('  CMORPH files seen, e.g.:', [n for v in dirs.values() for n in v][:6])
    return acc, got, ('ctl' if ctl and not ctl.get('assumed') else 'assumed grid') + (' ' + note if note else '')

def cmorph_nc(buf):
    try:
        import netCDF4
        D = netCDF4.Dataset('m.nc', memory=buf); V = D.variables
        vn = next((k for k in V if 'cmorph' in k.lower() or 'precip' in k.lower()), None)
        la = next(V[k][:] for k in V if k.lower() in ('lat', 'latitude')); lo = next(V[k][:] for k in V if k.lower() in ('lon', 'longitude'))
        X = np.ma.filled(np.ma.asarray(V[vn][:]).astype(float), np.nan)
        X = X.reshape((-1,) + X.shape[-2:]); X = np.where(X < 0, np.nan, X)
        return np.nansum(X, 0) * (1.0 / X.shape[0]), np.asarray(la, float), np.asarray(lo, float)
    except Exception as e:
        log('  CMORPH netCDF read failed', repr(e)[:120]); return None

def persiann(t_end, hours=6):
    """PERSIANN-CCS (0.04 deg, 60S-60N): the 6-hourly file for the period ending at t_end, else hourly files."""
    la = 59.98 - 0.04 * np.arange(3000); lo = 0.02 + 0.04 * np.arange(9000)
    def read(url):
        b = http(url, timeout=180, tries=2, quiet=True)
        if not b: return None
        b = unpack(b)
        if len(b) == 3000 * 9000 * 2: A = np.frombuffer(b, '>i2').reshape(3000, 9000).astype(float); A = np.where(A < 0, np.nan, A / 100.0)
        elif len(b) == 3000 * 9000 * 4: A = np.frombuffer(b, '>f4').reshape(3000, 9000).astype(float); A = np.where(A < 0, np.nan, A)
        else: log('  PERSIANN unexpected size', len(b)); return None
        return to_grid(A[::-1], la[::-1], lo)
    st = t_end - dt.timedelta(hours=hours)
    if hours == 6 and st.hour % 6 == 0:
        try:
            G6 = read(PCCS + f'6hrly/rgccs6h{st:%y}{st.timetuple().tm_yday:03d}{st:%H}.bin.gz')
            if G6 is not None: return G6, 6.0, '6-hourly'
        except Exception: pass
    acc = None; got = 0
    for k in range(hours):
        h = st + dt.timedelta(hours=k)
        try: Gh = read(PCCS + f'hrly/rgccs1h{h:%y}{h.timetuple().tm_yday:03d}{h:%H}.bin.gz')
        except Exception: Gh = None
        if Gh is None: continue
        acc = Gh if acc is None else acc + Gh; got += 1
    if not got: return None, 0.0, 'no files'
    return acc * hours / got, float(got), 'hourly'

# ================================================================================================ lightning
def lightning(t0):
    """strike-cell counts per 0.25 deg over the 6 h before t0 (whatever of it recent.json still holds), and an
    activity proxy from the movement-vector history (strike cells per 1.2-deg block, at block centres)."""
    def get(name):
        try:
            subprocess.run(['git', '-C', ROOT, 'fetch', '-q', 'origin', 'lightning-data'], check=True, timeout=120, capture_output=True)   # one orphan commit
            return subprocess.run(['git', '-C', ROOT, 'show', f'FETCH_HEAD:{name}'], check=True, capture_output=True, timeout=60).stdout
        except Exception:
            repo = os.environ.get('GITHUB_REPOSITORY', 'sridhar13294-rgb/tn-rainfall-map')
            return http(f'https://raw.githubusercontent.com/{repo}/lightning-data/{name}', timeout=60)
    G = np.zeros((len(RLAT), len(RLON))); A = np.zeros_like(G); maps = 0; tmin = None; tmax = None
    def put(M, lo, la, w=1.0):
        j = int(np.floor((la - DOM['lat0']) / 0.25)); i = int(np.floor((lo - DOM['lon0']) / 0.25))
        if 0 <= j < M.shape[0] and 0 <= i < M.shape[1]: M[j, i] += w
    a, b = t0 - dt.timedelta(hours=6), t0 + dt.timedelta(minutes=15)
    try:
        for rec in json.loads(get('recent.json')):
            te = dt.datetime.fromisoformat(rec['t_end'])
            if not (a < te <= b): continue
            maps += 1; tmin = te if tmin is None or te < tmin else tmin; tmax = te if tmax is None or te > tmax else tmax
            for lo, la in rec['pts']: put(G, lo, la, 15.0 / 20.0)            # 20-min windows every 15 min: count each once on average
    except Exception as e:
        log('  lightning recent.json failed', repr(e)[:120])
    nh = 0
    try:
        for line in get('hist.jsonl').decode().splitlines():
            if not line.strip(): continue
            r = json.loads(line); te = dt.datetime.fromisoformat(r['t_end'])
            if not (a < te <= b): continue
            nh += 1
            for v in r.get('vectors', []): put(A, v[0], v[1], v[4] / 9.0)       # overlapping blocks (stride 1/3 of the block): /9
    except Exception as e:
        log('  lightning hist.jsonl failed', repr(e)[:120])
    hrs = 0.0 if not maps else ((tmax - tmin).total_seconds() / 3600.0 + 0.25)
    return G, A, hrs, maps, nh

# ================================================================================================ main
def in_box(lat, lon, b):
    return (lat >= b[0]) & (lat <= b[1]) & ((lon % 360) >= b[2]) & ((lon % 360) <= b[3])

def main(argv):
    args = [a for a in argv if not a.startswith('-')]
    if args and args[0] == 'run': args = args[1:]
    now = dt.datetime.now(UTC); run = args[0] if args and args[0].strip() else 'latest'
    if run == 'latest':
        x = now - dt.timedelta(hours=3); t0 = x.replace(hour=(x.hour // 6) * 6, minute=0, second=0, microsecond=0)
    else:
        t0 = dt.datetime.strptime(run, '%Y%m%d%H').replace(tzinfo=UTC)
    t_from = t0 - dt.timedelta(hours=6); t_to = min(t0 + dt.timedelta(hours=3), now)
    log(f'== obs {t0:%Y%m%d%H} (window {t_from:%d %H:%M}-{t_to:%d %H:%M} UTC, fetched {now:%Y-%m-%d %H:%M} UTC)')
    os.makedirs(OUT, exist_ok=True); R = Recs(); counts = {}
    try: S = stations(); log(f'  stations: {len(S)}')
    except Exception as e: S = {}; log('  station list failed', repr(e)[:150])
    st = gts(t0, t_from, t_to, now, S, R) if S else {}
    tsids = st.pop('temp_sids', set())
    counts['gts'] = {k: v for k, v in st.items()}
    n_syn_in = len({r[1] for r in R.r if r[0] == 'synop' and INDIA[0] <= r[2] <= INDIA[1] and INDIA[2] <= r[3] <= INDIA[3]})
    n_tmp_in = len({s for s in tsids if s[:2] in ('42', '43')})
    log(f"  GTS: {st}; India synop stations {n_syn_in}, India radiosondes {n_tmp_in}")
    if S and n_syn_in < 50:
        try: k = ogimet_india(t_from, t_to, S, t0, R); counts['ogimet_india'] = k; log(f'  Ogimet India synops: {k}')
        except Exception as e: log('  Ogimet failed', repr(e)[:150])
    if S and t0.hour in (0, 12) and n_tmp_in < 5:
        ua = sorted(s for s, v in S.items() if s[:2] in ('42', '43') and v.get('ualat') is not None)
        try: k = wyoming(S, t0, R, ua); counts['wyoming_india'] = k; log(f'  Wyoming India soundings: {k} of {len(ua)} asked')
        except Exception as e: log('  Wyoming failed', repr(e)[:150])
    try:
        nm, nq = metars(t_from, t_to, R); counts['metar'] = nm; log(f'  METAR: {nm} reports in {nq} requests')
    except Exception as e: log('  METAR failed', repr(e)[:150])
    try: counts['scat'] = scat_eumetsat(t_from, t_to, R) or scat(t_from, t_to, R)              # own EUMETSAT key first, KNMI shared key as fallback
    except Exception as e: log('  scat failed', repr(e)[:150])
    rain, rh, rsrc = None, 0.0, ''
    try:
        rain, rh, note = cmorph(t0, 6); rsrc = 'CMORPH_RT ' + note
        log(f'  CMORPH: {rh:.0f} of 6 h ({note})')
    except Exception as e: log('  CMORPH failed', repr(e)[:150])
    if rain is None or rh < 4:
        try:
            r2, h2, note = persiann(t0, 6); log(f'  PERSIANN-CCS: {h2:.0f} of 6 h ({note})')
            if r2 is not None and h2 >= max(rh, 4): rain, rh, rsrc = r2, h2, 'PERSIANN-CCS ' + note
        except Exception as e: log('  PERSIANN failed', repr(e)[:150])
    if rain is None: rain = np.full((len(RLAT), len(RLON)), np.nan); rsrc = 'none'
    try: ltg, act, lh, lmaps, lhist = lightning(t0); log(f'  lightning: {lmaps} maps ({lh:.1f} h), {int(ltg.sum())} strike cells; activity records {lhist}')
    except Exception as e: ltg = np.zeros((len(RLAT), len(RLON))); act = ltg.copy(); lh = 0.0; lmaps = lhist = 0; log('  lightning failed', repr(e)[:150])
    A = R.arrays()
    # counts per source: all / India box (records of the main variables)
    for typ in ('synop', 'ship', 'temp', 'metar', 'scat'):
        m = A['type'] == typ; mi = m & in_box(A['lat'], A['lon'], INDIA)
        counts[typ + '_records'] = int(m.sum()); counts[typ + '_india'] = int(mi.sum())
        counts[typ + '_sites_india'] = int(len(set(A['sid'][mi])))
    counts['rain'] = dict(src=rsrc, hours=rh, mean_mm_india=float(np.nanmean(rain[np.ix_((RLAT >= INDIA[0]) & (RLAT <= INDIA[1]), (RLON >= INDIA[2]) & (RLON <= INDIA[3]))])) if np.isfinite(rain).any() else None)
    counts['lightning'] = dict(maps=lmaps, hours=lh, cells=float(ltg.sum()), hist_records=lhist)
    fn = os.path.join(OUT, f'obs_{t0:%Y%m%d%H}.npz')
    np.savez_compressed(fn, **A, rain6=rain.astype(np.float32), rain_lat=RLAT, rain_lon=RLON, rain_src=np.array(rsrc), rain_hours=np.array(rh),
                        ltg6=ltg.astype(np.float32), ltg_act6=act.astype(np.float32), ltg_hours=np.array(lh), ltg_maps=np.array(lmaps),
                        run=np.array(f'{t0:%Y%m%d%H}'), t_from=np.array(unix(t_from)), t_to=np.array(unix(t_to)), counts=np.array(json.dumps(counts, default=str)))
    log(f'  saved {fn}: {len(A["lat"])} records, {os.path.getsize(fn) / 1e6:.1f} MB')
    log('  counts ' + json.dumps(counts, default=str))
    os.makedirs(os.path.dirname(LOGF), exist_ok=True)
    with open(LOGF, 'a') as f: f.write('\n'.join(_log) + '\n')
    return fn

if __name__ == '__main__':
    main(sys.argv[1:])
