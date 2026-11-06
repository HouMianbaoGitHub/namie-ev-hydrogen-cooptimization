"""Pre-run check: registry (params/*.yaml) vs effective model values (src/model.py + src/default_D2_args.txt + inputs/).
Run before every batch; launch only if it prints ALL PASS. Writes params/check_reports/check_<timestamp>.md.
Usage: python check_all.py [--remote]   (--remote also compares model/args/inputs MD5 with workstation-1)"""
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

HERE = Path(__file__).parent
ROOT = HERE.parent
SCR = HERE / 'mapping' / 'scripts'
ENV = dict(os.environ, PYTHONIOENCODING='utf-8')
REMOTE_SRC = 'D:/CodexRuns/namie_ev_controls_20261017'
INPUTS = ['profiles.parquet', 'fixed_fleet_charging_newbase.parquet', 'tohoku_price_plan_ref2024.parquet', 'namie_renewables_ninja_2024.parquet',
          'hydro_monthly.parquet', 'h2_buildcost_original_plexos.csv'] + [f'S{i}_{k}.json' for i in range(5) for k in ('annuity', 'parameters')]
results = []   # (check, ok, detail)


def run(script):
    p = subprocess.run([sys.executable, str(script)], cwd=script.parent, env=ENV, capture_output=True, text=True, encoding='utf-8')
    return p.returncode, p.stdout + p.stderr


def add(name, ok, detail=''):
    results.append((name, bool(ok), detail))


# 1. registry is valid and REGISTRY.md regenerates
code, out = run(HERE / 'build_registry_md.py')
add('registry: YAML valid, ids unique, REGISTRY.md regenerated', code == 0, out.strip().splitlines()[-1] if out.strip() else '')

# 2. hydrogen unit costs (capex + FO&M + stack replacement) year by year
code, out = run(HERE / 'check_h2_costs.py')
add('h2: unit cost per year = registry (check_h2_costs.py)', code == 0 and 'all match' in out, '' if 'all match' in out else out[-500:])

# 3. hydrogen mapping (all h2.yaml entries that the script evaluates)
accepted = {e['id']: e['reason'] for e in yaml.safe_load((HERE / 'accepted_exceptions.yaml').read_text(encoding='utf-8')) or []}
code, out = run(SCR / 'h2' / 'check_h2_map.py')
h = json.loads((SCR / 'h2' / 'h2_map_results.json').read_text(encoding='utf-8'))
for k, v in h.items():
    if isinstance(v, dict) and 'ok' in v:
        ok = str(v['ok']) == 'True'
        add(f'h2: {k}', ok or k in accepted, '' if ok else (f'accepted: {accepted[k]}' if k in accepted else f"effective {v.get('effective')} vs expected {v.get('expected')}"))
add('h2: check_h2_map.py ran', code == 0, out[-300:] if code else '')

# 4. EV mapping (31 checks)
code, out = run(SCR / 'ev' / 'check_ev_map.py')
m = re.search(r'(\d+)/(\d+) checks passed', out)
add('ev: check_ev_map.py all checks passed', code == 0 and m and m.group(1) == m.group(2), m.group(0) if m else out[-500:])
for line in out.splitlines():
    if line.startswith('FAIL'):
        add(f'ev: {line[5:]}', False)

# 5. grid / market / economics: effective values vs registry
code, out = run(SCR / 'grid_econ' / 'compute_grid_econ.py')
add('grid: compute_grid_econ.py ran', code == 0, out[-300:] if code else '')
g = json.loads((SCR / 'grid_econ' / 'effective_values.json').read_text(encoding='utf-8'))
reg = {r['id']: r for r in yaml.safe_load((HERE / 'grid_econ.yaml').read_text(encoding='utf-8'))}
add('grid: truncated at 2050 (default_F5), W2050 = 1.03^-26 (one year)', g['PERP'] is False and abs(g['W2050'] - 1.03 ** -26) < 1e-4, f"W2050={g['W2050']}")
for s in ('S0', 'S1', 'S2', 'S3', 'S4'):
    v = g[f'{s}_interface_and_fleet']
    add(f'grid: {s} interface import/export = registry {reg["grid_interface_mw"]["value"]} MW',
        v['import_p_nom'] == v['export_p_nom'] == float(reg['grid_interface_mw']['value']), f"{v['import_p_nom']}/{v['export_p_nom']}")
add('grid: price series covers every snapshot, no NaN', g['price_missing_snapshots'] == 0 and g['nan_after_mapping'] == 0)
add('grid: price floor 0.01 JPY/kWh', abs(g['price_min_model'] - 0.01) < 1e-9, str(g['price_min_model']))
add('grid: price file identical to price-model output', g['price_file_identical_to_price_model_output'] is True)
add('grid: PV diurnal peak at local midday (JST)', 10 <= int(g['pv_diurnal_peak_hour']) <= 13, f"peak hour {g['pv_diurnal_peak_hour']}")
add('grid: interface reinforcement PV per MW (D2 args) = registry', g['grid_pv_per_MW_2031_D2_args'] == g['grid_pv_per_MW_2031_registry'],
    f"{g['grid_pv_per_MW_2031_D2_args']} vs {g['grid_pv_per_MW_2031_registry']}")
args = (ROOT / 'src' / 'default_D2_args.txt').read_text().split()
add('grid: D2 network fees = registry (0 / 0)', args[args.index('--import-adder-jpy-per-kwh') + 1] == '0' and args[args.index('--export-deduction-jpy-per-kwh') + 1] == '0')

# 6. provenance: what was checked
md5 = lambda p: hashlib.md5(Path(p).read_bytes()).hexdigest()
prov = {'src/model.py': md5(ROOT / 'src' / 'model.py'), 'src/default_D2_args.txt': md5(ROOT / 'src' / 'default_D2_args.txt')}
prov.update({f'inputs/{f}': md5(ROOT / 'inputs' / f) for f in INPUTS})
if '--remote' in sys.argv:
    files = ' '.join(f'inputs/{f}' for f in INPUTS)
    r = subprocess.run(['ssh', 'workstation-1', f'cd {REMOTE_SRC} && md5sum src/model_current.py {files}'], capture_output=True, text=True, timeout=120)
    remote = {ln.split()[1].lstrip('*'): ln.split()[0] for ln in r.stdout.splitlines() if ln.strip()}
    add('remote: model_current.py on bigmem = local model.py', remote.get('src/model_current.py') == prov['src/model.py'], remote.get('src/model_current.py', 'missing'))
    for f in INPUTS:
        add(f'remote: inputs/{f} identical', remote.get(f'inputs/{f}') == prov[f'inputs/{f}'])

# report
n_fail = sum(not ok for _, ok, _ in results)
stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
rep = HERE / 'check_reports' / f'check_{stamp}.md'
rep.parent.mkdir(exist_ok=True)
L = [f'# check_all {stamp}', '', f'**{"ALL PASS" if not n_fail else f"{n_fail} FAIL"}**（{len(results)} 项）', '', '| 检查 | 结果 | 说明 |', '|---|---|---|']
L += [f"| {n} | {'PASS' if ok else 'FAIL'} | {d.replace('|', '/')[:300]} |" for n, ok, d in results]
L += ['', '## 核对对象（MD5）', ''] + [f'- `{k}` {v}' for k, v in prov.items()]
rep.write_text('\n'.join(L) + '\n', encoding='utf-8')
for n, ok, d in results:
    if not ok:
        print('FAIL', n, d[:200])
print(f"{'ALL PASS' if not n_fail else f'{n_fail} FAIL'} ({len(results)} checks); report: {rep}")
sys.exit(1 if n_fail else 0)
