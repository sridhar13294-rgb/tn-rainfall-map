import sys, json, os, datetime as dt
sys.path.insert(0, 'scripts'); import verify, forecast
W = '/tmp/claude-0/-home-claude-tn-rainfall-map/2c3b34a9-cc00-53e0-8864-49737f9cdb93/scratchpad/wt-radar'
verify.sat_day = lambda d: (json.load(open(W + '/data/satradar/satdaily/%s.json' % d)) if os.path.exists(W + '/data/satradar/satdaily/%s.json' % d) else None)
verify.SCORES = '/tmp/claude-0/-home-claude/2c3b34a9-cc00-53e0-8864-49737f9cdb93/scratchpad/daily23/scores_23.json'
pts = forecast.tn_points(json.load(open('data/geo.json')))
now = dt.datetime(2026, 10, 23, 5, 0, tzinfo=dt.timezone.utc)
def run(win):
    verify.WINDOW_DAYS = win; return verify.verify(pts, now)
def row(n, l, s): return f"{n:16s} L{l} | MAE {s['mae']:5} | bias {s['bias']} | POD {s['pod']} | FAR {s['far']} | ETS {s['ets']} | heavy {s['heavy']['hit']}/{s['heavy']['miss']}/{s['heavy']['false']} | days {s['days']}"
for label, win in (('23 Oct only', 0), ('all days', 30)):
    out = run(win); S_ = out['scores']; print('=====', label, '| weights', out['weights'], '| note', out['note'])
    for l in ('1', '2'):
        for n in sorted(S_, key=lambda n: (S_[n].get(l) or {}).get('mae', 99)):
            if S_[n].get(l): print(row(n, l, S_[n][l]))
    sat = (out.get('satellite') or {}).get('vs_gauges'); print('satellite vs gauges', json.dumps(sat))
    if label == 'all days':
        for r in out['daily']: print(r['date'], 'obs', r['obs'], 'sat', r.get('sat'), r['fc'])
        print('weight detail', json.dumps((out.get('satellite') or {}).get('weight_detail')))
