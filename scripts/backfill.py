"""Fill data/daily/ with every past TN SMART day of the year that is missing (or all, with --all)."""
import concurrent.futures as cf, datetime as dt, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import update as U

def main():
    geo = U.load(U.P('data/geo.json'), None)
    stations = U.load(U.P('data/stations.json'), {})
    today = dt.datetime.now(U.IST).date()
    start = dt.date(today.year, 1, 1)
    have = set(f[:10] for f in os.listdir(U.P('data/daily'))) if os.path.isdir(U.P('data/daily')) else set()
    days = [(start + dt.timedelta(days=i)).isoformat() for i in range((today - start).days)]
    todo = days if '--all' in sys.argv else [d for d in days if d not in have]
    print(len(todo), 'days to fetch', flush=True)
    res = {}
    def one(d):
        page = U.fetch_date(d)
        return U.save_day(page, geo['d'], stations, want=d)
    with cf.ThreadPoolExecutor(max_workers=3) as pool:
        fut = {pool.submit(one, d): d for d in todo}
        for f in cf.as_completed(fut):
            d = fut[f]
            try:
                date, rows = f.result(); res[d] = sum(r['rain'] is not None for r in rows)
            except Exception as e:
                res[d] = f'FAILED {e}'
            print(d, res[d], flush=True)
    U.save(U.P('data/stations.json'), stations)
    U.save(U.P('data/backfill_status.json'), dict(run=dt.datetime.now(U.IST).isoformat(timespec='seconds'), days=res))

if __name__ == '__main__':
    main()
