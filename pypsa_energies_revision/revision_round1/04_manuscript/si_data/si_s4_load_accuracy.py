"""Recompute the accuracy metrics of the three sector load models (SI S4) from the original training data.

The three models are the ones listed as final in 8_LoadCalculation/4_统合分析/0_Readme.md and used for the Namie
profiles:
  residential  8_LoadCalculation/1_Residential_Load/1_ShichiTown/4_新地町的建模.py   (Random Forest, Shinchi smart meters)
  commercial   8_LoadCalculation/2_Commercial_Load/Load/3_多种方法对比-5万样本-加入星期和节假日-只画前5个重要变量 20251014.py
               (five algorithms per floor-area x contract group, SII BEMS 2022; its group 中規模・低圧 random forest is the
               model_area中規模_contract低圧_Random_Forest.pkl loaded by Load/4_预测浪江町_商业V20251022.py for the Namie profile)
  industrial   8_LoadCalculation/3_Industrial_Load/3_工业-终极优化版-中规模-高压小口 new.py (XGBoost per industry, SII BEMS, 2022)

Each original script is executed unchanged except that (i) every write to disk (joblib.dump, savefig, to_csv) is
disabled and the working directory is a temporary folder, (ii) the 3 GB BEMS CSV is replaced by an identical 2022 subset
(both scripts keep only 2022 immediately after reading), and (iii) the held-out observations and predictions are captured.
Nothing in 8_LoadCalculation is modified. Besides the metric as each script defines it, the standard MAPE on all held-out
points (sklearn definition) and WAPE = sum|e| / sum y are reported.

Usage: python si_s4_load_accuracy.py [cache|residential|commercial|industrial|all] [--cache-dir DIR]
Outputs (this folder): si_s4_load_accuracy_<sector>.json, si_s4_load_accuracy.csv (after all three exist)
"""
import argparse
import contextlib
import io
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]                     # repository folder
LC = ROOT / '8_LoadCalculation'
BEMS = LC / '2_Commercial_Load' / 'Load' / 'cleaned_combined_data.csv'   # byte-identical copy in 3_Industrial_Load
SCRIPTS = {
    'residential': LC / '1_Residential_Load' / '1_ShichiTown' / '4_新地町的建模.py',
    'commercial': LC / '2_Commercial_Load' / 'Load' / '3_多种方法对比-5万样本-加入星期和节假日-只画前5个重要变量 20251014.py',
    'industrial': LC / '3_Industrial_Load' / '3_工业-终极优化版-中规模-高压小口 new.py',
}
# the original code is cut before these lines (plots, Namie prediction, saving the universal model)
STOP = {
    'residential': None,
    'commercial': '# Step 9: Build & train',
    'industrial': '# 保存通用工业负荷预测模型',
}


def standard_metrics(y, p):
    from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, mean_squared_error, r2_score
    y = np.asarray(y, float); p = np.asarray(p, float)
    return {'n_test': int(len(y)), 'n_test_zero': int((y == 0).sum()),
            'MAPE_all_pct': float(mean_absolute_percentage_error(y, p) * 100),
            'MAPE_nonzero_pct': float(np.mean(np.abs(p[y != 0] - y[y != 0]) / np.abs(y[y != 0])) * 100),
            'WAPE_pct': float(np.abs(p - y).sum() / np.abs(y).sum() * 100),
            'RMSE_kW': float(np.sqrt(mean_squared_error(y, p))), 'MAE_kW': float(mean_absolute_error(y, p)),
            'R2': float(r2_score(y, p))}


def bems_2022(cache_dir):
    f = Path(cache_dir) / 'bems_2022.pkl'
    if f.exists():
        return pd.read_pickle(f)
    t0 = time.time(); parts = []
    for ch in pd.read_csv(BEMS, chunksize=2_000_000):
        parts.append(ch[ch['計測日'].astype(str).str.startswith('2022/')])
    d = pd.concat(parts, ignore_index=True)
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    d.to_pickle(f)
    print(f'cached 2022 subset {d.shape} in {time.time() - t0:.0f} s -> {f}', flush=True)
    return d


