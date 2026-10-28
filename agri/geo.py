"""Fetch climate and soil data for a clicked map point.

Weather : Open-Meteo Historical Weather API (free, no key, CC BY 4.0 data)
Soil    : ISRIC SoilGrids v2.0 REST API (free, no key, CC BY 4.0 data)

If a service cannot be reached, a clearly-labelled estimate is used instead so
the app still works offline; the result tells the user which source was used.
"""
import datetime as dt
import requests

TIMEOUT_WEATHER = 15
TIMEOUT_SOIL = 25

SOIL_PROPS = ["nitrogen", "phh2o", "soc", "clay"]
# default conversion factors (mapped unit -> conventional unit) if API omits them
D_FACTOR = {"nitrogen": 100.0, "phh2o": 10.0, "soc": 10.0, "clay": 10.0}


class NoSoilData(Exception):
    """SoilGrids has no value here (water body, glacier, built-up area...)."""


def valid_point(lat, lon):
    return (isinstance(lat, (int, float)) and isinstance(lon, (int, float))
            and -60.0 <= lat <= 75.0 and -180.0 <= lon <= 180.0)


def _mean(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def _estimate_climate(lat):
    a = abs(lat)
    temp = max(2.0, 28.0 - 0.45 * a)
    rain = 1100.0 if a < 30 else 800.0
    return dict(temp=round(temp, 1), rain=rain, humidity=65.0)


def fetch_weather(lat, lon):
    """Return (dict(temp, rain, humidity), source_label)."""
    end = dt.date.today() - dt.timedelta(days=7)
    start = end - dt.timedelta(days=364)
    try:
        r = requests.get(
            "https://archive-api.open-meteo.com/v1/archive",
            params={
                "latitude": lat, "longitude": lon,
                "start_date": start.isoformat(), "end_date": end.isoformat(),
                "daily": "temperature_2m_mean,precipitation_sum",
                "hourly": "relative_humidity_2m",
                "timezone": "auto",
            },
            timeout=TIMEOUT_WEATHER,
        )
        r.raise_for_status()
        j = r.json()
        temp = _mean(j["daily"]["temperature_2m_mean"])
        precip = [p for p in j["daily"]["precipitation_sum"] if p is not None]
        hum = _mean(j.get("hourly", {}).get("relative_humidity_2m", []))
        if temp is None or not precip:
            raise ValueError("empty weather data")
        return dict(temp=round(temp, 1), rain=round(sum(precip), 0),
                    humidity=round(hum if hum is not None else 65.0, 1)), \
            "Open-Meteo (last 12 months)"
    except Exception:
        return _estimate_climate(lat), "Estimated from latitude (weather service unreachable)"


def reverse_geocode(lat, lon):
    """Return (state, district) names from OpenStreetMap Nominatim, or (None, None).

    Used only to look up historical yields for India. Nominatim's usage policy
    requires an identifying User-Agent and light use (one request per click).
    Data (c) OpenStreetMap contributors, ODbL.
    """
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 10,
                    "addressdetails": 1},
            headers={"User-Agent": "SmartAgriDSS-student-project/1.0"},
            timeout=8,
        )
        r.raise_for_status()
        a = r.json().get("address", {})
        if a.get("country_code") != "in":
            return None, None
        district = a.get("state_district") or a.get("county") or a.get("city_district")
        return a.get("state"), district
    except Exception:
        return None, None


def _soil_defaults():
    return dict(ph=6.5, nitrogen=1.0, soc=10.0, clay=25.0)


def fetch_soil(lat, lon):
    """Return (dict(ph, nitrogen g/kg, soc g/kg, clay %), source_label).

    Raises NoSoilData if the service answered but has no soil at this point.
    """
    try:
        params = [("lon", lon), ("lat", lat), ("depth", "0-5cm"),
                  ("depth", "5-15cm"), ("value", "mean")]
        params += [("property", p) for p in SOIL_PROPS]
        r = requests.get("https://rest.isric.org/soilgrids/v2.0/properties/query",
                         params=params, timeout=TIMEOUT_SOIL)
        r.raise_for_status()
        layers = r.json()["properties"]["layers"]
    except Exception:
        return _soil_defaults(), "Typical default values (soil service unreachable)"

    out = {}
    for layer in layers:
        name = layer.get("name")
        factor = (layer.get("unit_measure") or {}).get("d_factor") or D_FACTOR.get(name, 1.0)
        vals = [d["values"].get("mean") for d in layer.get("depths", [])]
        m = _mean(vals)
        out[name] = None if m is None else m / factor

    if all(out.get(p) is None for p in SOIL_PROPS):
        raise NoSoilData()

    d = _soil_defaults()
    soil = dict(
        ph=out.get("phh2o") if out.get("phh2o") is not None else d["ph"],
        nitrogen=out.get("nitrogen") if out.get("nitrogen") is not None else d["nitrogen"],
        soc=out.get("soc") if out.get("soc") is not None else d["soc"],
        clay=out.get("clay") if out.get("clay") is not None else d["clay"],
    )
    return {k: round(v, 2) for k, v in soil.items()}, "ISRIC SoilGrids (0-15 cm mean)"
