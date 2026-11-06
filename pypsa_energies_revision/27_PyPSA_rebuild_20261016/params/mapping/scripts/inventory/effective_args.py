"""Read-only: effective D2 argparse values and their origin, from model.py (ast) and default_D2_args.txt.

Order as in model.main(): argparse default -> PRESET_PLEXOS (set_defaults) -> command line.
Does not import model.py. Output: effective_args.json next to this script.
"""
import ast, json, shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / 'src' / 'model.py'
ARGS = ROOT / 'src' / 'default_D2_args.txt'
tree = ast.parse(SRC.read_text(encoding='utf-8'))


def lit(node):
    try:
        return ast.literal_eval(node)
    except Exception:
        return ast.unparse(node)


preset = {}
for node in tree.body:
    if isinstance(node, ast.Assign) and getattr(node.targets[0], 'id', '') == 'PRESET_PLEXOS':
        for kw in node.value.keywords:
            preset[kw.arg] = (lit(kw.value), kw.value.lineno)

args = {}
for node in ast.walk(tree):
    if isinstance(node, ast.Call) and getattr(node.func, 'attr', '') == 'add_argument':
        flag = node.args[0].value
        kws = {k.arg: k.value for k in node.keywords}
        dest = flag.lstrip('-').replace('-', '_')
        action = lit(kws['action']) if 'action' in kws else None
        if 'default' in kws:
            default = lit(kws['default'])
        elif action == 'store_true':
            default = False
        else:
            default = None
        args[dest] = dict(flag=flag, line=node.lineno, default=default, action=action,
                          type=ast.unparse(kws['type']) if 'type' in kws else None)

tokens = shlex.split(ARGS.read_text(encoding='utf-8').replace('{INP}', 'inputs/'), posix=True)
cli = {}
i = 0
while i < len(tokens):
    t = tokens[i]
    if '=' in t:
        k, v = t.split('=', 1); cli[k] = v; i += 1; continue
    nxt = tokens[i + 1] if i + 1 < len(tokens) else None
    if nxt is not None and not nxt.startswith('--'):
        cli[t] = nxt; i += 2
    else:
        cli[t] = True; i += 1

out = {}
for dest, a in args.items():
    value, origin = a['default'], 'argparse_default'
    if dest in preset:
        value, origin = preset[dest][0], f'preset_plexos(L{preset[dest][1]})'
    for flag, v in cli.items():
        f = flag.lstrip('-').replace('-', '_')
        if f == dest:
            value, origin = v, 'cli'
        elif a['action'] is not None and 'BooleanOptional' in str(a['action']) and f == 'no_' + dest:
            value, origin = False, 'cli'
    out[dest] = dict(flag=a['flag'], line=a['line'], argparse_default=a['default'],
                     preset_plexos=preset.get(dest, (None,))[0] if dest in preset else '(not set)',
                     d2_value=value, origin=origin)
unknown = [f for f in cli if f.lstrip('-').replace('-', '_') not in args and f.lstrip('-').replace('-', '_')[3:] not in args]
(Path(__file__).with_name('effective_args.json')).write_text(
    json.dumps(dict(args=out, preset_keys_not_in_argparse=[k for k in preset if k not in args], cli_unknown=unknown),
               indent=1, ensure_ascii=False, default=str), encoding='utf-8')
for d, r in out.items():
    print(f"{r['line']}\t{r['flag']}\t{r['d2_value']!r}\t{r['origin']}\tdefault={r['argparse_default']!r}\tpreset={r['preset_plexos']!r}")
print('preset keys not in argparse:', [k for k in preset if k not in args]); print('unknown cli:', unknown)
