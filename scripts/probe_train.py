"""One-off probe: which history can a day-ahead heavy-rain model be trained on?
1. TN SMART past days (2021-2025 north-east monsoon), via the page's date form.
2. Open-Meteo Previous Runs API: what each model forecast one day before (2024 onwards), with storm ingredients.
3. Open-Meteo Historical Forecast API (2021 onwards).
4. IMD Pune gridded rainfall (imdlib)."""
import json, sys, os, urllib.request, urllib.parse, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
out = {}
def get(u, t=60):
    with urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0 (tn-rainfall-map probe)'}), timeout=t) as r:
        return r.read()
# 1. TN SMART
try:
    import update as U
    geo = U.load(U.P('data/geo.json'), None); res = {}
    for d in ['2025-12-01', '2025-10-22', '2024-12-01', '2024-11-30', '2024-10-15', '2023-12-04', '2022-11-12', '2021-11-07', '2021-01-15']:
        try:
            page = U.fetch_date(d); date, rows = U.parse_page(page, geo['d'] + list(U.ALIASES))
            vals = [r['rain'] for r in rows if r['rain'] is not None]
            top = sorted([(r['rain'], r.get('name') or r.get('station')) for r in rows if r['rain'] is not None], key=lambda x: -x[0])[:3]
            res[d] = dict(page_date=date, gauges=len(vals), top=top)
        except Exception as e:
            res[d] = 'ERR ' + str(e)[:200]
    out['tnsmart'] = res
except Exception as e:
    out['tnsmart'] = 'ERR ' + traceback.format_exc()[-500:]
# 2. previous runs (day-1 forecasts)
pr = {}
for model in ['gfs_seamless', 'ecmwf_ifs025', 'icon_seamless', 'gem_seamless', 'ecmwf_aifs025_single']:
    q = dict(latitude=13.08, longitude=80.27, start_date='2024-11-29', end_date='2024-12-01', models=model, timezone='Asia/Kolkata',
             hourly='precipitation_previous_day1,cape_previous_day1,total_column_integrated_water_vapour_previous_day1,wind_speed_850hPa_previous_day1')
    try:
        j = json.loads(get('https://previous-runs-api.open-meteo.com/v1/forecast?' + urllib.parse.urlencode(q)))
        h = j.get('hourly', {}); pr[model] = {k: (None if not v else [x for x in v if x is not None][:3] + ['n=%d' % sum(x is not None for x in v), 'sum=%.1f' % sum(x for x in v if x is not None)] ) for k, v in h.items() if k != 'time'}
    except Exception as e:
        pr[model] = 'ERR ' + str(e)[:300]
    # earliest year available
    for y in ['2022-11-12', '2023-12-04']:
        q2 = dict(latitude=13.08, longitude=80.27, start_date=y, end_date=y, models=model, hourly='precipitation_previous_day1')
        try:
            j = json.loads(get('https://previous-runs-api.open-meteo.com/v1/forecast?' + urllib.parse.urlencode(q2)))
            v = j['hourly']['precipitation_previous_day1']; pr[model + '@' + y] = 'n=%d sum=%.1f' % (sum(x is not None for x in v), sum(x for x in v if x is not None))
        except Exception as e:
            pr[model + '@' + y] = 'ERR ' + str(e)[:200]
out['previous_runs'] = pr
# 3. historical forecast
try:
    q = dict(latitude=13.08, longitude=80.27, start_date='2021-11-06', end_date='2021-11-07', models='gfs_seamless', daily='precipitation_sum', timezone='Asia/Kolkata')
    out['historical_forecast_2021'] = json.loads(get('https://historical-forecast-api.open-meteo.com/v1/forecast?' + urllib.parse.urlencode(q))).get('daily')
except Exception as e:
    out['historical_forecast_2021'] = 'ERR ' + str(e)[:300]
# 4. IMD Pune gridded rain
for u in ['https://imdpune.gov.in/cmpg/Griddata/Rainfall_25_Bin.html', 'https://imdpune.gov.in/cmpg/Griddata/RF25.php']:
    try:
        b = get(u, 40); out['imdpune ' + u] = 'ok %d bytes' % len(b)
    except Exception as e:
        out['imdpune ' + u] = 'ERR ' + str(e)[:200]
os.makedirs('data', exist_ok=True); json.dump(out, open('data/probe_train.json', 'w'), indent=1); print(json.dumps(out, indent=1)[:6000])
