"""Smart Agriculture Decision Support System - map-click edition (Flask)."""
import json
import os
import re
import secrets
import sqlite3
import time
from pathlib import Path

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from agri import apy, geo, model, rules

BASE = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("DSS_DB", BASE / "dss.db"))


def _secret_key():
    env = os.environ.get("SECRET_KEY")
    if env:
        return env
    f = BASE / ".secret_key"
    if not f.exists():
        f.write_text(secrets.token_hex(32))
    return f.read_text().strip()


app = Flask(__name__)
app.config.update(
    SECRET_KEY=_secret_key(),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    MAX_CONTENT_LENGTH=16 * 1024,
)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_failed = {}  # (ip, email) -> [timestamps]


# ---------- database ----------
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d is not None:
        d.close()


def init_db():
    with sqlite3.connect(DB_PATH) as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            pw_hash TEXT NOT NULL,
            created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS analyses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            lat REAL NOT NULL, lon REAL NOT NULL,
            result TEXT NOT NULL,
            created TEXT DEFAULT CURRENT_TIMESTAMP);
        """)


# ---------- security helpers ----------
def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def csrf_protect():
    if request.method == "POST":
        sent = request.headers.get("X-CSRF-Token") or request.form.get("csrf")
        if not sent or not secrets.compare_digest(sent, session.get("csrf", "")):
            abort(400, "Invalid CSRF token")


@app.after_request
def headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "same-origin"
    return resp


def login_required(fn):
    from functools import wraps

    @wraps(fn)
    def wrapper(*a, **kw):
        if "uid" not in session:
            if request.path.startswith("/api/"):
                return jsonify(error="Please log in first."), 401
            return redirect(url_for("login"))
        return fn(*a, **kw)
    return wrapper


def too_many_failures(key):
    now = time.time()
    _failed[key] = [t for t in _failed.get(key, []) if now - t < 600]
    return len(_failed[key]) >= 5


# ---------- auth ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        if not EMAIL_RE.match(email) or len(email) > 120:
            flash("Enter a valid email address.")
        elif len(pw) < 8:
            flash("Password must be at least 8 characters.")
        else:
            try:
                db().execute("INSERT INTO users(email, pw_hash) VALUES(?,?)",
                             (email, generate_password_hash(pw)))
                db().commit()
                flash("Account created. Please log in.")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("That email is already registered.")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        key = (request.remote_addr, email)
        if too_many_failures(key):
            flash("Too many failed attempts. Try again in 10 minutes.")
            return render_template("login.html"), 429
        row = db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if row and check_password_hash(row["pw_hash"], pw):
            session.clear()
            session["uid"] = row["id"]
            session["email"] = row["email"]
            csrf_token()
            return redirect(url_for("index"))
        _failed.setdefault(key, []).append(time.time())
        flash("Invalid email or password.")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- pages ----------
@app.route("/")
@login_required
def index():
    return render_template("index.html", metrics=model.get_metrics())


@app.route("/history")
@login_required
def history():
    rows = db().execute(
        "SELECT id, lat, lon, result, created FROM analyses WHERE user_id=? "
        "ORDER BY id DESC LIMIT 50", (session["uid"],)).fetchall()
    items = []
    for r in rows:
        res = json.loads(r["result"])
        items.append(dict(id=r["id"], lat=r["lat"], lon=r["lon"], created=r["created"],
                          best=res["best_crop"], yield_t_ha=res["ranking"][0]["yield_t_ha"]))
    return render_template("history.html", items=items)


@app.route("/api/history/<int:aid>")
@login_required
def history_item(aid):
    r = db().execute("SELECT result FROM analyses WHERE id=? AND user_id=?",
                     (aid, session["uid"])).fetchone()
    if not r:
        abort(404)
    return jsonify(json.loads(r["result"]))


# ---------- analysis API ----------
@app.route("/api/analyze", methods=["POST"])
@login_required
def analyze():
    data = request.get_json(silent=True) or {}
    try:
        lat, lon = float(data.get("lat")), float(data.get("lon"))
    except (TypeError, ValueError):
        return jsonify(error="Click a point on the map."), 400
    if not geo.valid_point(lat, lon):
        return jsonify(error="Please click on land between 60°S and 75°N."), 400
    lat, lon = round(lat, 4), round(lon, 4)

    weather, w_src = geo.fetch_weather(lat, lon)
    try:
        soil, s_src = geo.fetch_soil(lat, lon)
    except geo.NoSoilData:
        return jsonify(error="No soil data at this point (water, ice or built-up area). "
                             "Click on farmland."), 422

    inputs = {**weather, **soil}
    ranking = model.predict_all(inputs)

    # Real historical yields (India APY data) for the clicked district/state
    g_state, g_district = geo.reverse_geocode(lat, lon)
    a_state, a_district = apy.match_region(g_state, g_district)
    for row in ranking:
        val, level = apy.historical_yield(row["crop"], a_state, a_district)
        row["hist_yield_t_ha"], row["hist_level"] = val, level
    region = (f"{a_district.title()}, {a_state}" if a_district and a_state
              else a_state or "Outside India or region not recognised")
    best = ranking[0]["crop"]
    main, inter = rules.recommend_intercrops(ranking)
    rotation = rules.plan_rotation(ranking, start=best)
    nutrients = rules.estimate_nutrient_recovery(best, soil["nitrogen"])

    result = dict(
        lat=lat, lon=lon, best_crop=best, inputs=inputs, region=region,
        sources=dict(weather=w_src, soil=s_src),
        ranking=ranking[:6], intercrop_main=main, intercrops=inter,
        rotation=rotation, nutrients=nutrients,
        model=model.get_metrics(),
    )
    db().execute("INSERT INTO analyses(user_id, lat, lon, result) VALUES(?,?,?,?)",
                 (session["uid"], lat, lon, json.dumps(result)))
    db().commit()
    return jsonify(result)


init_db()

if __name__ == "__main__":
    model.get_model()  # train on first run if needed
    app.run(host="127.0.0.1", port=5000, debug=False)
