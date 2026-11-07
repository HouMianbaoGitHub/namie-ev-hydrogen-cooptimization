"""Validate the parameter registry (h2.yaml, ev.yaml, grid_econ.yaml) and generate REGISTRY.md.
The YAML files are the single source of truth; REGISTRY.md is generated, do not edit it by hand.
Usage: python build_registry_md.py"""
from collections import Counter
from datetime import date
from pathlib import Path

import yaml

HERE = Path(__file__).parent
PARTS = [('h2.yaml', '氢能'), ('ev.yaml', 'EV'), ('grid_econ.yaml', '电网、市场、可再生能源、负荷与经济')]
STATUS = {'confirmed': '已确定', 'conflict': '资料矛盾', 'no_source': '无出处', 'author_to_decide': '待作者决定'}
REQ = ('id', 'name', 'value', 'unit', 'source', 'status')


def cell(v):
    s = '' if v is None else (yaml.safe_dump(v, allow_unicode=True, default_flow_style=True).strip() if isinstance(v, (dict, list)) else str(v))
    return s.replace('|', '\\|').replace('\n', ' ')


rows, errors = [], []
for f, domain in PARTS:
    recs = yaml.safe_load((HERE / f).read_text(encoding='utf-8')) or []
    for r in recs:
        missing = [k for k in REQ if k not in r]
        if missing:
            errors.append(f'{f}: {r.get("id")} missing {missing}')
        if r.get('status') not in STATUS:
            errors.append(f'{f}: {r.get("id")} bad status {r.get("status")}')
        rows.append((domain, r))
dup = [k for k, n in Counter(r['id'] for _, r in rows).items() if n > 1]
if dup:
    errors.append(f'duplicate ids: {dup}')
if errors:
    raise SystemExit('registry errors:\n' + '\n'.join(errors))

L = ['# D2 参数登记表', '',
     f'由 `params/build_registry_md.py` 从 `h2.yaml`、`ev.yaml`、`grid_econ.yaml` 生成（{date.today()}）。**不要手改本文件，改 YAML 后重新生成。**', '',
     '规则：只记录有出处的最终采用值；作者决定优先于报告建议；没有新依据或审稿要求，不改数值。修改时在 YAML 的 decided 中写明日期和依据。', '']
cnt = Counter(r['status'] for _, r in rows)
L += ['## 概况', '', '| 状态 | 条数 |', '|---|---|'] + [f'| {STATUS[k]} | {cnt.get(k, 0)} |' for k in STATUS] + [f'| 合计 | {len(rows)} |', '']
L += ['## 待处理（非"已确定"）', '', '| 领域 | id | 名称 | 状态 | 采用值 | 代码现值 | 说明 |', '|---|---|---|---|---|---|---|']
for d, r in rows:
    if r['status'] != 'confirmed':
        L.append(f"| {d} | `{r['id']}` | {cell(r['name'])} | {STATUS[r['status']]} | {cell(r['value'])} | {cell(r.get('code_now'))} | {cell(r.get('notes'))} |")
L.append('')
for f, domain in PARTS:
    L += [f'## {domain}', '', '| id | 名称 | 采用值 | 单位 | 敏感性 | 出处 | 报告 | 决定 | 状态 | 代码现值 | 模型入口 |', '|---|---|---|---|---|---|---|---|---|---|---|']
    for d, r in rows:
        if d == domain:
            L.append('| ' + ' | '.join([f"`{r['id']}`", cell(r['name']), cell(r['value']), cell(r['unit']), cell(r.get('sensitivity')), cell(r['source']),
                                         cell(r.get('report')), cell(r.get('decided')), STATUS[r['status']], cell(r.get('code_now')), cell(r.get('model_entry'))]) + ' |')
    L.append('')
(HERE / 'REGISTRY.md').write_text('\n'.join(L), encoding='utf-8')
print(f'ok: {len(rows)} records', dict(cnt))
