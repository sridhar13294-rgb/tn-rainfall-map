"""Collector for push-only Kaggle launches (5 Nov 17:50; GitHub's 20 concurrent runners were the real cap because every
launch workflow polled its kernel for up to 9 h). data/cyclone/pending/<slug>__<account>: one empty marker file per
pushed kernel (one file each, so launches and the collector never edit the same file -> no rebase conflicts).
For each: kaggle kernels status with that account's credentials (env U<a>/T<a>); terminal (COMPLETE/ERROR/CANCEL) ->
download outputs into data/cyclone/kaggle/<slug>/ exactly as the old polling step did (json, job.log, kernel_*.log tails,
.npz to release model-maps), remove the line. Still running -> one status line appended. Run by cyclone-collect.yml."""
import os, re, subprocess, glob, shutil, time
P = 'data/cyclone/pending'
def run(c, env=None): return subprocess.run(c, shell=True, capture_output=True, text=True, env=env)
lines = [os.path.basename(f).split('__') for f in sorted(glob.glob(f'{P}/*__*'))]
keep = []
for ln in lines:
    slug, a = ln[0], ln[1]; u, t = os.environ.get(f'U{a}', ''), os.environ.get(f'T{a}', '')
    if not u or not t: print(slug, 'account', a, 'not configured'); keep.append(ln); continue
    kind = 'new-token' if t.startswith('KGAT') else 'legacy-key'
    # 5 Nov 20:00: a fresh HOME per account - the kaggle CLI caches credentials/tokens under ~/.kaggle and ~/.config, so
    # in one process later accounts were answered as another account ('Permission kernels.get denied' for 8 of 14).
    hm = f'/tmp/khome_{a}'; shutil.rmtree(hm, ignore_errors=True); os.makedirs(hm)
    env = dict(os.environ, HOME=hm, XDG_CONFIG_HOME=hm + '/.config', KAGGLE_CONFIG_DIR=hm + '/.kaggle', KAGGLE_USERNAME=u, KAGGLE_KEY=t, KAGGLE_API_TOKEN=t); D = f'data/cyclone/kaggle/{slug}'; os.makedirs(D, exist_ok=True)
    r = run(f'kaggle kernels status {u}/{slug}', env); s = (r.stdout + r.stderr).strip().split('\n')[-1].replace(u, 'USER')
    stamp = time.strftime('%H:%M', time.gmtime()); open(f'{D}/status.txt', 'a').write(f'{stamp} {s}\n'); print(slug, a, kind, s)
    if not re.search(r'complete|error|cancel', s, re.I): keep.append(ln); continue
    out = f'/tmp/kout_{slug}'; shutil.rmtree(out, ignore_errors=True); os.makedirs(out)
    print(run(f'kaggle kernels output {u}/{slug} -p {out}', env).stdout[-300:].replace(u, 'USER'))
    for f in glob.glob(f'{out}/*.json'): shutil.copy(f, D)
    if os.path.exists(f'{out}/job.log'): shutil.copy(f'{out}/job.log', D)
    for f in glob.glob(f'{out}/*.log'): open(f'{D}/kernel_{os.path.basename(f)}', 'w').write(open(f, errors='replace').read()[-30000:])
    for f in glob.glob(f'{D}/*'):
        if os.path.isfile(f) and not f.endswith('.npz'):
            try: txt = open(f).read(); open(f, 'w').write(txt.replace(u, 'USER'))
            except UnicodeDecodeError: pass
    for f in glob.glob(f'{out}/*.npz'):
        if run('gh release view model-maps').returncode: run('gh release create model-maps --title "Model map data" --notes "Forecast fields for the map viewer (from Kaggle jobs)" --target cases')
        if run(f'gh release upload model-maps {f} --clobber').returncode == 0: open(f'{D}/status.txt', 'a').write(f'uploaded {os.path.basename(f)} to release model-maps\n')
    open(f'{D}/status.txt', 'a').write(f'{stamp} collected\n'); os.remove(f'{P}/{slug}__{a}')
print(len(lines) - len(keep), 'collected,', len(keep), 'still running')
