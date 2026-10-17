"""One-off probe: which history can a day-ahead heavy-rain model be trained on?
1. TN SMART past days (2021-2025 north-east monsoon), via the page's date form.
2. Open-Meteo Previous Runs API: what each model forecast one day before (2024 onwards), with storm ingredients.
3. Open-Meteo Historical Forecast API (2021 onwards).
4. IMD Pune gridded rainfall (imdlib)."""
import json, sys, os, urllib.request, urllib.parse, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
out = {}
import json as _j
def get(u, t=60):
    with urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0 (tn-rainfall-map probe)'}), timeout=t) as r:
        return r.read()
# round 2
import update as U
geo = U.load(U.P('data/geo.json'), None); res = {}
for d in ['2025-01-10', '2025-06-01', '2025-09-15', '2025-11-25', '2026-01-02', '2024-01-08', '2020-11-25', '2019-12-02']:
    try:
        page = U.fetch_date(d); date, rows = U.parse_page(page, geo['d'] + list(U.ALIASES))
        res[d] = dict(page_date=date, gauges=sum(r['rain'] is not None for r in rows))
    except Exception as e:
        res[d] = 'ERR ' + str(e)[:200]
out['tnsmart_more'] = res
pr = {}
for model in ['gfs_seamless', 'ecmwf_ifs025', 'icon_seamless', 'gem_seamless']:
    for var in ['precipitation_previous_day1', 'cape_previous_day1', 'total_column_integrated_water_vapour_previous_day1', 'wind_speed_850hPa_previous_day1', 'precipitation_previous_day2']:
        q = dict(latitude=13.08, longitude=80.27, start_date='2024-11-29', end_date='2024-12-01', models=model, hourly=var, timezone='Asia/Kolkata')
        try:
            j_ = json.loads(get('https://previous-runs-api.open-meteo.com/v1/forecast?' + urllib.parse.urlencode(q))); v = j_['hourly'][var]
            pr[model + ' ' + var] = 'n=%d sum=%.1f max=%.1f' % (sum(x is not None for x in v), sum(x for x in v if x is not None), max([x for x in v if x is not None] or [0]))
        except Exception as e:
            pr[model + ' ' + var] = 'ERR ' + str(e)[:120]
    for y in ['2024-01-10', '2024-04-10', '2024-10-15']:
        q2 = dict(latitude=13.08, longitude=80.27, start_date=y, end_date=y, models=model, hourly='precipitation_previous_day1')
        try:
            j_ = json.loads(get('https://previous-runs-api.open-meteo.com/v1/forecast?' + urllib.parse.urlencode(q2))); v = j_['hourly']['precipitation_previous_day1']
            pr[model + '@' + y] = 'n=%d sum=%.1f' % (sum(x is not None for x in v), sum(x for x in v if x is not None))
        except Exception as e:
            pr[model + '@' + y] = 'ERR ' + str(e)[:120]
out['previous_runs'] = pr
hf = {}
for var in ['precipitation', 'cape', 'total_column_integrated_water_vapour', 'wind_speed_850hPa', 'wind_direction_850hPa']:
    q = dict(latitude=13.08, longitude=80.27, start_date='2021-11-06', end_date='2021-11-06', models='gfs_seamless', hourly=var, timezone='Asia/Kolkata')
    try:
        v = json.loads(get('https://historical-forecast-api.open-meteo.com/v1/forecast?' + urllib.parse.urlencode(q)))['hourly'][var]
        hf[var] = 'n=%d max=%s' % (sum(x is not None for x in v), max([x for x in v if x is not None] or [None]))
    except Exception as e:
        hf[var] = 'ERR ' + str(e)[:120]
out['historical_forecast_vars_2021'] = hf
os.makedirs('data', exist_ok=True); json.dump(out, open('data/probe_train.json', 'w'), indent=1); print(json.dumps(out, indent=1)[:6000])
