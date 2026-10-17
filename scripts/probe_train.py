"""Probe round 4: ECMWF open-data archive on AWS (ecmwf-forecasts bucket): which dates, resolutions, models and fields."""
import json, os, re, urllib.request
out = {}
def get(u, t=60):
    with urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'tn-rainfall-map probe'}), timeout=t) as r: return r.read()
B = 'https://ecmwf-forecasts.s3.eu-central-1.amazonaws.com'
for d in ['20230120', '20231115', '20241201', '20251101', '20261015']:
    try:
        x = get(f'{B}/?list-type=2&prefix={d}/00z/&max-keys=1000').decode()
        keys = re.findall(r'<Key>([^<]+)</Key>', x)
        dirs = sorted({'/'.join(k.split('/')[:5]) for k in keys})
        out[d] = dict(n=len(keys), dirs=dirs[:20], sample=[k for k in keys if '24h' in k][:6])
    except Exception as e:
        out[d] = 'ERR ' + str(e)[:200]
try:
    keys = out['20231115']['sample'] if isinstance(out.get('20231115'), dict) else []
    k = [k for k in keys if k.endswith('.index') and 'oper' in k][:1] or [k for k in keys if k.endswith('.index')][:1]
    if k:
        t = get(f'{B}/{k[0]}').decode().strip().split('\n')
        out['index_sample'] = dict(key=k[0], lines=len(t), params=sorted({json.loads(l).get('param') for l in t}), first=t[0][:300])
except Exception as e:
    out['index_sample'] = 'ERR ' + str(e)[:200]
try:
    keys = out['20241201']['sample'] if isinstance(out.get('20241201'), dict) else []
    k = [k for k in keys if k.endswith('.index')]
    out['index_2024'] = {kk: sorted({json.loads(l).get('param') for l in get(f'{B}/{kk}').decode().strip().split('\n')}) for kk in k[:4]}
except Exception as e:
    out['index_2024'] = 'ERR ' + str(e)[:200]
os.makedirs('data', exist_ok=True); json.dump(out, open('data/probe_train.json', 'w'), indent=1); print(json.dumps(out, indent=1)[:5000])
