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
    """busy slots per account = unfinished workflow runs (queued ones will push when they start), each mapped to the
    account in ITS OWN commit's data/cyclone/KAGGLE (5 Nov 17:40 fix: mapping by slug's latest launch undercounted when a
    slug had been launched on several accounts -> pushes refused -> relaunch storm). Same slug + account counted once
    (one Kaggle kernel)."""
    busy = {}
    for stt in ('in_progress', 'queued', 'waiting', 'pending', 'requested'):
        r = sh(f"gh api 'repos/sridhar13294-rgb/tn-rainfall-map/actions/workflows/cyclone-kaggle.yml/runs?status={stt}&per_page=100' --jq '.workflow_runs[] | (.display_title + \"|\" + .head_sha)'").stdout
        for l in r.split('\n'):
            if '|' not in l: continue
            slug, sha = l.replace('Cyclone study: Kaggle job ', '').strip().split('|')
            k = sh(f"git show {sha}:data/cyclone/KAGGLE").stdout.split('\n')
            if len(k) >= 5 and k[4].strip():
                b_ = busy.setdefault(k[4].strip(), [])
                if slug not in b_: b_.append(slug)
    import glob as _g                                                           # push-only launches (5 Nov 17:50): kernels awaiting the collector
    for f in _g.glob('data/cyclone/pending/*__*'):
        slug, a = os.path.basename(f).split('__'); b_ = busy.setdefault(a, [])
        if slug not in b_: b_.append(slug)
    return busy
def collect_now():
    """ask cyclone-collect.yml to fetch finished push-only kernels (frees their slots), wait for it (max 8 min)"""
    import glob as _g
    if not _g.glob('data/cyclone/pending/*__*'): return
    open('data/cyclone/COLLECT_REQ', 'w').write(time.strftime('%Y-%m-%dT%H:%M:%SZ\n', time.gmtime()))
    sh("git add data/cyclone/COLLECT_REQ; git commit -qm 'Collect request'; git pull -q --rebase origin cases; git push -q origin cases")
    time.sleep(30)
    for _ in range(16):
        r = sh("gh run list --workflow cyclone-collect.yml -L 3 --json status --jq '.[].status'").stdout.split()
        if r and all(x == 'completed' for x in r): break
        time.sleep(30)
    sh('git pull -q --rebase origin cases')
while True:
    sh('git pull -q --rebase origin cases'); collect_now()
    q = json.load(open(Q)) if os.path.exists(Q) else []
    # re-queue launches that Kaggle refused (e.g. 'Maximum batch GPU session count of 2 reached') - self-correcting
    d = json.load(open(DONE)) if os.path.exists(DONE) else []; keep = []; back = []
    def _fresh(j): return bool(j.get('at')) and time.time() - time.mktime(time.strptime(j['at'], '%Y-%m-%dT%H:%MZ')) + time.timezone < 1500
    freshslugs = {j['slug'] for j in d if _fresh(j)}
    for j in d:
        # refused = the LATEST push attempt failed (push.txt is rewritten by every run; status.txt keeps old lines until the new run polls)
        pt = f"data/cyclone/kaggle/{j['slug']}/push.txt"; last = open(pt).read().strip().split('\n')[-1] if os.path.exists(pt) else ''
        last = 'push refused' if (last and not re.search(r'successfully pushed', last, re.I)) or re.search(r'error|authentication required|denied', last, re.I) else ''
        fresh = j.get('at') and time.time() - time.mktime(time.strptime(j['at'], '%Y-%m-%dT%H:%MZ')) + time.timezone < 1500
        # 5 Nov 17:35 fix: DONE can hold the same slug several times (each earlier launch) -> re-queue it ONCE only,
        # and never while a newer launch of that slug is still fresh (fresh = any entry of that slug < 25 min old)
        dropped = set(open('data/cyclone/queue_dropped.txt').read().split()) if os.path.exists('data/cyclone/queue_dropped.txt') else set()   # 6 Nov: jobs cancelled on purpose are never re-queued
        if 'push refused' in last and not fresh and j['slug'] not in {x['slug'] for x in q} | {x['slug'] for x in back} | freshslugs | dropped:
            back.append({k: v for k, v in j.items() if k not in ('account', 'at')}); print('re-queued (refused):', j['slug'], flush=True)
        else: keep.append(j)
    if back: q = back + q
    q = list({j['slug']: j for j in reversed(q)}.values())[::-1]                # never two queue entries of one slug                                                       # in memory only: files are written + committed at the end
    refused = {j['slug'] for j in back}
    if not q: print('queue empty'); break
    busy = running(); left = []; newdone = []
    for j in q:
        down = set(open('data/cyclone/accounts_down.txt').read().split()) if os.path.exists('data/cyclone/accounts_down.txt') else set()   # 5 Nov 20:10: API auth lost
        accts = [a for a in ([str(j['account'])] if j.get('account') else [str(a) for a in range(1, 15)]) if a not in down]
        amax = dict(l.split() for l in open('data/cyclone/accounts_max.txt').read().split('\n') if l.strip()) if os.path.exists('data/cyclone/accounts_max.txt') else {}   # per-account cap (partner account 4: 1 job at a time)
        free = [a for a in accts if len(busy.get(a, [])) < int(amax.get(a, MAXPER))]
        if not free: left.append(j); continue
        a = min(free, key=lambda x: len(busy.get(x, [])))
        r = sh(f". scripts/cyclone/cycle_tools.sh; FORCE=1 launch {j['slug']} {j['inputs']} {shlex.quote(j["cmd"])} {a} {j.get('note', 'q')}")
        out = (r.stdout + r.stderr).strip().split('\n')[-1]; print(j['slug'], '->', a, '|', out, flush=True)
        if 'launched' in out:                                                   # kept in memory: writing files between launches breaks the next launch's git sync
            busy.setdefault(a, []).append(j['slug']); newdone.append(dict(j, account=a, at=time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime())))
        else: left.append(j)
    launched = {j['slug'] for j in q} - {j['slug'] for j in left}
    sh('git pull -q --rebase origin cases')                                      # merge: entries added meanwhile are kept
    cur = json.load(open(Q)) if os.path.exists(Q) else []
    left = [j for j in back + cur if j['slug'] not in launched]; left = list({j['slug']: j for j in left}.values())
    if back:                                                                    # drop the refused entries from the done list
        dd = json.load(open(DONE)) if os.path.exists(DONE) else []; json.dump([j for j in dd if j['slug'] not in refused or j['slug'] in launched], open(DONE, 'w'), indent=1)
    json.dump(left, open(Q, 'w'), indent=1)
    dd = json.load(open(DONE)) if os.path.exists(DONE) else []; json.dump(dd + newdone, open(DONE, 'w'), indent=1)
    sh(f"git add {Q} {DONE}; git commit -qm 'Queue: {len(launched)} launched, {len(left)} waiting'")
    for _i in range(6):                                                         # 5 Nov 23:15: the single push could fail on a race and leave the queue stale
        if sh('git pull -q --rebase origin cases && git push -q origin cases').returncode == 0: break
        time.sleep(15)
    else: print('WARNING: queue commit not pushed', flush=True)
    print(len(left), 'waiting', flush=True)
    if not left or not LOOP: break
    time.sleep(LOOP * 60)
