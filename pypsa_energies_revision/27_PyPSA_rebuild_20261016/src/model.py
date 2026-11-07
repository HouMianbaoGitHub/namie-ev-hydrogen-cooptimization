"""Single-node PyPSA/Linopy reconstruction, with explicit fidelity boundaries.

Annual builds and hourly dispatch are continuous variables. Capital
coefficients are read from the historical PLEXOS annuity diagnostics, not guessed.
"""
from pathlib import Path
import argparse, json, logging, time, platform
import hashlib
import numpy as np
import pandas as pd
import xarray as xr
import pypsa

ROOT=Path(__file__).resolve().parents[1]
TECH={
 'wind':('NewOnshoreWInd OnshoreWind','Max Capacity'),
 'roof':('NewRooftopPV RooftopPV','Max Capacity'),
 'solar':('NewUtilityPV UtilityPV','Max Capacity'),
 'fuelcell':('FH2R Fuel Cell Power Station Hydrogen','Max Capacity'),
 'electrolyzer':('Power to H2 Facility','Max Operating Level'),
 'tank':('H2 Storage Tank','Max Inventory'),
}

def param(cfg,obj,key,default=0):return cfg.get(obj,{}).get(key,{}).get('value',default)

def file_sha256(path):
 digest=hashlib.sha256()
 with open(path,'rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):digest.update(block)
 return digest.hexdigest()

OLD_CAPEX={'electrolyzer':{2025:45000,2030:28774,2040:18774,2050:9591},
           'fuelcell':{2025:250,2030:150,2040:80,2050:80},
           'tank':{2025:59024,2030:48816,2040:29512,2050:29512}}

def _interp(points,y):
 ys=sorted(points);return float(np.interp(y,ys,[points[k] for k in ys]))

def parse_path(s):
 """'2025:0,2035:0.9,2050:1.4' -> {2025: 0.0, ...} (linear in between, flat outside)."""
 return {int(k):float(v) for k,v in (p.split(':') for p in s.split(','))}

def extend_years(frame):
 """Append copies of the 2050 rows relabelled to 2051..YEND (end-effect test: 2050 conditions held constant)."""
 if YEND<=2050:return frame
 base=frame.loc[frame.index.year==2050]
 parts=[frame]+[base.set_axis(base.index+pd.DateOffset(years=y-2050)) for y in range(2051,YEND+1)]
 return pd.concat(parts)

def load_annuity(source,scenario):
 ann=json.loads((source/f'{scenario}_annuity.json').read_text(encoding='utf-8'))
 if YEND>2050:  # later vintages: 2050 cost per unit, discounted to the build year
  ann=ann+[dict(r,year=y,pv_per_unit=r['pv_per_unit']*1.03**-(y-2050)) for r in ann if r['year']==2050 for y in range(2051,YEND+1)]
 return ann

def scale_annuity(ann,args):
 """Replace the capex part of the PLEXOS PV per unit by the new hydrogen capex path.
 PLEXOS PV per unit = original build cost of that year (inputs/h2_buildcost_original_plexos.csv: yearly values, steps for
 fuel cell and tank) discounted to 2025, plus (fuel cell only) the perpetual FO&M; only the build-cost part is swapped."""
 if isinstance(ann,list):rows=ann
 else:return ann
 new={}
 for k in ('electrolyzer','fuelcell','tank'):
  spec=getattr(args,'capex_'+k,None)
  if spec:new[k]={int(a):float(b) for a,b in (x.split(':') for x in spec.split(','))}
 orig=pd.read_csv(ROOT/'inputs'/'h2_buildcost_original_plexos.csv',index_col=0) if new else None
 col={'electrolyzer':('electrolyzer_JPY_per_block',1.),'fuelcell':('fuelcell_JPY_per_kW',UNIT_KW['fuelcell']),'tank':('tank_JPY_per_t',1.)}
 fom=parse_kv(args.h2_fom) if args.h2_fom else {}          # share of build-year capex per year
 stk=parse_kv(args.h2_stack_repl) if args.h2_stack_repl else {}  # (share of capex per replacement, years between replacements)
 out={}
 for r in rows:
  key=(r['object'],r['year']);v=r['pv_per_unit'];y=r['year']
  for k,pts in new.items():
   if r['object']==TECH[k][0]:
    c,u=col[k];old=float(orig.at[min(y,2050),c])*u;nv=_interp(pts,y)*1000*u  # JPY per unit, build year y
    d=1.03**-(y-2025)
    if k in fom or k in stk:
     # registry (params/h2.yaml): replace the original O&M part of the PLEXOS PV (PV - discounted original build cost)
     # by FO&M = share x capex, perpetual (same 1/r factor as PLEXOS), plus perpetual stack replacements every L years
     extra=nv*fom.get(k,(0.,))[0]/.03
     if k in stk:sh,L=stk[k];extra+=nv*sh/(1.03**L-1)
     v=d*(nv+extra)
    else:v=v+d*(nv-old)
  out[key]=v
 return out

def parse_kv(s):
 """'electrolyzer:0.02,fuelcell:0.03' -> {k:(0.02,)}; 'electrolyzer:0.11:40' -> {k:(0.11,40.)}"""
 out={}
 for part in s.split(','):
  k,*v=part.split(':');out[k]=tuple(float(x) for x in v)
 return out

def grid_pv_per_mw(y,args):
 """PV (million JPY, 2024) of 1 MW of interface reinforcement built in year y, incl. perpetuity."""
 w,L=args.grid_wacc,args.grid_life
 crf=w/(1-(1+w)**-L)
 annual=args.grid_capex_jpy_per_kw*1000*(crf+args.grid_fom)/1e6
 return annual if STATIC else annual*annuity_factor(y)

CAPEX={  # thousand JPY per kW (tank: per tonne); appendix A for renewables
 'wind':{2025:293,2030:248,2040:177,2050:127},'solar':{2025:189,2030:172,2040:142,2050:118},'roof':{2025:265,2030:234,2040:182,2050:141}}
H2_CAPEX={  # reports/氢能设备造价核实.md
 'base':{'electrolyzer':{2025:300,2030:235,2040:190,2050:150},'fuelcell':{2025:350,2030:250,2040:190,2050:150},'tank':{2025:150000,2030:135000,2040:100000,2050:80000}},
 'low': {'electrolyzer':{2025:120,2030:52,2040:40,2050:30},'fuelcell':{2025:180,2030:150,2040:113,2050:113},'tank':{2025:112000,2030:96000,2040:63000,2050:54000}},
 'high':{'electrolyzer':{2025:375,2030:285,2040:245,2050:205},'fuelcell':{2025:600,2030:375,2040:300,2050:250},'tank':{2025:250000,2030:200000,2040:160000,2050:136000}},
 'old': {'electrolyzer':{2025:85,2030:54,2040:35,2050:18},'fuelcell':{2025:250,2030:150,2040:80,2050:80},'tank':{2025:59024,2030:48816,2040:29512,2050:29512}}}  # original submission (PLEXOS inputs; reports/氢能设备造价核实.md 'current model')
H2_FOM={'base':{'electrolyzer':.04,'fuelcell':.05,'tank':.01},'low':{'electrolyzer':.02,'fuelcell':.03,'tank':.005},'high':{'electrolyzer':.06,'fuelcell':.07,'tank':.02}}
H2_LIFE={'base':{'electrolyzer':20,'fuelcell':20,'tank':30},'low':{'electrolyzer':20,'fuelcell':20,'tank':30},'high':{'electrolyzer':15,'fuelcell':12,'tank':25}}
UNIT_KW={'wind':40000,'solar':20000,'roof':20,'fuelcell':10000,'electrolyzer':549.2,'tank':1}  # electrolyzer: 10 kg/h block at full-load input (49.12 x 1.1181 kWh/kg), params/h2.yaml h2_el_block_kw_basis  # tank: tonnes per unit

PERP=True  # set from --no-perpetuity in main(); False = horizon ends in 2050 (2050 weighted as one year, no annuities after 2050)
HEND=2050  # last modelled year (= --end-year in rolling/myopic windows); truncated annuities stop here
YEND=2050  # final year of the horizon; > 2050 with --extend-to (2050 conditions repeated, end-effect test)
STATIC=None  # --static-year: one year of operation, undiscounted, investment at annualised cost (no pathway)
def W2050():
 return 1.03**-(YEND-2025)/.03 if PERP else 1.03**-(YEND-2024)

def annuity_factor(y):
 return sum(1.03**-(t-2024) for t in range(y,YEND))+W2050()

H2_PHYS={'electrolyzer_MW':2000.,'fuelcell_MW':500.,'tank_t':10000.}
EL_FL_RATIO=54.92/49.12  # full-load system kWh/kg / linear coefficient with the F3 part-load curve and no-load (registry h2_el_sec_basis)

# Verified O&M / life (reports/电解槽燃料电池运维与寿命核实.md): system life by build year (DEA AEC 10 MW),
# FOM excluding stack replacement, stack replacement as an equivalent annual cost.
EL_LIFE_PATH={2025:20,2030:25,2040:30,2050:35}
H2_STACK={'electrolyzer':(.11,15),'fuelcell':(.20,10)}   # (share of capex, interval in years)
H2_FOM_V={'electrolyzer':.04,'fuelcell':.04,'tank':.01}
def tech_life(k,args,year=2030):
 if k in ('electrolyzer','fuelcell') and args.h2_life:return int(args.h2_life)
 if k in ('wind','solar','roof'):return 30
 if args.h2_om_set=='verified':
  return int(round(_interp(EL_LIFE_PATH,year))) if k=='electrolyzer' else {'fuelcell':20,'tank':30}[k]
 return H2_LIFE[args.h2_om_set][k]
def h2_fom_eff(k,L,args,w):
 """FOM plus stack replacement as an equivalent annual share of capex."""
 crf=lambda n:w/(1-(1+w)**-n)
 if args.h2_om_set!='verified':return H2_FOM[args.h2_om_set][k]
 f=H2_FOM_V[k]
 if k in H2_STACK:
  s,Ls=H2_STACK[k]
  if Ls<L:f+=s*(crf(Ls)-crf(L))
 return f

def s_inf(a):
 return 1.03**-(a-2024)*1.03/.03

def vintage_pv(a_v,a_2050,v,L):
 if not PERP:  # annuities only up to 2050 (equivalent to a salvage value for the remaining life)
  return a_v*sum(1.03**-(t-2024) for t in range(v,min(v+L,HEND+1)))
 own=sum(1.03**-(t-2024) for t in range(v,v+L))
 return a_v*own+(a_2050*s_inf(v+L) if v+L-1>=YEND else 0.)

def annuity_pv(args,ann_raw):
 """PV per unit (JPY) keyed by (PLEXOS object, year) under the equivalent-annuity method."""
 w=args.wacc;crf=lambda L:w/(1-(1+w)**-L)
 out={}
 for r in ann_raw:
  y=int(r['year']);k=[x for x,(o,_) in TECH.items() if o==r['object']]
  if not k:continue
  k=k[0]
  def cy(year):  # cost year: hydrogen costs/lives frozen at their 2050 values from --h2-cost-flat-from on (timing test)
   return 2050 if (args.h2_cost_flat_from and k in ('electrolyzer','fuelcell','tank') and year>=args.h2_cost_flat_from) else year
  def pay(year):
   year=cy(year);L=tech_life(k,args,year)
   if k in ('wind','solar','roof'):
    capex=_interp(CAPEX[k],year)*1000*UNIT_KW[k];return capex*crf(L)+args.re_fom_jpy_per_kw*UNIT_KW[k]
   capex=_interp(H2_CAPEX[args.h2_capex][k],year)*1000*UNIT_KW[k]*args.h2_capex_scale
   return capex*(crf(L)+h2_fom_eff(k,L,args,w))
  out[(r['object'],y)]=vintage_pv(pay(y),pay(2050),y,tech_life(k,args,cy(y)))
 return out

def static_annual_cost(args,ann_raw):
 """--static-year: cost per unit and year (JPY) of capacity standing in year y = capex(y) x CRF(wacc, life) + FO&M
 + stack replacements falling inside the life (PV at wacc, annualised with the same CRF). Wind/PV: appendix capex,
 30-year life, --re-fom-jpy-per-kw. Hydrogen: --capex-* (unit basis as in scale_annuity), --h2-fom, --h2-stack-repl,
 system life from tech_life (params/h2.yaml h2_*_system_life)."""
 w=args.wacc;crf=lambda L:w/(1-(1+w)**-L)
 out={}
 for r in ann_raw:
  y=int(r['year']);k=[x for x,(o,_) in TECH.items() if o==r['object']]
  if not k:continue
  k=k[0];L=tech_life(k,args,y)
  if k in ('wind','solar','roof'):
   capex=_interp(CAPEX[k],y)*1000*UNIT_KW[k];out[(r['object'],y)]=capex*crf(L)+args.re_fom_jpy_per_kw*UNIT_KW[k];continue
  out[(r['object'],y)]=h2_unit_annual_cost(k,y,args)
 return out

def h2_unit_annual_cost(k,y,args):
 """Yearly cost (JPY) of one hydrogen unit built in year y: capex(y) x (CRF(wacc, life) x (1 + stack replacements inside
 the life, PV at wacc) + FO&M). Capex from --capex-*, FO&M from --h2-fom, stacks from --h2-stack-repl, life from tech_life.
 Shared by --static-year and --h2-annuity (registry h2_annuity_method)."""
 w=args.wacc;crf=lambda L:w/(1-(1+w)**-L)
 fom=parse_kv(args.h2_fom) if args.h2_fom else {};stk=parse_kv(args.h2_stack_repl) if args.h2_stack_repl else {}
 unit={'electrolyzer':1.,'fuelcell':UNIT_KW['fuelcell'],'tank':1.}  # --capex-electrolyzer is per block, fuel cell per kW, tank per t
 L=tech_life(k,args,y)
 spec=getattr(args,'capex_'+k)
 if not spec:raise ValueError('--static-year / --h2-annuity need --capex-'+k)
 capex=_interp(parse_path(spec),y)*1000*unit[k]
 repl=0.
 if k in stk:
  sh,Ls=stk[k];repl=sum(sh*(1+w)**-t for t in np.arange(Ls,L,Ls))
 return capex*(crf(L)*(1+repl)+fom.get(k,(0.,))[0])

def investment_pv(args,ann_raw):
 if STATIC:return static_annual_cost(args,ann_raw)
 if args.investment_method=='annuity':return annuity_pv(args,ann_raw)
 out=scale_annuity(ann_raw,args)
 if args.all_annuity:
  # --all-annuity: every new asset as finite-life annuities on the F3 costs (registry all_annuity_method). Wind/PV capex is
  # recovered from the PLEXOS PV per unit (PV = d x (capex + FO&M/r), d = 1.03^-(y-2025)); hydrogen uses h2_unit_annual_cost.
  # vintage_pv: perpetuity -> renewal at 2050 cost after the life; --no-perpetuity -> annuities up to 2050 only (salvage).
  w=args.wacc;crf=lambda L:w/(1-(1+w)**-L);pv={(r['object'],int(r['year'])):r['pv_per_unit'] for r in ann_raw}
  def pay(k,y):
   if k in ('electrolyzer','fuelcell','tank'):return h2_unit_annual_cost(k,y,args)
   capex=pv[(TECH[k][0],y)]/1.03**-(y-2025)-1000*UNIT_KW[k]/.03  # PLEXOS FO&M Charge 1,000 JPY/kW-yr (S*_parameters.json)
   return capex*crf(tech_life(k,args,y))+args.re_fom_jpy_per_kw*UNIT_KW[k]
  for r in ann_raw:
   y=int(r['year']);k=[x for x,(o,_) in TECH.items() if o==r['object']]
   if k:out[(r['object'],r['year'])]=vintage_pv(pay(k[0],y),pay(k[0],min(YEND,2050)),y,tech_life(k[0],args,y))
  return out
 if args.h2_annuity:
  # hydrogen only: yearly cost over the life, retirement at end of life, renewal at 2050 cost in perpetuity (vintage_pv)
  for r in ann_raw:
   y=int(r['year']);k=[x for x,(o,_) in TECH.items() if o==r['object'] and x in ('electrolyzer','fuelcell','tank')]
   if k:out[(r['object'],r['year'])]=vintage_pv(h2_unit_annual_cost(k[0],y,args),h2_unit_annual_cost(k[0],2050,args),y,tech_life(k[0],args,y))
 return out

def tsam_segment(df,n_seg,dep_hour,extra=None):
 """Aggregate an hourly frame year by year into n_seg chronological segments."""
 # Clustering input as in PyPSA-Eur scripts/time_aggregation.py and PyPSA-Japan
 # (15_JapanHydrogenPotentail apply_tsam_segmentation): every series normalised by its
 # annual maximum, near-constant series dropped; legacy tsam API kept deliberately
 # (its deprecation warning is not silenced, as in PyPSA-Japan).
 import tsam.timeseriesaggregation as tsa
 feats=[c for c in ['load_MW','solar_pu','wind_pu','price_JPY_MWh','commercial_availability','residential_availability','commercial_drive_MWh','residential_drive_MWh'] if c in df.columns]
 full=df.copy()
 if extra is not None:full=full.join(extra)
 full['dep_flag']=(full.index.hour==dep_hour).astype(float)
 parts=[]
 for y in sorted(full.index.year.unique()):
  d=full.loc[full.index.year==y]
  if len(d)<=n_seg:
   g=d.copy();g['seg_hours']=1.;parts.append(g);continue
  raw=d[feats];raw=raw.loc[:,raw.std()>1e-6];raw=raw/raw.abs().max().replace(0,1)
  a=tsa.TimeSeriesAggregation(raw,noTypicalPeriods=1,hoursPerPeriod=len(d),segmentation=True,noSegments=n_seg,clusterMethod='hierarchical',representationMethod='meanRepresentation')
  a.createTypicalPeriods()
  dur=[v for _,v in sorted(a.segmentDurationDict['Segment Duration'].items())]
  ids=np.repeat(np.arange(len(dur)),dur)
  agg={c:('max' if c=='dep_flag' else 'mean') for c in d.columns}
  g=d.groupby(ids).agg(agg);g.index=d.index[np.cumsum([0]+dur[:-1])];g['seg_hours']=np.array(dur,float)
  parts.append(g)
 out=pd.concat(parts);out.index.name=df.index.name
 return out

def build(args):
 t0=time.perf_counter(); source=ROOT/'inputs'
 hu=1e-3 if args.unit_scaling else 1.  # hydrogen: tonnes instead of kg
 bu=1e-3 if args.unit_scaling else 1.  # biomass: TJ instead of GJ
 ecap=.07*args.ev_capacity_scale  # usable MWh per vehicle
 es,ebc,ebd=args.ev_station_eff,args.ev_batt_charge_eff,args.ev_batt_discharge_eff  # charger and battery efficiencies
 kw_ev=args.ev_charger_kw/1000  # MW per connected managed vehicle (DC side)
 cfg=json.loads((source/f'{args.scenario}_parameters.json').read_text(encoding='utf-8'))
 ann=load_annuity(source,args.scenario)
 ann=investment_pv(args,ann)
 all_profiles=extend_years(pd.read_parquet(source/'profiles.parquet'))
 if STATIC or args.only_year:
  all_profiles=all_profiles.loc[str(STATIC or args.only_year)]
 elif args.end_year:
  all_profiles=all_profiles.loc[:str(args.end_year)]
 # Deterministic pipeline sampling, deliberately NOT PLEXOS statistical resampling.
 if args.days_per_year:
  keep=(all_profiles.index.month==1)&(all_profiles.index.day<=args.days_per_year)
  df=all_profiles.loc[keep].copy()
 else:df=all_profiles.copy()
 if args.renewable_profile:
  # Local PV/wind capacity factors of a reference weather year (e.g. Renewables.ninja 2024), mapped by month-day-hour.
  rp=pd.read_parquet(args.renewable_profile);key=lambda ix:list(zip(ix.month,ix.day,ix.hour))
  for col in ('solar_pu','wind_pu'):
   m=dict(zip(key(rp.index),rp[col].values));df[col]=[m.get(k,np.nan) for k in key(df.index)]
   df[col]=df[col].interpolate().bfill().ffill()
 if args.price_series:
  # Portfolio-based Tohoku price (JPY/kWh) and regional curtailment rate per model year and reference-year hour
  # (revision_round1/03_analysis/price_model/build_future_prices.py); replaces the historical price and the beta/curtailment proxies.
  ps=pd.read_parquet(args.price_series)
  pm={(y,t.month,t.day,t.hour):(p,c) for (y,t),p,c in zip(ps.index,ps['price'].values,ps['curtail_rate'].values)}
  ylast=max(y for y,*_ in pm)
  vals=[pm.get((min(t.year,ylast),t.month,t.day,t.hour)) for t in df.index]
  if any(v is None for v in vals):raise ValueError('price series does not cover all snapshots')
  df['price_JPY_MWh']=[v[0]*1000 for v in vals];df['curt_rate']=[v[1] for v in vals]
 df['solar_pu']=(df['solar_pu']*args.renewable_scale).clip(upper=1)
 df['wind_pu']=(df['wind_pu']*args.renewable_scale*args.wind_scale).clip(upper=1)
 df['price_JPY_MWh']=df['price_JPY_MWh']*args.price_scale
 df['load_MW']=df['load_MW']*args.load_scale  # non-EV local demand (registry sensitivity_F5_load_tank_20261030)
 yrs=pd.Series(df.index.year,index=df.index)
 beta_t=(yrs.map(lambda y:_interp(parse_path(args.price_wind_beta_path),y)) if args.price_wind_beta_path else pd.Series(args.price_wind_beta,index=df.index))*args.price_wind_beta_scale
 if (beta_t!=0).any():
  # Future high-VRE price scenario (reports/高比例可再生电价情景与长时储能需求.md, scheme A):
  # p' = p exp(-beta z), z = standardised anomaly of the centred 7-day mean of local wind (proxy for
  # Tohoku wind); rescaled month by month so monthly mean prices are unchanged; floor 10 JPY/MWh.
  # With --price-wind-beta-path, beta rises year by year (e.g. 2025 historical -> 2050 high-VRE).
  w7=df['wind_pu'].rolling(168,center=True,min_periods=24).mean()
  z=(w7-w7.mean())/w7.std()
  adj=df['price_JPY_MWh']*np.exp(-beta_t*z)
  key=[df.index.year,df.index.month]
  adj=adj*(df['price_JPY_MWh'].groupby(key).transform('mean')/adj.groupby(key).transform('mean'))
  df['price_JPY_MWh']=adj.clip(lower=10.)
 for group in ('commercial','residential'):
  column=group+'_availability'
  df[column]=(df[column]*args.ev_availability_scale).clip(upper=1)
 share_t=(yrs.map(lambda y:_interp(parse_path(args.export_curtail_share_path),y)) if args.export_curtail_share_path else pd.Series(args.export_curtail_share,index=df.index))*args.export_curtail_share_scale
 share_t=share_t.clip(0,1)
 if (share_t>0).any():
  # Regional output curtailment (出力制御) proxy: in the hours of each year with the highest local
  # wind+PV availability (proxy for Tohoku-wide surplus), exports are cut to a fraction of the limit.
  # Proxy validated against Tohoku 2022-2025 curtailment (reports/东北出力制御现状与展望.md): PV-led mix
  # (2035 Tohoku PV 16.2 GW / wind 7.3 GW -> wind weight 0.3), x season (Mar-Jun, Sep-Nov = 1, else 0.5)
  # x weekend 1.15.
  vre=args.curtail_wind_weight*df['wind_pu']+(1-args.curtail_wind_weight)*df['solar_pu']
  if args.curtail_calendar:
   vre=vre*np.where(df.index.month.isin([3,4,5,6,9,10,11]),1.,.5)*np.where(df.index.dayofweek>=5,1.15,1.)
  rank=vre.groupby(df.index.year).rank(pct=True,method='first')
  df['curt_flag']=(rank>1-share_t).astype(float)
 # Per-year check of the grid-condition paths: beta, curtailed-hour share, wind value factor.
 g=df.groupby(df.index.year)
 args.output.mkdir(parents=True,exist_ok=True)
 pd.DataFrame({'beta':beta_t.groupby(df.index.year).mean(),'curtail_share':(g['curt_flag'].mean() if 'curt_flag' in df.columns else (g['curt_rate'].mean() if 'curt_rate' in df.columns else 0.)),
               'mean_price':g['price_JPY_MWh'].mean(),
               'wind_value_factor':g.apply(lambda x:(x['price_JPY_MWh']*x['wind_pu']).sum()/x['wind_pu'].sum()/x['price_JPY_MWh'].mean())}).rename_axis('year').to_csv(args.output/'grid_conditions_by_year.csv')
 seg=None
 if args.tsam_segments>0:
  extra=None
  if args.ev_control=='fixed' or args.ev_participation<1:
   fx=extend_years(pd.read_parquet(args.fixed_charge_profile or source/'fixed_fleet_charging.parquet')).loc[df.index]
   extra=fx.add_prefix('fx__')
  h_dep0=(args.ev_departure_hour-1)%24 if args.model_fixes else args.ev_departure_hour
  df=tsam_segment(df,args.tsam_segments,h_dep0,extra);seg=df['seg_hours']
 snapshots=df.index;years=pd.Index(sorted(snapshots.year.unique()),name='year')
 fixed_charge=None
 if args.ev_control=='fixed' or args.ev_participation<1:
  fixed_path=args.fixed_charge_profile or source/'fixed_fleet_charging.parquet'
  fixed_charge=extend_years(pd.read_parquet(fixed_path)) if seg is None else df[[c for c in df.columns if c.startswith('fx__')]].rename(columns=lambda c:c[4:])
  if not snapshots.isin(fixed_charge.index).all():raise ValueError('Fixed charging profile does not cover every modeled hour')
  fixed_charge=fixed_charge.loc[snapshots]
  if fixed_charge.isna().any().any():raise ValueError('Fixed charging profile contains missing values')
 weight=pd.Series(1.,index=snapshots) if seg is None else seg.copy()
 hrs=pd.Series(1.,index=snapshots) if seg is None else seg.copy()  # elapsed hours per snapshot
 _hrs_arr=hrs.to_numpy()
 if seg is not None and args.days_per_year:raise ValueError('--tsam-segments cannot be combined with --days-per-year')
 if args.days_per_year:
  weight=pd.Series(np.where(snapshots.is_leap_year,366,365)/args.days_per_year,index=snapshots)
 discount=pd.Series(1.03**(-(snapshots.year-2024)),index=snapshots)
 discount.loc[snapshots.year==YEND]=W2050()
 if STATIC:discount[:]=1.  # one representative year, objective = annual cost
 n=pypsa.Network();n.name=f'Namie_{args.scenario}';n.set_snapshots(snapshots)
 n._hrs=_hrs_arr
 n.snapshot_weightings['objective']=weight*discount
 n.snapshot_weightings['generators']=weight
 n.snapshot_weightings['stores']=1. if seg is None else seg
 for carrier in ['electricity','hydrogen','battery','biomass_fuel']:n.add('Carrier',carrier)
 n.add('Bus','electricity',carrier='electricity')
 n.add('Load','fixed_load',bus='electricity',p_set=df.load_MW)
 has_ev='EV Residential Cars' in cfg;has_h2='H2 Storage Tank' in cfg
 candidates=[k for k,(o,_) in TECH.items() if param(cfg,o,'Max Units Built')>0]
 # Identical solar/wind profiles and zero dispatch costs permit aggregation.
 fixed_solar=sum(param(cfg,o,'Units')*param(cfg,o,'Max Capacity') for o in cfg if 'UtilityPV' in o or o=='Namie RooftopPV')
 fixed_wind=param(cfg,'Fukushima Revitalization OnshoreWind','Max Capacity')*param(cfg,'Fukushima Revitalization OnshoreWind','Units')
 max_solar=fixed_solar+sum(param(cfg,TECH[k][0],'Max Units Built')*param(cfg,TECH[k][0],TECH[k][1]) for k in ['roof','solar'])
 max_wind=fixed_wind+param(cfg,TECH['wind'][0],'Max Units Built')*param(cfg,TECH['wind'][0],TECH['wind'][1])
 n.add('Generator','solar',bus='electricity',p_nom=max_solar,p_max_pu=df.solar_pu)
 n.add('Generator','wind',bus='electricity',p_nom=max_wind,p_max_pu=df.wind_pu)
 n.add('Generator','hydro',bus='electricity',p_nom=param(cfg,'Ukedo Gawa Hydro','Max Capacity',1))
 market=args.market_limit_mw if args.market_limit_mw is not None else param(cfg,'TohokuPowerMarket','Max Purchases',150)
 gmax=args.grid_max_mw if args.grid_max_mw>0 else 0.
 n.add('Generator','import',bus='electricity',p_nom=market+gmax,marginal_cost=(df.price_JPY_MWh+args.import_adder_jpy_per_kwh*1000)/1e6)  # wholesale + network charges
 export_limit=args.market_limit_mw if args.market_limit_mw is not None else param(cfg,'TohokuPowerMarket','Max Sales',150)
 n.add('Generator','export',bus='electricity',p_nom=export_limit+gmax,p_max_pu=(1-df['curt_rate']*args.series_curtail_scale).clip(0,1) if 'curt_rate' in df.columns else ((1-df['curt_flag']*(1-args.export_curtail_level)) if 'curt_flag' in df.columns else 1.),sign=-1,marginal_cost=-(df.price_JPY_MWh-args.export_deduction_jpy_per_kwh*1000)/1e6)  # wholesale - generator-side charges
 # Explicit finite biomass stock; unit ~ is interpreted as GJ. See fidelity ledger.
 n.add('Bus','biomass_fuel',carrier='biomass_fuel')
 n.add('Store','biomass_stock',bus='biomass_fuel',e_nom=100000*bu,e_initial=10000*bu,e_cyclic=bool(STATIC))  # static: no windfall from the initial stock
 n.add('Link','biomass',bus0='biomass_fuel',bus1='electricity',p_nom=20*bu,efficiency=.1/bu)
 fuel_price=pd.read_csv(source/'historical_s4/DataFiles/Hydrogen_Biomass_Market_Benchmark_Price_yearly.csv')
 if 'year' in fuel_price.columns:
  fprice=pd.Series(snapshots.year,index=snapshots).map(fuel_price.set_index('year')['BiomassMarket'])
 else:
  fprice=pd.Series(float(fuel_price.iloc[0,-1]),index=snapshots)
 n.add('Generator','biomass_sale',bus='biomass_fuel',p_nom=100000*bu,sign=-1,marginal_cost=-fprice/1e6/bu)
 if has_h2:
  n.add('Bus','hydrogen',carrier='hydrogen')
  a_el=args.h2_electrolysis_mwh_per_kg
  h2_loss=1-(1-args.h2_standing_loss_per_day)**(1/24)
  h2s=float('inf') if (args.h2_unlimited or args.h2_total_unlimited) else args.h2_limit_scale  # totals and process capacities
  big=lambda v,phys:phys if h2s==float('inf') else v*h2s
  n.add('Store','hydrogen',bus='hydrogen',e_nom=big(50000*hu,H2_PHYS['tank_t']*1000*hu),e_initial=0,e_cyclic=bool(STATIC),standing_loss=h2_loss)
  n.add('Link','electrolyzer',bus0='electricity',bus1='hydrogen',p_nom=big(500*a_el,H2_PHYS['electrolyzer_MW']),efficiency=hu/a_el,marginal_cost=(4/a_el)/1e6)
  fk=args.fc_kg_per_mwh*hu
  # Efficiency paths by operating year (registry h2_efficiency_path): --el-sec-path gives the full-load system kWh/kg; the linear
  # coefficient is that value / EL_FL_RATIO (part-load curve and no-load kept); --fc-kg-path gives kg/MWh. Without them: constants.
  yser=pd.Series(snapshots.year,index=snapshots)
  ael_t=yser.map(lambda y:_interp(parse_path(args.el_sec_path),y)/1000/EL_FL_RATIO) if args.el_sec_path else pd.Series(a_el,index=snapshots)
  fk_t=yser.map(lambda y:_interp(parse_path(args.fc_kg_path),y)*hu) if args.fc_kg_path else pd.Series(fk,index=snapshots)
  n._ael_t,n._fk_t=ael_t,fk_t
  if args.h2_sale_price>0:
   # Hydrogen sold off-site (mobility/industry) at a fixed price; optional hourly cap (kg/h).
   cap_kgph=args.h2_sale_max_kgph if args.h2_sale_max_kgph>0 else 1e5
   n.add('Generator','h2_sale',bus='hydrogen',p_nom=cap_kgph*hu,sign=-1,marginal_cost=-args.h2_sale_price/hu/1e6)
  n.add('Link','fuelcell',bus0='hydrogen',bus1='electricity',p_nom=big(300*fk,H2_PHYS['fuelcell_MW']*fk),efficiency=1/fk)
  if args.el_degradation>0:
   age=((args.el_stack_life-1)/2) if args.degradation_average else (snapshots.year-2025)%args.el_stack_life
   n.links_t.efficiency['electrolyzer']=hu/(ael_t*(1+args.el_degradation*age))
  elif args.el_sec_path:n.links_t.efficiency['electrolyzer']=hu/ael_t
  if args.el_sec_path:n.links_t.marginal_cost['electrolyzer']=(4/ael_t)/1e6
  if args.fc_degradation>0:
   age=((args.fc_stack_life-1)/2) if args.degradation_average else (snapshots.year-2025)%args.fc_stack_life
   n.links_t.efficiency['fuelcell']=1/(fk_t*(1+args.fc_degradation*age))
  elif args.fc_kg_path:n.links_t.efficiency['fuelcell']=1/fk_t
  if args.el_noload>0 or args.el_curve:
   n.add('Bus','h2_eff',carrier='electricity')
   n.add('Link','el_eff_aux',bus0='electricity',bus1='h2_eff',p_nom=1000.,efficiency=1)
   n.add('Generator','h2_eff_sink',bus='h2_eff',p_nom=1000.,sign=-1)
  if args.h2_uc and (args.el_standby_power>0 or args.fc_standby_power>0 or args.el_startup_energy>0 or args.fc_startup_energy>0):
   n.add('Bus','h2_aux',carrier='electricity')
   n.add('Link','h2_aux_power',bus0='electricity',bus1='h2_aux',p_nom=500.,efficiency=1)
   n.add('Generator','h2_aux_sink',bus='h2_aux',p_nom=500.,sign=-1)
 ev_names=[]
 if has_ev and args.ev_control=='fixed':
  # The fixed policy is audited outside the optimization against the same
  # fleet travel, charger-availability, efficiency and SoC inputs. Inside the
  # system LP it is an exogenous charging load, matching the PLEXOS control.
  fixed_grid_mw=fixed_charge['commercial_grid_charge_MW']+fixed_charge['residential_grid_charge_MW']
  n.add('Load','ev_fixed_charge',bus='electricity',p_set=fixed_grid_mw)
 if has_ev and args.ev_control!='fixed' and args.ev_participation<1:
  # PyPSA-Eur style participation (bev_dsm_availability): a share p of each fleet is managed
  # (smart charging / V2G, departure SoC); the rest charges on the uncontrolled profile (regime A).
  p_ev=args.ev_participation
  fixed_grid_mw=fixed_charge['commercial_grid_charge_MW']+fixed_charge['residential_grid_charge_MW']
  n.add('Load','ev_nonparticipating_charge',bus='electricity',p_set=(1-p_ev)*fixed_grid_mw)
  for key in ('commercial','residential'):
   df[key+'_vehicles']=df[key+'_vehicles']*p_ev;df[key+'_drive_MWh']=df[key+'_drive_MWh']*p_ev
 ev_series={}
 dep_floor=pd.Series(.35,index=snapshots);dep_groups=args.ev_departure_groups.split(',')
 floor_dep=pd.Series(.35*(.07 if args.model_fixes else ecap),index=snapshots)  # MWh per vehicle
 floor_base=floor_dep.copy()
 if args.ev_departure_soc is not None:
  dep_floor[snapshots.hour==args.ev_departure_hour]=max(.35,args.ev_departure_soc)
  h_dep=(args.ev_departure_hour-1)%24 if args.model_fixes else args.ev_departure_hour
  dmask=(df['dep_flag']>0).to_numpy() if seg is not None else (snapshots.hour==h_dep)
  floor_dep[dmask]=np.maximum(floor_dep[dmask],args.ev_departure_soc*ecap)
 if has_ev and args.ev_control!='fixed' and args.ev_cohorts>1:
  # Cohort test (R1.4): split each fleet into K equal cohorts. Vehicles away from
  # chargers in each hour are allocated by mixing a proportional split (theta=0,
  # identical cohorts) with sequential stacking (theta=1, cohort 1 absorbs away
  # vehicles first). Hourly totals of vehicles, connected vehicles, and traction
  # energy equal the aggregate fleet; each cohort has its own SoC window and
  # shared charge+discharge power limit, so energy cannot move between cohorts.
  K=args.ev_cohorts;w=1/K;theta=args.ev_cohort_theta
  for key,obj in [('commercial','EV JR Namie Commercial Area'),('residential','EV Residential Cars')]:
   count=df[key+'_vehicles'];avail=df[key+'_availability'];away=count*(1-avail)
   maxsoc=param(cfg,obj,'Max SoC')/100 if args.ev_max_soc is None else args.ev_max_soc
   for k in range(K):
    stack=(away-k*w*count).clip(lower=0).clip(upper=w*count)
    away_k=(1-theta)*w*away+theta*stack
    count_k=count*w;avail_k=(1-away_k/count_k).clip(lower=0,upper=1)
    share=(away_k/away).where(away>0,w)
    drive_k=df[key+'_drive_MWh']*share
    bus=f'ev_{key}_c{k+1}';ev_names.append((key,bus,obj));n.add('Bus',bus,carrier='battery')
    nom=float(count_k.max())*ecap
    n.add('Store',bus,bus=bus,e_nom=nom,e_initial=float(count_k.iloc[0])*ecap*.96,e_min_pu=count_k*(floor_dep if key in dep_groups else floor_base)/nom,e_max_pu=count_k*ecap*maxsoc/nom,standing_loss=.0005,e_cyclic=False)
    energy_arrivals=count_k.diff().fillna(0)*ecap*.96/hrs
    n.add('Load',bus+'_traction',bus=bus,p_set=drive_k-energy_arrivals)
    pnom=float(count_k.max())*kw_ev/es;availability=count_k/count_k.max()*avail_k
    n.add('Link',bus+'_charge',bus0='electricity',bus1=bus,p_nom=pnom,p_max_pu=availability,efficiency=es*ebc)
    n.add('Link',bus+'_discharge',bus0=bus,bus1='electricity',p_nom=(float(count_k.max())*kw_ev/ebd if args.model_fixes else pnom),p_max_pu=availability,efficiency=ebd*es,marginal_cost=args.v2g_cost_jpy_per_kwh/1000)
    ev_series[bus]=(count_k,avail_k)
 elif has_ev and args.ev_control!='fixed':
  for key,obj in [('commercial','EV JR Namie Commercial Area'),('residential','EV Residential Cars')]:
   bus='ev_'+key;ev_names.append((key,bus,obj));n.add('Bus',bus,carrier='battery')
   count=df[key+'_vehicles'];nom=float(count.max())*ecap
   maxsoc=param(cfg,obj,'Max SoC')/100 if args.ev_max_soc is None else args.ev_max_soc
   n.add('Store',bus,bus=bus,e_nom=nom,e_initial=float(count.iloc[0])*ecap*.96,e_min_pu=count*(floor_dep if key in dep_groups else floor_base)/nom,e_max_pu=count*ecap*maxsoc/nom,standing_loss=.0005,e_cyclic=bool(STATIC))
   # Fleet growth/shrinkage carries energy at its configured initial SoC.
   energy_arrivals=count.diff().fillna(0)*ecap*.96/hrs
   n.add('Load',bus+'_traction',bus=bus,p_set=df[key+'_drive_MWh']-energy_arrivals)
   pnom=float(count.max())*kw_ev/es;availability=count/count.max()*df[key+'_availability']
   n.add('Link',bus+'_charge',bus0='electricity',bus1=bus,p_nom=pnom,p_max_pu=availability,efficiency=es*ebc)
   # Optional battery-throughput (degradation) cost per battery-side kWh discharged.
   n.add('Link',bus+'_discharge',bus0=bus,bus1='electricity',p_nom=(float(count.max())*kw_ev/ebd if args.model_fixes else pnom),p_max_pu=availability,efficiency=ebd*es,marginal_cost=args.v2g_cost_jpy_per_kwh/1000)
 model=n.optimize.create_model(include_objective_constant=False)
 gen=model['Generator-p'];links=model['Link-p'];stores=model['Store-e']
 iy=xr.DataArray(snapshots.year,dims='snapshot',coords={'snapshot':snapshots})
 buildvar=None;cost=None
 if candidates:
  techs=pd.Index(candidates,name='technology')
  BSC={'wind':40.,'solar':20.,'roof':.02,'fuelcell':10.,'electrolyzer':1.,'tank':1.}
  bsc=xr.DataArray([BSC[k] if args.unit_scaling else 1. for k in candidates],dims='technology',coords={'technology':techs})
  n._bsc=bsc
  h2s=float('inf') if (args.h2_unlimited or args.h2_total_unlimited) else args.h2_limit_scale  # total build limits
  h2a=float('inf') if (args.h2_unlimited or args.h2_annual_unlimited) else args.h2_limit_scale  # annual build limits
  phys_units={'electrolyzer':H2_PHYS['electrolyzer_MW']/(10*args.h2_electrolysis_mwh_per_kg),'fuelcell':H2_PHYS['fuelcell_MW']/10.,'tank':H2_PHYS['tank_t']}
  def h2cap_units(k,v):return phys_units[k] if h2s==float('inf') else v*h2s
  def h2cap_annual(k,v):return phys_units[k] if h2a==float('inf') else v*h2a
  ykey='Max Units Built' if STATIC else 'Max Units Built in Year'  # static: one build year, only the total limit applies
  upper=xr.DataArray([param(cfg,TECH[k][0],ykey,param(cfg,TECH[k][0],'Max Units Built')) if k not in ('fuelcell','electrolyzer','tank') else h2cap_annual(k,param(cfg,TECH[k][0],'Max Units Built in Year',param(cfg,TECH[k][0],'Max Units Built'))) for k in candidates],dims='technology',coords={'technology':techs})*bsc
  buildvar=model.add_variables(lower=0,upper=upper,coords=[years,techs],integer=False,name='annual_build')
  installed=model.add_variables(lower=0,coords=[years,techs],name='installed_units')
  if args.investment_method=='annuity' or args.all_annuity:
   for k in candidates:
    for y in years:
     alive=[v for v in years if v<=y and y<v+tech_life(k,args,int(v))]
     model.add_constraints(installed.sel(year=y,technology=k)==buildvar.sel(year=alive,technology=k).sum(),name=f'vintage_capacity_{k}_{y}')
  elif args.h2_annuity:
   # --h2-annuity: hydrogen units retire at the end of their life; the other technologies accumulate as in the PLEXOS method
   h2k=[k for k in candidates if k in ('electrolyzer','fuelcell','tank')];acc=[k for k in candidates if k not in h2k]
   for k in h2k:
    for y in years:
     alive=[v for v in years if v<=y and y<v+tech_life(k,args,int(v))]
     model.add_constraints(installed.sel(year=y,technology=k)==buildvar.sel(year=alive,technology=k).sum(),name=f'vintage_capacity_{k}_{y}')
   if acc:
    model.add_constraints(installed.sel(year=years[0],technology=acc,drop=True)==buildvar.sel(year=years[0],technology=acc,drop=True),name='initial_capacity_accumulation')
    for y in years[1:]:
     model.add_constraints(installed.sel(year=y,technology=acc,drop=True)==installed.sel(year=y-1,technology=acc,drop=True)+buildvar.sel(year=y,technology=acc,drop=True),name=f'annual_capacity_accumulation_{y}')
  else:
   model.add_constraints(installed.sel(year=years[0],drop=True)==buildvar.sel(year=years[0],drop=True),name='initial_capacity_accumulation')
   for y in years[1:]:
    model.add_constraints(installed.sel(year=y,drop=True)==installed.sel(year=y-1,drop=True)+buildvar.sel(year=y,drop=True),name=f'annual_capacity_accumulation_{y}')
  if args.fix_builds is not None and args.fix_before:
   # Rolling / myopic windows: builds before --fix-before are fixed to an earlier window's annual_build.csv (unscaled units).
   fb=pd.read_csv(args.fix_builds,index_col=0)
   for y in [v for v in years if v<args.fix_before]:
    for k in candidates:
     val=float(fb.loc[y,k]) if (y in fb.index and k in fb.columns) else 0.
     model.add_constraints(buildvar.sel(year=y,technology=k)==max(val,0.)*float(bsc.sel(technology=k)),name=f'fixed_build_{k}_{y}')
  if args.h2_no_build_from:
   # End-effect test: no new hydrogen capacity from this year on.
   for k in [x for x in ('electrolyzer','fuelcell','tank') if x in candidates]:
    model.add_constraints(buildvar.sel(year=[v for v in years if v>=args.h2_no_build_from],technology=k)==0,name=f'h2_no_build_{k}')
  for k in candidates:
   obj=TECH[k][0]
   lim=h2cap_units(k,param(cfg,obj,'Max Units Built')) if k in ('fuelcell','electrolyzer','tank') else param(cfg,obj,'Max Units Built')
   model.add_constraints(installed.sel(technology=k)<=lim*float(bsc.sel(technology=k)),name='total_build_'+k)
  if args.tank_max_t and 'tank' in candidates:  # storage-capacity cap in every year (R2.6)
   model.add_constraints(installed.sel(technology='tank')<=args.tank_max_t*float(bsc.sel(technology='tank')),name='tank_max_t')
  costs=xr.DataArray([[ann[(TECH[k][0],int(y))]/1e6 for k in candidates] for y in years],dims=['year','technology'],coords={'year':years,'technology':techs})/bsc
  cost=(buildvar*costs).sum();model.add_objective(model.objective.expression+cost,overwrite=True)
  def cap(k):return installed.sel(technology=k).sel(year=iy)*(param(cfg,TECH[k][0],TECH[k][1])/float(bsc.sel(technology=k)))
  if 'wind' in candidates:model.add_constraints(gen.sel(name='wind')<=(fixed_wind+cap('wind'))*xr.DataArray(df.wind_pu),name='wind_year_capacity')
  solar_cap=fixed_solar
  for k in ['roof','solar']:
   if k in candidates:solar_cap=solar_cap+cap(k)
  model.add_constraints(gen.sel(name='solar')<=solar_cap*xr.DataArray(df.solar_pu),name='solar_year_capacity')
  if has_h2:
   el_av=args.el_availability if args.el_availability is not None else args.h2_availability
   fc_av=args.fc_availability if args.fc_availability is not None else args.h2_availability
   sx=lambda s:xr.DataArray(s.to_numpy(),dims='snapshot',coords={'snapshot':snapshots})
   h2cap={'electrolyzer':cap('electrolyzer')*(sx(n._ael_t) if args.el_sec_path else args.h2_electrolysis_mwh_per_kg)*el_av,
          'fuelcell':cap('fuelcell')*(sx(n._fk_t) if args.fc_kg_path else args.fc_kg_per_mwh*hu)*fc_av}
   model.add_constraints(links.sel(name='electrolyzer')<=h2cap['electrolyzer'],name='electrolyzer_year_capacity')
   model.add_constraints(links.sel(name='fuelcell')<=h2cap['fuelcell'],name='fuelcell_year_capacity')
   ow=xr.DataArray((n.snapshot_weightings.objective/hrs).to_numpy(),dims='snapshot',coords={'snapshot':snapshots})  # start-ups are events: discount x sampling factor, not x hours
   hw=xr.DataArray(hrs.to_numpy(),dims='snapshot',coords={'snapshot':snapshots})
   uc={'electrolyzer':(args.el_min_load,args.el_startup_cost,args.el_ramp),'fuelcell':(args.fc_min_load,args.fc_startup_cost,args.fc_ramp)}
   startup_cost=0;aux_terms=[]
   for k,(pmin,csu,ramp) in uc.items():
    p_k=links.sel(name=k);C=h2cap[k]
    # Link-p units: MW electricity (electrolyzer), kg/h hydrogen (fuel cell); costs are per MW electricity.
    mw_per_unit=1. if k=='electrolyzer' else 1/(args.fc_kg_per_mwh*hu)
    if args.h2_uc:
     u=model.add_variables(lower=0,coords=[snapshots],name=k+'_committed')
     su=model.add_variables(lower=0,coords=[snapshots],name=k+'_startup')
     s_k=args.el_standby_power if k=='electrolyzer' else args.fc_standby_power
     e_k=args.el_startup_energy if k=='electrolyzer' else args.fc_startup_energy
     if s_k>0:
      hs=model.add_variables(lower=0,coords=[snapshots],name=k+'_standby')
      warm=u+hs
     else:
      hs=None;warm=u
     sh_k=args.h2_startup_hours if (k=='electrolyzer' or args.fc_startup_hours is None) else args.fc_startup_hours
     if sh_k>0:
      # Cold start: capacity started in hour t is committed but not yet productive.
      model.add_constraints(p_k<=u-su/hw,name=k+'_p_le_committed')
      model.add_constraints(p_k>=pmin*(u-su/hw),name=k+'_min_load')
     else:
      model.add_constraints(p_k<=u,name=k+'_p_le_committed')
      model.add_constraints(p_k>=pmin*u,name=k+'_min_load')
     model.add_constraints(warm<=C,name=k+'_committed_le_capacity')
     model.add_constraints(su>=warm-warm.shift(snapshot=1),name=k+'_startup_def')
     aux_terms.append(su*(e_k*mw_per_unit)/hw)
     if hs is not None:aux_terms.append(hs*(s_k*mw_per_unit))
     model.add_constraints(su<=warm,name=k+'_startup_le_committed')
     startup_cost=startup_cost+(su*ow).sum()*csu*mw_per_unit/1e6
    if ramp<=1:
     dp=p_k-p_k.shift(snapshot=1)
     model.add_constraints(dp<=ramp*C,name=k+'_ramp_up')
     model.add_constraints(-dp<=ramp*C,name=k+'_ramp_down')
   if args.h2_uc:model.add_objective(model.objective.expression+startup_cost,overwrite=True)
   if 'el_eff_aux' in n.links.index:
    extra=links.sel(name='el_eff_aux');p_el=links.sel(name='electrolyzer');C_el=h2cap['electrolyzer']
    n._el_cap_expr=C_el
    base=args.el_noload*model['electrolyzer_committed'] if (args.h2_uc and args.el_noload>0) else 0
    if args.el_noload>0 and not args.h2_uc:raise ValueError('--el-noload requires --h2-uc')
    if args.el_noload>0:model.add_constraints(extra>=base,name='el_eff_noload')
    for j,piece in enumerate([x for x in (args.el_curve or '').split(',') if x]):
     b,s=(float(v) for v in piece.split(':'))
     ref=(model['electrolyzer_committed']-model['electrolyzer_startup'] if args.h2_startup_hours>0 else model['electrolyzer_committed']) if (args.model_fixes and args.h2_uc) else C_el
     model.add_constraints(extra>=base+s*(p_el-b*ref),name=f'el_eff_piece_{j}')
   if 'h2_aux_power' in n.links.index:
    aux=aux_terms[0]
    for term in aux_terms[1:]:aux=aux+term
    model.add_constraints(links.sel(name='h2_aux_power')==aux,name='h2_aux_power_def')
   model.add_constraints(stores.sel(name='hydrogen')<=cap('tank')*hu,name='tank_year_capacity')
   if args.island_days>0:
    # Resilience (grid outage, no credit for wind/PV): stored hydrogen must at all times cover
    # island_days of the critical load after reconversion, and fuel-cell capacity its peak.
    crit=df['load_MW']*args.island_load_share
    on=xr.DataArray((snapshots.year>=args.island_start_year).astype(float),dims='snapshot',coords={'snapshot':snapshots})
    req=xr.DataArray((crit.groupby(snapshots.year).transform('mean')*24*args.island_days).to_numpy(),dims='snapshot',coords={'snapshot':snapshots})
    peak=xr.DataArray(crit.groupby(snapshots.year).transform('max').to_numpy(),dims='snapshot',coords={'snapshot':snapshots})
    model.add_constraints(stores.sel(name='hydrogen')*(1/(args.fc_kg_per_mwh*hu))>=req*on,name='island_energy')
    model.add_constraints(cap('fuelcell')>=peak*on,name='island_power')
 if gmax>0:
  gup=xr.DataArray([gmax if int(y)>=args.grid_start_year else 0. for y in years],dims='year',coords={'year':years})
  gbuild=model.add_variables(lower=0,upper=gup,coords=[years],name='grid_build')
  gcum=model.add_variables(lower=0,upper=gmax,coords=[years],name='grid_installed')
  model.add_constraints(gcum.sel(year=years[0])==gbuild.sel(year=years[0]),name='grid_cum_0')
  for y in years[1:]:model.add_constraints(gcum.sel(year=y)==gcum.sel(year=y-1)+gbuild.sel(year=y),name=f'grid_cum_{y}')
  gpv=xr.DataArray([grid_pv_per_mw(int(y),args) for y in years],dims='year',coords={'year':years})
  model.add_objective(model.objective.expression+(gbuild*gpv).sum(),overwrite=True)
  gt=gcum.sel(year=iy)
  model.add_constraints(gen.sel(name='import')<=market+gt,name='import_with_expansion')
  model.add_constraints(gen.sel(name='export')<=export_limit+gt,name='export_with_expansion')
 steady=args.model_fixes and (snapshots.year==snapshots[-1].year-1).any()
 if steady:
  last_prev=snapshots[snapshots.year==snapshots[-1].year-1][-1];last=snapshots[-1]
  model.add_constraints(stores.sel(name='biomass_stock',snapshot=last)==stores.sel(name='biomass_stock',snapshot=last_prev),name='biomass_steady_final_year')
  if has_h2:model.add_constraints(stores.sel(name='hydrogen',snapshot=last)==stores.sel(name='hydrogen',snapshot=last_prev),name='hydrogen_steady_final_year')
 elif has_h2 and not STATIC:model.add_constraints(stores.sel(name='hydrogen',snapshot=snapshots[-1])==0,name='hydrogen_terminal_recycle')
 for key,bus,obj in ev_names:
  cnt,av=ev_series.get(bus,(df[key+'_vehicles'],df[key+'_availability']))
  allowed=xr.DataArray(cnt*kw_ev/es*av)
  if args.model_fixes:
   model.add_constraints(links.sel(name=bus+'_charge')*es+links.sel(name=bus+'_discharge')*ebd<=xr.DataArray(cnt*kw_ev*av),name=bus+'_aggregate_mode')
  else:
   model.add_constraints(links.sel(name=bus+'_charge')+links.sel(name=bus+'_discharge')<=allowed,name=bus+'_aggregate_mode')
  if args.ev_control in ('charge_only','fixed'):
   model.add_constraints(links.sel(name=bus+'_discharge')==0,name=bus+'_no_discharge')
  if args.ev_v2g_efc_cap is not None:
   for y in years:
    sel=snapshots[snapshots.year==y]
    cap_mwh=float(cnt[sel].mean())*ecap*args.ev_v2g_efc_cap
    model.add_constraints((links.sel(name=bus+'_discharge',snapshot=sel)*xr.DataArray(hrs[sel].to_numpy(),dims='snapshot',coords={'snapshot':sel})).sum()<=cap_mwh,name=f'{bus}_v2g_cap_{y}')
  if steady:
   ratio=float(cnt.loc[last])/float(cnt.loc[last_prev]) if float(cnt.loc[last_prev])>0 else 1.
   model.add_constraints(stores.sel(name=bus,snapshot=last)==stores.sel(name=bus,snapshot=last_prev)*ratio,name=bus+'_steady_final_year')
  elif key=='residential' and not STATIC:model.add_constraints(stores.sel(name=bus,snapshot=snapshots[-1])==float(cnt.iloc[-1])*ecap*.96,name=bus+'_terminal_recycle')
 # Fuel holding charge on each end-of-year inventory, including perpetuity.
 holding_expression=0
 for y in years:
  last=snapshots[snapshots.year==y][-1]
  coeff=10/1e6/bu*(1. if STATIC else 1.03**(-(int(y)-2024)) if y!=YEND else W2050())
  holding_expression=holding_expression+stores.sel(name='biomass_stock',snapshot=last)*coeff
 model.add_objective(model.objective.expression+holding_expression,overwrite=True)
 if args.import_limit_mw is not None:
  model.add_constraints(gen.sel(name='import')<=args.import_limit_mw,name='import_limit')
 if args.self_sufficiency>0:
  # Annual imports limited to (1 - s) of the annual non-EV local demand.
  for y in years:
   sel=snapshots[snapshots.year==y]
   h=xr.DataArray(hrs[sel].to_numpy(),dims='snapshot',coords={'snapshot':sel})
   lim=(1-args.self_sufficiency)*float((df.load_MW[sel]*hrs[sel]).sum())
   model.add_constraints((gen.sel(name='import',snapshot=sel)*h).sum()<=lim,name=f'self_sufficiency_{y}')
 hydro=extend_years(pd.read_parquet(source/'hydro_monthly.parquet').hydro_GWh)
 if args.days_per_year:
  for y in years:
   mask=snapshots.year==y
   model.add_constraints((gen.sel(name='hydro',snapshot=snapshots[mask])*xr.DataArray(weight[mask])).sum()<=float(hydro[hydro.index.year==y].sum())*1000,name=f'hydro_annual_{y}')
 else:
  for (y,month),indices in pd.Series(np.arange(len(snapshots)),index=snapshots).groupby([snapshots.year,snapshots.month]):
   times=indices.index;limit=float(hydro[(hydro.index.year==y)&(hydro.index.month==month)].sum())*1000
   model.add_constraints((gen.sel(name='hydro',snapshot=times)*xr.DataArray(hrs[times].to_numpy(),dims='snapshot',coords={'snapshot':times})).sum()<=limit,name=f'hydro_month_{y}_{month}')
 return n,df,buildvar,dict(build_seconds=time.perf_counter()-t0,has_ev=has_ev,has_h2=has_h2,snapshots=len(df),variables=int(model.nvars),constraints=int(model.ncons),sampled=bool(args.days_per_year),ev_control=args.ev_control,fixed_charge_profile_sha256=file_sha256(args.fixed_charge_profile or source/'fixed_fleet_charging.parquet') if args.ev_control=='fixed' else None)

# Reviewed new baseline (revision round 1, 2026-10-19). Sources: revision_round1/reports/*.md
PRESET_NEWBASE=dict(
 no_perpetuity=True,  # main results: horizon 2025-2050 with truncated annuities (PyPSA/GenX practice); --perpetuity for robustness
 ev_station_eff=.93,ev_batt_charge_eff=.98,ev_batt_discharge_eff=.98,  # 83.1% round trip, DC CHAdeMO
 v2g_cost_jpy_per_kwh=3.,ev_capacity_scale=.9,ev_departure_soc=.8,ev_departure_hour=7,ev_participation=.5,  # PyPSA-Eur defaults (bev_dsm_availability 0.5, 80% at 07:00)
 h2_unlimited=True,h2_uc=True,h2_startup_hours=1,fc_startup_hours=0,
 el_min_load=.2,fc_min_load=.2,el_ramp=1.,fc_ramp=1.,
 el_standby_power=.0224,el_startup_energy=.168,el_startup_cost=8944.,  # full-load basis (x1.118)
 h2_electrolysis_mwh_per_kg=.04912,el_curve='0.35:0.1057,0.5185:0.2038',el_noload=.02,
 el_availability=.97,fc_availability=.95,
 el_degradation=.006,el_stack_life=15,fc_degradation=.006,fc_stack_life=10,degradation_average=True,
 h2_standing_loss_per_day=0.,  # steel tanks: negligible (reports/R1_5_parameter_sources.md); 0.1%/day as sensitivity
model_fixes=True,
 import_adder_jpy_per_kwh=2.,export_deduction_jpy_per_kwh=1.,re_fom_jpy_per_kw=2193.,  # RE FOM 1,000 + 発電側課金 kW part 1,193 JPY/kW-yr
  # reports/东北输配电费与发电侧课金.md: 特別高圧 wheeling ~2.0; 発電側課金 0.30 + FIP balancing 0.7
 market_limit_mw=118.,  # documented N-1 rating of the 66 kV Namie line (tohoku2025fukushima); 150 MW = reinforcement case
 investment_method='annuity',h2_capex='base',
 grid_capex_jpy_per_kw=105000.,grid_fom=.019,grid_life=28.,grid_start_year=2031,grid_max_mw=0.,  # reports/送电接口扩容成本与上限.md
 fixed_charge_profile=ROOT/'inputs'/'fixed_fleet_charging_newbase.parquet')  # regime A rebuilt for newbase (build_fixed_profile.py --preset newbase)
# Original formulation, equivalent to the PLEXOS LP (used to validate PyPSA against PLEXOS).
PRESET_PLEXOS=dict(
 ev_station_eff=.9,ev_batt_charge_eff=.95,ev_batt_discharge_eff=.9,
 v2g_cost_jpy_per_kwh=0.,ev_capacity_scale=1.,ev_departure_soc=None,ev_departure_hour=7,ev_participation=1.,
 h2_unlimited=False,h2_uc=False,h2_startup_hours=0,fc_startup_hours=None,
 el_min_load=0.,fc_min_load=0.,el_ramp=2.,fc_ramp=2.,
 el_standby_power=0.,el_startup_energy=0.,el_startup_cost=0.,
 h2_electrolysis_mwh_per_kg=.053,el_curve=None,el_noload=0.,
 el_availability=None,fc_availability=None,
 el_degradation=0.,el_stack_life=10,fc_degradation=0.,fc_stack_life=10,degradation_average=False,
 h2_standing_loss_per_day=0.,model_fixes=False,fixed_charge_profile=None,market_limit_mw=None,investment_method='plexos',import_adder_jpy_per_kwh=0.,export_deduction_jpy_per_kwh=0.)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--scenario',choices=['S0','S1','S2','S3','S4'],required=True);parser.add_argument('--days-per-year',type=int,default=0);parser.add_argument('--only-year',type=int,help='Diagnostic one-year slice; not a full-horizon manuscript result');parser.add_argument('--end-year',type=int,help='Diagnostic cumulative slice through this year');parser.add_argument('--continuous',action='store_true',default=True,help='Compatibility flag; this model always uses continuous construction');parser.add_argument('--market-limit-mw',type=float,help='Override both market purchase and sale limits');parser.add_argument('--renewable-scale',type=float,default=1);parser.add_argument('--ev-availability-scale',type=float,default=1);parser.add_argument('--price-scale',type=float,default=1);parser.add_argument('--ev-control',choices=['bidirectional','charge_only','fixed'],default='bidirectional',help='Fleet-level EV charging rule');parser.add_argument('--fixed-charge-profile',type=Path,help='Parquet with precomputed aggregate grid charging power');parser.add_argument('--solver',default='highs',choices=['highs','gurobi']);parser.add_argument('--time-limit',type=int,default=120);parser.add_argument('--threads',type=int,default=8);parser.add_argument('--ev-max-soc',type=float);parser.add_argument('--v2g-cost-jpy-per-kwh',type=float,default=0.,help='Throughput cost on battery-side EV discharge');parser.add_argument('--ev-cohorts',type=int,default=1,help='Split each EV fleet into this many cohorts (R1.4 aggregation test)');parser.add_argument('--ev-cohort-theta',type=float,default=1.,help='0 = identical cohorts, 1 = sequential stacking of away vehicles');parser.add_argument('--ev-capacity-scale',type=float,default=1.,help='Usable battery energy per vehicle relative to 70 kWh (capacity fade)');parser.add_argument('--h2-electrolysis-mwh-per-kg',type=float,default=.053,help='Electricity per kg H2 incl. compression and auxiliaries');parser.add_argument('--h2-availability',type=float,default=1.,help='Electrolyzer and fuel-cell capacity derating');parser.add_argument('--h2-standing-loss-per-day',type=float,default=0.,help='Hydrogen tank loss fraction per day');parser.add_argument('--h2-limit-scale',type=float,default=1.,help='Scale hydrogen build limits (annual, cumulative, process)');parser.add_argument('--h2-unlimited',action=argparse.BooleanOptionalAction,default=False,help='Remove hydrogen build limits');parser.add_argument('--h2-annual-unlimited',action='store_true',help='Remove only the annual hydrogen build limits');parser.add_argument('--h2-total-unlimited',action='store_true',help='Remove only the total hydrogen build limits and process capacities');parser.add_argument('--h2-uc',action=argparse.BooleanOptionalAction,default=False,help='Linear-relaxed unit commitment for electrolyzer and fuel cell');parser.add_argument('--el-min-load',type=float,default=0.);parser.add_argument('--fc-min-load',type=float,default=0.);parser.add_argument('--el-startup-cost',type=float,default=0.,help='JPY per MW started');parser.add_argument('--fc-startup-cost',type=float,default=0.,help='JPY per MW started');parser.add_argument('--el-ramp',type=float,default=2.,help='p.u. of installed capacity per hour; values >1 mean no ramp constraint');parser.add_argument('--fc-ramp',type=float,default=2.);parser.add_argument('--investment-method',choices=['annuity','plexos'],default='plexos',help='annuity = equivalent annuity with replacement through the perpetuity');parser.add_argument('--h2-capex',choices=['base','low','high','old'],default='base',help='Hydrogen capex set (annuity method)');parser.add_argument('--wacc',type=float,default=.03);parser.add_argument('--grid-max-mw',type=float,default=0.,help='Max interface reinforcement above the base limit (MW); 0 = none');parser.add_argument('--grid-capex-jpy-per-kw',type=float,default=0.);parser.add_argument('--grid-fom',type=float,default=.01,help='Fixed O&M, fraction of capex per year');parser.add_argument('--grid-life',type=float,default=40.);parser.add_argument('--grid-wacc',type=float,default=.03);parser.add_argument('--grid-start-year',type=int,default=2030);parser.add_argument('--capex-electrolyzer',help='2025:a,2030:b,... thousand JPY per 10 kg/h block');parser.add_argument('--capex-fuelcell',help='thousand JPY per kW');parser.add_argument('--capex-tank',help='thousand JPY per tonne');parser.add_argument('--h2-om-set',choices=['verified','base','low','high'],default='verified',help='Hydrogen FOM/life: verified = DEA life path + stack replacement (independent of the capex set)');parser.add_argument('--h2-sale-price',type=float,default=0.,help='Off-site hydrogen sale price, JPY/kg (0 = no sales)');parser.add_argument('--h2-sale-max-kgph',type=float,default=0.,help='Max hydrogen sales, kg/h (0 = unbounded)');parser.add_argument('--h2-capex-scale',type=float,default=1.,help='Multiplier on the selected hydrogen capex set');parser.add_argument('--h2-cost-flat-from',type=int,default=0,help='Timing test: hydrogen capex, FOM and life of vintages from this year take their 2050 values (0 = off)');parser.add_argument('--h2-annuity',action='store_true',help='PLEXOS method with hydrogen investment as finite-life annuities: retirement at end of life, renewal at 2050 cost in perpetuity (registry h2_annuity_method)');parser.add_argument('--el-sec-path',help='Electrolysis full-load system kWh/kg by operating year, e.g. 2025:54.92,2050:48 (linear coefficient = value/EL_FL_RATIO; registry h2_efficiency_path)');parser.add_argument('--fc-kg-path',help='Fuel-cell kg H2 per MWh by operating year, e.g. 2025:60.6,2050:53.6 (registry h2_efficiency_path)');parser.add_argument('--all-annuity',action='store_true',help='PLEXOS-preset costs with every new asset as finite-life annuities (retirement at end of life); with perpetuity renewal at 2050 cost is charged, with --no-perpetuity annuities stop in 2050 (salvage) (registry all_annuity_method)');parser.add_argument('--h2-life',type=float,default=0.,help='Override electrolyzer and fuel-cell life (years)');parser.add_argument('--tsam-segments',type=int,default=0,help='Chronological tsam segments per year (0 = hourly)');parser.add_argument('--unit-scaling',action=argparse.BooleanOptionalAction,default=True,help='Hydrogen in t, biomass in TJ, builds in MW (numerics only)');parser.add_argument('--model-fixes',action=argparse.BooleanOptionalAction,default=False,help='Review fixes: steady final year, DC metering, absolute 35%% floor, curve on committed capacity');parser.add_argument('--degradation-average',action=argparse.BooleanOptionalAction,default=False,help='Lifetime-average stack degradation instead of a 2025-based sawtooth');parser.add_argument('--fc-kg-per-mwh',type=float,default=60.6,help='Fuel-cell hydrogen use per MWh electricity (60.6 = 49.5%% LHV)');parser.add_argument('--ev-station-eff',type=float,default=.9,help='Charger conversion efficiency, each direction');parser.add_argument('--ev-batt-charge-eff',type=float,default=.95);parser.add_argument('--ev-batt-discharge-eff',type=float,default=.9);parser.add_argument('--re-fom-jpy-per-kw',type=float,default=1000.,help='Wind/PV fixed O&M incl. generator-side kW charge (annuity method)');parser.add_argument('--export-curtail-share',type=float,default=0.,help='Share of hours per year (highest local VRE) with exports curtailed');parser.add_argument('--export-curtail-level',type=float,default=0.,help='Remaining export fraction during curtailed hours (0 = none)');parser.add_argument('--curtail-wind-weight',type=float,default=.3,help='Wind weight in the regional-surplus proxy (Tohoku 2035 mix)');parser.add_argument('--curtail-calendar',action=argparse.BooleanOptionalAction,default=True,help='Season and weekend factors in the proxy');parser.add_argument('--price-wind-beta',type=float,default=0.,help='Weekly wind-price coupling (scheme A); 0 = historical shape');parser.add_argument('--price-series',type=Path,help='Parquet (year, ts) with price JPY/kWh and curtail_rate; replaces historical price, beta and curtailment proxy');parser.add_argument('--series-curtail-scale',type=float,default=1.,help='Multiplier on the series curtailment rate applied to exports');parser.add_argument('--renewable-profile',type=Path,help='Parquet ts -> solar_pu, wind_pu (reference weather year), mapped by month-day-hour');parser.add_argument('--price-wind-beta-path',help='Year path for beta, e.g. 2025:0,2035:0.9,2050:1.4 (overrides --price-wind-beta)');parser.add_argument('--price-wind-beta-scale',type=float,default=1.,help='Multiplier on beta (path or scalar)');parser.add_argument('--export-curtail-share-path',help='Year path for the curtailed-hour share, e.g. 2025:0.06,2035:0.15,2050:0.25 (overrides --export-curtail-share)');parser.add_argument('--export-curtail-share-scale',type=float,default=1.,help='Multiplier on the curtailed-hour share (path or scalar)');parser.add_argument('--import-limit-mw',type=float,help='Hourly import cap (MW), below the interface rating');parser.add_argument('--self-sufficiency',type=float,default=0.,help='Min share of annual non-EV demand not imported (0-1)');parser.add_argument('--island-days',type=float,default=0.,help='Days of critical load the hydrogen store must hold at all times');parser.add_argument('--island-load-share',type=float,default=1.,help='Critical share of the non-EV load');parser.add_argument('--island-start-year',type=int,default=2030);parser.add_argument('--import-adder-jpy-per-kwh',type=float,default=0.,help='Network (wheeling) charge added to purchases');parser.add_argument('--export-deduction-jpy-per-kwh',type=float,default=0.,help='Generator-side charges deducted from sales');parser.add_argument('--ev-charger-kw',type=float,default=10.,help='Charger power per connected managed vehicle (kW)');parser.add_argument('--ev-participation',type=float,default=1.,help='Share of each fleet in managed charging/V2G (rest on the uncontrolled profile)');parser.add_argument('--ev-departure-soc',type=float);parser.add_argument('--ev-departure-hour',type=int,default=7);parser.add_argument('--ev-departure-groups',default='commercial,residential');parser.add_argument('--ev-v2g-efc-cap',type=float,help='Annual V2G equivalent full cycles per vehicle');parser.add_argument('--h2-startup-hours',type=int,default=0);parser.add_argument('--fc-startup-hours',type=int,help='Fuel-cell start-up hours (default: --h2-startup-hours)');parser.add_argument('--el-noload',type=float,default=0.,help='No-load BoP consumption, MW per MW committed');parser.add_argument('--el-curve',help='Convex part-load pieces b:s,b:s (load fraction : extra MW per MW)');parser.add_argument('--el-degradation',type=float,default=0.,help='Fractional increase in kWh/kg per year of stack age');parser.add_argument('--el-stack-life',type=int,default=10);parser.add_argument('--fc-degradation',type=float,default=0.);parser.add_argument('--fc-stack-life',type=int,default=10);parser.add_argument('--el-standby-power',type=float,default=0.);parser.add_argument('--fc-standby-power',type=float,default=0.);parser.add_argument('--el-startup-energy',type=float,default=0.,help='MWh per MW started');parser.add_argument('--fc-startup-energy',type=float,default=0.);parser.add_argument('--el-availability',type=float);parser.add_argument('--fc-availability',type=float);parser.add_argument('--gurobi-method',type=int,choices=[0,1,2]);parser.add_argument('--gurobi-numeric-focus',type=int,choices=[0,1,2,3]);parser.add_argument('--gurobi-bar-homogeneous',type=int,choices=[-1,0,1]);parser.add_argument('--gurobi-crossover',type=int,choices=[-1,0,1,2,3,4]);parser.add_argument('--bar-conv-tol',type=float);parser.add_argument('--fix-builds',type=Path,help='annual_build.csv of an earlier rolling/myopic window');parser.add_argument('--fix-before',type=int,default=0,help='Fix builds of years before this to --fix-builds');parser.add_argument('--no-perpetuity',action='store_true',help='End the horizon in 2050: 2050 weighted as one year and no annuities after 2050 (salvage value). Default in the newbase preset');parser.add_argument('--perpetuity',action='store_true',help='Override: repeat 2050 in perpetuity (robustness; plexos preset default)');parser.add_argument('--h2-no-build-from',type=int,default=None,help='End-effect test: forbid new hydrogen builds from this year (with --fix-builds/--fix-before; 0 = fixed builds only, perpetuity allowed)');parser.add_argument('--h2-fom',help='PLEXOS method: hydrogen FO&M as share of build-year capex per year, e.g. electrolyzer:0.02,fuelcell:0.03,tank:0.005 (replaces the original O&M in the PLEXOS PV)');parser.add_argument('--h2-stack-repl',help='PLEXOS method: stack replacement share:years, e.g. electrolyzer:0.11:40,fuelcell:0.20:10');parser.add_argument('--load-scale',type=float,default=1.,help='Multiplier on non-EV local demand (sensitivity, registry sensitivity_F5_load_tank_20261030)');parser.add_argument('--tank-max-t',type=float,default=0.,help='Cap on installed hydrogen tank (t) in every year; 0 = off');parser.add_argument('--wind-scale',type=float,default=1.,help='Multiplier on wind capacity factors only (sensitivity)');parser.add_argument('--extend-to',type=int,default=2050,help='End-effect test: extend the horizon to this year, repeating 2050 conditions and costs');parser.add_argument('--static-year',type=int,help='Static single-year model (no pathway): operate this year once, undiscounted; capacity at annualised cost (capex x CRF(--wacc, life) + FO&M + stack replacements); storage cyclic. Objective and npv_billion_JPY are then annual values');parser.add_argument('--output',type=Path,required=True);parser.add_argument('--build-only',action='store_true');parser.add_argument('--preset',choices=['newbase','plexos'],default='newbase',help='newbase = reviewed baseline (default); plexos = original PLEXOS-equivalent formulation');pre,_=parser.parse_known_args();parser.set_defaults(**(PRESET_PLEXOS if pre.preset=='plexos' else PRESET_NEWBASE));args=parser.parse_args();global PERP,HEND,YEND,STATIC;PERP=args.perpetuity or not args.no_perpetuity;YEND=args.extend_to;HEND=args.end_year or YEND;STATIC=args.static_year
 if STATIC and (args.only_year or args.end_year or args.days_per_year or args.tsam_segments or args.fix_builds or args.h2_no_build_from is not None or args.extend_to!=2050 or args.ev_cohorts>1):
  parser.error('--static-year cannot be combined with --only-year/--end-year/--days-per-year/--tsam-segments/--fix-builds/--h2-no-build-from/--extend-to/--ev-cohorts')
 if args.fix_builds is not None and PERP and args.h2_no_build_from is None:parser.error('rolling/myopic windows (--fix-builds) require truncated annuities (no perpetuity)')
 if args.all_annuity and (STATIC or args.investment_method=='annuity' or args.h2_annuity or args.h2_cost_flat_from or args.fix_builds is not None):parser.error('--all-annuity applies to the PLEXOS-method pathway only (not with --static-year, --investment-method annuity, --h2-annuity, --h2-cost-flat-from or --fix-builds)')
 if args.h2_annuity and (STATIC or args.investment_method=='annuity' or args.h2_cost_flat_from):parser.error('--h2-annuity applies to the PLEXOS-method pathway only (not with --static-year, --investment-method annuity or --h2-cost-flat-from)')
 if args.market_limit_mw is not None and args.market_limit_mw<=0:parser.error('--market-limit-mw must be positive')
 if min(args.renewable_scale,args.ev_availability_scale,args.price_scale,args.load_scale)<=0:parser.error('Profile scale factors must be positive')
 uses_fixed=args.ev_control=='fixed' or args.ev_participation<1
 default_profiles={None,str(ROOT/'inputs'/'fixed_fleet_charging_newbase.parquet'),str(ROOT/'inputs'/'fixed_fleet_charging.parquet')}
 if uses_fixed and args.ev_availability_scale!=1 and (None if args.fixed_charge_profile is None else str(args.fixed_charge_profile)) in default_profiles:
  parser.error('Availability is scaled: pass --fixed-charge-profile built with the same --availability-scale (build_fixed_profile.py)')
 args.output.mkdir(parents=True,exist_ok=True);logging.basicConfig(level=logging.INFO,handlers=[logging.FileHandler(args.output/'python.log',encoding='utf-8'),logging.StreamHandler()])
 n,df,buildvar,stats=build(args);stats.update(scenario=args.scenario,continuous=args.continuous,market_purchase_mw=float(n.generators.at['import','p_nom']),market_sale_mw=float(n.generators.at['export','p_nom']),renewable_scale=args.renewable_scale,ev_availability_scale=args.ev_availability_scale,price_scale=args.price_scale,solver=args.solver,pypsa=pypsa.__version__,objective_unit='million JPY',validation_status='reconstruction prototype; see fidelity ledger',command={k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items()})
 (args.output/'build_stats.json').write_text(json.dumps(stats,indent=2),encoding='utf-8')
 if args.build_only:return
 options={'time_limit':args.time_limit,'threads':args.threads} if args.solver=='highs' else {'TimeLimit':args.time_limit,'Threads':args.threads}
 if args.solver=='gurobi':
  if args.gurobi_method is not None:options['Method']=args.gurobi_method
  if args.bar_conv_tol is not None:options['BarConvTol']=args.bar_conv_tol
  if args.gurobi_numeric_focus is not None:options['NumericFocus']=args.gurobi_numeric_focus
  if args.gurobi_bar_homogeneous is not None:options['BarHomogeneous']=args.gurobi_bar_homogeneous
  if args.gurobi_crossover is not None:options['Crossover']=args.gurobi_crossover
 t0=time.perf_counter();status,termination=n.optimize.solve_model(solver_name=args.solver,solver_options=options,log_fn=str(args.output/'solver.log'))
 stats.update(solve_seconds=time.perf_counter()-t0,status=status,termination_condition=termination)
 if n.model.status=='ok':
  stats['objective_million_JPY']=float(n.model.objective.value)
  stats['npv_billion_JPY']=-float(n.model.objective.value)/1000
  if STATIC:stats.update(static_year=STATIC,objective_basis='static: annual net value of one year (billion JPY/yr), undiscounted')
  if buildvar is not None:(buildvar.solution/n._bsc).to_pandas().to_csv(args.output/'annual_build.csv')
  if 'installed_units' in n.model.variables:
   inst=(n.model['installed_units'].solution/n._bsc).to_pandas();inst.to_csv(args.output/'installed_units.csv')
   if args.h2_unlimited:
    caps={'electrolyzer':H2_PHYS['electrolyzer_MW']/(10*args.h2_electrolysis_mwh_per_kg),'fuelcell':H2_PHYS['fuelcell_MW']/10.,'tank':H2_PHYS['tank_t']}
    stats['physical_cap_check']={k:{'max_installed_units':float(inst[k].max()),'cap_units':caps[k],'binding':bool(inst[k].max()>.99*caps[k])} for k in caps if k in inst.columns}
    if any(v['binding'] for v in stats['physical_cap_check'].values()):logging.warning('A physical hydrogen cap binds: %s',stats['physical_cap_check'])
  # Meaningful residual check: electricity balance from independent output tables.
  balance=n.generators_t.p.mul(n.generators.sign).T.groupby(n.generators.bus).sum().T['electricity']-n.loads_t.p_set.loc[:,n.loads.bus=='electricity'].sum(axis=1)
  for name in n.links.index:
   if n.links.at[name,'bus0']=='electricity':balance-=n.links_t.p0[name]
   if n.links.at[name,'bus1']=='electricity':balance-=n.links_t.p1[name]
  stats['max_electricity_balance_residual_MW']=float(balance.abs().max())
  # Independent cash-flow ledger, including build coefficients and stock holding.
  terms={}
  for component,dispatch,static,dynamic in [('Generator',n.generators_t.p,n.generators,n.generators_t),('Link',n.links_t.p0,n.links,n.links_t)]:
   mc=dynamic.marginal_cost.reindex(index=n.snapshots,columns=static.index).fillna(static.marginal_cost)
   terms[component+'_operation_million_JPY']=float(dispatch.mul(mc).mul(n.snapshot_weightings.objective,axis=0).to_numpy().sum())
  holding=0.
  for y in sorted(df.index.year.unique()):
   last=df.index[df.index.year==y][-1];factor=1. if STATIC else 1.03**(-(int(y)-2024)) if y!=YEND else W2050()
   holding+=float(n.stores_t.e.at[last,'biomass_stock'])*10/1e6/(1e-3 if args.unit_scaling else 1.)*factor
  terms['fuel_holding_million_JPY']=holding
  investment=0.
  if buildvar is not None:
   built=(buildvar.solution/n._bsc).to_pandas();coeffs=investment_pv(args,load_annuity(ROOT/'inputs',args.scenario))
   coeffs={key:v/1e6 for key,v in coeffs.items()}
   investment=sum(float(built.at[y,k])*coeffs[(TECH[k][0],int(y))] for y in built.index for k in built.columns)
   stats['max_integer_deviation']=None
  terms['investment_and_fixed_million_JPY']=investment
  if 'grid_build' in n.model.variables:
   gb=n.model['grid_build'].solution.to_pandas()
   terms['grid_expansion_million_JPY']=float(sum(gb[y]*grid_pv_per_mw(int(y),args) for y in gb.index))
   stats['grid_expansion']={'built_MW_by_year':{int(y):float(v) for y,v in gb.items() if v>1e-6},'total_MW':float(gb.sum())}
  if args.h2_uc and 'electrolyzer_startup' in n.model.variables:
   ow=(n.snapshot_weightings.objective.to_numpy()/n._hrs);su_total={}
   terms['h2_startup_million_JPY']=0.
   for k,csu in [('electrolyzer',args.el_startup_cost),('fuelcell',args.fc_startup_cost)]:
    s=n.model[k+'_startup'].solution.to_numpy();mw=1. if k=='electrolyzer' else 1/(args.fc_kg_per_mwh*(1e-3 if args.unit_scaling else 1.))
    terms['h2_startup_million_JPY']+=float((s*ow).sum())*csu*mw/1e6
    su_total[k+'_started_MW_total']=float(s.sum()*mw)
    committed=n.model[k+'_committed'].solution.to_numpy()*mw;su_total[k+'_mean_committed_MW']=float(committed.mean())
    if k+'_standby' in n.model.variables:su_total[k+'_mean_standby_MW']=float(n.model[k+'_standby'].solution.to_numpy().mean()*mw)
   if 'el_eff_aux' in n.links.index:
    # Report the formula value; the LP may over-fill the slack in hours with worthless surplus.
    pe=n.links_t.p0['electrolyzer'].to_numpy();Cv=n._el_cap_expr.solution.to_numpy()
    uv=n.model['electrolyzer_committed'].solution.to_numpy() if args.h2_uc else 0*pe
    ex=args.el_noload*uv
    for piece in [x for x in (args.el_curve or '').split(',') if x]:
     bj,sj=(float(v) for v in piece.split(':'));ex=np.maximum(ex,args.el_noload*uv+sj*(pe-bj*Cv))
    su_total['el_extra_energy_GWh_total']=float(ex.sum()/1000);su_total['el_extra_share_of_input']=float(ex.sum()/max(pe.sum(),1e-9))
    su_total['el_eff_aux_slack_GWh']=float(n.links_t.p0['el_eff_aux'].sum()/1000-ex.sum()/1000)
   if 'h2_aux_power' in n.links.index:su_total['aux_energy_GWh_total']=float(n.links_t.p0['h2_aux_power'].sum()/1000)
   stats['h2_uc']=su_total
  if args.ev_v2g_efc_cap is not None:
   shadow={}
   for name in n.model.constraints:
    if '_v2g_cap_' in name:
     y=int(name.rsplit('_',1)[1]);disc=1. if STATIC else 1.03**(-(y-2024)) if y!=YEND else W2050()
     shadow[name]=abs(float(n.model.constraints[name].dual))*1000/disc  # JPY per battery-side kWh
   stats['v2g_cap_shadow_JPY_per_kWh']=shadow
  stats['objective_ledger']=terms;stats['objective_ledger_residual_million_JPY']=sum(terms.values())-stats['objective_million_JPY']
  residuals={}
  for store in n.stores.index:
   e=n.stores_t.e[store];prev=e.shift(1);prev.iloc[0]=n.stores.at[store,'e_initial']
   residual=e-prev*(1-n.stores.at[store,'standing_loss'])+n.stores_t.p[store]
   residual.iloc[0]=e.iloc[0]-n.stores.at[store,'e_initial']+n.stores_t.p[store].iloc[0]
   residuals[store]=float(residual.abs().max())
  stats['store_balance_residual_by_native_unit']=residuals
  tol_bal=1e-5 if args.gurobi_crossover!=0 else 1e-3;tol_led=max(.01,1e-6*abs(stats['objective_million_JPY']))
  stats['check_tolerances']={'balance_MW':tol_bal,'ledger_million_JPY':tol_led}
  stats['check_passed']=bool(stats['max_electricity_balance_residual_MW']<=tol_bal and abs(stats['objective_ledger_residual_million_JPY'])<=tol_led and stats['termination_condition']=='optimal')
  (args.output/'summary.json').write_text(json.dumps(stats,indent=2,default=str),encoding='utf-8')
  if not stats['check_passed']:raise RuntimeError('Independent conservation/accounting check failed (summary.json written)')
  n.generators_t.p.to_parquet(args.output/'generator_dispatch.parquet');n.stores_t.e.to_parquet(args.output/'store_inventory.parquet')
  n.links_t.p0.to_parquet(args.output/'link_input.parquet')
  hourly=pd.DataFrame({'import':n.generators_t.p['import'],'export':n.generators_t.p['export'],'load':n.loads_t.p_set.loc[:,n.loads.bus=='electricity'].sum(axis=1)})
  hourly.to_parquet(args.output/'electricity_exchange.parquet')
 (args.output/'summary.json').write_text(json.dumps(stats,indent=2,default=str),encoding='utf-8');print(json.dumps(stats,indent=2,default=str),flush=True)

if __name__=='__main__':main()
