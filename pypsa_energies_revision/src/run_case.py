"""Run one case of cases.csv. Usage: python src/run_case.py <case_id> --output <dir> [further model.py options]"""
import subprocess
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
INP = (HERE.parent / 'inputs').as_posix() + '/'
SOLVER = ['--solver', 'gurobi', '--threads', '5', '--time-limit', '36000',
          '--gurobi-numeric-focus', '1', '--gurobi-bar-homogeneous', '1']


def setarg(args, key, value=None, drop=False):
    a = [x for x in args if not x.startswith(key + '=')]
    if key in a:
        i = a.index(key)
        flag = i + 1 >= len(a) or a[i + 1].startswith('--')
        del a[i:i + (1 if flag else 2)]
    if not drop:
        a += [key] if value is None else [key, value]
    return a


def case_args(case_id):
    row = pd.read_csv(HERE / 'cases.csv', keep_default_na=False).set_index('case_id').loc[case_id]
    args = (HERE / 'base_args.txt').read_text().replace('{INP}', INP).split()
    tokens = row['changes'].replace('{INP}', INP).split()
    i = 0
    while i < len(tokens):
        key = tokens[i]
        if key.startswith('!'):
            args = setarg(args, key[1:], drop=True)
            i += 1
        elif i + 1 < len(tokens) and not tokens[i + 1].startswith(('--', '!')):
            args = setarg(args, key, tokens[i + 1])
            i += 2
        else:
            args = setarg(args, key)
            i += 1
    head = ['--scenario', row['scenario']] + (['--ev-control', row['ev_control']] if row['ev_control'] else [])
    return head + args


if __name__ == '__main__':
    cmd = [sys.executable, str(HERE / 'model.py')] + case_args(sys.argv[1]) + SOLVER + sys.argv[2:]
    sys.exit(subprocess.call(cmd))
