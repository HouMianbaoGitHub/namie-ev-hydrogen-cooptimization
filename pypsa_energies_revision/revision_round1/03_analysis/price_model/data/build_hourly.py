"""Build hourly Tohoku/Tokyo price + area supply-demand panel.

Usage: python -I -X utf8 build_hourly.py <data_dir>
Reads raw/ (untouched downloads), writes processed/.
Timestamps: JST (no DST in Japan), HOUR-BEGINNING (2024-04-01 00:00 = 00:00-01:00).
"""
import sys, os, glob, io
import numpy as np
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
D = sys.argv[1]
RAW = os.path.join(D, "raw")
OUT = os.path.join(D, "processed")
os.makedirs(OUT, exist_ok=True)


def read_text(f):
    b = open(f, "rb").read()
    for enc in ("utf-8-sig", "cp932"):
        try:
            return b.decode(enc), enc
        except UnicodeDecodeError:
            pass
    raise ValueError(f)


def num(s):
    return pd.to_numeric(s.astype(str).str.replace(",", "").str.strip(), errors="coerce")


# ---------------------------------------------------------------- JEPX
frames = []
for f in sorted(glob.glob(os.path.join(RAW, "jepx", "spot_summary_*.csv"))):
    t, _ = read_text(f)
    df = pd.read_csv(io.StringIO(t))
    c = list(df.columns)
    # positional mapping (header verified identical in all files 2019-2026)
    m = {c[0]: "date", c[1]: "slot", c[4]: "jepx_volume_kwh", c[5]: "price_system",
         c[6]: "price_hokkaido", c[7]: "price_tohoku", c[8]: "price_tokyo"}
    assert "システムプライス" in c[5] and "東北" in c[7] and "東京" in c[8] and "北海道" in c[6] and "約定総量" in c[4]
    df = df.rename(columns=m)[list(m.values())]
    df["ts"] = pd.to_datetime(df["date"]) + pd.to_timedelta((df["slot"] - 1) * 30, unit="min")
    frames.append(df.drop(columns=["date", "slot"]))
jepx = pd.concat(frames).drop_duplicates("ts").set_index("ts").sort_index()
for col in jepx.columns:
    jepx[col] = num(jepx[col])
jepx_h = jepx.groupby(jepx.index.floor("h")).agg(
    {"price_system": "mean", "price_hokkaido": "mean", "price_tohoku": "mean", "price_tokyo": "mean",
     "jepx_volume_kwh": "sum"})
jepx_h["jepx_volume_mwh"] = jepx_h.pop("jepx_volume_kwh") / 1000.0  # MWh per hour
# 30-min splitting share (finer than hourly): fraction of the 2 slots with tohoku != tokyo
jepx["split_slot"] = (jepx.price_tohoku - jepx.price_tokyo).abs() > 0.005
jepx_h["split_slots"] = jepx.groupby(jepx.index.floor("h"))["split_slot"].sum()

# --------------------------------------------- generic monthly 30-min eria_jukyu (MW avg)
def read_eria(files, prefix):
    out = []
    for f in files:
        t, _ = read_text(f)
        df = pd.read_csv(io.StringIO(t), skiprows=1)
        df["ts"] = pd.to_datetime(df["DATE"] + " " + df["TIME"], format="%Y/%m/%d %H:%M")
        for c in df.columns[2:]:
            if c != "ts":
                df[c] = num(df[c])
        thermal_cols = [c for c in df.columns if c.startswith("火力(")]
        r = pd.DataFrame({
            "ts": df["ts"],
            "demand": df["エリア需要"],
            "nuclear": df["原子力"],
            "thermal": df[thermal_cols].sum(axis=1, min_count=1),
            "hydro": df["水力"],
            "geothermal": df["地熱"],
            "biomass": df["バイオマス"],
            "solar": df["太陽光発電実績"],
            "solar_curtail": df["太陽光出力制御量"],
            "wind": df["風力発電実績"],
            "wind_curtail": df["風力出力制御量"],
            "pumped": df["揚水"],
            "battery": df["蓄電池"] if "蓄電池" in df else np.nan,
            "interconnector": df["連系線"],
            "other": df["その他"] if "その他" in df else np.nan,
        })
        out.append(r)
    a = pd.concat(out).drop_duplicates("ts").set_index("ts").sort_index()
    h = a.groupby(a.index.floor("h")).mean()  # MW average of the hour
    h["n_slots"] = a.groupby(a.index.floor("h"))["demand"].count()
    return h.add_prefix(prefix + "_")


