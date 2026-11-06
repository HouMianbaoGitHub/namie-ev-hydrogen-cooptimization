"""Main-text figures for the F6 revision of energies-4608521 (Namie Town; EV fleet + hydrogen + wind/PV; PyPSA LP 2025-2050).

Usage:  python make_figures_f6.py            (all figures)
        python make_figures_f6.py 3 5        (only Fig. 3 and Fig. 5)

Outputs (this folder): Fig<N>_<id>.png (600 dpi) and .pdf.  Fig. 7 / Fig. 8 read sensitivity CSVs if present
(see SENS_CSV / LHS_CSV / PRCC_CSV below for the column format); otherwise they draw PLACEHOLDER versions from
synthetic numbers, watermarked "PLACEHOLDER".

Data (read only):
  27_PyPSA_rebuild_20261016/results/f6_20261030/F6_summary.csv, F6__<case>/installed_units.csv, postprocess/*.csv
  27_PyPSA_rebuild_20261016/inputs/namie_renewables_ninja_2024.parquet, tohoku_price_plan_ref2024.parquet
  Fig. 6 (SoC traces, FIFO ages) reuses the loaders of 27_PyPSA_rebuild_20261016/src/f6_postprocess.py so that the
  definitions are identical to the postprocess report (H2 SoC = % of tank; EV SoC = % of usable 63 kWh, managed 50 %).

Colour system (validated with the dataviz validate_palette.js, light surface, all-pairs):
  EV control  S (no fleet) = neutral grey, A = #2a78d6, B = #eb6834, C = #1baf7a   (CVD dE >= 9.2, normal >= 24)
  with / without hydrogen = filled / open marker (or solid / light bar); never colour alone.
  Resource    H2 = #6250d6, EV = #008300 (dE 28.8 / 35.5);  wind = #256abf, solar = #eda100 (dE 32.7 / 39.1)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]                                   # repository folder
PYPSA = BASE / '27_PyPSA_rebuild_20261016'
RES = PYPSA / 'results' / 'f6_20261030'
PP = RES / 'postprocess'
INP = PYPSA / 'inputs'
MAP_PNG = BASE / 'revision_round1' / '04_manuscript' / 'figures' / 'Namie_Cho.png'
SENS_CSV = HERE / 'data' / 'fig7_sensitivity.csv'
LHS_CSV = HERE / 'data' / 'fig8_lhs_samples.csv'
PRCC_CSV = HERE / 'data' / 'fig8_prcc.csv'

# ------------------------------------------------------------------ style
INK, INK2, MUTED = '#0b0b0b', '#52514e', '#898781'
GRID, AXIS = '#e1e0d9', '#c3c2b7'
CTRL = {'S': '#6f6e69', 'A': '#2a78d6', 'B': '#eb6834', 'C': '#1baf7a'}
CTRL_NAME = {'S': 'No EV fleet', 'A': 'A: uncontrolled', 'B': 'B: smart charging', 'C': 'C: smart + V2G'}
H2C, EVC = '#6250d6', '#008300'
WIND, SOLAR = '#256abf', '#eda100'
# ordinal blue ramp (dataviz palette steps 250 -> 700) for ordered classes
RAMP = ['#86b6ef', '#3987e5', '#1c5cab', '#0d366b']
W2 = 7.09                                                # double-column width, inches (180 mm)

plt.rcParams.update({
    'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'font.size': 7.5, 'axes.titlesize': 8, 'axes.labelsize': 7.5, 'xtick.labelsize': 7, 'ytick.labelsize': 7,
    'legend.fontsize': 7, 'axes.edgecolor': AXIS, 'axes.linewidth': 0.6, 'axes.labelcolor': INK,
    'xtick.color': INK2, 'ytick.color': INK2, 'xtick.major.width': 0.6, 'ytick.major.width': 0.6,
    'xtick.major.size': 2.5, 'ytick.major.size': 2.5, 'axes.grid': False, 'grid.color': GRID, 'grid.linewidth': 0.5,
    'axes.spines.top': False, 'axes.spines.right': False, 'legend.frameon': False, 'lines.linewidth': 1.3,
    'pdf.fonttype': 42, 'ps.fonttype': 42, 'savefig.facecolor': 'white', 'axes.titleweight': 'bold',
    'axes.titlelocation': 'left', 'mathtext.default': 'regular'})


def save(fig, name):
    for ext in ('png', 'pdf'):
        fig.savefig(HERE / f'{name}.{ext}', dpi=600, bbox_inches='tight', pad_inches=0.03)
    plt.close(fig)
    print('wrote', name)


def ygrid(ax, axis='y'):
    ax.grid(True, axis=axis, color=GRID, linewidth=0.5)
    ax.set_axisbelow(True)


def tag(ax, letter, x=-0.02, y=1.02):
    ax.text(x, y, f'({letter})', transform=ax.transAxes, fontsize=8.5, fontweight='bold', va='bottom', ha='right')


def light(hexc, f=0.55):
    c = np.array(matplotlib.colors.to_rgb(hexc))
    return tuple(c + (1 - c) * f)


def summary():
    s = pd.read_csv(RES / 'F6_summary.csv')
    return s[s.batch == 'F6'].set_index('case')


# ================================================================== Fig. 1 system chart
def fig1():
    NAVY = '#17324d'
    fig, ax = plt.subplots(figsize=(W2, 4.4))
    ax.set_xlim(0, 100); ax.axis('off')

    def box(x, y, w, h, title, detail, edge, tsize=8.6, dsize=6.6, lw=1.4):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.25,rounding_size=1.0', linewidth=lw,
                                    edgecolor=edge, facecolor='#f9f9f7'))
        ax.text(x + w / 2, y + h - 2.1, title, ha='center', va='top', fontsize=tsize, fontweight='bold', color=NAVY)
        if detail:
            ax.text(x + w / 2, y + h - 5.0, detail, ha='center', va='top', fontsize=dsize, color=INK2, linespacing=1.25)

    def arrow(p, q, color, two=False, label=None, off=(0, 0), rad=0):
        ax.add_patch(FancyArrowPatch(p, q, arrowstyle='<|-|>' if two else '-|>', mutation_scale=8, linewidth=1.2,
                                     color=color, shrinkA=1, shrinkB=1, connectionstyle=f'arc3,rad={rad}'))
        if label:
            ax.text((p[0] + q[0]) / 2 + off[0], (p[1] + q[1]) / 2 + off[1], label, ha='center', va='center',
                    fontsize=6.4, color=INK2, bbox=dict(facecolor='white', edgecolor='none', pad=0.6))

    # row 1: supply and demand
    box(1, 47, 22, 10, 'Onshore wind', 'existing 38 MW\n+ new capacity (optimized)', WIND)
    box(26, 47, 22, 10, 'Solar PV', 'existing 103 MW\n+ new capacity (optimized)', SOLAR)
    box(51, 47, 22, 10, 'Hydro, biomass', 'existing plants (fixed)', MUTED)
    box(76, 47, 23, 10, 'Local demand', 'exogenous hourly load', MUTED)
    # row 2
    box(1, 24.5, 27, 14, 'EV fleet (exogenous)', 'fleet size and travel demand fixed\n50% managed, 50% uncontrolled\n'
        'A: all uncontrolled\nB: smart charging   C: smart + V2G', EVC, dsize=6.3)
    box(36.5, 27, 27, 9, 'Namie electricity bus', 'hourly balance, single node', NAVY, lw=1.8)
    box(72, 24.5, 27, 14, 'Tohoku grid', 'exogenous hourly price\n(planned generation mix,\nreference year 2024)\n'
        'price taker; buy price = sell price', MUTED, dsize=6.3)
    # row 3: hydrogen chain
    box(6, 2, 24, 10, 'Electrolyzer', 'alkaline; power → H$_2$\ncapacity optimized', H2C)
    box(38, 2, 24, 10, 'Hydrogen tank', 'compressed H$_2$\ncapacity optimized', H2C)
    box(70, 2, 24, 10, 'Fuel cell', 'H$_2$ → power\ncapacity optimized', H2C)

    arrow((12, 47), (42, 36.4), WIND)
    arrow((37, 47), (47, 36.4), SOLAR)
    arrow((62, 47), (54, 36.4), MUTED)
    arrow((58, 36.4), (87.5, 47), MUTED)
    arrow((28.6, 31.5), (36, 31.5), EVC, two=True)
    arrow((64, 31.5), (71.4, 31.5), MUTED, two=True)
    ax.text(67.75, 33.0, '118 MW', ha='center', va='bottom', fontsize=6.4, color=INK2)
    ax.text(67.75, 30.0, 'import /\nexport', ha='center', va='top', fontsize=6.0, color=INK2)
    arrow((42, 27), (22, 12.4), H2C)
    arrow((30, 7), (38, 7), H2C)
    arrow((62, 7), (70, 7), H2C)
    arrow((78, 12.4), (58, 27), H2C)
    ax.text(50, 61.5, 'PyPSA linear capacity-expansion model, 2025–2050, hourly resolution, perfect foresight',
            ha='center', va='center', fontsize=7, color=INK2)
    ax.set_ylim(0, 63)
    save(fig, 'Fig1_system')


# ================================================================== Fig. 2 inputs
def fig2():
    rp = pd.read_parquet(INP / 'namie_renewables_ninja_2024.parquet')
    ps = pd.read_parquet(INP / 'tohoku_price_plan_ref2024.parquet')
    has_map = MAP_PNG.exists()
    fig = plt.figure(figsize=(W2, 6.1))
    gs = fig.add_gridspec(2, 4, height_ratios=[1.25, 1.0], hspace=0.5, wspace=0.12)
    top = gs[0, :].subgridspec(1, 2, width_ratios=[1.12, 1], wspace=0.22)
    if has_map:
        axm = fig.add_subplot(top[0, 0])
        axm.imshow(plt.imread(MAP_PNG)); axm.axis('off'); tag(axm, 'a', x=0.0, y=1.0)
        axm.annotate('Interface to Tohoku grid\n66 kV double circuit, 118 MW (N-1)', xy=(0.368, 0.86),
                     xytext=(0.395, 0.955), textcoords='axes fraction', xycoords='axes fraction', ha='left',
                     va='center', fontsize=5.4, fontweight='bold', color=INK, linespacing=1.2,
                     arrowprops=dict(arrowstyle='-', color=INK2, lw=0.4, shrinkA=0, shrinkB=0))
        axb = fig.add_subplot(top[0, 1])
    else:
        axb = fig.add_subplot(gs[0, :])
    # (b) capacity factors
    d = rp.resample('D').mean(); w = rp.resample('W').mean()
    for col, c, lab in (('wind_pu', WIND, 'Wind'), ('solar_pu', SOLAR, 'Solar PV')):
        axb.plot(d.index, d[col], color=light(c, 0.55), lw=0.5)
        axb.plot(w.index, w[col], color=c, lw=1.5, label=f'{lab} (mean {rp[col].mean():.3f})')
    axb.set_ylabel('Capacity factor (–)')
    axb.set_ylim(0, 1); axb.set_xlim(d.index[0], d.index[-1])
    axb.xaxis.set_major_locator(matplotlib.dates.MonthLocator(bymonth=[1, 3, 5, 7, 9, 11]))
    axb.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%b'))
    axb.set_xlabel('2024 (Renewables.ninja)')
    axb.legend(loc='lower right', bbox_to_anchor=(1.02, 1.0), ncol=2, handlelength=1.3, columnspacing=1.0)
    axb.text(0.99, 0.97, 'thin: daily mean\nthick: weekly mean', transform=axb.transAxes, ha='right', va='top',
             fontsize=6.3, color=INK2, bbox=dict(facecolor='white', edgecolor='none', alpha=0.85, pad=1))
    ygrid(axb); tag(axb, 'b' if has_map else 'a', x=-0.08)
    # (c) price shape by season and hour
    p = ps.reset_index()
    p['month'] = p['ts'].dt.month; p['hour'] = p['ts'].dt.hour
    season = {12: 'Winter (DJF)', 1: 'Winter (DJF)', 2: 'Winter (DJF)', 3: 'Spring (MAM)', 4: 'Spring (MAM)',
              5: 'Spring (MAM)', 6: 'Summer (JJA)', 7: 'Summer (JJA)', 8: 'Summer (JJA)', 9: 'Autumn (SON)',
              10: 'Autumn (SON)', 11: 'Autumn (SON)'}
    p['season'] = p['month'].map(season)
    years = {2030: RAMP[0], 2040: RAMP[1], 2050: RAMP[3]}
    p = p[p.year.isin(years)]
    g = p.groupby(['season', 'year', 'hour'])['price'].mean()
    ymax = float(g.max()) * 1.08
    axs = [fig.add_subplot(gs[1, i]) for i in range(4)]
    for i, sname in enumerate(['Winter (DJF)', 'Spring (MAM)', 'Summer (JJA)', 'Autumn (SON)']):
        ax = axs[i]
        for y, c in years.items():
            ax.plot(range(24), g.loc[(sname, y)].values, color=c, lw=1.5, label=str(y))
        ax.set_title(sname, fontsize=7.5, fontweight='normal', loc='center')
        ax.set_xlim(0, 23); ax.set_ylim(0, ymax); ax.set_xticks([0, 6, 12, 18, 23])
        ygrid(ax)
        if i:
            ax.tick_params(labelleft=False)
        else:
            ax.set_ylabel('Mean price (JPY/kWh)')
    axs[3].legend(loc='lower right', bbox_to_anchor=(1.0, 1.1), ncol=3, handlelength=1.4, columnspacing=1.0)
    fig.text(0.5, 0.045, 'Hour of day', ha='center', fontsize=7.5)
    tag(axs[0], 'c' if has_map else 'b', x=-0.18, y=1.12)
    save(fig, 'Fig2_inputs')


# ================================================================== Fig. 3 value sources
def fig3():
    s = summary(); npv = s['npv']
    fig = plt.figure(figsize=(W2, 2.9))
    gs = fig.add_gridspec(1, 3, width_ratios=[1, 1, 0.95], wspace=0.22)
    rows = [('a', 'Without hydrogen', ['S1', 'A0', 'B0', 'C0']), ('b', 'With hydrogen', ['S2', 'AH', 'BH', 'CH'])]
    steps = ['Travel\nload', 'Smart\ncharging', 'V2G']
    stepc = [CTRL['A'], CTRL['B'], CTRL['C']]
    ax0 = None
    for k, (letter, title, cs) in enumerate(rows):
        ax = fig.add_subplot(gs[0, k], sharey=ax0); ax0 = ax0 or ax
        v = [npv[c] for c in cs]
        xs = [0, 1.5, 3, 4.5, 6]
        # start total
        ax.hlines(v[0], xs[0] - 0.42, xs[0] + 0.42, color=CTRL['S'], lw=2.4)
        ax.text(xs[0], v[0] + 0.25, f'{v[0]:.2f}', ha='center', va='bottom', fontsize=6.8, color=INK)
        for i in range(3):
            lo, hi = sorted((v[i], v[i + 1])); dv = v[i + 1] - v[i]
            hatch = None
            ax.bar(xs[i + 1], hi - lo, bottom=lo, width=0.62, color=stepc[i], edgecolor='none', hatch=hatch)
            ax.hlines(v[i], xs[i] + 0.31 if i else xs[i] + 0.42, xs[i + 1] - 0.31, color=AXIS, lw=0.6)
            ax.text(xs[i + 1], hi + 0.25, f'{dv:+.2f}', ha='center', va='bottom', fontsize=6.8, color=INK,
                    fontweight='bold')
        ax.hlines(v[3], xs[3] + 0.31, xs[4] - 0.42, color=AXIS, lw=0.6)
        ax.hlines(v[3], xs[4] - 0.42, xs[4] + 0.42, color=CTRL['C'], lw=2.4)
        ax.text(xs[4], v[3] + 0.25, f'{v[3]:.2f}', ha='center', va='bottom', fontsize=6.8, color=INK)
        ax.set_xticks(xs)
        ax.set_xticklabels([cs[0]] + steps + [cs[3]], fontsize=6.4)
        ax.set_xlim(-0.6, 6.6)
        ax.set_ylim(31, 41)
        ygrid(ax)
        ax.set_title(title, fontsize=7.5)
        if k == 0:
            ax.set_ylabel('NPV (billion JPY, 2024 present value, 3%)')
        else:
            ax.tick_params(labelleft=False)
        tag(ax, letter, x=-0.04 if k else -0.2)
    # (c) nine-scenario NPV dumbbell
    # same NPV scale as (a,b) so the three panels read together; S0 (no new build, 20.21) is off-scale -> note
    ax = fig.add_subplot(gs[0, 2], sharey=ax0)
    groups = [('S', 'No\nfleet', 'S1', 'S2'), ('A', 'A', 'A0', 'AH'), ('B', 'B', 'B0', 'BH'), ('C', 'C', 'C0', 'CH')]
    for x, (kx, lab, c0, ch) in enumerate(groups):
        ax.plot([x, x], [npv[c0], npv[ch]], color=AXIS, lw=1.0, zorder=1)
        ax.scatter(x, npv[c0], s=34, facecolor='white', edgecolor=CTRL[kx], linewidth=1.5, zorder=3)
        ax.scatter(x, npv[ch], s=34, facecolor=CTRL[kx], edgecolor='white', linewidth=0.8, zorder=3)
        if x == 0:
            ax.text(x + 0.14, npv[ch] + 0.05, f'{ch} {npv[ch]:.2f}', ha='left', va='bottom', fontsize=6.0, color=INK2)
        else:
            ax.text(x - 0.14, npv[ch] + 0.05, f'{ch} {npv[ch]:.2f}', ha='right', va='bottom', fontsize=6.0,
                    color=INK2)
        ax.text(x + 0.14, npv[c0] - 0.05, f'{c0} {npv[c0]:.2f}', ha='left', va='top', fontsize=6.0, color=INK2)
    ax.set_xticks(range(4)); ax.set_xticklabels([g[1] for g in groups], fontsize=6.4)
    ax.set_xlim(-0.4, 4.0); ax.set_xlabel('EV control', fontsize=6.8)
    ax.tick_params(labelleft=False)
    ygrid(ax)
    ax.legend(handles=[Line2D([], [], ls='', marker='o', mfc='white', mec=INK2, ms=5, label='without H$_2$ (x0)'),
                       Line2D([], [], ls='', marker='o', mfc=INK2, mec='white', ms=5.5, label='with H$_2$ (xH)')],
              loc='lower left', handletextpad=0.2, borderaxespad=0.2)
    ax.text(0.98, 0.97, f'S0 (no new build): {npv["S0"]:.2f}', transform=ax.transAxes, ha='right', va='top',
            fontsize=6.0, color=INK2)
    ax.set_title('Scenario NPV', fontsize=7.5)
    tag(ax, 'c', x=-0.04)
    save(fig, 'Fig3_value_sources')


# ================================================================== Fig. 4 capacity pathways
def capacity_paths():
    s = summary()
    out = {}
    for c in ('S2', 'AH', 'BH', 'CH'):
        u = pd.read_csv(RES / f'F6__{c}' / 'installed_units.csv', index_col=0)
        df = pd.DataFrame({'wind_MW': u['wind'] * 40.0, 'el_kgph': u['electrolyzer'] * 10.0,
                           'fc_MW': u['fuelcell'] * 10.0, 'tank_t': u['tank'] * 1.0})
        df['el_MW'] = df['el_kgph'] * 0.054
        # unit sizes cross-checked against F6_summary (2050)
        for col, ref in (('wind_MW', 'wind_MW_2050'), ('el_kgph', 'el_kgph_2050'), ('fc_MW', 'fc_MW_2050'),
                         ('tank_t', 'tank_t_2050')):
            assert abs(df.at[2050, col] - s.at[c, ref]) < 1e-6 * max(1, s.at[c, ref]), (c, col)
        out[c] = df
    return out


def fig4():
    cp = capacity_paths()
    fig, axs = plt.subplots(1, 4, figsize=(W2, 2.35))
    panels = [('wind_MW', 'New onshore wind (MW)'), ('el_MW', 'Electrolyzer (MW$_e$)'),
              ('fc_MW', 'Fuel cell (MW)'), ('tank_t', 'Hydrogen tank (t H$_2$)')]
    cases = [('S2', 'S'), ('AH', 'A'), ('BH', 'B'), ('CH', 'C')]
    for i, (ax, (col, lab)) in enumerate(zip(axs, panels)):
        for c, k in cases:
            ax.plot(cp[c].index, cp[c][col], color=CTRL[k], lw=1.5, label=c, solid_capstyle='round')
        ax.set_title(lab, fontsize=7.3, fontweight='normal', loc='left')
        ax.set_xlim(2025, 2050); ax.set_xticks([2030, 2040, 2050])
        ax.set_ylim(0, None); ygrid(ax)
        tag(ax, 'abcd'[i], x=-0.12, y=1.06)
        if col != 'wind_MW':
            ax.set_xlim(2035, 2050); ax.set_xticks([2035, 2040, 2045, 2050])
    # end labels on the electrolyzer panel (values identical to capacity_summary.csv)
    ax = axs[1]
    for c, k in cases:
        v = cp[c]['el_MW'].iloc[-1]
    axs[0].legend(loc='upper left', handlelength=1.4, labelspacing=0.3)
    v_ah, v_ch = cp['AH']['el_MW'].iloc[-1], cp['CH']['el_MW'].iloc[-1]
    axs[1].text(2049.8, 45, f'2050,\nAH → CH:\n{100 * (v_ch / v_ah - 1):.0f}%'.replace('-', '−'), ha='right', va='center',
                fontsize=6.4, color=INK2)
    fig.subplots_adjust(wspace=0.38)
    fig.text(0.5, -0.04, 'Year (capacity in service; wind panel excludes the existing 38 MW; electrolyzer MW at 54 kWh/kg)',
             ha='center', fontsize=6.8, color=INK2)
    save(fig, 'Fig4_capacity_paths')


# ================================================================== Fig. 5 crowding out
def fig5():
    s = summary(); npv = s['npv']
    mech = pd.read_csv(PP / 'mechanism_2050.csv').set_index('case')
    fig = plt.figure(figsize=(W2, 4.6))
    gs = fig.add_gridspec(2, 1, height_ratios=[1, 0.95], hspace=0.62)
    top = gs[0].subgridspec(1, 2, width_ratios=[1.3, 2.2], wspace=0.3)
    # (a) hydrogen value by EV control
    ax = fig.add_subplot(top[0, 0])
    hv = [('S', npv['S2'] - npv['S1']), ('A', npv['AH'] - npv['A0']), ('B', npv['BH'] - npv['B0']),
          ('C', npv['CH'] - npv['C0'])]
    xs = np.arange(4)
    for x, (k, v) in zip(xs, hv):
        ax.bar(x, v, width=0.6, color=CTRL[k], edgecolor='none')
        ax.text(x, 0.03, f'{v:.3f}', ha='center', va='bottom', fontsize=6.0, color='white')
    a_val = hv[1][1]
    ax.hlines(a_val, 0.7, 3.3, color=INK2, lw=0.6)
    for x, (k, v) in ((2, hv[2]), (3, hv[3])):
        ax.annotate('', xy=(x, v), xytext=(x, a_val),
                    arrowprops=dict(arrowstyle='-|>', color=INK, lw=0.7, mutation_scale=6, shrinkA=0, shrinkB=0))
        name = 'I_B' if x == 2 else 'I_C'
        ax.text(x, a_val + 0.02, f'${name}$\n{v - a_val:+.3f}'.replace('-', '−'), ha='center', va='bottom',
                fontsize=6.2, color=INK)
    ax.set_xticks(xs); ax.set_xticklabels(['No\nfleet', 'A', 'B', 'C'])
    ax.set_xlim(-0.5, 3.5); ax.set_ylim(0, 0.92)
    ax.set_ylabel('Hydrogen value, xH − x0\n(billion JPY)')
    ygrid(ax); tag(ax, 'a', x=-0.3, y=1.04)
    ax.set_xlabel('EV control')
    # (b) 2050 hydrogen capacities, three small axes
    sub = top[0, 1].subgridspec(1, 3, wspace=0.55)
    cases = [('S2', 'S'), ('AH', 'A'), ('BH', 'B'), ('CH', 'C')]
    items = [('el_MW_2050', 'Electrolyzer (MW$_e$)', '{:.0f}'), ('fc_MW_2050', 'Fuel cell (MW)', '{:.1f}'),
             ('tank_t_2050', 'Tank (t H$_2$)', '{:.0f}')]
    for j, (col, lab, fmt) in enumerate(items):
        axb = fig.add_subplot(sub[0, j])
        for x, (c, k) in enumerate(cases):
            v = s.at[c, col]
            axb.bar(x, v, width=0.62, color=CTRL[k], edgecolor='none')
            axb.text(x, v * 1.015, fmt.format(v), ha='center', va='bottom', fontsize=6.0, color=INK)
        axb.set_xticks(range(4)); axb.set_xticklabels([c for c, _ in cases], fontsize=6.6)
        axb.set_ylim(0, s[col].max() * 1.16)
        axb.set_title(lab, fontsize=7.0, fontweight='normal', loc='left')
        ygrid(axb)
        if j == 0:
            tag(axb, 'b', x=-0.3, y=1.04)
    # (c) mechanism: hour classes of electrolyzer and managed EV charging energy, 2050
    axc = fig.add_subplot(gs[1])
    rows = [('Electrolyzer, S2', 'S2', 'el', 'S', H2C), ('Electrolyzer, CH', 'CH', 'el', 'C', H2C),
            ('Managed EV charging, C0', 'C0', 'ev', 'C', EVC), ('Managed EV charging, CH', 'CH', 'ev', 'C', EVC)]
    cls = [('Export at limit, with VRE curtailment', RAMP[3]), ('Export at limit, no curtailment', RAMP[0]),
           ('Other hours', '#e1e0d9'), ('Net-import hours', '#e34948')]
    yy = np.arange(len(rows))[::-1]
    for y, (lab, c, kind, k, rc) in zip(yy, rows):
        K = mech.at[c, f'{kind}_share_in_K'] * 100; X = mech.at[c, f'{kind}_share_in_X'] * 100
        I = mech.at[c, f'{kind}_share_in_import'] * 100
        segs = [K, X - K, 100 - X - I, I]
        left = 0
        for (name, col), w in zip(cls, segs):
            axc.barh(y, w - 0.25, left=left + 0.125, height=0.62, color=col, edgecolor='none')
            if w > 6:
                txtc = 'white' if col in (RAMP[3], '#e34948') else INK
                axc.text(left + w / 2, y, f'{w:.0f}%', ha='center', va='center', fontsize=6.4, color=txtc)
            left += w
        # absorbed surplus energy and total energy (text, right)
        tot = mech.at[c, 'el_elec_GWh' if kind == 'el' else 'ev_ch_GWh']
        axc.text(101.5, y, f'{tot:.0f} GWh', ha='left', va='center', fontsize=6.4, color=INK2)
    axc.set_yticks(yy); axc.set_yticklabels([r[0] for r in rows], fontsize=6.8)
    # identity markers next to the row labels (resource colour)
    for y, r in zip(yy, rows):
        axc.scatter(-1.4, y, s=14, color=r[4], clip_on=False, zorder=4)
    axc.set_xlim(0, 100); axc.set_xlabel('Share of 2050 electricity use falling in each hour class (%)')
    axc.spines['left'].set_visible(False); axc.tick_params(axis='y', length=0, pad=13)
    axc.legend(handles=[Patch(color=col, label=name) for name, col in cls], ncol=4, loc='lower left',
               bbox_to_anchor=(0, 1.0), handlelength=1.2, columnspacing=1.2, borderaxespad=0.2)
    axc.text(101.5, len(rows) - 0.45, 'Annual\nenergy', fontsize=6.2, color=MUTED, va='bottom')
    tag(axc, 'c', x=-0.26, y=1.1)
    save(fig, 'Fig5_crowding_out')


# ================================================================== Fig. 6 timescales
def fifo_ages(frame: pd.DataFrame):
    """Same FIFO queue as lp_timescale_metrics.residence, returning the age distribution (hours, weights)."""
    from collections import deque
    q = deque()
    first_open = float(frame['opening'].iloc[0]) if not np.isnan(frame['opening'].iloc[0]) else float(frame['stock'].iloc[0])
    q.append([None, first_open]); ages, wts = [], []; prev = first_open
    for t, (inflow, outflow, stock) in enumerate(frame[['in', 'out', 'stock']].to_numpy()):
        if inflow > 0:
            q.append([t, float(inflow)])
        loss = max(prev + inflow - outflow - stock, 0.0)
        for amount, record in ((outflow, True), (loss, False)):
            need = float(amount)
            while need > 1e-9 and q:
                layer = q[0]; take = min(layer[1], need)
                if record and layer[0] is not None:
                    ages.append(t - layer[0]); wts.append(take)
                layer[1] -= take; need -= take
                if layer[1] <= 1e-9:
                    q.popleft()
        prev = stock
    a, w = np.asarray(ages, float), np.asarray(wts, float)
    o = np.argsort(a)
    return a[o], w[o]


def fig6():
    sys.path.insert(0, str(PYPSA / 'src'))
    import f6_postprocess as fp  # noqa: E402  (loads model inputs on import)
    r = fp.load('CH')
    h2, _ = fp.h2_frame(r, 2050)
    ev, _ = fp.ev_frame(r, 2050, 'managed')
    tm = pd.read_csv(PP / 'timescale_metrics.csv')
    tm = tm[tm.year == 2050].set_index(['case', 'storage'])
    fig = plt.figure(figsize=(W2, 4.7))
    gs = fig.add_gridspec(2, 2, hspace=0.55, wspace=0.3)
    wins = [('a', 'Winter, 13–26 January 2050', '2050-01-13', '2050-01-26 23:00'),
            ('b', 'Summer, 14–27 July 2050', '2050-07-14', '2050-07-27 23:00')]
    for j, (letter, title, t0, t1) in enumerate(wins):
        ax = fig.add_subplot(gs[0, j])
        ax.plot(h2.loc[t0:t1].index, h2.loc[t0:t1, 'soc'], color=H2C, lw=1.1, label='Hydrogen tank (% of capacity)')
        ax.plot(ev.loc[t0:t1].index, ev.loc[t0:t1, 'soc'], color=EVC, lw=1.1,
                label='Managed EV fleet (% of usable 63 kWh)')
        ax.set_ylim(0, 105); ax.set_ylabel('State of charge (%)' if j == 0 else '')
        ax.xaxis.set_major_locator(matplotlib.dates.DayLocator(bymonthday=[t for t in range(1, 32)], interval=2))
        ax.xaxis.set_major_locator(matplotlib.dates.DayLocator(interval=2))
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%d'))
        ax.set_xlim(pd.Timestamp(t0), pd.Timestamp(t1))
        ax.set_xlabel('Day of month')
        ax.set_title(title, fontsize=7.3, fontweight='normal')
        ygrid(ax); tag(ax, letter, x=-0.08, y=1.04)
        if j == 0:
            ax.legend(loc='lower left', bbox_to_anchor=(0, 1.1), ncol=2, handlelength=1.5)
    # (c) variance decomposition
    ax = fig.add_subplot(gs[1, 0])
    rows = [('H$_2$, S2', ('S2', 'H2'), H2C), ('H$_2$, CH', ('CH', 'H2'), H2C),
            ('EV managed, C0', ('C0', 'EV managed'), EVC), ('EV managed, CH', ('CH', 'EV managed'), EVC)]
    bands = [('var_lt1d_7_28', '< 1 day'), ('var_1to7d', '1–7 days'), ('var_7to28d', '7–28 days'), ('var_gt28d', '> 28 days')]
    yy = np.arange(len(rows))[::-1]
    for y, (lab, key, rc) in zip(yy, rows):
        left = 0
        for (col, name), cc in zip(bands, RAMP):
            w = float(tm.loc[key, col])
            ax.barh(y, max(w - 0.3, 0), left=left + 0.15, height=0.6, color=cc, edgecolor='none')
            if w > 7:
                ax.text(left + w / 2, y, f'{w:.0f}', ha='center', va='center', fontsize=6.3,
                        color=INK if cc == RAMP[0] else 'white')
            left += w
        ax.scatter(-2.2, y, s=14, color=rc, clip_on=False, zorder=4)
    ax.set_yticks(yy); ax.set_yticklabels([r[0] for r in rows], fontsize=6.8)
    ax.tick_params(axis='y', length=0, pad=9); ax.spines['left'].set_visible(False)
    ax.set_xlim(0, 100); ax.set_xlabel('Share of SoC variance, 2050 (%)')
    ax.legend(handles=[Patch(color=c, label=n) for (_, n), c in zip(bands, RAMP)], ncol=4, loc='lower left',
              bbox_to_anchor=(-0.02, 1.0), handlelength=1.0, columnspacing=0.8, handletextpad=0.4)
    tag(ax, 'c', x=-0.3, y=1.12)
    # (d) FIFO residence CDF
    ax = fig.add_subplot(gs[1, 1])
    for lab, fr, c, key in (('Hydrogen, CH', h2, H2C, ('CH', 'H2')), ('Managed EV, CH', ev, EVC, ('CH', 'EV managed'))):
        a, w = fifo_ages(fr)
        cw = np.cumsum(w) / w.sum()
        mean_d = float(np.average(a, weights=w)) / 24
        assert abs(mean_d - tm.loc[key, 'fifo_mean_days']) < 0.02, (lab, mean_d)
        ax.step(a / 24, cw, where='post', color=c, lw=1.5, label=f'{lab}\n(mean {mean_d:.2f} d, dot)')
        ax.scatter(mean_d, np.interp(mean_d * 24, a, cw), s=22, color=c, edgecolor='white', linewidth=1.0, zorder=4)
    ax.set_xlim(0, 7); ax.set_ylim(0, 1.02)
    ax.set_xlabel('FIFO residence time (days)'); ax.set_ylabel('Cumulative share of output')
    ax.legend(loc='lower right', handlelength=1.5)
    ygrid(ax); tag(ax, 'd', x=-0.16, y=1.04)
    save(fig, 'Fig6_timescales')


# ================================================================== Fig. 7 sensitivity (input format + placeholder)
# Metric keys used in the CSVs. NOTE: the sensitivity batch runs only S1/S2/C0/CH (A0/AH are not re-solved), so
# the producer of the CSV must state how I_C and EV flexibility are formed for each group (e.g. I_C relative to the
# F5 A-level, or (CH-C0)-(S2-S1)); titles can be overridden with an optional 'metric_label' column.
def fig7():
    """Input CSV (data/fig7_sensitivity.csv, data/make_fig7_csv.py), one row per sensitivity group and metric:
         theme     str   row block, e.g. 'EV fleet', 'Hydrogen technology and operation', 'End of horizon (different basis)'
         group     str   group name as in F5_敏感性清单.md (+ F6 补充), e.g. 'v2g6', 'mkt100'
         label     str   short English label shown on the axis, e.g. 'V2G wear 6 JPY/kWh'
         metric    str   one of dH_S, dH_C, I_C (= ΔH(C) − ΔH(S)), ratio (= ΔH(C)/ΔH(S)), EV_flex_CA
         value     float billion JPY (PV 2024); ratio dimensionless
         baseline  float base-case value of the same metric
    Panels: (a) ΔH(S) filled and ΔH(C) open; (b) I^S_C; (c) ratio; (d) C − A. The end-of-horizon block is plotted at the axis
    edge with its value written next to it when it lies outside the range of the other groups (different basis)."""
    df = pd.read_csv(SENS_CSV)
    labels = df.drop_duplicates('group')[['theme', 'group', 'label']].reset_index(drop=True)
    # y layout: one header line per theme, then its groups
    rows, y = [], 0
    for th, g in labels.groupby('theme', sort=False):
        rows.append(('h', th, None, y)); y += 1
        for r in g.itertuples():
            rows.append(('g', r.label, r.group, y)); y += 1
    ymax = y - 1
    ypos = {g: ymax - yy for k, _, g, yy in rows if k == 'g'}
    EH = 'End of horizon (different basis)'
    eh = set(df[df.theme == EH].group)
    weak = set(df[(df.metric == 'dH_S') & (df.value < 0.05)].group)   # hydrogen barely built: ratio uninformative
    fig, axs = plt.subplots(1, 4, figsize=(W2, 0.155 * (ymax + 1) + 1.0), sharey=True,
                            gridspec_kw=dict(width_ratios=[1.25, 1, 1, 1]))
    PAN = [(['dH_S', 'dH_C'], 'Hydrogen value ΔH\n(billion JPY)', 'a'),
           (['I_C'], 'Interaction $I^S_C$ = ΔH(C) − ΔH(S)\n(billion JPY)', 'b'),
           (['ratio'], 'Crowding-out ratio\nΔH(C)/ΔH(S)', 'c'), (['EV_flex_CA'], 'EV flexibility C − A\n(billion JPY)', 'd')]
    for ax, (ms, title, letter) in zip(axs, PAN):
        inner = df[df.metric.isin(ms) & ~df.group.isin(eh)]
        lo, hi = min(inner.value.min(), inner.baseline.min(), 0), max(inner.value.max(), inner.baseline.max(), 0)
        pad = 0.08 * (hi - lo)
        lo, hi = lo - pad, hi + pad
        if ms == ['ratio']:
            lo, hi = 0, 1
        edge = {}
        for m in ms:
            d = df[df.metric == m]
            if not len(d):
                continue
            filled = m != 'dH_C'
            b = float(d.baseline.iloc[0])
            ax.axvline(b, color=INK2, lw=0.7, ls='-' if filled else (0, (2, 1.5)), zorder=1)
            for r in d.itertuples():
                yy = ypos[r.group]
                hollow = (not filled) or r.group in eh or (m == 'ratio' and r.group in weak)
                mk = 'o' if filled else 'D'
                x = r.value
                if x > hi or x < lo:   # outside the range of the comparable groups: mark at the edge
                    xe = hi if x > hi else lo
                    ax.scatter([xe], [yy], marker='>' if x > hi else '<', s=18, facecolor='white', edgecolor=MUTED, lw=0.7, zorder=3)
                    edge.setdefault((xe, yy, x > hi), []).append(f'{x:.2f}')
                    continue
                col = MUTED if r.group in eh else CTRL['C']
                ax.scatter([x], [yy], marker=mk, s=13 if filled else 11, facecolor='white' if hollow else col,
                           edgecolor=col, linewidth=0.7, zorder=3)
        for (xe, yy, right), vals in edge.items():
            ax.annotate(' / '.join(vals).replace('-', '−'), (xe, yy), xytext=(-3 if right else 3, 3.5), textcoords='offset points',
                        ha='right' if right else 'left', va='bottom', fontsize=5.4, color=INK2)
        ax.set_xlim(lo, hi)
        ax.axvline(0, color=AXIS, lw=0.6, zorder=0)
        ax.set_title(title, fontsize=6.8, fontweight='normal', loc='center')
        tag(ax, letter, x=-0.02 if letter != 'a' else -0.02, y=1.0)
        ygrid(ax, 'x')
        for k, _, _, yy in rows:
            if k == 'h' and yy > 0:
                ax.axhline(ymax - yy + 0.5, color=GRID, lw=0.6)
        ax.tick_params(axis='x', labelsize=6)
    axs[0].set_ylim(-0.6, ymax + 0.6)
    axs[0].set_yticks([ymax - yy for _, _, _, yy in rows])
    axs[0].set_yticklabels([lab for _, lab, _, _ in rows], fontsize=6.0)
    for tl, (k, _, _, _) in zip(axs[0].get_yticklabels(), rows):
        if k == 'h':
            tl.set_fontweight('bold'); tl.set_color(INK)
    axs[0].tick_params(axis='y', length=0)
    axs[0].legend(handles=[Line2D([], [], ls='', marker='o', ms=3.4, mfc=CTRL['C'], mec=CTRL['C'], label='ΔH(S), no fleet'),
                           Line2D([], [], ls='', marker='D', ms=3.0, mfc='white', mec=CTRL['C'], label='ΔH(C), V2G fleet'),
                           Line2D([], [], color=INK2, lw=0.7, label='Base case')],
                  loc='lower center', bbox_to_anchor=(2.4, 1.075), ncol=3, fontsize=6.2, handlelength=1.4, frameon=False)
    fig.subplots_adjust(wspace=0.14)
    save(fig, 'Fig7_sensitivity')


# ================================================================== Fig. 8 LHS
def fig8():
    """Input CSVs (data/make_fig8_csv.py from results/lhsF6_20261031):
       data/fig8_lhs_samples.csv : one row per LHS sample; columns sample, dH_S, dH_A, dH_C, I_C (= ΔH(C) − ΔH(A)),
           EV_flex_CA (billion JPY), ratio (ΔH(C)/ΔH(A), empty where hydrogen is not built), ev_participation
       data/fig8_prcc.csv        : columns parameter (English label), metric (I_C|ratio|EV_flex_CA), prcc (-1..1)
    """
    smp = pd.read_csv(LHS_CSV); prcc = pd.read_csv(PRCC_CSV)
    s = summary().npv
    base = {'dH_S': s.S2 - s.S1, 'dH_A': s.AH - s.A0, 'dH_C': s.CH - s.C0, 'EV_flex_CA': s.C0 - s.A0}
    base['I_C'] = base['dH_C'] - base['dH_A']
    built = smp.dH_A > 0.01
    fig = plt.figure(figsize=(W2, 5.0))
    top, bot = fig.add_gridspec(2, 1, height_ratios=[1.15, 1], hspace=0.42)
    gs = top.subgridspec(1, 2, width_ratios=[1.2, 1], wspace=0.3)
    ga = gs[0, 0].subgridspec(1, 2, width_ratios=[4, 1.1], wspace=0.45)
    rng = np.random.default_rng(8)

    def strip(ax, i, v, col, b, nb):
        ax.boxplot(v, positions=[i], widths=0.5, showfliers=False, medianprops=dict(color=INK, lw=1.1),
                   boxprops=dict(color=INK2, lw=0.6), whiskerprops=dict(color=INK2, lw=0.6), capprops=dict(color=INK2, lw=0.6))
        x = i + rng.uniform(-0.16, 0.16, len(v))
        ax.scatter(x[~nb], v[~nb], s=9, color=col, edgecolor='white', linewidth=0.4, zorder=3)
        ax.scatter(x[nb], v[nb], s=9, facecolor='white', edgecolor=col, linewidth=0.7, zorder=3)
        ax.plot([i - 0.3, i + 0.3], [b, b], color=INK, lw=1.4, zorder=4, solid_capstyle='butt')

    ax = fig.add_subplot(ga[0, 0])
    cols = {'dH_S': CTRL['S'], 'dH_A': CTRL['A'], 'dH_C': CTRL['C'], 'I_C': INK2}
    labs = {'dH_S': 'ΔH(S)', 'dH_A': 'ΔH(A)', 'dH_C': 'ΔH(C)', 'I_C': '$I_C$'}
    for i, m in enumerate(cols):
        strip(ax, i, smp[m].to_numpy(), cols[m], base[m], ~built.to_numpy())
    ax.axhline(0, color=AXIS, lw=0.6)
    ax.set_xticks(range(4)); ax.set_xticklabels(labs.values(), fontsize=6.8)
    ax.set_xlim(-0.6, 3.6)
    ax.set_ylabel('billion JPY (2024 present value)'); ygrid(ax); tag(ax, 'a', x=-0.2)
    ax2 = fig.add_subplot(ga[0, 1])
    strip(ax2, 0, smp.EV_flex_CA.to_numpy(), EVC, base['EV_flex_CA'], np.zeros(len(smp), bool))
    ax2.set_xticks([0]); ax2.set_xticklabels(['C − A'], fontsize=6.8); ax2.set_xlim(-0.6, 0.6)
    ax2.set_ylim(0, None); ygrid(ax2)
    ax.legend(handles=[Line2D([], [], color=INK, lw=1.4, label='Base case'),
                       Line2D([], [], ls='', marker='o', ms=3.2, mfc='white', mec=INK2, mew=0.7, label='ΔH(A) < 0.01')],
              loc='upper right', fontsize=6, handlelength=1.2, borderaxespad=0.2)

    axb = fig.add_subplot(gs[0, 1])
    b = smp[built]
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list('ramp', RAMP)
    sc = axb.scatter(b.dH_A, b.ratio, c=b.ev_participation * 100, cmap=cmap, vmin=25, vmax=100, s=14,
                     edgecolor='white', linewidth=0.4, zorder=3)
    axb.scatter([base['dH_A']], [base['dH_C'] / base['dH_A']], marker='D', s=22, facecolor='none', edgecolor=INK, lw=0.9,
                zorder=4)
    axb.annotate('Base case', (base['dH_A'], base['dH_C'] / base['dH_A']), xytext=(-22, -26), textcoords='offset points', arrowprops=dict(arrowstyle='-', color=INK2, lw=0.5, shrinkA=1, shrinkB=4),
                 fontsize=6, color=INK2)
    axb.set_xscale('log'); axb.set_xticks([0.02, 0.1, 0.5, 2]); axb.set_xticklabels(['0.02', '0.1', '0.5', '2'])
    axb.set_ylim(0, 1); axb.set_xlabel('ΔH(A), billion JPY (log)'); axb.set_ylabel('Crowding-out ratio ΔH(C)/ΔH(A)')
    ygrid(axb); tag(axb, 'b', x=-0.15)
    cb = fig.colorbar(sc, ax=axb, fraction=0.06, pad=0.03, aspect=22)
    cb.set_label('EV participation (%)', fontsize=6.4); cb.ax.tick_params(labelsize=6, width=0.5, length=2)
    cb.outline.set_linewidth(0.4)

    gc = bot.subgridspec(1, 3, wspace=0.08)
    params = list(dict.fromkeys(prcc.parameter))
    yp = np.arange(len(params))[::-1]
    for k, (m, mlab) in enumerate((('I_C', 'Interaction $I_C$'), ('ratio', 'Crowding-out ratio'), ('EV_flex_CA', 'EV flexibility C − A'))):
        axp = fig.add_subplot(gc[0, k])
        d = prcc[prcc.metric == m].set_index('parameter').reindex(params)
        axp.barh(yp, d.prcc, height=0.62, color=[CTRL['A'] if v >= 0 else '#e34948' for v in d.prcc], edgecolor='none')
        axp.axvline(0, color=AXIS, lw=0.6)
        axp.set_xlim(-1, 1); axp.set_xticks([-0.5, 0, 0.5]); axp.set_xticklabels(['−0.5', '0', '0.5'], fontsize=6)
        axp.set_title(mlab, fontsize=6.8, fontweight='normal', loc='center')
        axp.set_yticks(yp); axp.set_yticklabels(params if k == 0 else [], fontsize=6.2)
        axp.tick_params(axis='y', length=0)
        ygrid(axp, 'x')
        if k == 0:
            tag(axp, 'c', x=-0.55)
        if k == 1:
            axp.set_xlabel('Partial rank correlation', fontsize=6.8)
    save(fig, 'Fig8_lhs')


FIGS = {1: fig1, 2: fig2, 3: fig3, 4: fig4, 5: fig5, 6: fig6, 7: fig7, 8: fig8}

if __name__ == '__main__':
    sel = [int(a) for a in sys.argv[1:]] or list(FIGS)
    for k in sel:
        FIGS[k]()
