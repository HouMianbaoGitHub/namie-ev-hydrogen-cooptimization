"""First-build timing of hydrogen (S2 only): F3 (= registry-v1 D2 args, default_D2_args.txt) with one factor changed per case.
Reference: reg1 d2__S2 (electrolyzer first built 2040). Two case sets:
  remove  (energies4608521_timing_20261028): the factor removed - extreme bounds, internal reference only
  graded  (energies4608521_timing2_20261028): the factor moved about halfway towards its ideal value - sensitivity
  flat    (energies4608521_timing4_20261029): cost level vs waiting value - H2 capex flat at one year's F3 level, or F3 then frozen
  annuity (energies4608521_annuity_20261029): F3 with hydrogen investment as finite-life annuities (--h2-annuity), S2 and CH
  effpath (energies4608521_effpath_20261029, C:): F3 with electrolysis/fuel-cell efficiency paths by operating year, S2 and CH
  f5      (energies4608521_f5_20261030, C:): default F5 (all-annuity, truncated 2050) and truncated 2060, nine scenarios each
  f4      (energies4608521_f4_20261029, C:): default F4 (default_D2_args.txt), AH and BH
  h2tech  (energies4608521_h2tech_20261029, C:): efficiency-path base + newest DEA SEC / PEM set / stricter AEL, S2 and CH
  sensf5  (energies4608521_sensF5_20261030, C:): F5 sensitivity, first batch (registry sensitivity_F5_20261030); scenarios per group
          from SENS_SCEN (hydrogen-only S2/CH, EV-only C0/CH, system-wide S1/S2/C0/CH)
  f6      (energies4608521_f6_20261030, C:): default F6 (F5 + electrolyzer start-up wear, hot standby, 15-yr stack; no fuel-cell UC),
          truncated 2050 and 2060, nine scenarios each (registry default_F6)
  sensf6  (energies4608521_sensF6_20261030, C:): F6 sensitivity (registry sensitivity_F6_20261030); only runs with hydrogen,
          S1/C0 of each group are unchanged from sensf5 (F6 changes hydrogen parameters only)
  a0f6    (energies4608521_a0F6_20261107, C:): A0 for evcap080, chg6 and joint090, plus the base A0 as a reproduction check
          (registry sensitivity_a0_F6_20261107)
  allann  (energies4608521_allann_20261029, C: drive): F3 with every new asset as annuities (--all-annuity), perpetuity vs
          truncated at 2050 (--no-perpetuity) and at 2060 (+ --extend-to 2060); S1, S2, C0, CH (R1.3 terminal-value comparison, registry all_annuity_method)
Usage: python make_timing_batch.py remove|graded -> run_<tag>.ps1, launch_<tag>.ps1"""
import sys
from pathlib import Path

BS = chr(92)
SET = sys.argv[1] if __name__ == '__main__' else 'graded'   # imported (make_aoba_batch.py): case definitions only
TAG = {'remove': 'energies4608521_timing_20261028', 'graded': 'energies4608521_timing2_20261028', 'more': 'timing3_20261029',
       'flat': 'energies4608521_timing4_20261029', 'annuity': 'energies4608521_annuity_20261029', 'allann': 'energies4608521_allann_20261029', 'effpath': 'energies4608521_effpath_20261029', 'h2tech': 'energies4608521_h2tech_20261029', 'f4': 'energies4608521_f4_20261029', 'f5': 'energies4608521_f5_20261030', 'sensf5': 'energies4608521_sensF5_20261030', 'f6test': 'energies4608521_f6test_20261030', 'f6': 'energies4608521_f6_20261030', 'sensf6': 'energies4608521_sensF6_20261030', 'revf6': 'energies4608521_revF6_20261101', 'a0f6': 'energies4608521_a0F6_20261107'}[SET]
