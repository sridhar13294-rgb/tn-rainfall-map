"""Parse a TNSDMA 'TN Smart Monthly and Overall Rainfall Report' PDF into data/baseline.json.

Usage: python scripts/parse_report.py REPORT.pdf SYNC_DATE   (SYNC_DATE = YYYY-MM-DD the report is synced till)
The report has a red rotated watermark that corrupts table extraction, so red chars are dropped and
each row is rebuilt from the character stream; a row is accepted only if Jan..Dec sum to the Total.
"""
import json, re, sys, collections
import pdfplumber

DISTRICTS = ['Ariyalur','Chengalpattu','Chennai','Coimbatore','Cuddalore','Dharmapuri','Dindigul','Erode','Kallakurichi',
 'Kancheepuram','Kanniyakumari','Karur','Krishnagiri','Madurai','Mayiladuthurai','Nagapattinam','Namakkal','Nilgiris',
 'Perambalur','Pudukkottai','Ramanathapuram','Ranipet','Salem','Sivagangai','Tenkasi','Thanjavur','Theni',
 'Thiruchirappalli','Thiruvarur','Thoothukudi','Tirunelveli','Tirupathur','Tiruppur','Tiruvallur','Tiruvannamalai',
 'Vellore','Villupuram','Virudhunagar']
BY_LEN = sorted(DISTRICTS, key=len, reverse=True)

def keep(o):
    return o.get('object_type') != 'char' or tuple(o['non_stroking_color'] or ()) != (1.0, 0.0, 0.0)

def parse(path):
    rows, fails = [], []
    with pdfplumber.open(path) as pdf:
        for pi, page in enumerate(pdf.pages):
            lines = collections.OrderedDict()
            for ch in page.filter(keep).chars:
                if ch['top'] < 125:
                    continue
                lines.setdefault(round(ch['top'] / 3), []).append(ch)
            for chs in lines.values():
                txt = ''.join(c['text'] for c in chs)
                if txt.startswith('District'):
                    continue
                dots = [i for i, c in enumerate(txt) if c == '.']
                d = next((x for x in BY_LEN if txt.startswith(x)), None)
                if len(dots) < 13 or not d:
                    fails.append((pi + 1, txt)); continue
                tail, best = dots[-13:], None
                for n0 in range(1, 6):
                    s = tail[0] - n0
                    if s < len(d) or not txt[s:tail[0]].isdigit():
                        break
                    nums, pos, ok = [], s, True
                    for dp in tail:
                        seg = txt[pos:dp + 2]
                        if not re.fullmatch(r'\d+\.\d', seg):
                            ok = False; break
                        nums.append(float(seg)); pos = dp + 2
                    if ok and pos == len(txt) and abs(sum(nums[:12]) - nums[12]) <= 0.65:
                        best = (s, nums); break
                if not best:
                    fails.append((pi + 1, txt)); continue
                s, nums = best
                rows.append({'district': d, 'station': txt[len(d):s].strip(), 'm': nums[:12], 'total': nums[12]})
    return rows, fails

if __name__ == '__main__':
    rows, fails = parse(sys.argv[1])
    out = {'source': 'TNSDMA TN Smart Monthly and Overall Rainfall Report', 'synced_till': sys.argv[2], 'stations': rows}
    json.dump(out, open('data/baseline.json', 'w'), indent=0)
    print(f'{len(rows)} stations parsed, {len(fails)} rows failed')
    for f in fails[:20]:
        print('FAILED', f)
