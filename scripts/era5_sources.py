"""Which public copies of ERA5 can a GitHub runner read without the Copernicus queue?  Writes data/cases/era5/sources.json."""
import json, time, os, traceback
OUT = {}
def t(name, fn):
    t0 = time.time()
    try: OUT[name] = dict(ok=True, info=fn(), s=round(time.time() - t0, 1))
    except Exception as e: OUT[name] = dict(ok=False, err=repr(e)[:600], tb=traceback.format_exc()[-600:], s=round(time.time() - t0, 1))
    print(name, OUT[name], flush=True)
def wb2():
    import xarray as xr
    out = {}
    for u in ['gs://weatherbench2/datasets/era5/1959-2023_01_10-wb13-6h-1440x721_with_derived_variables.zarr',
              'gs://weatherbench2/datasets/era5/1959-2023_01_10-6h-240x121_equiangular_with_poles_conservative.zarr']:
        ds = xr.open_zarr(u, storage_options={'token': 'anon'}, chunks=None)
        v = ds['u_component_of_wind'] if 'u_component_of_wind' in ds else list(ds.data_vars.values())[0]
        out[u.split('/')[-1]] = dict(vars=list(ds.data_vars)[:40], dims=dict(ds.sizes), chunks=str(v.encoding.get('chunks')), t0=str(ds.time.values[0]), t1=str(ds.time.values[-1]))
    return out
def arco():
    import xarray as xr
    ds = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
    v = ds['u_component_of_wind']; t0 = time.time()
    x = v.sel(time='2015-12-01T00', level=850).sel(latitude=slice(40, 0), longitude=slice(50, 110)).values
    return dict(dims=dict(ds.sizes), chunks=str(v.encoding.get('chunks')), t1=str(ds.time.values[-1]), sample_shape=list(x.shape), one_read_s=round(time.time() - t0, 1),
                attrs={k: str(v)[:80] for k, v in list(ds.attrs.items())[:5]})
def ncar_s3():
    import s3fs, h5py
    fs = s3fs.S3FileSystem(anon=True)
    L = fs.ls('nsf-ncar-era5/e5.oper.an.pl/201512/')[:6]
    f = [x for x in fs.ls('nsf-ncar-era5/e5.oper.an.pl/201512/') if '128_131_u' in x][0]
    with fs.open(f) as fh:
        h = h5py.File(fh); k = [x for x in h.keys() if x.upper() == 'U'][0]; d = h[k]
        return dict(sample=L, file=f, shape=d.shape, chunks=d.chunks, compression=d.compression, size_mb=round(fs.size(f) / 1e6))
def rda_thredds():
    import urllib.request
    u = 'https://thredds.rda.ucar.edu/thredds/dodsC/files/g/d633000/e5.oper.an.pl/201512/e5.oper.an.pl.128_131_u.ll025uv.2015120100_2015120123.nc.dds'
    return urllib.request.urlopen(u, timeout=60).read()[:300].decode('latin1')
for n, f in [('weatherbench2', wb2), ('arco_era5', arco), ('ncar_s3', ncar_s3), ('rda_thredds', rda_thredds)]: t(n, f)
json.dump(OUT, open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data/cases/era5/sources.json'), 'w'), indent=1, default=str)
