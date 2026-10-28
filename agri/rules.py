"""Rule-based modules: intercropping, crop rotation, nutrient recovery.

All rules are original, simple, explainable agronomic heuristics (general
practice: cereal + legume pairing, avoid same family back-to-back, legume after
heavy feeders). Row ratios are indicative only; confirm locally.
"""
from .crops import CROPS

# (main crop, partner, indicative row ratio, reason)
INTERCROP_PAIRS = [
    ("Maize", "Soybean", "2 : 1", "Legume adds nitrogen; different canopy heights share light."),
    ("Maize", "Groundnut", "2 : 2", "Low-growing legume covers soil and fixes nitrogen."),
    ("Maize", "Potato", "1 : 2", "Staggered growth periods reduce competition."),
    ("Cotton", "Groundnut", "1 : 2", "Legume cover suppresses weeds and improves soil nitrogen."),
    ("Cotton", "Soybean", "1 : 1", "Short-duration legume fills the wide cotton row spacing."),
    ("Sugarcane", "Potato", "1 : 1", "Quick crop harvested before cane canopy closes."),
    ("Sugarcane", "Chickpea", "1 : 2", "Legume uses the open inter-row space in early cane growth."),
    ("Sugarcane", "Mustard", "1 : 1", "Short-duration oilseed uses idle inter-row space."),
    ("Wheat", "Mustard", "6 : 1", "Mustard border rows add income and can attract beneficial insects."),
    ("Wheat", "Chickpea", "2 : 2", "Cereal-legume pairing improves nitrogen balance."),
    ("Pearl millet", "Groundnut", "1 : 3", "Drought-hardy cereal with a nitrogen-fixing legume."),
    ("Pearl millet", "Soybean", "2 : 1", "Legume complements the shallow-rooted cereal."),
    ("Potato", "Maize", "2 : 1", "Maize rows give light shade and wind break in warm spells."),
    ("Rice", "Soybean", "bund crop", "Soybean on field bunds uses otherwise unused space."),
]

MIN_SUITABILITY = 20.0  # % relative yield potential to count a crop as viable


def recommend_intercrops(ranking, main=None, limit=3):
    """ranking: output of model.predict_all (sorted). Returns (main_crop, list)."""
    suit = {r["crop"]: r["suitability_pct"] for r in ranking}
    candidates = [r["crop"] for r in ranking if suit[r["crop"]] >= MIN_SUITABILITY]
    if main is None:
        main = next((c for c in candidates
                     if any(p[0] == c for p in INTERCROP_PAIRS)), ranking[0]["crop"])
    out = []
    for m, partner, ratio, reason in INTERCROP_PAIRS:
        if m == main and suit.get(partner, 0) >= MIN_SUITABILITY:
            score = round((suit[m] + suit[partner]) / 2, 1)
            out.append(dict(main=m, partner=partner, ratio=ratio, reason=reason,
                            partner_suitability_pct=suit[partner], combo_score=score))
    out.sort(key=lambda d: d["combo_score"], reverse=True)
    return main, out[:limit]


def plan_rotation(ranking, start=None, seasons=4):
    """Greedy rule-based rotation. Returns list of season dicts."""
    suit = {r["crop"]: r["suitability_pct"] for r in ranking}
    viable = [r["crop"] for r in ranking if suit[r["crop"]] >= MIN_SUITABILITY] or \
             [ranking[0]["crop"]]
    seq = [start if start in viable else viable[0]]
    notes = ["Start with the best-suited crop for this location."]
    while len(seq) < seasons:
        prev = seq[-1]
        pf = CROPS[prev]["family"]
        two_back_f = CROPS[seq[-2]]["family"] if len(seq) > 1 else None
        pool = [c for c in viable if CROPS[c]["family"] != pf]
        if not CROPS[prev]["legume"]:
            legumes = [c for c in pool if CROPS[c]["legume"]]
            if legumes:
                seq.append(legumes[0])
                notes.append(f"Legume after {prev} restores soil nitrogen and breaks the pest cycle.")
                continue
        pref = [c for c in pool if CROPS[c]["family"] != two_back_f and not CROPS[c]["legume"]] \
            or [c for c in pool if not CROPS[c]["legume"]] or pool or viable
        seq.append(pref[0])
        notes.append(f"Different plant family from {prev} to reduce disease and pest build-up.")
    return [dict(season=i + 1, crop=c, family=CROPS[c]["family"],
                 legume=CROPS[c]["legume"], reason=notes[i])
            for i, c in enumerate(seq)]


# Approximate typical nutrient content (% of fresh weight) and first-season
# availability fractions. Indicative textbook-style values, not lab results.
ORGANIC_SOURCES = {
    "Farmyard manure": dict(N=0.5, P2O5=0.2, K2O=0.5),
    "Compost":         dict(N=1.0, P2O5=0.5, K2O=1.0),
    "Vermicompost":    dict(N=1.6, P2O5=0.7, K2O=0.8),
    "Poultry manure":  dict(N=1.5, P2O5=1.2, K2O=0.8),
}
AVAILABILITY = dict(N=0.40, P2O5=0.60, K2O=0.80)
STANDARD_RATE_T_HA = 5.0  # standard application used for comparison


def estimate_nutrient_recovery(crop, soil_n_gkg):
    """Nutrients recovered from each organic source at a standard rate.

    Compared with the crop's nitrogen need (after an estimated soil supply).
    """
    n_req = CROPS[crop]["n_req"]
    soil_fraction = min(0.35, 0.15 * soil_n_gkg)
    net_need = round(n_req * (1 - soil_fraction), 1)
    rows = []
    for name, c in ORGANIC_SOURCES.items():
        kg = STANDARD_RATE_T_HA * 1000
        n = kg * c["N"] / 100 * AVAILABILITY["N"]
        p = kg * c["P2O5"] / 100 * AVAILABILITY["P2O5"]
        k = kg * c["K2O"] / 100 * AVAILABILITY["K2O"]
        offset = min(100.0, 100 * n / net_need) if net_need else 0.0
        rows.append(dict(source=name, rate_t_ha=STANDARD_RATE_T_HA,
                         N_kg_ha=round(n, 1), P2O5_kg_ha=round(p, 1),
                         K2O_kg_ha=round(k, 1), n_offset_pct=round(offset, 1)))
    rows.sort(key=lambda d: d["n_offset_pct"], reverse=True)
    return dict(crop=crop, crop_n_requirement_kg_ha=n_req,
                net_n_need_kg_ha=net_need, sources=rows)
