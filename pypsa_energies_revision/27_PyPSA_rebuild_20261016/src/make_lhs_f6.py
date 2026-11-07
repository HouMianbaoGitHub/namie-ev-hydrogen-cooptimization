"""Latin-hypercube joint sampling on the F6 default (registry lhs_F6_20261031; R2.2 / R2.4 / R2.6).

Each sample solves S1, S2, A0, AH, C0, CH, so that hydrogen value (S2−S1, AH−A0, CH−C0), EV flexibility (C0−A0, CH−AH),
the interactions I_S = (CH−C0)−(S2−S1), I_A = (CH−C0)−(AH−A0) and the crowding-out ratios are available per sample.
Ranges follow the one-at-a-time groups of sensitivity_F6_20261030 (02_plan/F5_敏感性清单.md); the samples cover the
ranges with equal weight and are not a probability forecast.
Writes results/lhsF6_20261031/lhs_samples.csv, run_lhsF6.ps1 and launch_lhsF6.ps1 (bigmem, C:, global cap 22).
Usage: python make_lhs_f6.py"""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import qmc

from make_timing_batch import BS, DESIGN, F6, PY, SRC, scaled, setarg

TAG = 'energies4608521_lhsF6_20261031'
ROOT = 'C:' + BS + 'CodexRuns' + BS + TAG
N, SEED = 40, 20261031
EL = {2025: 59, 2030: 57, 2040: 56, 2050: 54}           # F6 --el-sec-path (kWh/kg)
FC = {2025: 60.6, 2030: 57.7, 2040: 54.6, 2050: 53.6}   # F6 --fc-kg-path (kg/MWh)
path = lambda d, f: ','.join(f'{y}:{v * f:.4g}' for y, v in d.items())
PARAMS = {   # name: (low, high, changes(value)); F6 value in the comment
    'price_scale': (0.9, 1.1, lambda v: [('--price-scale', f'{v:.4f}')]),                     # 1; price090/110
    'wind_scale': (0.8, 1.1, lambda v: [('--wind-scale', f'{v:.4f}')]),                       # 1; wind075
    'market_limit_mw': (100, 150, lambda v: [('--market-limit-mw', f'{v:.1f}')]),             # 118; mkt100/150
    'load_scale': (0.9, 1.1, lambda v: [('--load-scale', f'{v:.4f}')]),                       # 1; load090/110
    'h2_capex_scale': (0.7, 1.3, lambda v: [(f'--capex-{k}', scaled(k, v)) for k in ('electrolyzer', 'fuelcell', 'tank')]),   # 1; capex070/130
    'el_sec_scale': (0.89, 1.09, lambda v: [('--el-sec-path', path(EL, v))]),                 # 1; 2050 48–59 kWh/kg = eff_hi/eff_lo
    'fc_kg_scale': (0.95, 1.13, lambda v: [('--fc-kg-path', path(FC, v))]),                   # 1; 2050 51–60.6 kg/MWh (eff_lo 60.6)
    'ev_participation': (0.25, 1.0, lambda v: [('--ev-participation', f'{v:.4f}')]),          # 0.5; part025/075/100
    'v2g_cost': (0.0, 10.0, lambda v: [('--v2g-cost-jpy-per-kwh', f'{v:.3f}')]),              # 3; v2g6/v2g10
}
SCEN = ('S1', 'S2', 'A0', 'AH', 'C0', 'CH')

u = qmc.LatinHypercube(d=len(PARAMS), seed=SEED).random(N)
lo = np.array([p[0] for p in PARAMS.values()]); hi = np.array([p[1] for p in PARAMS.values()])
samples = pd.DataFrame(lo + u * (hi - lo), columns=list(PARAMS), index=[f'L{i + 1:02d}' for i in range(N)]).rename_axis('sample')
jobs = []
for sid, row in samples.iterrows():
    a = list(F6)
    for name, (_, _, ch) in PARAMS.items():
        for k, v in ch(row[name]):
            a = setarg(a, k, v)
    jobs += [(f'{sid}__{s}', DESIGN[s] + a) for s in SCEN]
order = {'AH': 0, 'S2': 1, 'CH': 2, 'C0': 3, 'S1': 4, 'A0': 5}   # longest first so the tail is short
jobs.sort(key=lambda j: (order[j[0].split('__')[1]], j[0]))

