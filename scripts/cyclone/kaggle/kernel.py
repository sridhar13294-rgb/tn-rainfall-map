# Kaggle job (pushed by .github/workflows/cyclone-kaggle.yml): installs JAX for the accelerator and Dinosaur, takes our
# model code from the public repo, downloads the inputs from the repo's release, runs the command in JOB below and
# leaves results in /kaggle/working (fetched back by the workflow).
import subprocess, os, sys, time
JOB = "__JOB__"            # filled in by the workflow
W = '/kaggle/working'; os.chdir(W)
def sh(c):
    print('+', c, flush=True); r = subprocess.run(c, shell=True); print('exit', r.returncode, flush=True); return r.returncode
t = time.time()
sh('nvidia-smi || true')
ACC = "__ACC__"           # accelerator asked for (filled in by the workflow)
import glob
acc = 'tpu' if (ACC.lower().startswith('tpu') or os.environ.get('TPU_NAME') or glob.glob('/dev/accel*') or os.path.exists('/dev/vfio')
                or os.environ.get('TPU_ACCELERATOR_TYPE')) else 'cuda12'
print('accelerator asked', ACC, '-> jax for', acc, flush=True)
if acc == 'tpu': sh('pip uninstall -y -q jax-cuda12-plugin jax-cuda12-pjrt 2>/dev/null; pip install -q -U "jax[tpu]" -f https://storage.googleapis.com/jax-releases/libtpu_releases.html')
else:
    # 10 Nov: one fixed GPU stack for every run. Kaggle preinstalls jax_cuda13_plugin 0.11.1; with an unpinned upgrade some runs
    # failed to initialise the cuda12 plugin (FFI API 0.5 vs 0.4) and ran on another library stack -> base2 d3 Bay u850 -4.65 vs
    # -4.33 for identical code and starts. Remove the cuda13 plugin, pin versions, and STOP if the cuda12 plugin does not load.
    sh('pip uninstall -y -q jax-cuda13-plugin jax-cuda13-pjrt 2>/dev/null; pip install -q "jax[cuda12]==0.12.0.1"')
    chk = subprocess.run('python -c "import jax; d = jax.devices(); print(d, jax.__version__); assert d[0].platform == \'gpu\'"',
                         shell=True, capture_output=True, text=True)
    print(chk.stdout, chk.stderr[-2000:], flush=True)
    # (10 Nov 16:10) the 'cudnn_rnn_ffi ... API version' plugin message is harmless (runs with and without it had the same speed
    # and identical track results); stop only if JAX is not on the GPU.
    if chk.returncode:
        print('STACK CHECK FAILED - stopping before any model run (no mixed-library results)', flush=True); sys.exit(3)
sh('free -g; nproc')
sh('pip install -q xarray "git+https://github.com/google-research/dinosaur@91e07a733ed6b579e4d83c4a9d9225b85ab3fae0"')
sh('rm -rf repo && git clone -q --depth 1 -b cases https://github.com/sridhar13294-rgb/tn-rainfall-map.git repo')
for f in "__FILES__".split(','):
    if f: sh('curl -sSL --retry 6 --retry-all-errors --retry-delay 15 -o %s https://github.com/sridhar13294-rgb/tn-rainfall-map/releases/download/era5-cases/%s && python -c "import zipfile,sys; f=sys.argv[1]; sys.exit(0 if not f.endswith(\'.npz\') or zipfile.is_zipfile(f) else 1)" %s || { echo BAD_DOWNLOAD %s; rm -f %s; curl -sSL --retry 6 --retry-all-errors --retry-delay 30 -o %s https://github.com/sridhar13294-rgb/tn-rainfall-map/releases/download/era5-cases/%s; }' % (f, f, f, f, f, f, f))
print('setup s', round(time.time() - t), flush=True)
sh(JOB + ' 2>&1 | tee job.log')
sh('rm -rf repo ' + ' '.join("__FILES__".split(',')))
print('total s', round(time.time() - t), flush=True)
