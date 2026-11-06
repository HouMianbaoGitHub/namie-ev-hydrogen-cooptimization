"""Refresh code_now / model_entry of the registry from the mapping audit (params/mapping/*_map.yaml) and add a
`verified` line (date, mapping file, verdict). Sources, values and decisions are not touched.
Usage: python refresh_from_mapping.py <date>"""
import re
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).parent
DATE = sys.argv[1] if len(sys.argv) > 1 else 'unknown'


def q(s):
    return yaml.safe_dump(str(s), allow_unicode=True, width=100000, default_style='"').strip().removesuffix('...').strip()


def setline(block, key, value, after=None):
    """Replace a (possibly folded) `  key:` line; if absent and `after` is given, insert it after that key."""
    pat = re.compile(rf'^  {key}: .*(?:\n    .*)*', flags=re.M)
    line = f'  {key}: {value}'
    if pat.search(block):
        return pat.sub(lambda _: line, block, count=1)
    return re.sub(rf'^(  {after}: .*\n)', lambda m: m.group(1) + line + '\n', block, count=1, flags=re.M)


for part in ('h2', 'ev', 'grid_econ'):
    maps = {m['id']: m for m in yaml.safe_load((HERE / 'mapping' / f'{part}_map.yaml').read_text(encoding='utf-8'))}
    p = HERE / f'{part}.yaml'
    t = p.read_text(encoding='utf-8')
    n = 0
    for i, m in maps.items():
        mm = re.search(rf'^- id: {re.escape(i)}\n(.*?)(?=^- id: |^# -{{5,}}|\Z)', t, flags=re.S | re.M)
        if not mm:
            print('not in registry:', i)
            continue
        b = mm.group(0)
        b = setline(b, 'code_now', q(m.get('effective_value')))
        b = setline(b, 'model_entry', q(f"{m.get('code')}；进入：{m.get('enters')}"))
        b = setline(b, 'verified', q(f"{DATE} mapping/{part}_map.yaml verdict={m.get('verdict')}"), after='status')
        t = t.replace(mm.group(0), b)
        n += 1
    p.write_text(t, encoding='utf-8')
    print(part, n, 'entries refreshed')
