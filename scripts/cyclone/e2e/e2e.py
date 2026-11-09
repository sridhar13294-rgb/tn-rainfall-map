"""E2E Networks TIR (GPU) driver for MEGAM jobs (9 Nov 2026). Used by .github/workflows/e2e-run.yml.
Secrets (GitHub, added by Sridhar, never in chat): E2E_API_KEY, E2E_API_TOKEN, E2E_PROJECT_ID. Location Delhi.
Rules (docs/HANDOFF.md 6 Nov 01:15): nothing idles - the container is deleted on finish, on failure and by the reaper at
the start of every run; hard wall-clock limit; minute ledger; 20-h cap.
Commands:
  discover                       -> print plan / image / security-group ids (names and numbers only; repo is public)
  reap                           -> delete every instance named megam-* (left over from a crashed run)
  create NAME PUBKEY_FILE        -> add the run's one-off SSH key, create the instance, wait until running; prints
                                    'ID IP KEYID'
  delete ID KEYID                -> delete instance and SSH key
Plan / image / security group come from data/cyclone/e2e/ids.json (filled from 'discover'; not secret)."""
import json, os, sys, time, urllib.request, urllib.parse

BASE = 'https://api.e2enetworks.com/myaccount/api/v1/gpu'
KEY, TOK, PID = os.environ['E2E_API_KEY'], os.environ['E2E_API_TOKEN'], os.environ['E2E_PROJECT_ID']
LOC = os.environ.get('E2E_LOCATION', 'Delhi')
IDS = 'data/cyclone/e2e/ids.json'


def call(method, path, body=None, extra=None):
    q = dict(apikey=KEY, project_id=PID, location=LOC, **(extra or {}))
    url = BASE + path + ('&' if '?' in path else '?') + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={'Authorization': 'Bearer ' + TOK, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read() or b'{}')
        except Exception: return e.code, {}


SAFE = {'id', 'name', 'sku_item_price_id', 'sku_id', 'unit_price', 'gpu', 'cpu', 'memory', 'series', 'currency', 'sku_type',
        'image_id', 'version_id', 'image_version_id', 'version', 'framework', 'status', 'committed_days', 'is_active',
        'available_inventory_status', 'gpu_name', 'image_version', 'description', 'rules', 'port_range', 'protocol', 'is_default',
        'slug_name', 'sku_name', 'gpu_type', 'gpu_count', 'cpu_count', 'memory_in_gb', 'location', 'price', 'plan_name',
        'is_inventory_available', 'inventory_status', 'unit', 'sku_type_name', 'display_name', 'type'}


def safe(o, depth=0):                       # keep only harmless fields (public logs)
    if isinstance(o, dict): return {k: safe(v, depth + 1) for k, v in o.items() if k in SAFE or isinstance(v, (dict, list))}
    if isinstance(o, list): return [safe(v, depth + 1) for v in o[:60]]
    return o


def instances():
    s, r = call('GET', '/notebooks/')
    d = r.get('data') if isinstance(r, dict) else None
    return d if isinstance(d, list) else (d or {}).get('results', []) if isinstance(d, dict) else []


cmd = sys.argv[1]
if cmd == 'discover':
    # 9 Nov: paths from docs.e2enetworks.com (get-gpu-service-image, get-gpu-plans-and-pricing-list, SKU list)
    def show(p, extra=None, n=6000):
        s, r = call('GET', p, extra=extra); d = r.get('data', r) if isinstance(r, dict) else r
        first = d[0] if isinstance(d, list) and d else d
        print(f'== GET {p} {extra or ""} -> HTTP {s}; keys:', sorted(first.keys())[:40] if isinstance(first, dict) else type(first).__name__)
        print(json.dumps(safe(d))[:n]); return d
    # 9 Nov run 3: compact table of 1-GPU hourly plans (SKU list = /gpu_service/sku/?image_version_id=..&service=notebook)
    for vid in (97, 111):              # Python 3.10 CUDA 12.4; Ubuntu 24.04 CUDA 13.0
        s_, r = call('GET', '/gpu_service/sku/', extra=dict(image_version_id=vid, service='notebook'))
        print(f'== SKUs for image_version_id {vid}: HTTP {s_}')
        for kind in ('GPU', 'SPOT_INSTANCE'):
            for it in (r.get('data') or {}).get(kind, []) or []:
                if str(it.get('gpu')) != '1': continue
                for pl in it.get('plans', []):
                    if pl.get('sku_type') == 'hourly' or kind == 'SPOT_INSTANCE':
                        print(f"  {kind:13s} {it.get('name'):38s} cpu {it.get('cpu'):>3s} mem {it.get('memory'):>6s} "
                              f"price_id {pl.get('sku_item_price_id')} Rs/h {pl.get('unit_price')} {pl.get('sku_type')} "
                              f"loc {pl.get('location')} avail {it.get('is_inventory_available')}")
    for p in ('/security_groups/', '/notebooks/'):
        show(p)
