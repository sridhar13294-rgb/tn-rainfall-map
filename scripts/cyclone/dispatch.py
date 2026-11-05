"""Job queue dispatcher (5 Nov, Sridhar: run all tests in parallel). Kaggle accepts 2 GPU jobs per account at once.
Queue file data/cyclone/queue.json: list of {slug, inputs, cmd, note, (account)} launched in order onto any account with
fewer than MAXPER running jobs (running = launched slug without a COMPLETE/ERROR/CANCEL status yet). Launched entries are
moved to data/cyclone/queue_done.json. python dispatch.py [MAXPER=2] [LOOP_MIN=0]"""
import json, os, re, shlex, subprocess, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); os.chdir(ROOT)
MAXPER = int(sys.argv[1]) if len(sys.argv) > 1 else 2; LOOP = float(sys.argv[2]) if len(sys.argv) > 2 else 0
Q, DONE = 'data/cyclone/queue.json', 'data/cyclone/queue_done.json'
def sh(c): return subprocess.run(c, shell=True, capture_output=True, text=True)
def running():
    log = sh("git log --format=%H -400 -- data/cyclone/KAGGLE").stdout.split(); seen = set(); busy = {}
    for h in log:
        k = sh(f"git show {h}:data/cyclone/KAGGLE").stdout.split('\n')
        if len(k) < 5: continue
        slug, acct = k[0].strip(), k[4].strip()
        if slug in seen: continue
        seen.add(slug); st = f'data/cyclone/kaggle/{slug}/status.txt'
        last = open(st).read().strip().split('\n')[-1] if os.path.exists(st) else ''
        if not re.search(r'COMPLETE|ERROR|CANCEL|refused', last, re.I): busy.setdefault(acct, []).append(slug)
    return busy
while True:
    sh('git pull -q --rebase origin cases')
    q = json.load(open(Q)) if os.path.exists(Q) else []
    if not q: print('queue empty'); break
    busy = running(); left = []
    for j in q:
        accts = [str(j['account'])] if j.get('account') else [str(a) for a in range(1, 15)]
        free = [a for a in accts if len(busy.get(a, [])) < MAXPER]
        if not free: left.append(j); continue
        a = min(free, key=lambda x: len(busy.get(x, [])))
        r = sh(f". scripts/cyclone/cycle_tools.sh; FORCE=1 launch {j['slug']} {j['inputs']} {shlex.quote(j["cmd"])} {a} {j.get('note', 'q')}")
        out = (r.stdout + r.stderr).strip().split('\n')[-1]; print(j['slug'], '->', a, '|', out, flush=True)
        if 'launched' in out:
            busy.setdefault(a, []).append(j['slug']); d = json.load(open(DONE)) if os.path.exists(DONE) else []
            d.append(dict(j, account=a, at=time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime()))); json.dump(d, open(DONE, 'w'), indent=1)
        else: left.append(j)
    json.dump(left, open(Q, 'w'), indent=1)
    sh(f"git add {Q} {DONE}; git commit -qm 'Queue: {len(q) - len(left)} launched, {len(left)} waiting' ; git pull -q --rebase origin cases; git push -q origin cases")
    print(len(left), 'waiting', flush=True)
    if not left or not LOOP: break
    time.sleep(LOOP * 60)
