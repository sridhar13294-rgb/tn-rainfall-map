"""Step 5: check the forecast against TN SMART rain gauges, and weight the model average by recent skill.

Every forecast run saves what each model said for the next few TN SMART rain days (data/verify/fc/RUN.json).
A TN SMART day D is the 24 hours to 08:30 IST on D (03 UTC D-1 to 03 UTC D). The models give rain in 6-hour blocks
starting at 00/06/12/18 UTC, so that window is taken as half of 00-06 UTC on D-1, the three blocks 06 UTC to 00 UTC,
and half of 00-06 UTC on D (the same 24 hours, centred on the gauge window).

When gauge readings for a day arrive (data/daily/D.json, saved by the rainfall-map update), each saved forecast is
scored on the 0.25 degree forecast cells that hold at least one gauge (gauges in a cell are averaged).
Lead 1 = the latest run made 0-24 h before the window starts, lead 2 = 24-48 h, lead 3 = 48-72 h.
"""
import datetime as dt, json, math, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
OBS = lambda *a: os.path.join(os.environ.get('OBS_ROOT') or ROOT, *a)   # gauge data (main branch copy on test branches)
FC_DIR = P('data', 'verify', 'fc')
SCORES = P('data', 'verify', 'scores.json')
KEEP_DAYS = 45            # forecast archives older than this are deleted
WINDOW_DAYS = 30          # scores and weights use the last 30 verified days
MIN_DAYS = 10             # weights switch on once every model has this many verified days at leads 1-2
RAIN = 2.5                # IMD rainy-day threshold (mm)
HEAVY = 64.5              # IMD heavy rain (mm)
BLOCK_W = (0.5, 1, 1, 1, 0.5)


def utc(s):
    return dt.datetime.strptime(s, '%Y%m%d%H').replace(tzinfo=dt.timezone.utc)


def window_start(day):
    """Start (UTC) of the TN SMART rain day `day` (a date)."""
    return dt.datetime(day.year, day.month, day.day, 3, tzinfo=dt.timezone.utc) - dt.timedelta(days=1)


def gauge_days(d0, nper, now, max_days=5):
    """TN SMART days fully covered by 6-hourly blocks from d0 and starting after `now`: [(date, first_block)]."""
    out = []
    for k in range(0, nper - 4, 4):                     # block k = 00 UTC of day D-1
        start = d0 + dt.timedelta(hours=6 * k)
        day = (start + dt.timedelta(days=1)).date()
        if window_start(day) > now and len(out) < max_days:
            out.append((day, k))
    return out


def archive(per6, labels, weights, d0, now, npts):
    """Save each model's (and the averages') rain for the coming TN SMART days. per6: {model: [6-hourly arrays]}."""
    os.makedirs(FC_DIR, exist_ok=True)
    nper = max(len(v) for v in per6.values())
    days = {}
    for day, k in gauge_days(d0, nper, now):
        vals = {}
        for n in labels:
            blocks = per6[n][k:k + 5]
            if len(blocks) == 5 and all(b is not None for b in blocks):
                vals[n] = sum(w * b for w, b in zip(BLOCK_W, blocks))
        if not vals:
            continue
        rec = {n: [int(round(float(x) * 10)) for x in v] for n, v in vals.items()}
        rec['Average'] = [int(round(sum(float(vals[n][i]) for n in vals) / len(vals) * 10)) for i in range(npts)]
        if weights:
            ws = {n: weights[n] for n in vals if n in weights}
            tot = sum(ws.values())
            if tot > 0:
                rec['Weighted average'] = [int(round(sum(ws[n] * float(vals[n][i]) for n in ws) / tot * 10)) for i in range(npts)]
        days[day.isoformat()] = rec
    if days:
        json.dump(dict(run_utc=now.strftime('%Y-%m-%dT%H:%MZ'), days=days),
                  open(os.path.join(FC_DIR, now.strftime('%Y%m%d%H') + '.json'), 'w'), separators=(',', ':'))
    cutoff = now - dt.timedelta(days=KEEP_DAYS)
    for f in os.listdir(FC_DIR):
        try:
            if utc(f[:10]) < cutoff:
                os.remove(os.path.join(FC_DIR, f))
        except ValueError:
            pass
    return len(days)


def dead_gauges(st, days=30):
    """Gauges that read 0 mm on every day of the last `days` saved days while the median gauge in their district had
    40 mm or more: almost certainly not reporting, so their zeros would wrongly count as 'dry' in the forecast check."""
    import statistics
    d = OBS('data', 'daily')
    if not os.path.isdir(d):
        return set()
    files = sorted(f for f in os.listdir(d) if f.endswith('.json'))[-days:]
    if len(files) < 20:
        return set()
    tot = {}
    for f in files:
        for k, v in json.load(open(os.path.join(d, f))).items():
            if v is not None:
                tot[k] = tot.get(k, 0) + v
    byd = {}
    for k, t in tot.items():
        byd.setdefault(st.get(k, {}).get('district'), []).append(t)
    med = {dname: statistics.median(v) for dname, v in byd.items()}
    return {k for k, t in tot.items() if t == 0 and med.get(st.get(k, {}).get('district'), 0) >= 40}


def gauge_cells(pts):
    """{cell index: [station ids]} for TN SMART gauges inside a 0.25 degree forecast cell (gauges that have stopped
    reporting are left out)."""
    try:
        st = json.load(open(OBS('data', 'stations.json')))
    except Exception:
        return {}
    dead = dead_gauges(st)
    cells = {}
    for sid, s in st.items():
        if s.get('lat') is None or s.get('lon') is None or sid in dead:
            continue
        best = min(range(len(pts)), key=lambda i: (pts[i][0] - s['lon']) ** 2 + (pts[i][1] - s['lat']) ** 2)
        if abs(pts[best][0] - s['lon']) <= 0.13 and abs(pts[best][1] - s['lat']) <= 0.13:
            cells.setdefault(best, []).append(sid)
    return cells


