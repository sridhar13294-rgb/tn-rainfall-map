"""Coastlines, country borders and Indian state borders for the MEGAM map viewer (Natural Earth, public domain),
simplified and written as small JSON line lists: python maps_borders.py OUT_DIR"""
import sys, os, json, io, zipfile, urllib.request
import geopandas as gpd
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
SRC = {'coast': ('50m', 'physical', 'ne_50m_coastline'), 'countries': ('50m', 'cultural', 'ne_50m_admin_0_boundary_lines_land'),
       'states': ('10m', 'cultural', 'ne_10m_admin_1_states_provinces_lines'), 'lakes': ('50m', 'physical', 'ne_50m_lakes')}
def load(scale, kind, name):
    for url in (f'https://naciscdn.org/naturalearth/{scale}/{kind}/{name}.zip', f'https://naturalearth.s3.amazonaws.com/{scale}_{kind}/{name}.zip'):
        try:
            data = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=120).read()
            d = f'/tmp/{name}'; zipfile.ZipFile(io.BytesIO(data)).extractall(d); return gpd.read_file(f'{d}/{name}.shp')
        except Exception as e: print('failed', url, repr(e)[:200], flush=True)
    return None
def lines(geom, tol):
    g = geom.simplify(tol, preserve_topology=False); out = []
    parts = getattr(g, 'geoms', [g])
    for p in parts:
        if p.is_empty: continue
        rings = [p.exterior] + list(p.interiors) if p.geom_type == 'Polygon' else [p]
        for r in rings:
            c = [[round(x, 2), round(y, 2)] for x, y in r.coords]
            if len(c) >= 2: out.append(c)
    return out
res = {}
for key, (scale, kind, name) in SRC.items():
    df = load(scale, kind, name)
    if df is None: continue
    if key == 'states':                                                                          # Indian states only (and neighbours' in the region)
        col = 'adm0_name' if 'adm0_name' in df.columns else ('ADM0_NAME' if 'ADM0_NAME' in df.columns else None)
        if col: df = df[df[col].isin(['India'])]
    if key == 'lakes': df = df[df.geometry.area > 0.5]
    L = []
    for geom in df.geometry:
        if geom is not None: L += lines(geom, 0.03 if key != 'states' else 0.02)
    res[key] = L; print(key, len(df), 'features', len(L), 'lines', sum(len(x) for x in L), 'points', flush=True)
json.dump(res, open(os.path.join(OUT, 'borders.json'), 'w'), separators=(',', ':'))
print('size KB', os.path.getsize(os.path.join(OUT, 'borders.json')) // 1024)
