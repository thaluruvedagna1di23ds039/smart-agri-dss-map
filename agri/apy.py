"""Look up real historical yields (APY data) for a clicked location.

Data: India's district-wise Area-Production-Yield statistics (Government of
India open data), pre-aggregated by prep_apy.py into data/apy_summary.csv.
"""
import difflib
from pathlib import Path

import pandas as pd

PATH = Path(__file__).resolve().parent.parent / "data" / "apy_summary.csv"
_df = None

STATE_ALIASES = {
    "orissa": "odisha", "uttaranchal": "uttarakhand", "nct of delhi": "delhi",
    "andaman and nicobar islands": "andaman and nicobar island",
    "jammu & kashmir": "jammu and kashmir", "pondicherry": "puducherry",
}


def _data():
    global _df
    if _df is None:
        if PATH.exists():
            _df = pd.read_csv(PATH).fillna("")
            _df["state_l"] = _df["state"].str.lower()
        else:
            _df = pd.DataFrame(columns=["level", "state", "district", "crop",
                                        "median_yield", "n", "state_l"])
    return _df


def match_region(state, district):
    """Map names from the geocoder onto APY spellings. Returns (state, district|None)."""
    df = _data()
    if not state or df.empty:
        return None, None
    s = STATE_ALIASES.get(state.strip().lower(), state.strip().lower())
    states = df.loc[df["level"] == "state", "state"].unique()
    hit = next((x for x in states if x.lower() == s), None)
    if hit is None:
        close = difflib.get_close_matches(s, [x.lower() for x in states], n=1, cutoff=0.8)
        hit = next((x for x in states if close and x.lower() == close[0]), None)
    if hit is None:
        return None, None
    dist = None
    if district:
        d = district.upper().replace(" DISTRICT", "").strip()
        names = df.loc[(df["level"] == "district") & (df["state"] == hit), "district"].unique().tolist()
        if d in names:
            dist = d
        else:
            quals = {"URBAN", "RURAL", "NORTH", "SOUTH", "EAST", "WEST", "CENTRAL"}
            want = set(d.split()) & quals
            close = [n for n in difflib.get_close_matches(d, names, n=3, cutoff=0.85)
                     if set(n.split()) & quals == want]  # never swap Rural/Urban, North/South...
            dist = close[0] if close else None  # no safe match -> use state-level data
    return hit, dist


def historical_yield(crop, state=None, district=None):
    """Best available real yield for a crop: (value t/ha, level label) or (None, None)."""
    df = _data()
    c = df[df["crop"] == crop]
    if c.empty:
        return None, None
    if state and district:
        r = c[(c["level"] == "district") & (c["state"] == state) & (c["district"] == district)]
        if len(r) and r.iloc[0]["n"] >= 3:
            return float(r.iloc[0]["median_yield"]), f"{district.title()} district"
    if state:
        r = c[(c["level"] == "state") & (c["state"] == state)]
        if len(r) and r.iloc[0]["n"] >= 5:
            return float(r.iloc[0]["median_yield"]), f"{state} state"
    r = c[c["level"] == "national"]
    if len(r):
        return float(r.iloc[0]["median_yield"]), "All-India"
    return None, None
