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
    """busy slots per account = workflow runs still in progress (each one is a live Kaggle session or a push about to be
    made), mapped to the account of that slug's latest launch. Status files go stale; the run list does not."""
    live = []
    for stt in ('in_progress', 'queued', 'waiting', 'pending', 'requested'):
        r = sh(f"gh api 'repos/sridhar13294-rgb/tn-rainfall-map/actions/workflows/cyclone-kaggle.yml/runs?status={stt}&per_page=100' --jq '.workflow_runs[].display_title'").stdout
        live += [l.replace('Cyclone study: Kaggle job ', '').strip() for l in r.split('\n') if l.strip()]
    acct_of = {}
    for h in sh("git log --format=%H -400 -- data/cyclone/KAGGLE").stdout.split():
        k = sh(f"git show {h}:data/cyclone/KAGGLE").stdout.split('\n')
        if len(k) >= 5 and k[0].strip() not in acct_of: acct_of[k[0].strip()] = k[4].strip()
    busy = {}
    for slug in sorted(set(live)):                                              # several runs can poll the same kernel
        if slug in acct_of: busy.setdefault(acct_of[slug], []).append(slug)
    return busy
while True:
    sh('git pull -q --rebase origin cases')
    q = json.load(open(Q)) if os.path.exists(Q) else []
    # re-queue launches that Kaggle refused (e.g. 'Maximum batch GPU session count of 2 reached') - self-correcting
    d = json.load(open(DONE)) if os.path.exists(DONE) else []; keep = []; back = []
    for j in d:
        # refused = the LATEST push attempt failed (push.txt is rewritten by every run; status.txt keeps old lines until the new run polls)
        pt = f"data/cyclone/kaggle/{j['slug']}/push.txt"; last = open(pt).read().strip().split('\n')[-1] if os.path.exists(pt) else ''
        last = 'push refused' if re.search(r'error', last, re.I) else ''
        fresh = j.get('at') and time.time() - time.mktime(time.strptime(j['at'], '%Y-%m-%dT%H:%MZ')) + time.timezone < 1500
        if 'push refused' in last and not fresh and j['slug'] not in {x['slug'] for x in q}:
            back.append({k: v for k, v in j.items() if k not in ('account', 'at')}); print('re-queued (refused):', j['slug'], flush=True)
        else: keep.append(j)
    if back: q = back + q                                                       # in memory only: files are written + committed at the end
    refused = {j['slug'] for j in back}
    if not q: print('queue empty'); break
    busy = running(); left = []; newdone = []
    for j in q:
        accts = [str(j['account'])] if j.get('account') else [str(a) for a in range(1, 15)]
        free = [a for a in accts if len(busy.get(a, [])) < MAXPER]
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
    sh(f"git add {Q} {DONE}; git commit -qm 'Queue: {len(launched)} launched, {len(left)} waiting' ; git pull -q --rebase origin cases; git push -q origin cases")
    print(len(left), 'waiting', flush=True)
    if not left or not LOOP: break
    time.sleep(LOOP * 60)
