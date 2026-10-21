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
if [ ! -f data/cyclone/mm/live/$RUNID/ens.json ] && [ "$(head -n 1 data/cyclone/MMLIVE 2>/dev/null)" != "$RUNID" ]; then
  printf '%s\n#moist model live ensemble %s\n' "$RUNID" "$(date -u +%FT%H:%MZ)" > data/cyclone/MMLIVE
  git add data/cyclone/MMLIVE; git commit -qm "Moist model: live ensemble on GFS $RUNID" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AXxjaemsi36VrJDzeKZ8zA"
  for i in 1 2 3 4 5; do git pull -q --rebase origin cases && git push -q origin HEAD:cases && break; sleep 7; done
  SHA=$(git rev-parse HEAD); sleep 20
  RID=""; for i in $(seq 1 30); do RID=$(gh api "$R/actions/workflows/cyclone-mmlive.yml/runs?head_sha=$SHA" -q '.workflow_runs[0].id' 2>/dev/null); [ -n "$RID" ] && break; sleep 10; done
  until [ "$(gh api $R/actions/runs/$RID -q .status)" = completed ]; do sleep 30; done
  git pull -q --rebase origin cases
fi
for f in live_GFS_$RUNID.npz; do [ -s "$W/$f" ] || { ID=$(gh api $R/releases/tags/era5-cases -q ".assets[]|select(.name==\"$f\")|.id"); gh api -H 'Accept: application/octet-stream' $R/releases/assets/$ID > "$W/$f"; }; done
git fetch -q origin main; git show origin/main:data/sst_indices.json > "$W/sst.json"
N=$(ls data/cyclone/mm/live/$RUNID/part_*.json | wc -l)
python3 -W ignore scripts/cyclone/mm/live.py merge "$W/live_GFS_$RUNID.npz" "$W/sst.json" data/cyclone/ours/live_inputs.json "$W/ens_m_$RUNID.json" data/cyclone/mm/live/$RUNID/part_*.json
cp "$W/ens_m_$RUNID.json" data/cyclone/mm/live/$RUNID/ens.json
python3 scripts/cyclone/ours/ours_page.py "$W/ens_m_$RUNID.json" "$A/moist_preview.html" --method moist
git add data/cyclone/mm/live data/cyclone/ours/live_history_moist.json; git commit -qm "Moist model: live ensemble $RUNID merged" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AXxjaemsi36VrJDzeKZ8zA" || true
for i in 1 2 3 4 5; do git pull -q --rebase origin cases && git push -q origin HEAD:cases && break; sleep 7; done
echo "DONE_M $RUNID parts $N page: $A/moist_preview.html"
