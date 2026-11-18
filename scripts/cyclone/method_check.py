"""Flags verdict lines in docs/rootcause.md (from 19 Nov) that lack the method stamp, and any 'rejected' without a failure 5-Why."""
import re, sys
L = open('docs/rootcause.md').read().splitlines(); start = next((i for i, l in enumerate(L) if 'METHOD RULE (Sridhar 23:50)' in l), 0) + 5
bad = []
for i, l in enumerate(L[start:], start + 1):
    if re.search(r'\b(REJECT|rejected|NOT supported|not supported|NOT named|NOT met|-> FAIL|PASS)\b', l) and not any('fail-5why' in x for x in L[i - 1:i + 4]):
        bad.append(f'{i}: {l.strip()[:140]}')
print(f'method_check: {len(bad)} verdict line(s) without the stamp'); print('\n'.join(bad)); sys.exit(1 if bad else 0)