RUN = {'remove': 'timing', 'graded': 'timing2', 'more': 'timing3', 'flat': 'timing4', 'annuity': 'annuity', 'allann': 'allann', 'effpath': 'effpath', 'h2tech': 'h2tech', 'f4': 'f4', 'f5': 'f5', 'sensf5': 'sensF5', 'f6test': 'f6test', 'f6': 'f6', 'sensf6': 'sensF6', 'revf6': 'revF6', 'a0f6': 'a0F6'}[SET]
ROOT = ('C:' if SET in ('allann', 'effpath', 'h2tech', 'f4', 'f5', 'sensf5', 'f6test', 'f6', 'sensf6', 'revf6', 'a0f6') else 'D:') + BS + 'CodexRuns' + BS + TAG   # bigmem D: is an HDD; new batches on C:
SRC = 'D:' + BS + 'CodexRuns' + BS + 'namie_ev_controls_20261017' + BS + 'src'
PY = 'C:' + BS + 'Python314' + BS + 'python.exe'
INP = 'inputs/'
F3 = Path('default_D2_args_F3_20261029.txt').read_text().replace('{INP}', INP).split()
F4 = Path('default_D2_args_F4_20261030.txt').read_text().replace('{INP}', INP).split()   # default 2026-10-29 (registry default_F4)
F5 = Path('default_D2_args_F5_20261030.txt').read_text().replace('{INP}', INP).split()   # registry default_F5
F6 = Path('default_D2_args.txt').read_text().replace('{INP}', INP).split()   # default from 2026-10-30 (registry default_F6)
DESIGN = {'S0': ['--scenario', 'S0'], 'S1': ['--scenario', 'S1'], 'S2': ['--scenario', 'S2'],
          'A0': ['--scenario', 'S3', '--ev-control', 'fixed'], 'AH': ['--scenario', 'S4', '--ev-control', 'fixed'],
          'B0': ['--scenario', 'S3', '--ev-control', 'charge_only'], 'BH': ['--scenario', 'S4', '--ev-control', 'charge_only'],
          'C0': ['--scenario', 'S3', '--ev-control', 'bidirectional'], 'CH': ['--scenario', 'S4', '--ev-control', 'bidirectional']}   # = make_reg1_batch.py


def setarg(args, key, value=None, drop=False):
    """Return args with `key` replaced (value), removed (drop=True) or appended."""
    a = [x for x in args if not x.startswith(key + '=')]
    if key in a:
        i = a.index(key)
        flag = i + 1 >= len(a) or a[i + 1].startswith('--')
        del a[i:i + (1 if flag else 2)]
    if not drop:
        a += [key] if value is None else [key, value]
    return a


def geo(v30, v50, v25):
    """Yearly points: 2025 value kept, constant-rate decline 2030 -> 2050 (no kink at 2040)."""
    return ','.join([f'2025:{v25}'] + [f'{y}:{v30 * (v50 / v30) ** ((y - 2030) / 20):.4g}' for y in range(2030, 2051)])


REMOVE = {
    # cost side
    'flat2035': [('--capex-electrolyzer', '2025:25263.2,2050:25263.2'), ('--capex-fuelcell', '2025:131.5,2050:131.5'),
                 ('--capex-tank', '2025:79500,2050:79500')],                        # 2035 cost level in every year: no waiting value
    'fcdecline': [('--capex-fuelcell', '2025:180,2030:150,2040:113,2050:85')],        # fuel cell keeps falling after 2040
    'smooth': [('--capex-electrolyzer', geo(28558.4, 16476, 65904)), ('--capex-fuelcell', geo(150, 113, 180)),
               ('--capex-tank', geo(96000, 54000, 112000))],                        # constant-rate decline 2030-2050
    'nofom': [('--h2-fom', 'electrolyzer:0,fuelcell:0,tank:0'), ('--h2-stack-repl', 'electrolyzer:0:40,fuelcell:0:10')],
    # operation side
    'nouc': [('--h2-uc', None, True), ('--el-min-load', '0'), ('--fc-min-load', '0'), ('--h2-startup-hours', '0')],
    'nodeg': [('--el-degradation', '0'), ('--fc-degradation', '0')],
    'nopartload': [('--el-curve', None, True), ('--el-noload', '0')],
    'avail1': [('--el-availability', '1'), ('--fc-availability', '1')],
    'idealops': [('--h2-uc', None, True), ('--el-min-load', '0'), ('--fc-min-load', '0'), ('--h2-startup-hours', '0'),
                 ('--el-degradation', '0'), ('--fc-degradation', '0'), ('--el-curve', None, True), ('--el-noload', '0'),
                 ('--el-availability', '1'), ('--fc-availability', '1')],
    # revenue side
    'wind125': [('--wind-scale', '1.25')],
}
H2 = {'electrolyzer': {2025: 65904, 2030: 28558.4, 2040: 21968, 2050: 16476}, 'fuelcell': {2025: 180, 2030: 150, 2040: 113, 2050: 113},
      'tank': {2025: 112000, 2030: 96000, 2040: 63000, 2050: 54000}}     # F3 capex points (default_D2_args.txt)