# ---------------------------------------------------------------- Tohoku
tohoku_old = []
for f in sorted(glob.glob(os.path.join(RAW, "tohoku", "juyo_20*_tohoku_*Q.csv"))):
    t, _ = read_text(f)
    df = pd.read_csv(io.StringIO(t))
    df.columns = ["dt", "demand", "hydro", "thermal", "nuclear", "solar", "solar_curtail", "wind",
                  "wind_curtail", "geothermal", "biomass", "pumped", "interconnector"]
    df["ts"] = pd.to_datetime(df["dt"], format="%Y/%m/%d %H:%M")
    for c in df.columns[1:-1]:
        df[c] = num(df[c])  # MWh per hour == MW average
    tohoku_old.append(df.drop(columns="dt"))
t_old = pd.concat(tohoku_old).drop_duplicates("ts").set_index("ts").sort_index()
t_old = t_old[t_old.index < "2024-02-01"].add_prefix("tohoku_")
t_new = read_eria(sorted(glob.glob(os.path.join(RAW, "tohoku", "eria_jukyu_*_02.csv"))), "tohoku")
t_new = t_new[t_new.index >= "2024-02-01"]
tohoku = pd.concat([t_old, t_new]).sort_index()

# ---------------------------------------------------------------- Tokyo
tk_old = []
for f in sorted(glob.glob(os.path.join(RAW, "tepco", "area-20*.csv"))):
    t, _ = read_text(f)
    df = pd.read_csv(io.StringIO(t), skiprows=3, header=None)
    df = df.iloc[:, :15]
    df.columns = ["date", "time", "demand", "nuclear", "thermal", "hydro", "geothermal", "biomass", "solar",
                  "solar_curtail", "wind", "wind_curtail", "pumped", "interconnector", "total"]
    df = df.dropna(subset=["date"])
    df["ts"] = pd.to_datetime(df["date"] + " " + df["time"], format="%Y/%m/%d %H:%M")
    for c in df.columns[2:15]:
        df[c] = num(df[c]) * 10.0  # 万kWh per hour -> MWh per hour == MW average
    tk_old.append(df.drop(columns=["date", "time", "total"]))
k_old = pd.concat(tk_old).drop_duplicates("ts").set_index("ts").sort_index()
k_old = k_old[k_old.index < "2024-02-01"].add_prefix("tokyo_")
k_new = read_eria(sorted(glob.glob(os.path.join(RAW, "tepco", "eria_jukyu_*_03.csv"))), "tokyo")
k_new = k_new[k_new.index >= "2024-02-01"]
tokyo = pd.concat([k_old, k_new]).sort_index()

# ---------------------------------------------------------------- merge on full hourly grid
start = pd.Timestamp("2019-04-01 00:00")
end = max(jepx_h.index.max(), tohoku.index.max(), tokyo.index.max())
grid = pd.date_range(start, end, freq="h", name="ts_jst_hour_beginning")
P = jepx_h.reindex(grid).join(tohoku.reindex(grid)).join(tokyo.reindex(grid))
P["fy"] = np.where(P.index.month >= 4, P.index.year, P.index.year - 1)

main_cols = ["price_system", "price_tohoku", "price_tokyo", "price_hokkaido", "jepx_volume_mwh",
             "tohoku_demand", "tohoku_solar", "tohoku_wind", "tohoku_hydro", "tohoku_nuclear", "tohoku_thermal",
             "tohoku_geothermal", "tohoku_biomass", "tohoku_pumped", "tohoku_battery",
             "tohoku_solar_curtail", "tohoku_wind_curtail", "tohoku_interconnector",
             "tokyo_demand", "tokyo_solar", "tokyo_wind", "tokyo_hydro", "tokyo_nuclear", "tokyo_thermal",
             "tokyo_geothermal", "tokyo_biomass", "tokyo_pumped", "tokyo_battery",
             "tokyo_solar_curtail", "tokyo_wind_curtail", "tokyo_interconnector",
             "split_slots", "fy"]
