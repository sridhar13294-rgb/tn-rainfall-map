"""Training history, part 1: TN SMART gauge readings for the north-east monsoon (1 Oct - 31 Dec) of past years.
Saved to data/history/tnsmart/YYYY-MM-DD.json (gauge id -> mm), new gauge positions to data/history/stations_hist.json.
The live data (data/daily, data/stations.json) is not touched. Resumable: days already saved are skipped."""
import concurrent.futures as cf, datetime as dt, json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import update as U
OUT = U.P('data/history/tnsmart'); os.makedirs(OUT, exist_ok=True)
geo = U.load(U.P('data/geo.json'), None)
stations = U.load(U.P('data/history/stations_hist.json'), None) or U.load(U.P('data/stations.json'), {})
years = [int(y) for y in (sys.argv[1:] or ['2019', '2020', '2021', '2022', '2023', '2024'])]
days = [dt.date(y, 10, 1) + dt.timedelta(days=i) for y in years for i in range(92)]
todo = [d.isoformat() for d in days if not os.path.exists(f'{OUT}/{d}.json')]
print(len(todo), 'days to fetch', flush=True)
tmp = U.P('data/history/_tmp'); os.makedirs(tmp, exist_ok=True)
real_P = U.P
U.P = lambda *a: real_P('data/history/_tmp', *a[1:]) if a and a[0] == 'data/daily' else real_P(*a)   # keep live data/daily untouched
def one(d):
    page = U.fetch_date(d); return U.save_day(page, geo['d'], stations, want=d)
res = {}
with cf.ThreadPoolExecutor(max_workers=3) as pool:
    fut = {pool.submit(one, d): d for d in todo}
    for f in cf.as_completed(fut):
        d = fut[f]
        try:
            date, rows = f.result(); n = sum(r['rain'] is not None for r in rows); res[d] = n
            src = real_P('data/history/_tmp', d + '.json')
            if os.path.exists(src): shutil.move(src, f'{OUT}/{d}.json')
        except Exception as e:
            res[d] = f'FAILED {str(e)[:120]}'
        print(d, res[d], flush=True)
shutil.rmtree(tmp, ignore_errors=True)
U.save(real_P('data/history/stations_hist.json'), stations)
U.save(real_P('data/history/tnsmart_status.json'), dict(run=dt.datetime.now(U.IST).isoformat(timespec='seconds'), days=res))