def _empty():
    return dict(n=0, ae=0.0, fc=0.0, ob=0.0, h=0, m=0, f=0, c=0, hh=0, hm=0, hf=0)


def _add(s, fc, ob):
    s['n'] += 1; s['ae'] += abs(fc - ob); s['fc'] += fc; s['ob'] += ob
    if ob >= RAIN:
        s['h' if fc >= RAIN else 'm'] += 1
    else:
        s['f' if fc >= RAIN else 'c'] += 1
    if ob >= HEAVY:
        s['hh' if fc >= HEAVY else 'hm'] += 1
    elif fc >= HEAVY:
        s['hf'] += 1


def _summary(s, days):
    if not s['n']:
        return None
    h, m, f, c = s['h'], s['m'], s['f'], s['c']
    n = h + m + f + c
    hr = (h + m) * (h + f) / n if n else 0
    ets = (h - hr) / (h + m + f - hr) if (h + m + f - hr) > 0 else None
    return dict(days=days, cells=s['n'], mae=round(s['ae'] / s['n'], 1),
                bias=round(s['fc'] / s['ob'], 2) if s['ob'] > 0 else None,
                pod=round(h / (h + m), 2) if h + m else None, far=round(f / (h + f), 2) if h + f else None,
                ets=round(ets, 2) if ets is not None else None,
                heavy=dict(hit=s['hh'], miss=s['hm'], false=s['hf']))


def verify(pts, now):
    """Score saved forecasts against TN SMART gauges. Returns the scores dict (also written to data/verify/scores.json)."""
    cells = gauge_cells(pts)
    runs = []
    if os.path.isdir(FC_DIR):
        for f in sorted(os.listdir(FC_DIR)):
            try:
                runs.append((utc(f[:10]), os.path.join(FC_DIR, f)))
            except ValueError:
                pass
    obs_days = []
    if os.path.isdir(OBS('data', 'daily')):
        for f in sorted(os.listdir(OBS('data', 'daily'))):
            try:
                obs_days.append(dt.date.fromisoformat(f[:10]))
            except ValueError:
                pass
    first_run = runs[0][0] if runs else None
    obs_days = [d for d in obs_days if first_run and window_start(d) > first_run and (now.date() - d).days <= WINDOW_DAYS]
    cache = {}

    def load(path):
        if path not in cache:
            cache[path] = json.load(open(path))
        return cache[path]

    stats, daily_series, verified = {}, [], {}
    for day in obs_days:
        obs = json.load(open(OBS('data', 'daily', day.isoformat() + '.json')))
        ob_cell = {}
        for i, sids in cells.items():
            v = [obs[s] for s in sids if obs.get(s) is not None]
            if v:
                ob_cell[i] = sum(v) / len(v)
        if len(ob_cell) < 20:
            continue
        ws = window_start(day)
        row = dict(date=day.isoformat(), obs=round(sum(ob_cell.values()) / len(ob_cell), 1), fc={})
        for lead in (1, 2, 3):
            cand = [(t, p) for t, p in runs if ws - dt.timedelta(hours=24 * lead) <= t < ws - dt.timedelta(hours=24 * (lead - 1))]
            if not cand:
                continue
            t, p = cand[-1]
            fc = load(p)['days'].get(day.isoformat())
            if not fc:
                continue
            for n, arr in fc.items():
                s = stats.setdefault(n, {}).setdefault(lead, _empty())
                for i, ob in ob_cell.items():
                    _add(s, arr[i] / 10, ob)
                verified.setdefault(n, {}).setdefault(lead, set()).add(day)
                if lead == 1:
                    row['fc'][n] = round(sum(arr[i] / 10 for i in ob_cell) / len(ob_cell), 1)
        daily_series.append(row)

    scores = {n: {str(l): _summary(s, len(verified[n][l])) for l, s in by.items()} for n, by in stats.items()}
    # weights for the model average: inverse mean absolute error at leads 1-2, once every model has MIN_DAYS days
    models = [n for n in scores if n not in ('Average', 'Weighted average')]
    weights, note = None, None
    if models:
        mae, ok = {}, True
        for n in models:
            ae = sum(stats[n][l]['ae'] for l in (1, 2) if l in stats[n])
            cnt = sum(stats[n][l]['n'] for l in (1, 2) if l in stats[n])
            ndays = len(set().union(*[verified[n].get(l, set()) for l in (1, 2)]))
            if ndays < MIN_DAYS or not cnt:
                ok = False
            mae[n] = ae / cnt if cnt else None
        if ok:
            inv = {n: 1 / max(mae[n], 0.1) for n in models}
            eq = 1 / len(models)
            w = {n: v / sum(inv.values()) for n, v in inv.items()}
            w = {n: min(max(v, eq * 0.5), eq * 2) for n, v in w.items()}    # keep every model between half and double its equal share
            weights = {n: round(v / sum(w.values()), 3) for n, v in w.items()}
        else:
            have = min(len(set().union(*[verified[n].get(l, set()) for l in (1, 2)])) for n in models)
            note = f'{have} of {MIN_DAYS} verified days so far'
    out = dict(updated=now.strftime('%Y-%m-%dT%H:%MZ'), gauge_cells=len(cells), window_days=WINDOW_DAYS,
               min_days=MIN_DAYS, scores=scores, daily=daily_series, weights=weights, note=note,
               first_run=first_run.strftime('%Y-%m-%dT%H:%MZ') if first_run else None)
    os.makedirs(os.path.dirname(SCORES), exist_ok=True)
    json.dump(out, open(SCORES, 'w'), indent=1)
    return out
