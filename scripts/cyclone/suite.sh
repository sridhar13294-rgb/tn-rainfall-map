#!/bin/bash
# Standard Stage-1 test suite for one candidate (same tests, same starts, deterministic, every time).
# Usage: . scripts/cyclone/cycle_tools.sh; bash scripts/cyclone/suite.sh NAME 'SETTINGS_JSON' "ACCOUNTS (10 numbers)" [LAYERS]
#   NAME e.g. pkg2; SETTINGS_JSON e.g. '{"cmt_mf":1.0}'; LAYERS 32 (default) or tp75.
# Jobs (slug tn-s-NAME-*): exam q0-q3 (73 starts: z500, regional biases incl. Oct-Dec TN u850), genesis gen0/gen1, TN rain (6
# seasonal starts), budget evolution (6 starts, windows 0-24/48-72/96-120 h, lows), storm budget radial 72 h (Nivar/Michaung/
# Vardah, inserted storm), quick6 tracks (6 storms 72 h). Scored by scripts/cyclone/score_suite.py NAME against the control.
set -e
cd "$(dirname "$0")/../.."; . scripts/cyclone/cycle_tools.sh
N=$1; S=$2; read -r -a A <<< "$3"; L=${4:-32}; [ ${#A[@]} -eq 10 ] || { echo "need 10 accounts"; exit 1; }
python3 - "$N" "$S" "$L" <<'P'
import json, sys
n, s, L = sys.argv[1], json.loads(sys.argv[2]), sys.argv[3]; d = 'data/cyclone/kaggle_cfg/'
lay = {} if L == '32' else {'layers': L}
json.dump({'tag': f'wx_s_{n}', 'truth': '/kaggle/working/wx_truth_2020.npz', 'grid': 'T170', 'days': 10, 'variants': [dict({'name': f'T170_{n}', 'set': s}, **lay)], 'dt_min': 20.0}, open(d + f'suite_{n}_wx.json', 'w'))
json.dump({'tag': f'gen48_s_{n}', 'grid': 'T170', 'hours': 120, 'lead': 48, 'nchunk': 2, 'every': 1, 'layers': 32 if L == '32' else L, 'variants': {f'T170_{n}': s}}, open(d + f'suite_{n}_gen.json', 'w'))
json.dump({'tag': f'sb_s_{n}', 'grid': 'T170', 'dt_min': 20.0, 'hours': 72, 'step': 3, 'radial': True, 'storms': ['Nivar', 'Michaung', 'Vardah'], 'variants': [dict({'name': f'T170_{n}', 'bogus': True, 'set': s}, **lay)]}, open(d + f'suite_{n}_sb.json', 'w'))
json.dump({'tag': f'q6_s_{n}', 'grid': 'T170', 'dt_min': 20.0, 'hours': 72, 'storms': ['Sidr', 'Titli', 'Phailin', 'Giri', 'Hamoon', 'Nivar'], 'nchunk': 1, 'variants': [dict({'name': f'T170_{n}', 'bogus': True, 'set': s}, **lay)]}, open(d + f'suite_{n}_q6.json', 'w'))
v = dict(s, grid='T170', **lay); open(f'/tmp/suite_{n}_tnr.txt', 'w').write(json.dumps({n: v}))
open(f'/tmp/suite_{n}_evo.txt', 'w').write(json.dumps({n: dict(v, _budget=True, _win=[[0, 24], [48, 72], [96, 120]])}))
P
git add data/cyclone/kaggle_cfg/suite_${N}_*.json; git commit -qm "Suite configs for $N

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" || true
git pull -q --rebase origin cases; git push -q origin cases
X='XLA_FLAGS="--xla_gpu_deterministic_ops=true --xla_disable_hlo_passes=constant_folding"'
C=../../../data/cyclone/kaggle_cfg; TS=2020-05-20,2020-06-09,2020-07-19,2020-08-08,2020-10-27,2020-12-06
TNR=$(cat /tmp/suite_${N}_tnr.txt); EVO=$(cat /tmp/suite_${N}_evo.txt)
for q in 0 1 2 3; do launch tn-s-$N-wx$q libm_wx2020_fields.npz,wx_truth_2020.npz "$X python -W ignore wx2.py /kaggle/working/libm_wx2020_fields.npz $C/suite_${N}_wx.json $q 4 /kaggle/working/wx_$q.json > /kaggle/working/wx_$q.log 2>&1; tail -3 /kaggle/working/wx_$q.log" ${A[$q]} s$N; done
for g in 0 1; do launch tn-s-$N-gen$g libm48_fields.npz "$X python -W ignore genesis2.py /kaggle/working/libm48_fields.npz $C/suite_${N}_gen.json $g 2 /kaggle/working/gen_$g.json > /kaggle/working/gen_$g.log 2>&1; tail -3 /kaggle/working/gen_$g.log" ${A[$((4+g))]} s$N; done
launch tn-s-$N-tnr libm_wx2020_fields.npz,wx_truth_2020.npz "$X python -W ignore tn_rain_diag.py /kaggle/working/libm_wx2020_fields.npz /kaggle/working/wx_truth_2020.npz /kaggle/working/tnr.json $TS '$TNR' > /kaggle/working/tnr.log 2>&1; tail -12 /kaggle/working/tnr.log" ${A[6]} s$N
launch tn-s-$N-evo libm_wx2020_fields.npz "cd . && $X python -W ignore wx_prof.py /kaggle/working/libm_wx2020_fields.npz /kaggle/working/prof.json 6 '$EVO' > /kaggle/working/prof.log 2>&1; tail -40 /kaggle/working/prof.log" ${A[7]} s$N
launch tn-s-$N-sb libm_fields.npz "$X python -W ignore storm_budget.py /kaggle/working/libm_fields.npz $C/suite_${N}_sb.json /kaggle/working/sb.json > /kaggle/working/sb.log 2>&1; tail -20 /kaggle/working/sb.log" ${A[8]} s$N
launch tn-s-$N-q6 libm_fields.npz "$X python -W ignore hind2.py /kaggle/working/libm_fields.npz $C/suite_${N}_q6.json 0 1 /kaggle/working/q6.json > /kaggle/working/q6.log 2>&1; tail -8 /kaggle/working/q6.log" ${A[9]} s$N
