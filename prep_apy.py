"""Build data/apy_summary.csv from the APY (Area-Production-Yield) CSV.

Usage:  python prep_apy.py path/to/APY.csv

APY = India's district-wise crop statistics (Government of India open data).
We keep only the last 10 reporting years (2011+), drop zero/outlier yields
(above the crop's 99th percentile) and store medians per district, state and
all-India, so the web app does not need the 21 MB raw file.
"""
import sys
from pathlib import Path

import pandas as pd

APY_NAMES = {  # our crop -> APY crop name
    "Rice": "Rice", "Wheat": "Wheat", "Maize": "Maize", "Pearl millet": "Bajra",
    "Sugarcane": "Sugarcane", "Cotton": "Cotton(lint)", "Groundnut": "Groundnut",
    "Soybean": "Soyabean", "Chickpea": "Gram", "Potato": "Potato",
    "Mustard": "Rapeseed &Mustard",
}
OUT = Path(__file__).resolve().parent / "data" / "apy_summary.csv"


def main(path):
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    df = df.dropna(subset=["Crop", "State", "District", "Yield"])
    for c in ["State", "District", "Crop"]:
        df[c] = df[c].astype(str).str.strip()
    df["State"] = df["State"].replace({"THE DADRA AND NAGAR HAVELI": "Dadra and Nagar Haveli",
                                       "CHANDIGARH": "Chandigarh", "Laddak": "Ladakh"})
    df["District"] = df["District"].str.upper()
    df = df[(df["Crop_Year"] >= 2011) & (df["Yield"] > 0)]

    rows = []
    for ours, theirs in APY_NAMES.items():
        d = df[df["Crop"] == theirs]
        d = d[d["Yield"] <= d["Yield"].quantile(0.99)]
        if d.empty:
            continue
        unit = 0.17 if ours == "Cotton" else 1.0  # cotton is reported in 170-kg bales/ha
        rows.append(dict(level="national", state="", district="", crop=ours,
                         median_yield=d["Yield"].median() * unit, n=len(d)))
        for s, g in d.groupby("State"):
            rows.append(dict(level="state", state=s, district="", crop=ours,
                             median_yield=g["Yield"].median() * unit, n=len(g)))
        for (s, dist), g in d.groupby(["State", "District"]):
            rows.append(dict(level="district", state=s, district=dist, crop=ours,
                             median_yield=g["Yield"].median() * unit, n=len(g)))
    out = pd.DataFrame(rows)
    out["median_yield"] = out["median_yield"].round(2)
    OUT.parent.mkdir(exist_ok=True)
    out.to_csv(OUT, index=False)
    print(f"wrote {OUT} ({len(out)} rows)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
