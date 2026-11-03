"""Reference single-column runs with NOAA's CCPP SCM (GFS v16 physics) for the low-level heat-budget comparison (P1).
Builds ccpp-scm v7.0.0 in a micromamba env (gfortran, cmake, netcdf-fortran), runs the standard cases (BOMEX, TWP-ICE)
with the GFS v16 suite, and writes a compact JSON summary of every temperature/moisture tendency profile in the output
(time-mean over chosen windows) so MEGAM's column physics can be compared process by process on the same forcing.
Stage 1 of the comparison: get the reference running. python scm_ref.py OUT_JSON"""
import os, sys, json, subprocess, glob, time
OUT = sys.argv[1]; W = '/kaggle/working/scm'; os.makedirs(W, exist_ok=True); log = {'steps': []}
def sh(cmd, tag, cwd=None, tmo=5400):
    t = time.time(); r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=tmo)
    log['steps'].append(dict(tag=tag, rc=r.returncode, sec=round(time.time() - t), tail=(r.stdout + r.stderr)[-3000:]))
    print(f'== {tag}: rc {r.returncode} ({round(time.time() - t)} s)\n' + (r.stdout + r.stderr)[-1500:], flush=True)
    json.dump(log, open(OUT, 'w')); return r.returncode == 0
MM = '/tmp/bin/micromamba'; ENV = '/tmp/scmenv'
ok = sh(f'cd /tmp && curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xj bin/micromamba && {MM} create -y -q -p {ENV} -c conda-forge '
        'python=3.11 gfortran_linux-64 gcc_linux-64 gxx_linux-64 cmake make netcdf-fortran netcdf4 f90nml numpy openmpi', 'env')
if ok: ok = sh('git clone -q --recursive -b v7.0.0 https://github.com/NCAR/ccpp-scm', 'clone', cwd=W)
SRC = W + '/ccpp-scm'
envp = (f'export PATH={ENV}/bin:$PATH CC={ENV}/bin/x86_64-conda-linux-gnu-gcc FC={ENV}/bin/x86_64-conda-linux-gnu-gfortran CXX={ENV}/bin/x86_64-conda-linux-gnu-g++ '
        f'NETCDF={ENV} NETCDF_ROOT={ENV} CMAKE_PREFIX_PATH={ENV} LD_LIBRARY_PATH={ENV}/lib; ')
# NCEP libraries the SCM needs (bacio, sp, w3emc): not on conda-forge -> build from the NOAA-EMC sources into the env
for lib, tag in (('bacio', 'v2.4.1'), ('sp', 'v2.5.0'), ('w3emc', 'v2.11.0')):
    if ok: ok = sh(envp + f'git clone -q -b {tag} https://github.com/NOAA-EMC/NCEPLIBS-{lib} && mkdir -p NCEPLIBS-{lib}/b && cd NCEPLIBS-{lib}/b && '
                   f'cmake -DCMAKE_INSTALL_PREFIX={ENV} -DBUILD_TESTING=OFF -DOPENMP=OFF .. > c.log 2>&1; tail -5 c.log; make -j4 install > m.log 2>&1; rc=$?; tail -8 m.log; exit $rc', 'lib ' + lib, cwd=W)
# static physics data and processed case inputs (v7 scripts)
if ok: sh('./contrib/get_all_static_data.sh > gs.log 2>&1; tail -5 gs.log; ./contrib/get_thompson_tables.sh > gt.log 2>&1; tail -3 gt.log', 'static data', cwd=SRC)
if ok: ok = sh(envp + 'mkdir -p scm/bin && cd scm/bin && cmake -DCCPP_SUITES=SCM_GFS_v16 ../src > cm.log 2>&1; tail -30 cm.log; make -j4 > mk.log 2>&1; rc=$?; tail -40 mk.log; ls; exit $rc', 'build', cwd=SRC)
if ok: sh(envp + 'cd scm/bin && ls; python run_scm.py --help | head -30', 'runner help', cwd=SRC)
for case in ('bomex', 'twpice'):
    if ok: sh(envp + f'cd scm/bin && python run_scm.py -c {case} -s SCM_GFS_v16 > run_{case}.log 2>&1; tail -25 run_{case}.log; ls -R output_* | head -20', f'run {case}', cwd=SRC)
# summarise every tendency-like variable
try:
    subprocess.run('pip install -q netCDF4', shell=True)
    from netCDF4 import Dataset
    import numpy as np
    log['cases'] = {}
    for f in sorted(set(glob.glob(SRC + '/scm/**/output_*/output.nc', recursive=True))):
        d = Dataset(f); case = f.split('output_')[1].split('/')[0]; e = dict(vars={}, file=f)
        for n, v in d.variables.items():
            e['vars'][n] = dict(dims=list(v.dimensions), units=getattr(v, 'units', ''), desc=getattr(v, 'description', getattr(v, 'long_name', '')))
        for n, v in d.variables.items():
            nl = n.lower()
            if v.ndim >= 2 and any(s in nl for s in ('dt', 'tend', 'dq', 'pres', 'temp', 'qv', 'cld', 'rh', 'w_ls')):
                a = np.asarray(v[:], float); a = a.reshape(a.shape[0], -1)
                e.setdefault('mean', {})[n] = dict(all=np.nanmean(a, 0).round(8).tolist(), first_day=np.nanmean(a[:max(1, a.shape[0] // 4)], 0).round(8).tolist())
            elif v.ndim == 1 and n.lower() in ('time', 'time_inst', 'time_diag', 'pres_s', 'shf', 'lhf', 'rain', 'tprcp'):
                e.setdefault('series', {})[n] = np.asarray(v[:], float).round(5).tolist()[:400]
        log['cases'][case] = e
except Exception as ex:
    log['summary_error'] = repr(ex)
json.dump(log, open(OUT, 'w')); print('done', list(log.get('cases', {}).keys()), log.get('summary_error'))
