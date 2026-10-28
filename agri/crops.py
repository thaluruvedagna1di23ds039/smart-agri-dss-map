"""Crop knowledge table (original, hand-written agronomic ranges).

Each crop has an approximate optimum and tolerance (std-dev) for annual mean
temperature (C), annual rainfall (mm) and soil pH, a reference yield
(t/ha) used to scale model output, a botanical family (used by the rotation
module), a legume flag, and an approximate nitrogen requirement (kg N/ha).

These are generic textbook-style ballpark figures for a demo system. For a real
deployment, replace them with values from your local agricultural university /
extension service.
"""

CROPS = {
    "Rice":        dict(t=(26, 5), r=(1500, 600), ph=(6.0, 0.9), n_opt=1.5, base=4.5,  family="Poaceae",       legume=False, n_req=120),
    "Wheat":       dict(t=(18, 5), r=(700, 280),  ph=(6.8, 0.9), n_opt=1.4, base=3.5,  family="Poaceae",       legume=False, n_req=120),
    "Maize":       dict(t=(24, 5), r=(900, 350),  ph=(6.4, 0.9), n_opt=1.6, base=5.0,  family="Poaceae",       legume=False, n_req=150),
    "Pearl millet": dict(t=(28, 5), r=(500, 220), ph=(6.8, 1.1), n_opt=0.9, base=1.6,  family="Poaceae",       legume=False, n_req=60),
    "Sugarcane":   dict(t=(27, 5), r=(1500, 600), ph=(7.0, 1.0), n_opt=1.6, base=70.0, family="Poaceae",       legume=False, n_req=200),
    "Cotton":      dict(t=(26, 5), r=(800, 320),  ph=(7.0, 1.0), n_opt=1.2, base=2.0,  family="Malvaceae",     legume=False, n_req=100),
    "Groundnut":   dict(t=(26, 4), r=(700, 280),  ph=(6.3, 0.8), n_opt=0.9, base=1.8,  family="Fabaceae",      legume=True,  n_req=25),
    "Soybean":     dict(t=(25, 4), r=(900, 320),  ph=(6.4, 0.8), n_opt=1.1, base=2.2,  family="Fabaceae",      legume=True,  n_req=30),
    "Chickpea":    dict(t=(21, 5), r=(550, 220),  ph=(6.8, 0.9), n_opt=0.9, base=1.4,  family="Fabaceae",      legume=True,  n_req=20),
    "Tomato":      dict(t=(24, 4), r=(800, 320),  ph=(6.4, 0.8), n_opt=1.4, base=25.0, family="Solanaceae",    legume=False, n_req=120),
    "Potato":      dict(t=(18, 4), r=(700, 280),  ph=(5.8, 0.8), n_opt=1.4, base=22.0, family="Solanaceae",    legume=False, n_req=120),
    "Mustard":     dict(t=(18, 5), r=(500, 220),  ph=(6.8, 0.9), n_opt=1.1, base=1.4,  family="Brassicaceae",  legume=False, n_req=80),
}

CROP_NAMES = list(CROPS.keys())