scaled = lambda k, f: ','.join(f'{y}:{v * f:.6g}' for y, v in H2[k].items())
GRADED = {   # each factor both directions; "favourable" = towards earlier hydrogen build
    # cost side
    'fc2050_105': [('--capex-fuelcell', '2025:180,2030:150,2040:113,2050:105')],      # fuel cell still falls a little after 2040
    'fc2050_95': [('--capex-fuelcell', '2025:180,2030:150,2040:113,2050:95')],
    'capex080': [(f'--capex-{k}', scaled(k, 0.8)) for k in H2],                      # all hydrogen capex
    'capex090': [(f'--capex-{k}', scaled(k, 0.9)) for k in H2],
    'capex110': [(f'--capex-{k}', scaled(k, 1.1)) for k in H2],
    'capex120': [(f'--capex-{k}', scaled(k, 1.2)) for k in H2],
    'fom050': [('--h2-fom', 'electrolyzer:0.01,fuelcell:0.015,tank:0.0025')],          # FO&M
    'fom150': [('--h2-fom', 'electrolyzer:0.03,fuelcell:0.045,tank:0.0075')],
    'stack050': [('--h2-stack-repl', 'electrolyzer:0.055:40,fuelcell:0.10:10')],       # stack replacement share
    'stack150': [('--h2-stack-repl', 'electrolyzer:0.165:40,fuelcell:0.30:10')],
    'smooth': REMOVE['smooth'],                                                         # alternative interpolation, not a removal
    # operation side
    'minload010': [('--el-min-load', '0.1'), ('--fc-min-load', '0.1')],
    'minload030': [('--el-min-load', '0.3'), ('--fc-min-load', '0.3')],
    'deg050': [('--el-degradation', '0.0012'), ('--fc-degradation', '0.003')],
    'deg150': [('--el-degradation', '0.0036'), ('--fc-degradation', '0.009')],
    'avail_hi': [('--el-availability', '0.985'), ('--fc-availability', '0.975')],
    'avail_lo': [('--el-availability', '0.94'), ('--fc-availability', '0.90')],
    'partload050': [('--el-curve', '0.35:0.05285,0.5185:0.1019'), ('--el-noload', '0.01')],
    'partload150': [('--el-curve', '0.35:0.15855,0.5185:0.3057'), ('--el-noload', '0.03')],
    # revenue side
    'price090': [('--price-scale', '0.9')],                                             # Tohoku price level (all hours)
    'price110': [('--price-scale', '1.1')],
    'wind090': [('--wind-scale', '0.9')],                                               # wind x0.75 already in reg1
    'market100': [('--market-limit-mw', '100')],                                        # Namie interface (F3 118 MW)
    'market140': [('--market-limit-mw', '140')],
}
MORE = {    # factors not covered by GRADED (run on workstation-2, make_gpu_batch.py); efficiency +-10 %, single-component capex x0.8
    'elsec090': [('--h2-electrolysis-mwh-per-kg', '0.044208')],                        # electrolysis electricity per kg (F3 0.04912)
    'elsec110': [('--h2-electrolysis-mwh-per-kg', '0.054032')],
    'fckg090': [('--fc-kg-per-mwh', '54.54')],                                          # fuel-cell hydrogen per MWh (F3 60.6)
    'fckg110': [('--fc-kg-per-mwh', '66.66')],
    'rt_hi': [('--h2-electrolysis-mwh-per-kg', '0.044208'), ('--fc-kg-per-mwh', '54.54')],   # round trip both better
    'rt_lo': [('--h2-electrolysis-mwh-per-kg', '0.054032'), ('--fc-kg-per-mwh', '66.66')],   # round trip both worse
    'capex_el080': [('--capex-electrolyzer', scaled('electrolyzer', 0.8))],            # which component holds back the first build
    'capex_fc080': [('--capex-fuelcell', scaled('fuelcell', 0.8))],
    'capex_tank080': [('--capex-tank', scaled('tank', 0.8))],
    'curt050': [('--series-curtail-scale', '0.5')],                                     # regional curtailment applied to Namie exports
    'curt150': [('--series-curtail-scale', '1.5')],
    'trunc': [('--no-perpetuity', None)],                                               # truncated annuities instead of perpetuity
    'leak005': [('--h2-standing-loss-per-day', '0.0005')],                              # tank loss 0.05 %/day (F3 0)
    'leak010': [('--h2-standing-loss-per-day', '0.001')],
    'start0': [('--h2-startup-hours', '0')],                                            # electrolyzer cold start without output (F3 1 h)
    'start2': [('--h2-startup-hours', '2')],
}
# F3 capex at 2030/2035/2040/2045/2050 (linear between anchors): electrolyzer, fuel cell, tank
LEVEL = {2030: (28558.4, 150, 96000), 2035: (25263.2, 131.5, 79500), 2040: (21968, 113, 63000), 2045: (19222, 113, 58500),
         2050: (16476, 113, 54000)}
