#!/bin/bash
# One cycle of our live 51-member ensemble. Run from the repo root on the cases branch:
#   scripts/cyclone/ours/ours_cycle.sh <workdir>
# 1) trigger the workflow's live fetch (GFS analysis + MJO), 2) download it, the analogue library and the SST indices,
# 3) run the ensemble, 4) build the page (<workdir>/bay-storm-scenarios.html), 5) commit the run and the history to cases.
set -e
W=${1:?workdir}; mkdir -p "$W"; R=repos/sridhar13294-rgb/tn-rainfall-map
git config user.email noreply@anthropic.com; git config user.name Claude
git pull -q --rebase origin cases
printf 'ours\n\n#live ensemble %s\n' "$(date -u +%FT%H:%MZ)" > data/cyclone/RUN
git add data/cyclone/RUN; git commit -qm "Cyclone study: live inputs for our ensemble" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AXxjaemsi36VrJDzeKZ8zA"; git push -q origin HEAD:cases
sleep 15; RID=$(gh run list --workflow cyclone.yml -L 1 --json databaseId -q '.[0].databaseId')
until [ "$(gh api $R/actions/runs/$RID -q .status)" = completed ]; do sleep 15; done
git pull -q --rebase origin cases
LIVE=$(python3 -c "import json;print(json.load(open('data/cyclone/ours/live_inputs.json'))['file'])")
ID=$(gh api $R/releases/tags/era5-cases -q ".assets[]|select(.name==\"$LIVE\")|.id")
gh api -H 'Accept: application/octet-stream' $R/releases/assets/$ID > "$W/$LIVE"
if [ ! -s "$W/lib_fields.npz" ]; then LID=$(gh api $R/releases/tags/era5-cases -q '.assets[]|select(.name=="lib_fields.npz")|.id'); gh api -H 'Accept: application/octet-stream' $R/releases/assets/$LID > "$W/lib_fields.npz"; fi
git fetch -q origin main; git show origin/main:data/sst_indices.json > "$W/sst.json"
RUNID=${LIVE#live_GFS_}; RUNID=${RUNID%.npz}
MODE=$(cat data/cyclone/ours/ENV 2>/dev/null || echo past); SCRIPT=ours_live_past.py; [ "$MODE" = "bve" ] && SCRIPT=ours_live.py
(cd "$W" && python3 -W ignore "$OLDPWD/scripts/cyclone/analysis/$SCRIPT" lib_fields.npz "$LIVE" sst.json "$OLDPWD/data/cyclone/ours/live_inputs.json" "ens_$RUNID.json")
python3 scripts/cyclone/ours/ours_page.py "$W/ens_$RUNID.json" "$W/bay-storm-scenarios.html" --site "$W/cyclone.html"
python3 -c "
import json,sys;E=json.load(open('$W/ens_$RUNID.json'))
for r in E['runs']: r['pts']=r['pts'][::2]
json.dump(E,open('data/cyclone/ours/live_$RUNID.json','w'),default=str)"
git add data/cyclone/ours; git commit -qm "Cyclone study: our live ensemble $RUNID" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AXxjaemsi36VrJDzeKZ8zA" || true
git pull -q --rebase origin cases && git push -q origin HEAD:cases
# website: only after Sridhar said "go live" for the Cyclone page (marker file on cases)
if [ -f data/cyclone/ours/SITE_LIVE ]; then
  S=$W/site_main; [ -d "$S/.git" ] || [ -f "$S/.git" ] || git worktree add -f "$S" origin/main >/dev/null 2>&1 || true
  (cd "$S" && git fetch -q origin main && git checkout -q --detach origin/main && cp "$W/cyclone.html" site/cyclone.html && git add site/cyclone.html &&
   (git -c user.email=noreply@anthropic.com -c user.name=Claude commit -qm "Cyclone page update $RUNID" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AXxjaemsi36VrJDzeKZ8zA" && git push -q origin HEAD:main) || true)
  echo "SITE updated"
fi
echo "DONE $RUNID page: $W/bay-storm-scenarios.html site: $W/cyclone.html"
