"""English inset of the Tohoku bulk grid for Figure 1 (replaces the Japanese inset of the submitted figure).
Line routes and primary substations: Tohoku Electric Power Network transmission system map (KML), folders
"02_基幹系統(架空線)" (9 x 500 kV, 60 x 275 kV overhead lines; voltage from the line name) and
"02_500kV/275kV変電所(一次系変電所)" (33 substations), at
東北電力ネットワーク 送電系統図.kml.
Coastline and prefecture borders: Natural Earth 10m (public domain), via cartopy.
Size matches the inset slot in Fig1_system_source.pptx (5.3 x 6.36 cm).
Usage: python make_fig1_tohoku_inset.py  -> Fig1_tohoku_inset.{png,pdf,svg}"""
import xml.etree.ElementTree as ET
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.io.shapereader as shpreader
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

OUT = Path(__file__).resolve().parent
KML = Path('東北電力ネットワーク 送電系統図.kml')
RED, BLUE, GREEN = '#e00000', '#0070c0', '#2e8b2e'
plt.rcParams.update({'font.family': 'Arial', 'font.size': 5.5})
HALO = [pe.withStroke(linewidth=1.5, foreground='white')]
K = '{http://www.opengis.net/kml/2.2}'
NAMIE = (141.00, 37.49)


def coords(pm, tag):
    out = []
    for g in pm.iter(K + tag):
        txt = g.find(K + 'coordinates').text.split()
        out.append([tuple(map(float, c.split(',')[:2])) for c in txt])
    return out


lines, subs = [], []
for f in ET.parse(KML).getroot().iter(K + 'Folder'):
    name = f.find(K + 'name').text
    for pm in f.findall(K + 'Placemark'):
        n = (pm.find(K + 'name').text or '').strip()
        if name == '02_基幹系統(架空線)':
            kv = 500 if n.startswith('500kV') else 275
            lines += [(kv, seg) for seg in coords(pm, 'LineString')]
        elif name.startswith('02_500kV/275kV変電所'):
            subs += [(500 if n.startswith('500kV') else 275, p[0]) for p in coords(pm, 'Point')]

pc = ccrs.PlateCarree()
fig = plt.figure(figsize=(5.3 / 2.54, 6.36 / 2.54))
ax = fig.add_axes([0, 0, 1, 1], projection=ccrs.Mercator(central_longitude=140.2))
ax.set_extent([138.1, 142.15, 36.8, 41.6], crs=pc)
ax.axis('off')
prov = shpreader.natural_earth('10m', 'cultural', 'admin_1_states_provinces')
for r in shpreader.Reader(prov).records():
    if r.attributes.get('admin') == 'Japan':
        ax.add_geometries([r.geometry], pc, facecolor='white', edgecolor='#c0c0c0', lw=0.3, zorder=1)
land = shpreader.natural_earth('10m', 'physical', 'land')
ax.add_geometries(shpreader.Reader(land).geometries(), pc, facecolor='none', edgecolor='black', lw=0.4, zorder=2)

for kv, seg in sorted(lines, key=lambda x: x[0]):          # 500 kV drawn on top
    x, y = zip(*seg)
    ax.plot(x, y, color=RED if kv == 500 else BLUE, lw=1.6 if kv == 500 else 0.8, transform=pc,
            zorder=4 if kv == 500 else 3, solid_capstyle='round', solid_joinstyle='round')
for kv, (x, y) in subs:
    ax.plot(x, y, 'o', ms=2.4, mfc='white', mec=RED if kv == 500 else BLUE, mew=0.6, transform=pc, zorder=5)
ax.plot(*NAMIE, marker='*', ms=7, color=GREEN, mec='black', mew=0.4, transform=pc, zorder=6)
ax.text(NAMIE[0] + 0.12, NAMIE[1] - 0.02, 'Namie', transform=pc, ha='left', va='center', fontsize=6, fontweight='bold',
        zorder=6, path_effects=HALO)

h = [Line2D([], [], color=RED, lw=1.6, label='500 kV line'),
     Line2D([], [], color=BLUE, lw=0.8, label='275 kV line'),
     Line2D([], [], ls='', marker='o', ms=2.4, mfc='white', mec='black', mew=0.6, label='Substation')]
ax.legend(handles=h, loc='upper left', bbox_to_anchor=(0.0, 1.0), frameon=True, facecolor='white', edgecolor='none',
          framealpha=1, fontsize=5.5, handlelength=1.6, borderpad=0.2, labelspacing=0.3)
for ext in ('png', 'pdf', 'svg'):
    fig.savefig(OUT / f'Fig1_tohoku_inset.{ext}', dpi=600, transparent=(ext != 'png'))
print('ok', sum(kv == 500 for kv, _ in lines), 'x500 kV segments,', sum(kv == 275 for kv, _ in lines), 'x275 kV,', len(subs), 'substations')