elif cmd == 'reap':
    for n in instances():
        if str(n.get('name', '')).startswith('megam-'):
            s, _ = call('DELETE', f"/notebooks/{n['id']}/"); print('reaped', n.get('name'), n['id'], 'HTTP', s)
    print('reap done')
elif cmd == 'create':
    name, pub = sys.argv[2], open(sys.argv[3]).read().strip(); ids = json.load(open(IDS))
    s, r = call('POST', '/ssh_keys/', dict(label=name, ssh_key=pub)); print('ssh key add HTTP', s, file=sys.stderr)
    s, r = call('GET', '/ssh_keys/'); keyid = next((k.get('id') for k in (r.get('data') or []) if k.get('label') == name or k.get('name') == name), '')
    body = dict(name=name, cluster_type='tir-cluster', image_type='pre-built', is_jupyterlab_enabled=False, notebook_type='new',
                notebook_url='', disk_size_in_gb=int(ids.get('disk_gb', 50)), dataset_id_list=[], add_ons=[],
                image_version_id=int(ids['image_version_id']), sku_item_price_id=int(ids['sku_item_price_id']),
                instance_type='paid_usage', public_key=[pub], security_group_id=int(ids['security_group_id']))
    s, r = call('POST', '/notebooks/', body)
    if s >= 300: print('create failed HTTP', s, json.dumps(safe(r))[:800], file=sys.stderr); sys.exit(2)
    iid = r['data']['id']; t0 = time.time(); ip = ''; t_run = None
    import re as _re
    def find_ip(o):                                                 # the IP field name is not documented: search for it
        if isinstance(o, dict):
            for k, v in o.items():
                if isinstance(v, str) and 'ip' in k.lower() and _re.fullmatch(r'\d+\.\d+\.\d+\.\d+', v.strip()): return v.strip()
            for v in o.values():
                x = find_ip(v)
                if x: return x
        if isinstance(o, list):
            for v in o:
                x = find_ip(v)
                if x: return x
        return ''
    while time.time() - t0 < 900:                                   # wait up to 15 min for 'running' + public IP
        s, r = call('GET', f'/notebooks/{iid}/'); d = r.get('data', {}) if isinstance(r, dict) else {}
        st = str(d.get('status', '')).lower(); ip = d.get('public_ip') or find_ip(d)
        print('status', st, 'ip', 'yes' if ip else 'no', file=sys.stderr)
        if st in ('running', 'ready') and ip: break
        if st in ('running', 'ready'):
            t_run = t_run or time.time()
            if time.time() - t_run > 120:                           # running but no IP: stop paying, show field names
                print('running without an IP field; keys:', sorted(d.keys()), file=sys.stderr); break
        if st in ('failed', 'error'): break
        time.sleep(15)
    print(iid, ip or 'NONE', keyid or 'NONE')
elif cmd == 'delete':
    iid, keyid = sys.argv[2], sys.argv[3]
    if iid not in ('', 'NONE'): s, _ = call('DELETE', f'/notebooks/{iid}/'); print('instance delete HTTP', s)
    if keyid not in ('', 'NONE'): s, _ = call('DELETE', f'/ssh_keys/{keyid}/'); print('ssh key delete HTTP', s)
