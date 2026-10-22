#!/bin/bash
# One 6-hourly cycle of the moist multi-level model's 51-member ensemble. Run from the repo root on the cases branch,
# AFTER ours_cycle.sh (which fetches the GFS analysis, incl. the global multi-level copy):
#   scripts/cyclone/ours/ours_cycle_m.sh <workdir> <artdir>
# 1) start the moist-model workflow on that GFS run (17 parallel jobs, 3 members each), 2) wait for it,
# 3) merge the members, 4) build the preview page (<artdir>/moist_preview.html), 5) commit the run and the history.
set -e
W=${1:?workdir}; A=${2:?artdir}; R=repos/sridhar13294-rgb/tn-rainfall-map
git config user.email noreply@anthropic.com; git config user.name Claude
git pull -q --rebase origin cases
LIVE=$(python3 -c "import json;print(json.load(open('data/cyclone/ours/live_inputs.json'))['file'])"); RUNID=${LIVE#live_GFS_}; RUNID=${RUNID%.npz}
gh api $R/releases/tags/era5-cases -q ".assets[]|select(.name==\"live_GFSM_$RUNID.npz\")|.name" | grep -q GFSM || { echo "NO GFSM $RUNID"; exit 1; }
# which model: version 2 once a depression has formed (it is better on formed storms), version 1 before (v2 cannot yet
# build one coherent storm from a weak seedling). data/cyclone/mm/live_script, if present, overrides.
[ -s "$W/$LIVE" ] || { ID=$(gh api $R/releases/tags/era5-cases -q ".assets[]|select(.name==\"$LIVE\")|.id"); gh api -H 'Accept: application/octet-stream' $R/releases/assets/$ID > "$W/$LIVE"; }
FORMED=$(cd scripts/cyclone/analysis && python3 -W ignore -c "
from ours_live import detect; b=detect('$W/$LIVE')['bay']; print(int(b['vort850'] >= 7.0 and b['depth'] >= 2.5))" 2>/dev/null || echo 0)
LSC=$(cat data/cyclone/mm/live_script 2>/dev/null || { [ "$FORMED" = 1 ] && echo live2.py || echo live.py; }); SUF=""; [ "$LSC" = live2.py ] && SUF=-v2; LD=data/cyclone/mm/live/$RUNID$SUF
echo "formed=$FORMED model=$LSC" 
if [ ! -f $LD/ens.json ] && [ "$(head -n 2 data/cyclone/MMLIVE 2>/dev/null | tr '\n' ' ')" != "$RUNID $LSC " ]; then
  printf '%s\n%s\n#moist model live ensemble %s\n' "$RUNID" "$LSC" "$(date -u +%FT%H:%MZ)" > data/cyclone/MMLIVE
  git add data/cyclone/MMLIVE; git commit -qm "Moist model: live ensemble on GFS $RUNID" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AXxjaemsi36VrJDzeKZ8zA"
  for i in 1 2 3 4 5; do git pull -q --rebase origin cases && git push -q origin HEAD:cases && break; sleep 7; done
  SHA=$(git rev-parse HEAD); sleep 20
  RID=""; for i in $(seq 1 30); do RID=$(gh api "$R/actions/workflows/cyclone-mmlive.yml/runs?head_sha=$SHA" -q '.workflow_runs[0].id' 2>/dev/null); [ -n "$RID" ] && break; sleep 10; done
  until [ "$(gh api $R/actions/runs/$RID -q .status)" = completed ]; do sleep 30; done
  git pull -q --rebase origin cases
fi
# a run already started (e.g. resumed after a restart): wait for the latest moist-model workflow run to finish
RL=$(gh api "$R/actions/workflows/cyclone-mmlive.yml/runs?per_page=1" -q '.workflow_runs[0].id' 2>/dev/null)
[ -n "$RL" ] && until [ "$(gh api $R/actions/runs/$RL -q .status 2>/dev/null)" = completed ]; do sleep 30; done
git pull -q --rebase origin cases
for f in live_GFS_$RUNID.npz; do [ -s "$W/$f" ] || { ID=$(gh api $R/releases/tags/era5-cases -q ".assets[]|select(.name==\"$f\")|.id"); gh api -H 'Accept: application/octet-stream' $R/releases/assets/$ID > "$W/$f"; }; done
git fetch -q origin main; git show origin/main:data/sst_indices.json > "$W/sst.json"
N=$(ls $LD/part_*.json | wc -l)
if [ "$LSC" = "live2.py" ]; then
  python3 -W ignore scripts/cyclone/mm/live2.py merge "$W/live_GFS_$RUNID.npz" "$W/sst.json" data/cyclone/ours/live_inputs.json data/cyclone/mm/tn_sites.json "$W/ens_m_$RUNID.json" $LD/part_*.json
  MM=moist2
else
  python3 -W ignore scripts/cyclone/mm/live.py merge "$W/live_GFS_$RUNID.npz" "$W/sst.json" data/cyclone/ours/live_inputs.json "$W/ens_m_$RUNID.json" $LD/part_*.json
  MM=moist
fi
cp "$W/ens_m_$RUNID.json" $LD/ens.json
python3 scripts/cyclone/ours/ours_page.py "$W/ens_m_$RUNID.json" "$A/moist_preview.html" --method $MM
git add data/cyclone/mm/live data/cyclone/ours/live_history_moist*.json; git commit -qm "Moist model: live ensemble $RUNID merged" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AXxjaemsi36VrJDzeKZ8zA" || true
for i in 1 2 3 4 5; do git pull -q --rebase origin cases && git push -q origin HEAD:cases && break; sleep 7; done
echo "DONE_M $RUNID parts $N page: $A/moist_preview.html"