if __name__ == '__main__':
    out = Path(__file__).resolve().parents[1] / 'results' / 'lhsF6_20261031'
    out.mkdir(parents=True, exist_ok=True)
    samples.to_csv(out / 'lhs_samples.csv')
    SOLVER = ['--solver', 'gurobi', '--threads', '5', '--time-limit', '36000', '--gurobi-numeric-focus', '1', '--gurobi-bar-homogeneous', '1']
    q = lambda xs: ','.join("'" + x + "'" for x in xs)
    L = [f"$root = '{ROOT}'", f"$model = '{SRC}{BS}model_current.py'", f"$py = '{PY}'", "New-Item -ItemType Directory -Force -Path $root | Out-Null",
         "$tmp = Join-Path $root 'tmp'; New-Item -ItemType Directory -Force -Path $tmp | Out-Null", "$env:TEMP = $tmp; $env:TMP = $tmp",
         f"$solver = @({q(SOLVER)})", "$jobs = @()"]
    L += [f"$jobs += ,@('{n}',@({q(a)}))" for n, a in jobs]
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
    Path('run_lhsF6.ps1').write_text('\n'.join(L) + '\n', encoding='utf-8')
    Path('launch_lhsF6.ps1').write_text('\n'.join([
        f"New-Item -ItemType Directory -Force -Path '{ROOT}' | Out-Null",
        f"$cmd = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File {ROOT}{BS}run_lhsF6.ps1'",
        f"$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{{CommandLine=$cmd; CurrentDirectory='{ROOT}'}}",
        '"launched ReturnValue=$($r.ReturnValue) PID=$($r.ProcessId)"']) + '\n', encoding='utf-8')
    # workstation-2 share (2026-10-31): CH of L21-L40; bigmem gets empty placeholder dirs for these so its queue skips them
    GPU = [(n, a) for n, a in jobs if n.endswith('__CH') and int(n[1:3]) >= 21]
    G_ROOT, G_INP = 'C:' + BS + 'CodexRuns' + BS + 'namie_f6' + BS + TAG, 'C:/CodexRuns/namie_f6/inputs/'
    G = [f"$root = '{G_ROOT}'", f"$model = 'C:{BS}CodexRuns{BS}namie_f6{BS}src{BS}model_current.py'",
         f"$py = 'C:{BS}Users{BS}Zhang{BS}.venvs{BS}tohoku_h2_prod{BS}Scripts{BS}python.exe'", "New-Item -ItemType Directory -Force -Path $root | Out-Null",
         "$tmp = Join-Path $root 'tmp'; New-Item -ItemType Directory -Force -Path $tmp | Out-Null", "$env:TEMP = $tmp; $env:TMP = $tmp",
         f"$solver = @({q(SOLVER)})", "$jobs = @()"]
    G += [f"$jobs += ,@('{n}',@({q([x.replace('inputs/', G_INP) for x in a])}))" for n, a in GPU]
    G += ["function Busy { @(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*lhsF6*' }).Count }",
          "function FreeGB { (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB }",
          "foreach ($j in $jobs) {",
          "  $out = Join-Path $root $j[0]; if (Test-Path $out) { continue }",
          "  while ((Busy) -ge 10 -or (FreeGB) -lt 25) { Start-Sleep -Seconds 120 }",   # venv python spawns a second process: 10 = 5 runs
          "  New-Item -ItemType Directory -Force -Path $out | Out-Null",
          "  $args = @($model) + $j[1] + $solver + @('--output',$out)",
          "  Start-Process -FilePath $py -ArgumentList $args -WorkingDirectory (Split-Path $model) -WindowStyle Hidden -RedirectStandardOutput (Join-Path $out 'console.txt') -RedirectStandardError (Join-Path $out 'console_stderr.txt') | Out-Null",
          "  Add-Content (Join-Path $root 'launch_log.txt') \"$(Get-Date -Format s) started $($j[0]) free=$([int](FreeGB))GB\"", "  Start-Sleep -Seconds 90", "}",
          "while ((Busy) -gt 0) { Start-Sleep -Seconds 60 }",
          "'all done' | Set-Content (Join-Path $root 'DONE.txt')"]
    Path('run_lhsF6_gpu.ps1').write_text('\n'.join(G) + '\n', encoding='utf-8')
    Path('lhsF6_gpu_jobs.txt').write_text('\n'.join(n for n, _ in GPU) + '\n', encoding='utf-8')
    print(len(GPU), 'jobs for workstation-2')
    print(samples.round(3).to_string())
    print(samples.describe().loc[['min', 'max']].round(3).to_string())
    print(len(jobs), 'jobs; first', jobs[0][0], 'last', jobs[-1][0])