F3PATH = {'el': [(2025, 65904), (2030, 28558.4)], 'fc': [(2025, 180), (2030, 150)], 'tank': [(2025, 112000), (2030, 96000)]}


def flat(y):
    el, fc, tk = LEVEL[y]
    return [('--capex-electrolyzer', f'2025:{el},2050:{el}'), ('--capex-fuelcell', f'2025:{fc},2050:{fc}'), ('--capex-tank', f'2025:{tk},2050:{tk}')]


def freeze(y):
    pts = lambda k, v: ','.join(f'{a}:{b}' for a, b in F3PATH[k] + ([(2040, LEVEL[2040][('el', 'fc', 'tank').index(k)])] if y > 2040 else [])
                                + [(y, v), (2050, v)])
    el, fc, tk = LEVEL[y]
    return [('--capex-electrolyzer', pts('el', el)), ('--capex-fuelcell', pts('fc', fc)), ('--capex-tank', pts('tank', tk))]


FLAT = {'flat2030': flat(2030), 'flat2040': flat(2040), 'flat2045': flat(2045), 'flat2050': flat(2050),
        'freeze2035': freeze(2035), 'freeze2040': freeze(2040)}             # flat2035 is in REMOVE (timing_20261028)
ANNUITY = {'f3ann': [('--h2-annuity', None)]}
EFFPATH = {'effpath': [('--el-sec-path', '2025:54.92,2030:52.6,2040:50.6,2050:48.0'), ('--fc-kg-path', '2025:60.6,2030:57.7,2040:54.6,2050:53.6')]}   # registry h2_efficiency_path (S1/C0 unchanged: no hydrogen)
_EP = EFFPATH['effpath']
H2TECH = {   # registry h2_tech_sensitivity_20261029: on top of the efficiency-path base (later entries override earlier ones)
    'deav15': _EP + [('--el-sec-path', '2025:59,2030:57,2040:56,2050:54')],
    'pem': _EP + [('--el-sec-path', '2025:57.4,2030:53.6,2040:50.6,2050:47.5'), ('--capex-electrolyzer', '2025:143550,2030:37323,2040:28710,2050:21532'),
                  ('--el-min-load', '0.1'), ('--h2-startup-hours', '0'), ('--h2-stack-repl', 'electrolyzer:0.15:32,fuelcell:0.20:10'),
                  ('--el-degradation', '0.003'), ('--el-stack-life', '32')],
    'aelstrict': _EP + [('--el-min-load', '0.3'), ('--el-startup-cost', '8944')]}
ALLANN = {'aperp': [('--all-annuity', None)], 'atrunc': [('--all-annuity', None), ('--no-perpetuity', None)],
          'atrunc60': [('--all-annuity', None), ('--no-perpetuity', None), ('--extend-to', '2060')]}
