"""End-to-end test with network calls mocked.  Run: python test_app.py"""
import os
import tempfile

os.environ["DSS_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")

import app as appmod
from agri import geo

geo.fetch_weather = lambda lat, lon: (dict(temp=25.5, rain=950.0, humidity=68.0), "mock weather")
geo.fetch_soil = lambda lat, lon: (dict(ph=6.4, nitrogen=1.3, soc=14.0, clay=30.0), "mock soil")
geo.reverse_geocode = lambda lat, lon: ("Karnataka", "Bengaluru Rural")

c = appmod.app.test_client()


def token():
    with c.session_transaction() as s:
        return s.get("csrf", "")


# 1. unauthenticated access is blocked
assert c.get("/").status_code == 302
assert c.post("/api/analyze", json={"lat": 1, "lon": 1}).status_code == 400  # no CSRF

# 2. register + login
c.get("/register")
t = token()
r = c.post("/register", data=dict(csrf=t, email="a@b.com", password="short"))
assert b"at least 8" in r.data
r = c.post("/register", data=dict(csrf=t, email="a@b.com", password="longenough1"), follow_redirects=True)
assert b"Account created" in r.data
bad = c.post("/login", data=dict(csrf=token(), email="a@b.com", password="wrongpass"))
assert b"Invalid email" in bad.data
ok = c.post("/login", data=dict(csrf=token(), email="a@b.com", password="longenough1"))
assert ok.status_code == 302

# 3. map click -> analysis
assert c.get("/").status_code == 200
H = {"X-CSRF-Token": token()}
r = c.post("/api/analyze", json={"lat": 13.0, "lon": 77.6}, headers=H)
assert r.status_code == 200, r.data
d = r.get_json()
print("region:", d["region"])
print("best:", d["best_crop"], d["ranking"][:3])
print("intercrops:", [(x["main"], x["partner"]) for x in d["intercrops"]])
print("rotation:", [s["crop"] for s in d["rotation"]])
print("nutrients:", d["nutrients"]["sources"][0])
print("model:", d["model"])
assert len(d["rotation"]) == 4
fams = [s["family"] for s in d["rotation"]]
assert all(a != b for a, b in zip(fams, fams[1:])), "same family back-to-back"
assert any(s["legume"] for s in d["rotation"])
assert d["ranking"][0]["hist_yield_t_ha"] is not None

# 4. validation + history
assert c.post("/api/analyze", json={"lat": 999, "lon": 0}, headers=H).status_code == 400
assert c.post("/api/analyze", json={}, headers=H).status_code == 400
h = c.get("/history")
assert h.status_code == 200 and d["best_crop"].encode() in h.data

# 5. history is private to each user
c2 = appmod.app.test_client()
c2.get("/register")
with c2.session_transaction() as s:
    t2 = s["csrf"]
c2.post("/register", data=dict(csrf=t2, email="x@y.com", password="longenough2"))
c2.post("/login", data=dict(csrf=t2, email="x@y.com", password="longenough2"))
assert c2.get("/api/history/1").status_code == 404
print("ALL TESTS PASSED")
