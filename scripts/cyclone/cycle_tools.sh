#!/bin/bash
# Helpers for scheduled work cycles (fresh sessions). Source it: . scripts/cyclone/cycle_tools.sh
R=repos/sridhar13294-rgb/tn-rainfall-map
# dl RELEASE ASSET DIR  - download a release asset with the REST API (gh release download uses GraphQL = blocked here)
dl(){ id=$(gh api $R/releases/tags/$1 --jq ".assets[] | select(.name==\"$2\") | .id"); [ -n "$id" ] && gh api -H "Accept: application/octet-stream" $R/releases/assets/$id > $3/$2 && echo "got $2"; }
# launch SLUG INPUTS CMD ACCOUNT NOTE  - start one Kaggle job (writes data/cyclone/KAGGLE, commits, pushes, waits 40 s)
launch(){ printf '%s\n' "$1" "$2" "$3" NvidiaTeslaT4 "$4" "#$5 $(date -u +%FT%H:%MZ)" > data/cyclone/KAGGLE; git add data/cyclone/KAGGLE; git commit -qm "Cyclone study: Kaggle job $1

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"; git pull -q --rebase origin cases; git push -q origin cases 2>&1|tail -1; sleep 40; }
# prof JSON -> tropics day-5 T bias summary for a wx_prof job folder
prof(){ python3 -c "
import json,numpy as np,sys
for name,J in json.load(open(sys.argv[1]+'/prof.json')).items():
  T=np.mean([j['d5']['tropics']['T'] for j in J],0); o=np.mean([j.get('olr_trop') or np.nan for j in J])
  print(f'{name:9s} n{len(J):2d} olr {o:4.0f} | T 100:{T[1]:5.1f} 200:{T[3]:5.1f} 250:{T[4]:5.1f} 300:{T[5]:5.1f} 400:{T[6]:5.1f} 500:{T[7]:5.1f} 850:{T[10]:5.1f} 1000:{T[12]:5.1f}')" "$1"; }
# gen DIR VARIANT  - genesis gatekeeper rate (formed = dist<=300 km, vo>=5, depth>=2)
gen(){ python3 -c "
import json,glob,sys
R=[r for f in glob.glob(sys.argv[1]+'/gen_*.json') for r in json.load(open(f))]; v=sys.argv[2]
ok=[r for r in R if v in r['runs'] and 'dist' in r['runs'][v]]; f=[r for r in ok if r['runs'][v]['dist']<=300 and r['runs'][v]['vo']>=5 and r['runs'][v]['depth']>=2]
print('genesis',v,len(ok),'cases',round(100*len(f)/max(len(ok),1)),'%')" "$1" "$2"; }