H2_ = ('S2', 'CH'); EV_ = ('C0', 'CH'); SYS_ = ('S1', 'S2', 'C0', 'CH')
SENSF5 = {   # registry sensitivity_F5_20261030 (revision_round1/02_plan/F5_敏感性清单.md): name -> (changes, scenarios)
    'coh4_t05': ([('--ev-cohorts', '4'), ('--ev-cohort-theta', '0.5')], EV_),
    'coh4_t10': ([('--ev-cohorts', '4'), ('--ev-cohort-theta', '1')], EV_),   # theta 1 infeasible (known, ev_cohort_test)
    'coh3_t05': ([('--ev-cohorts', '3'), ('--ev-cohort-theta', '0.5')], EV_),   # registry ev_cohort_test K = 3
    'coh3_t075': ([('--ev-cohorts', '3'), ('--ev-cohort-theta', '0.75')], EV_),
    'v2g6': ([('--v2g-cost-jpy-per-kwh', '6')], EV_), 'v2g10': ([('--v2g-cost-jpy-per-kwh', '10')], EV_),
    'evcap080': ([('--ev-capacity-scale', '0.8'), ('--fixed-charge-profile', 'inputs/fixed_fleet_charging_newbase_soh08.parquet')], EV_),   # fixed profile rebuilt with the same EV parameters (ev.yaml)
    'minload030': ([('--el-min-load', '0.3'), ('--fc-min-load', '0.3')], H2_),
    'startcost': ([('--el-startup-cost', '8944')], H2_),
    'pem': ([c for c in H2TECH['pem'] if c[0] != '--fc-kg-path' and c not in _EP], H2_),
    'joint090': ([('--renewable-scale', '0.9'), ('--ev-availability-scale', '0.9'), ('--price-scale', '0.9'), ('--fixed-charge-profile', 'inputs/fixed_fleet_charging_newbase_av09.parquet')], SYS_),
    'leak01': ([('--h2-standing-loss-per-day', '0.001')], H2_), 'leak10': ([('--h2-standing-loss-per-day', '0.01')], H2_),
    'avail090': ([('--el-availability', '0.9'), ('--fc-availability', '0.9')], H2_),
    'eff_hi': ([('--el-sec-path', '2025:54.92,2030:52.6,2040:50.6,2050:48.0')], H2_),
    'eff_lo': ([('--el-sec-path', '2025:59,2050:59'), ('--fc-kg-path', '2025:60.6,2050:60.6')], H2_),
    'part025': ([('--ev-participation', '0.25')], EV_), 'part075': ([('--ev-participation', '0.75')], EV_),
    'part100': ([('--ev-participation', '1')], EV_),
    'mkt100': ([('--market-limit-mw', '100')], SYS_), 'mkt150': ([('--market-limit-mw', '150')], SYS_),
    'chg6': ([('--ev-charger-kw', '6'), ('--fixed-charge-profile', 'inputs/fixed_fleet_charging_newbase_chg6.parquet')], EV_),
    'capex070': ([(f'--capex-{k}', scaled(k, 0.7)) for k in H2], H2_), 'capex130': ([(f'--capex-{k}', scaled(k, 1.3)) for k in H2], H2_),
    'price090': ([('--price-scale', '0.9')], SYS_), 'price110': ([('--price-scale', '1.1')], SYS_),
    'wind075': ([('--wind-scale', '0.75')], SYS_),
    'netcharge': ([('--import-adder-jpy-per-kwh', '2'), ('--export-deduction-jpy-per-kwh', '1')], SYS_),
    'aperp': ([('--no-perpetuity', None, True)], SYS_),
    # registry sensitivity_F5_load_tank_20261030 (second launch, run_sensF5c.ps1)
    'load090': ([('--load-scale', '0.9')], SYS_), 'load110': ([('--load-scale', '1.1')], SYS_),
    'tank043': ([('--tank-max-t', '43')], H2_)}
F6TEST = {'F6c': [('--el-startup-cost', '1118'), ('--el-standby-power', '0.0224'), ('--h2-stack-repl', 'electrolyzer:0.11:15,fuelcell:0.20:10'),
                  ('--el-stack-life', '15'), ('--fc-min-load', '0')]}   # registry f6_candidate_20261030 (S2, AH, CH)
SENSF6 = {k: (c, ('CH',) if s == EV_ else ('S2', 'CH')) for k, (c, s) in SENSF5.items() if k != 'coh4_t10'}   # registry sensitivity_F6_20261030
SENSF6['minload030'] = ([('--el-min-load', '0.3')], H2_)   # no fuel-cell UC in F6
SENSF6['pem'] = ([c for c in SENSF5['pem'][0] if c[0] not in ('--h2-stack-repl', '--el-stack-life')]
                 + [('--h2-stack-repl', 'electrolyzer:0.15:15,fuelcell:0.20:10'), ('--el-stack-life', '15'), ('--el-startup-cost', '0')], H2_)   # calendar cap 15 yr; PEM no cold-start wear