def run_original(sector, cache_dir, hook_after, hook_code, only_group=None):
    """Execute the original script with writes disabled; hook_code is inserted after the line containing hook_after."""
    import joblib
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    src = SCRIPTS[sector].read_text(encoding='utf-8')
    if STOP[sector]:
        src = src[:src.index(STOP[sector])]
    src = src.replace("sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')", 'pass')
    lines = src.split('\n')
    k = [i for i, ln in enumerate(lines) if hook_after in ln]
    assert len(k) == 1, (sector, hook_after, k)
    ind = lines[k[0]][:len(lines[k[0]]) - len(lines[k[0]].lstrip())]
    lines.insert(k[0] + 1, '\n'.join(ind + h for h in hook_code))
    if only_group:                         # groups are independent (own data, fixed seeds): skip the others
        k = [i for i, ln in enumerate(lines) if ln.startswith('for (area, contract), group_data in grouped:')]
        assert len(k) == 1
        lines.insert(k[0] + 1, f'    if (area, contract) != {only_group!r}: continue')
    src = '\n'.join(lines)
    captured = []
    sub = bems_2022(cache_dir) if sector != 'residential' else None
    real_read_csv = pd.read_csv

    def read_csv(path, *a, **kw):
        if sub is not None and Path(path).name == 'cleaned_combined_data.csv':
            return sub.copy()
        return real_read_csv(path, *a, **kw)
    patches = [(joblib, 'dump', lambda *a, **k: None), (plt, 'savefig', lambda *a, **k: None),
               (plt, 'show', lambda *a, **k: None), (pd, 'read_csv', read_csv),
               (pd.DataFrame, 'to_csv', lambda *a, **k: None), (pd.DataFrame, 'to_excel', lambda *a, **k: None),
               (os, 'chdir', lambda *a, **k: None)]
    saved = [(o, n, getattr(o, n)) for o, n, _ in patches]
    cwd = os.getcwd(); tmp = tempfile.mkdtemp(prefix=f'si_s4_{sector}_')
    log = io.StringIO()
    try:
        os.chdir(tmp)                      # any relative write of the original code lands here
        for o, n, f in patches:
            setattr(o, n, f)
        g ={'__file__': str(SCRIPTS[sector]), '__name__': '__si_s4__', '_CAPTURE': captured}
        with contextlib.redirect_stdout(log):
            exec(compile(src, str(SCRIPTS[sector]), 'exec'), g)
    finally:
        for o, n, f in saved:
            setattr(o, n, f)
        os.chdir(cwd)
        (HERE / f'si_s4_load_accuracy_{sector}.log').write_text(log.getvalue(), encoding='utf-8')
    return captured, g


def residential(cache_dir):
    cap, g = run_original('residential', cache_dir, "smape = calculate_smape(y_test, y_pred)",
                          ["_CAPTURE.append((model_name, y_test.to_numpy(), y_pred))"])
    rf = [c for c in cap if c[0] == 'Random Forest'][0]
    r = {'sector': 'residential', 'model': 'Random Forest (default), 80/20 random split, seed 42',
         'data': 'Shinchi Town smart meters 2018, mean load of 50 households (final_modeling_data.csv)',
         'script_metric_definition': 'sklearn MAPE on all test points', **standard_metrics(rf[1], rf[2])}
    r['MAPE_script_pct'] = r['MAPE_all_pct']
    return r


def commercial(cache_dir):
    cap, g = run_original('commercial', cache_dir, "smape = calculate_smape(y_test_orig, y_pred_orig)",
                          ["_CAPTURE.append((area, contract, model_name, n_samples, np.asarray(y_test_orig), "
                           "np.asarray(y_pred_orig)))"], only_group=('中規模', '低圧'))
    rows = [{'area': a, 'contract': c, 'model': m, 'n_samples': int(n), **standard_metrics(y, p)}
            for a, c, m, n, y, p in cap]
    used = [r for r in rows if r['area'] == '中規模' and r['contract'] == '低圧']
    rf = [r for r in used if r['model'] == 'Random Forest'][0]
    r = {**rf, 'sector': 'commercial', 'model': 'Random Forest (default) of group 中規模・低圧, log1p target, 80/20 split, seed 42',
         'data': 'SII BEMS 2022, medium-size low-voltage buildings, targets above the group 90th percentile removed',
         'script_metric_definition': 'sklearn MAPE on all test points (original scale)',
         'MAPE_script_pct': rf['MAPE_all_pct'], 'five_algorithms_used_group': used}
    return r


