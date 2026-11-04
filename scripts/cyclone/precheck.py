"""Pre-launch check for Kaggle jobs (run by cycle_tools.sh launch before anything is pushed).
python scripts/cyclone/precheck.py SLUG ACCOUNT 'CMD'   -> exit 0 = OK, 1 = refuse (reasons printed)
Checks: 1 every inline JSON in the command parses; 2 every setting name (inline JSON or referenced kaggle_cfg file) is one the
model knows (mm2 DEFAULTS or a name the code reads through S[...] / S.get(...)), so a typo or an ignored setting cannot run
silently; 3 referenced config files and scripts exist and the config files parse; 4 the account is not still busy with an
earlier job (its last job has no COMPLETE/ERROR status yet) unless FORCE=1; 5 warns when no .json result file is written
(logs are cut to 30 kB)."""
import json, os, re, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MM = os.path.join(ROOT, 'scripts/cyclone/mm'); CFG = os.path.join(ROOT, 'data/cyclone/kaggle_cfg')
slug, acct, cmd = sys.argv[1], sys.argv[2], sys.argv[3]
bad, warn = [], []
src = open(os.path.join(MM, 'mm2.py')).read()
known = set(re.findall(r"S\[['\"](\w+)['\"]\]", src)) | set(re.findall(r"S\.get\(['\"](\w+)['\"]", src))
m = re.search(r"^DEFAULTS = dict\((.*?)\)\n", src, re.S | re.M)
known |= set(re.findall(r"(\w+)=", m.group(1))) if m else set()
known |= {'grid', 'layers', 'dt_min', 'set', 'name', 'bogus', 'dfi', 'rad_prm'}                    # handled by the drivers
DRIVER = {'_budget', '_win', '_months', '_chunk', '_split', '_ua'}
RADP = {'lw_cnt', 'alb_land', 'pdf', 'rhc_low', 'rhc_up'}
SETS = []
def check_settings(d, where):
    SETS.append((where, dict(d)))
    for k, v in d.items():
        if k in DRIVER: continue
        if k not in known: bad.append(f'{where}: setting "{k}" is not read anywhere in mm2.py (typo or ignored)')
        if k == 'rad_prm' and isinstance(v, dict):
            for kk in v:
                if kk not in RADP and kk not in open(os.path.join(MM, 'radcloud.py')).read(): bad.append(f'{where}: rad_prm "{kk}" unknown')
# 1 + 2: inline JSON between single quotes
for js in re.findall(r"'(\{.*?\})'", cmd):
    try: d = json.loads(js.replace('\\"', '"'))
    except Exception as e: bad.append(f'inline JSON does not parse: {e}: {js[:80]}'); continue
    for name, vs in d.items():
        if isinstance(vs, dict): check_settings(vs, f'inline[{name}]')
        else: check_settings(d, 'inline'); break
# 3: config files and scripts
for f in re.findall(r"kaggle_cfg/([\w.-]+\.json)", cmd):
    p = os.path.join(CFG, f)
    if not os.path.exists(p): bad.append(f'config {f} missing'); continue
    try: C = json.load(open(p))
    except Exception as e: bad.append(f'config {f} does not parse: {e}'); continue
    V = C.get('variants', {})
    for v in (V.values() if isinstance(V, dict) else [x.get('set', {}) | {kk: x[kk] for kk in ('layers', 'grid') if kk in x} for x in V]):
        check_settings(v or {}, f)
for s in re.findall(r"python [-\w ]*?(\w+\.py)", cmd):
    if not os.path.exists(os.path.join(MM, s)): bad.append(f'script {s} not in scripts/cyclone/mm')
# 4: account busy?
if os.environ.get('FORCE') != '1':
    log = subprocess.run(['git', '-C', ROOT, 'log', '--format=%H', '-40', '--', 'data/cyclone/KAGGLE'], capture_output=True, text=True).stdout.split()
    for h in log:
        k = subprocess.run(['git', '-C', ROOT, 'show', f'{h}:data/cyclone/KAGGLE'], capture_output=True, text=True).stdout.split('\n')
        if len(k) > 4 and k[4].strip() == str(acct):
            st = os.path.join(ROOT, 'data/cyclone/kaggle', k[0].strip(), 'status.txt')
            last = open(st).read().strip().split('\n')[-1] if os.path.exists(st) else ''
            if not re.search(r'COMPLETE|ERROR|CANCEL|refused', last, re.I) and k[0].strip() != slug:
                bad.append(f'account {acct} still busy with {k[0].strip()} (last status: "{last[-60:]}") - use FORCE=1 to override')
            break
# 5: full results saved?
if '/kaggle/working/' not in cmd or not re.search(r"/kaggle/working/[\w.-]+\.json", cmd): warn.append('no .json result file in /kaggle/working - only the last 30 kB of the log will come back')
# 2b (when JAX + dinosaur are installed here): build the model on a tiny grid with each settings set and confirm every
# setting arrived in the model's parameter table (catches settings a driver drops or renames)
try:
    sys.path.insert(0, MM); import mm2
    for where, d in SETS:
        dd = {k: v for k, v in d.items() if k not in DRIVER and k not in ('grid', 'layers', 'dt_min', 'set', 'name', 'bogus', 'dfi')}
        try:
            M = mm2.Model('T42', d.get('layers', 32) if not isinstance(d.get('layers'), dict) else 32, None, dd)
        except Exception as e:
            bad.append(f'{where}: model does not build with these settings: {repr(e)[:120]}'); continue
        for k, v in dd.items():
            if M.S.get(k) != v: bad.append(f'{where}: setting {k}={v} did not reach the model (got {M.S.get(k)})')
except ImportError:
    warn.append('JAX/dinosaur not installed here - dynamic settings check skipped')
# 6 (4 Nov): control regression - whenever the model code differs from the reference's code hash, the control (all options
# at defaults) must still be bit-identical to the last accepted version (scripts/cyclone/regress.py)
try:
    sys.path.insert(0, os.path.join(ROOT, 'scripts/cyclone')); import regress, numpy as _np
    if os.path.exists(regress.REF) and str(_np.load(regress.REF)['hash']) != regress.code_hash():
        print('PRECHECK: model code changed since the regression reference - running the control regression check')
        if regress.main([]) != 0: bad.append('control regression FAILED: the control model changed (see above); renew the reference only if intended')
except ImportError:
    warn.append('regression check skipped (JAX not installed here)')
for w in warn: print('PRECHECK warning:', w)
for b in bad: print('PRECHECK REFUSED:', b)
sys.exit(1 if bad else 0)