SENSF6['stack10'] = ([('--h2-stack-repl', 'electrolyzer:0.11:10,fuelcell:0.20:10'), ('--el-stack-life', '10')], H2_)
SENSF6['stack40'] = ([('--h2-stack-repl', 'electrolyzer:0.11:40,fuelcell:0.20:10'), ('--el-stack-life', '40')], H2_)   # F5 value
SENSF6['startenergy'] = ([('--el-startup-energy', '0.168')], H2_)   # 0.15 MWh/MW rated x 1.118, engineering estimate
MID = {'electrolyzer': '2025:164760,2030:129062,2040:104348,2050:82380',   # registry base 300/235/190/150 kJPY/kW x 549.2 kW/block
       'fuelcell': '2025:350,2030:250,2040:190,2050:150', 'tank': '2025:150000,2030:135000,2040:100000,2050:80000'}   # registry base
REVF6 = {   # registry sensitivity_review_F6_20261101 (mock review 2026-11-01: B1 hydrogen cost break-even, B2 price shape)
    'capex110': ([(f'--capex-{k}', scaled(k, 1.1)) for k in H2], ('S2', 'CH')),
    'capex120': ([(f'--capex-{k}', scaled(k, 1.2)) for k in H2], ('S2', 'CH')),
    'fom4': ([('--h2-fom', 'electrolyzer:0.04,fuelcell:0.04,tank:0.005')], ('S2', 'CH')),   # registry verified_excl_stack
    'capexmid': ([(f'--capex-{k}', v) for k, v in MID.items()] + [('--h2-fom', 'electrolyzer:0.04,fuelcell:0.05,tank:0.01')], ('S2', 'CH')),
    'spread070': ([('--price-series', INP + 'tohoku_price_plan_ref2024_spread070.parquet')], ('S1', 'S2', 'A0', 'AH', 'C0', 'CH')),   # make_price_variants.py
    'curt2x': ([('--series-curtail-scale', '2')], ('S1', 'S2', 'A0', 'AH', 'C0', 'CH'))}
CASES = {'remove': REMOVE, 'graded': GRADED, 'more': MORE, 'flat': FLAT, 'annuity': ANNUITY, 'allann': ALLANN, 'effpath': EFFPATH, 'h2tech': H2TECH, 'f4': {'F4': []}, 'f5': {'F5': [], 'F5t2060': [('--extend-to', '2060')]}, 'sensf5': {k: v[0] for k, v in SENSF5.items()}, 'f6test': F6TEST, 'f6': {'F6': [], 'F6t2060': [('--extend-to', '2060')]}, 'sensf6': {k: v[0] for k, v in SENSF6.items()}, 'revf6': {k: v[0] for k, v in REVF6.items()}, 'a0f6': {'F6check': [], **{k: SENSF6[k][0] for k in ('evcap080', 'chg6', 'joint090')}}}[SET]
jobs = []
for name, changes in CASES.items():
    a = {'f4': F4, 'f5': F5, 'sensf5': F5, 'f6test': F5, 'f6': F6, 'sensf6': F6, 'revf6': F6, 'a0f6': F6}.get(SET, F3)
    for c in changes:
        a = setarg(a, c[0], c[1], drop=len(c) > 2 and c[2])
    if SET == 'f6test':
        jobs += [(f'{name}__{x}', DESIGN[x] + a) for x in ('S2', 'AH', 'CH')]
        continue
    if SET == 'sensf5':
        jobs += [(f'{name}__{s}', DESIGN[s] + a) for s in SENSF5[name][1]]
        continue
    if SET == 'sensf6':
        jobs += [(f'{name}__{s}', DESIGN[s] + a) for s in SENSF6[name][1]]
        continue
    if SET == 'revf6':
        jobs += [(f'{name}__{s}', DESIGN[s] + a) for s in REVF6[name][1]]
        continue
    if SET == 'a0f6':   # registry sensitivity_a0_F6_20261107: A0 of the groups that rebuild the profile; F6check must return the base A0
        jobs.append((f'{name}__A0', DESIGN['A0'] + a))
        continue
    if SET in ('f5', 'f6'):   # all nine scenarios (truncation changes the 2050 weight, so S0 too)
        jobs += [(f'{name}__{s}', DESIGN[s] + a) for s in DESIGN]
        continue
    if SET == 'f4':   # F4 base: only scenarios with hydrogen differ from F3; S2/CH = h2tech deav15
        jobs += [(f'{name}__AH', ['--scenario', 'S4', '--ev-control', 'fixed'] + a), (f'{name}__BH', ['--scenario', 'S4', '--ev-control', 'charge_only'] + a)]
        continue
    if SET == 'allann':
        jobs += [(f'{name}__S1', ['--scenario', 'S1'] + a), (f'{name}__S2', ['--scenario', 'S2'] + a),
                 (f'{name}__C0', ['--scenario', 'S3', '--ev-control', 'bidirectional'] + a), (f'{name}__CH', ['--scenario', 'S4', '--ev-control', 'bidirectional'] + a)]
        continue
    jobs.append((f'{name}__S2', ['--scenario', 'S2'] + a))
    if SET in ('annuity', 'effpath', 'h2tech'):
        jobs.append((f'{name}__CH', ['--scenario', 'S4', '--ev-control', 'bidirectional'] + a))
