"""Daily station rainfall from the TN-ALERT app's public 'Observed Rainfall' page (TNSDMA / RIMES), used since the
TN SMART station page went behind a login (31 Oct 2026). Same gauges and the same readings as TN SMART: checked on
16, 28 and 30 Oct 2026 - all 565 of our gauges identical (403 with rain on 16 Oct).

python scripts/tnalert.py YYYY-MM-DD [YYYY-MM-DD ...]   -> data/daily/<date>.json (gauge id -> mm), data/tnalert/log.json
The page lists District / Taluk / Station name / Rainfall; gauges are matched to data/stations.json by district and
station name (exact, ignoring case and punctuation). Rows that match none of our gauges (e.g. extra Chennai GCC ward
gauges) are counted and skipped, so the set of gauges on the map does not change."""
import html, json, os, re, sys, time, urllib.request, uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import update                                                                                      # Rows parser, ALIASES, num, save

URL = 'https://beta-tnsmart.rimes.int/index.php/Api_mobile/Api_rainfall/daily_data'
P = lambda *a: os.path.join(ROOT, *a)


def fetch(date):
    """The page for one date (the page's own form: multipart POST date=YYYY-MM-DD)."""
    b = uuid.uuid4().hex
    body = ''.join(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n' for k, v in (('date', date), ('submit', 'Submit')))
    body = (body + f'--{b}--\r\n').encode()
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(URL, data=body, headers={'Content-Type': f'multipart/form-data; boundary={b}',
                                                                   'User-Agent': 'Mozilla/5.0 (tn-rainfall-map daily update)'})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception as e:
            last = e; time.sleep(10 * (attempt + 1))
    raise RuntimeError(f'could not download {date}: {last}')


def parse(page):
    """[(district, taluk, station, mm or None)] and the date the page says it shows."""
    m = re.search(r'name="date"[^>]*value="(\d{4}-\d{2}-\d{2})"', page) or re.search(r'value="(\d{4}-\d{2}-\d{2})"[^>]*name="date"', page)
    p = update.Rows(); p.feed(page); dist = None; out = []
    for row in p.rows:
        t = [html.unescape(c[0]).strip() for c in row]
        if len(t) == 1 and t[0]:
            dist = update.ALIASES.get(t[0], t[0]); continue
        if len(t) >= 3 and t[0].lower() != 'taluk':
            out.append((dist, t[0], t[1], update.num(t[2]) if t[2] else None))
    return (m.group(1) if m else None), out


key = lambda d, n: (str(d).lower().replace(' ', ''), re.sub(r'[^a-z0-9]', '', n.lower()))


def main(dates):
    stations = json.load(open(P('data/stations.json')))
    idx = {}
    for sid, s in stations.items():
        idx.setdefault(key(s['district'], s['name']), []).append(sid)
    log = update.load(P('data/tnalert/log.json'), {})
    for date in dates:
        shown, rows = parse(fetch(date))
        vals, skipped = {}, 0
        for d, tk, n, v in rows:
            ids = idx.get(key(d, n), [])
            if len(ids) == 1 and v is not None:
                vals[ids[0]] = v
            elif len(ids) != 1:
                skipped += 1
        rec = dict(page_date=shown, rows=len(rows), gauges=len(vals), skipped_rows=skipped, wet=sum(v > 0 for v in vals.values()),
                   fetched_utc=time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime()))
        if shown != date:
            rec['status'] = f'NOT SAVED: page shows {shown}'
        elif len(vals) < 0.5 * len(stations):
            rec['status'] = 'NOT SAVED: fewer than half of our gauges on the page'
        else:
            update.save(P('data/daily', date + '.json'), vals); rec['status'] = 'saved'
        log[date] = rec; print(date, rec, flush=True)
    update.save(P('data/tnalert/log.json'), log)


if __name__ == '__main__':
    main(sys.argv[1:])
