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
else: sh('pip install -q -U "jax[cuda12]"')
sh('free -g; nproc; python -c "import jax; print(jax.devices())" || true')
sh('pip install -q xarray "git+https://github.com/google-research/dinosaur@91e07a733ed6b579e4d83c4a9d9225b85ab3fae0"')
sh('rm -rf repo && git clone -q --depth 1 -b cases https://github.com/sridhar13294-rgb/tn-rainfall-map.git repo')
for f in "__FILES__".split(','):
    if f: sh('curl -sSL -o %s https://github.com/sridhar13294-rgb/tn-rainfall-map/releases/download/era5-cases/%s' % (f, f))
print('setup s', round(time.time() - t), flush=True)
sh(JOB + ' 2>&1 | tee job.log')
sh('rm -rf repo ' + ' '.join("__FILES__".split(',')))
print('total s', round(time.time() - t), flush=True)
