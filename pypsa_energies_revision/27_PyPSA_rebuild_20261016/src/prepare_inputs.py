"""Read immutable PLEXOS run snapshots; never modify the source project."""
from pathlib import Path
import argparse, hashlib, json, zipfile
import xml.etree.ElementTree as ET
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent

def tables(raw):
    tree = ET.fromstring(raw)
    for e in tree.iter(): e.tag = e.tag.split('}')[-1]
    out = {}
    for e in tree: out.setdefault(e.tag, []).append({c.tag:c.text for c in e})
    return out

def extract():
    dest=ROOT/'inputs'; dest.mkdir(exist_ok=True)
    archive_root=PROJECT/'4_基础场景的结果分析'/'0_Scenarios'
    manifest=[]
    for s in ['S0','S1','S2','S3','S4']:
        zpath=archive_root/f'Model {s} LT 2025-2050 Solution'/f'{s} LT 2025-2050.zip'
        with zipfile.ZipFile(zpath) as z:
            raw=z.read(f'{s} LT 2025-2050.xml'); ts=tables(raw)
            if s=='S4':
                data=dest/'historical_s4';data.mkdir(exist_ok=True)
                for name in z.namelist():
                    target=(data/name).resolve()
                    if not target.is_relative_to(data.resolve()):raise ValueError(name)
                    if not name.endswith('/'):target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(name))
        objects={r['object_id']:r for r in ts['t_object']}; props={r['property_id']:r for r in ts['t_property']}; mem={r['membership_id']:r for r in ts['t_membership']}
        texts={r['data_id']:r['value'] for r in ts.get('t_text',[])}
        param={}
        for row in ts['t_data']:
            ob=objects[mem[row['membership_id']]['child_object_id']]['name']
            param.setdefault(ob,{})[props[row['property_id']]['name']]={'value':float(row['value']),'file':texts.get(row['data_id'])}
        (dest/f'{s}_parameters.json').write_text(json.dumps(param,ensure_ascii=False,indent=2),encoding='utf-8')
        source_diag=archive_root/f'Model {s} LT 2025-2050 Solution'/f'Model ( {s} LT 2025-2050 ) LT Annuities Diagnostics.xml'
        ann=[]
        if source_diag.exists():
            for e in ET.parse(source_diag).getroot():ann.append(dict(object=e.get('c1'),year=int(e.get('c2'))+2024,pv_per_unit=float(e.get('c17'))))
        (dest/f'{s}_annuity.json').write_text(json.dumps(ann,indent=2),encoding='utf-8')
        manifest.append(dict(scenario=s,archive=str(zpath),xml_sha256=hashlib.sha256(raw).hexdigest(),has_ev=any(k.startswith('EV ') for k in param),has_h2='H2 Storage Tank' in param,expand=any('Max Units Built' in v for v in param.values())))
    (dest/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')

def load_time(path):
    df=pd.read_csv(path); key=next(c for c in df if c.upper()=='DATETIME')
    ix=pd.to_datetime(df.pop(key),format='mixed');df.index=ix
    if df.index.has_duplicates:raise ValueError(f'Duplicate timestamps: {path}')
    return df.sort_index()

def profiles():
    data=ROOT/'inputs'/'historical_s4';out=ROOT/'inputs'
    ix=pd.date_range('2025-01-01','2051-01-01',freq='h',inclusive='left',name='snapshot')
    result=pd.DataFrame(index=ix)
    cfg=json.loads((out/'S4_parameters.json').read_text(encoding='utf-8'))
    active_load=[k for k,v in cfg.items() if v.get('Load',{}).get('file')]
    load=load_time(data/'DataFiles/load_2024_2050.csv').reindex(ix)
    result['load_MW']=load[active_load].sum(axis=1,min_count=len(active_load))
    result['price_JPY_MWh']=load_time(data/'DataFiles/ElectricityPrice_Forecast_2024_2050.csv').reindex(ix)['Value']
    for short,path in [('solar','DataFiles/RF_SolarPV/RF_Solar_Namie.csv'),('wind','DataFiles/RF_Wind/RF_Wind_Namie.csv')]:
        df=pd.read_csv(data/path);look={(int(r.Month),int(r.Day),int(r.Period)-1):float(r.Value) for r in df.itertuples()}
        # Source RF data use percent (confirmed from input Rating Factor).
        result[short+'_pu']=[look.get((t.month,t.day,t.hour),look.get((2,28,t.hour),np.nan))/100 for t in ix]
    fleet=pd.read_csv(data/'DataFiles/ev_data/EVforecast - Integrated.csv').set_index('year')
    drive=load_time(data/'DataFiles/ev_data/ev_data_2018_2050.csv').reindex(ix)
    availability=load_time(data/'DataFiles/ev_data/ev_charging_share_2018_2050.csv').reindex(ix)
    for key,name in [('commercial','EV JR Namie Commercial Area'),('residential','EV Residential Cars')]:
        result[key+'_vehicles']=fleet[name].reindex(ix.year).to_numpy()
        result[key+'_drive_MWh']=result[key+'_vehicles']*.0002*drive[name]
        result[key+'_availability']=availability[name+'~CS_JR Namie Commercial Area']/100
    if result.isna().any().any():raise ValueError('Missing profile values: '+str(result.isna().sum()))
    if result[['solar_pu','wind_pu']].max().max()>1.001:raise ValueError('Renewable scaling')
    result.to_parquet(out/'profiles.parquet')
    hydro=load_time(data/'250_16_Month_0_0_1.csv');hydro.columns=['hydro_GWh']
    # This is a CHANGE-POINT series: omitted months retain the preceding value.
    monthly=pd.date_range('2025-01-01','2050-12-01',freq='MS')
    hydro=hydro.reindex(hydro.index.union(monthly)).sort_index().ffill().reindex(monthly)
    if hydro.isna().any().any():raise ValueError('Missing initial monthly hydro limit')
    hydro.to_parquet(out/'hydro_monthly.parquet')
    (out/'profile_summary.json').write_text(json.dumps(dict(hours=len(result),active_load=active_load,annual_load_GWh=(result.load_MW.groupby(result.index.year).sum()/1000).to_dict(),solar_max=float(result.solar_pu.max()),wind_max=float(result.wind_pu.max())),indent=2),encoding='utf-8')

if __name__=='__main__':
    extract();profiles();print('Historical S0-S4 inputs and shared hourly profiles prepared.')