if __name__ == '__main__':
    SOLVER = ['--solver', 'gurobi', '--threads', '5', '--time-limit', '36000', '--gurobi-numeric-focus', '1', '--gurobi-bar-homogeneous', '1']
    q = lambda xs: ','.join("'" + x + "'" for x in xs)
    L = [f"$root = '{ROOT}'", f"$model = '{SRC}{BS}model_current.py'", f"$py = '{PY}'", "New-Item -ItemType Directory -Force -Path $root | Out-Null",
         "$tmp = Join-Path $root 'tmp'; New-Item -ItemType Directory -Force -Path $tmp | Out-Null", "$env:TEMP = $tmp; $env:TMP = $tmp",
         f"$solver = @({q(SOLVER)})", "$jobs = @()"]
    for n, a in jobs:
        L.append(f"$jobs += ,@('{n}',@({q(a)}))")
    L += ["function Busy { @(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*energies4608521_*' }).Count }",
          "function FreeGB { (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB }",
          "foreach ($j in $jobs) {",
          "  $out = Join-Path $root $j[0]; if (Test-Path $out) { continue }",
          "  while ((Busy) -ge 22 -or (FreeGB) -lt 60) { Start-Sleep -Seconds 120 }",
          "  New-Item -ItemType Directory -Force -Path $out | Out-Null",
          "  $args = @($model) + $j[1] + $solver + @('--output',$out)",
          "  Start-Process -FilePath $py -ArgumentList $args -WorkingDirectory (Split-Path $model) -WindowStyle Hidden -RedirectStandardOutput (Join-Path $out 'console.txt') -RedirectStandardError (Join-Path $out 'console_stderr.txt') | Out-Null",
          "  Add-Content (Join-Path $root 'launch_log.txt') \"$(Get-Date -Format s) started $($j[0]) free=$([int](FreeGB))GB\"", "  Start-Sleep -Seconds 60", "}",
          f"while (@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object {{ $_.CommandLine -like '*{TAG}*' }}).Count -gt 0) {{ Start-Sleep -Seconds 60 }}",
          "'all done' | Set-Content (Join-Path $root 'DONE.txt')"]
    Path(f'run_{RUN}.ps1').write_text('\n'.join(L) + '\n', encoding='utf-8')
    launch = [f"New-Item -ItemType Directory -Force -Path '{ROOT}' | Out-Null",
              f"$cmd = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File {ROOT}{BS}run_{RUN}.ps1'",
              f"$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{{CommandLine=$cmd; CurrentDirectory='{ROOT}'}}",
              '"launched ReturnValue=$($r.ReturnValue) PID=$($r.ProcessId)"']
    Path(f'launch_{RUN}.ps1').write_text('\n'.join(launch) + '\n', encoding='utf-8')


    def kv(args):
        """{--key: value or True}; '--key=value' tokens split."""
        out, i = {}, 0
        while i < len(args):
            k, _, v = args[i].partition('=')
            if v:
                out[k] = v; i += 1
            elif i + 1 < len(args) and not args[i + 1].startswith('--'):
                out[k] = args[i + 1]; i += 2
            else:
                out[k] = True; i += 1
        return out


    base = kv(F6 if SET in ('f6', 'sensf6', 'revf6', 'a0f6') else F5 if SET in ('f5', 'sensf5', 'f6test') else F3)
    for n, a in jobs:
        new = kv(a[2:])
        ch = {k: v for k, v in new.items() if base.get(k) != v}
        print(f'{n:15s} changed: {" ".join(f"{k} {v}"[:60] for k, v in ch.items())}  removed: {" ".join(k for k in base if k not in new)}')
    print(len(jobs), 'jobs')