P = P[main_cols]
P.index.name = "ts_jst_hour_beginning"
P.to_parquet(os.path.join(OUT, "hourly_tohoku_tokyo.parquet"))
P.head(200).to_csv(os.path.join(OUT, "hourly_tohoku_tokyo_sample200.csv"), encoding="utf-8")

# ---------------------------------------------------------------- checks
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
rows = []
for fy, g in P.groupby("fy"):
    n = len(g)
    exp = len(pd.date_range(f"{fy}-04-01", f"{fy+1}-04-01", freq="h", inclusive="left"))
    r = dict(FY=fy, grid_h=n, expected_h=exp,
             price_h=int(g.price_tohoku.notna().sum()),
             tohoku_h=int(g.tohoku_demand.notna().sum()),
             tokyo_h=int(g.tokyo_demand.notna().sum()))
    ok = g.price_tohoku.notna() & g.price_tokyo.notna()
    r["split_share_hourly_%"] = 100 * ((g.price_tohoku - g.price_tokyo).abs() > 0.005)[ok].mean() if ok.any() else np.nan
    r["split_share_30min_%"] = 100 * g.split_slots[ok].sum() / (2 * ok.sum()) if ok.any() else np.nan
    r["tohoku>tokyo_h_%"] = 100 * ((g.price_tohoku - g.price_tokyo) > 0.005)[ok].mean() if ok.any() else np.nan
    r["tohoku<tokyo_h_%"] = 100 * ((g.price_tohoku - g.price_tokyo) < -0.005)[ok].mean() if ok.any() else np.nan
    for c in ["price_system", "price_tohoku", "price_tokyo", "price_hokkaido"]:
        r["mean_" + c] = g[c].mean()
    for a in ["tohoku", "tokyo"]:
        for v in ["demand", "solar", "wind", "solar_curtail", "wind_curtail", "nuclear", "interconnector"]:
            r[f"{a}_{v}_TWh"] = g[f"{a}_{v}"].sum(min_count=1) / 1e6
        r[f"{a}_solar_share_%"] = 100 * r[f"{a}_solar_TWh"] / r[f"{a}_demand_TWh"] if r[f"{a}_demand_TWh"] else np.nan
        r[f"{a}_wind_share_%"] = 100 * r[f"{a}_wind_TWh"] / r[f"{a}_demand_TWh"] if r[f"{a}_demand_TWh"] else np.nan
    rows.append(r)
C = pd.DataFrame(rows).set_index("FY")
C.to_csv(os.path.join(OUT, "checks_by_fy.csv"), encoding="utf-8")
print(C.round(2).T.to_string())

# missing-hour runs per source
def runs(mask):
    m = mask.astype(int).values
    idx = P.index
    out, i = [], 0
    while i < len(m):
        if m[i]:
            j = i
            while j + 1 < len(m) and m[j + 1]:
                j += 1
            out.append((idx[i], idx[j], j - i + 1))
            i = j + 1
        else:
            i += 1
    return out

for name, col in [("JEPX", "price_tohoku"), ("Tohoku", "tohoku_demand"), ("Tokyo", "tokyo_demand")]:
    rs = runs(P[col].isna())
    print(f"\n{name} missing runs: {len(rs)}")
    for a, b, n in rs[:15]:
        print(f"  {a} -> {b}  ({n} h)")
# energy-balance sanity: sum of supply == demand
for a in ["tohoku", "tokyo"]:
    s = P[[f"{a}_{v}" for v in ["nuclear", "thermal", "hydro", "geothermal", "biomass", "solar", "wind",
                                 "pumped", "interconnector"]]].sum(axis=1, min_count=1)
    s = s + P[f"{a}_battery"].fillna(0)
    resid = (s - P[f"{a}_demand"]).abs()
    print(f"\n{a}: |supply-demand| median {resid.median():.1f} MW, p99 {resid.quantile(.99):.1f} MW (excl. 'other')")
print("\nrows", len(P), "range", P.index.min(), P.index.max())