def industrial(cache_dir):
    cap, g = run_original('industrial', cache_dir, "smape = calculate_smape(y_test_orig, y_pred_orig)",
                          ["_CAPTURE.append((industry, model_name, n_samples, np.asarray(y_test_orig), "
                           "np.asarray(y_pred_orig), mape))"])
    rows = []
    for ind, m, n, y, p, mape in cap:
        if m != 'XGBoost-Optimized':
            continue
        rows.append({'industry': ind, 'n_samples': n, 'MAPE_script_pct': float(mape), **standard_metrics(y, p)})
    w = np.array([x['n_samples'] for x in rows], float)
    agg = {k: float(np.average([x[k] for x in rows], weights=w))
           for k in ('MAPE_script_pct', 'MAPE_all_pct', 'WAPE_pct', 'RMSE_kW', 'MAE_kW', 'R2')}
    uni = universal_holdout(g)
    return {'sector': 'industrial', 'model': 'XGBoost-Optimized, one model per industry, 80/20 random split, seed 42',
            'data': 'SII BEMS 2022, medium-size high-voltage (中規模・高圧小口) buildings, 10,000 samples per industry',
            'script_metric_definition': ('MAPE only on test points >= max(5 kW, 0.1 x median) with prediction >= half that '
                                         'and relative error < 10; sample-weighted mean over industries'),
            'features_note': 'uses observed load lags 1-24 h and 168 h and rolling statistics (one-step-ahead)',
            **agg, 'n_test': int(sum(x['n_test'] for x in rows)), 'by_industry': rows,
            'universal_model_holdout': uni}


def universal_holdout(g):
    """Held-out test of the pooled model that 4_预测浪江町_工业.py uses (universal_industrial_load_model.pkl). The original
    script fits it on all sampled data; here the same sampling, filters and settings are used with an 80/20 split."""
    from sklearn.base import clone
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import Pipeline
    data, vi, mx = g['data'], g['valid_industries'], g['max_samples_per_group']
    d = data[data['業種'].isin(vi)].copy()
    if len(d) > mx * len(vi):
        d = d.sample(n=mx * len(vi), random_state=42)
    X = d.drop(columns=['電力使用量_全体']); y = d['電力使用量_全体']
    X = X[y >= 1.0]; y = y[y >= 1.0]
    m = (y <= y.quantile(0.99)) & (y > 0); X = X[m].copy(); y = y[m]
    for col in g['numeric_features']:
        if col in X.columns:
            X[col] = X[col].clip(X[col].quantile(0.01), X[col].quantile(0.99))
    Xtr, Xte, ytr, yte = train_test_split(X, np.log1p(y), test_size=0.2, random_state=42)
    pipe = Pipeline([('preprocessor', clone(g['preprocessor'])), ('model', clone(g['optimized_xgb']))]).fit(Xtr, ytr)
    return {'note': 'one-step-ahead with observed lags; the Namie run feeds back its own predictions',
            **standard_metrics(np.expm1(yte), np.expm1(pipe.predict(Xte)))}


def table():
    out = []
    for s in ('residential', 'commercial', 'industrial'):
        f = HERE / f'si_s4_load_accuracy_{s}.json'
        if f.exists():
            d = json.loads(f.read_text(encoding='utf-8'))
            out.append({k: d.get(k) for k in ('sector', 'MAPE_script_pct', 'MAPE_all_pct', 'WAPE_pct', 'RMSE_kW',
                                              'MAE_kW', 'R2', 'n_test')})
    if out:
        pd.DataFrame(out).to_csv(HERE / 'si_s4_load_accuracy.csv', index=False, float_format='%.4g')
        print(pd.DataFrame(out).to_string(index=False))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('step', nargs='?', default='all')
    ap.add_argument('--cache-dir', default=os.path.join(tempfile.gettempdir(), 'si_s4_cache'))
    a = ap.parse_args()
    if a.step == 'cache':
        d = bems_2022(a.cache_dir); print(d.shape, d.dtypes.to_dict())
        sys.exit()
    for s in (('residential', 'commercial', 'industrial') if a.step == 'all' else (a.step,)):
        t0 = time.time()
        res = {'residential': residential, 'commercial': commercial, 'industrial': industrial}[s](a.cache_dir)
        res['runtime_s'] = round(time.time() - t0)
        (HERE / f'si_s4_load_accuracy_{s}.json').write_text(json.dumps(res, ensure_ascii=False, indent=1),
                                                              encoding='utf-8')
        print(s, {k: v for k, v in res.items() if k != 'by_industry'}, flush=True)
    table()
