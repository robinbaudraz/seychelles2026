from __future__ import annotations

import os
import secrets
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "instance" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{BASE_DIR / 'instance' / 'trip.db'}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="participant")


class DayPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day_date = db.Column(db.Date, nullable=False, unique=True)
    destination = db.Column(db.String(120), nullable=False)
    summary = db.Column(db.Text, nullable=True)
    activities = db.relationship("Activity", backref="day", cascade="all, delete-orphan", lazy=True)


class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    day_id = db.Column(db.Integer, db.ForeignKey("day_plan.id"), nullable=False)
    period = db.Column(db.String(20), nullable=False)  # matin/apres-midi/soir/autre
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    schedule = db.Column(db.String(120))
    provider = db.Column(db.String(200))
    link = db.Column(db.String(500))
    status = db.Column(db.String(20), nullable=False, default="option")
    reservation_ref = db.Column(db.String(120))
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    location_label = db.Column(db.String(255))

    attachments = db.relationship("Attachment", backref="activity", cascade="all, delete-orphan", lazy=True)
    photos = db.relationship("Photo", backref="activity", cascade="all, delete-orphan", lazy=True)


class Attachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey("activity.id"), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(255), nullable=False, unique=True)
    kind = db.Column(db.String(20), nullable=False, default="document")


class Photo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey("activity.id"), nullable=False)
    caption = db.Column(db.String(255))
    stored_name = db.Column(db.String(255), nullable=False, unique=True)


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


def is_admin() -> bool:
    return current_user.is_authenticated and current_user.role == "admin"


def require_admin():
    if not is_admin():
        flash("Action réservée à l'admin.", "error")
        return False
    return True


def save_upload(file_storage) -> tuple[str, str]:
    filename = secure_filename(file_storage.filename)
    token = secrets.token_hex(8)
    stored = f"{token}_{filename}"
    file_storage.save(UPLOAD_DIR / stored)
    return filename, stored


def seed_data():
    if not User.query.first():
        admin = User(username="admin", password_hash=generate_password_hash("admin1234"), role="admin")
        p1 = User(username="alice", password_hash=generate_password_hash("voyage2026"), role="participant")
        p2 = User(username="bob", password_hash=generate_password_hash("voyage2026"), role="participant")
        p3 = User(username="claire", password_hash=generate_password_hash("voyage2026"), role="participant")
        p4 = User(username="david", password_hash=generate_password_hash("voyage2026"), role="participant")
        db.session.add_all([admin, p1, p2, p3, p4])

    if not DayPlan.query.first():
        start = date(2026, 10, 7)
        end = date(2026, 10, 24)
        current = start
        while current <= end:
            if current <= date(2026, 10, 8):
                destination = "Dubaï"
            elif current == date(2026, 10, 9):
                destination = "Transfert Dubaï → Mahé"
            elif current >= date(2026, 10, 23):
                destination = "Seychelles / retour"
            else:
                destination = "Seychelles"
            db.session.add(DayPlan(day_date=current, destination=destination, summary=""))
            current += timedelta(days=1)

    db.session.commit()


@app.route("/")
@login_required
def index():
    days = DayPlan.query.order_by(DayPlan.day_date.asc()).all()
    counts = db.session.query(Activity.status, func.count(Activity.id)).group_by(Activity.status).all()
    status_counts = {k: v for k, v in counts}
    return render_template("index.html", days=days, status_counts=status_counts, is_admin=is_admin())


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("index"))
        flash("Identifiants invalides.", "error")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/days/add", methods=["POST"])
@login_required
def add_day():
    if not require_admin():
        return redirect(url_for("index"))
    try:
        d = datetime.strptime(request.form["day_date"], "%Y-%m-%d").date()
    except ValueError:
        flash("Date invalide", "error")
        return redirect(url_for("index"))
    if DayPlan.query.filter_by(day_date=d).first():
        flash("Cette date existe déjà.", "error")
        return redirect(url_for("index"))
    db.session.add(DayPlan(day_date=d, destination=request.form.get("destination", ""), summary=request.form.get("summary", "")))
    db.session.commit()
    flash("Journée ajoutée.", "success")
    return redirect(url_for("index"))


@app.route("/activities/add", methods=["POST"])
@login_required
def add_activity():
    if not require_admin():
        return redirect(url_for("index"))

    activity = Activity(
        day_id=int(request.form["day_id"]),
        period=request.form.get("period", "autre"),
        title=request.form.get("title", ""),
        description=request.form.get("description"),
        schedule=request.form.get("schedule"),
        provider=request.form.get("provider"),
        link=request.form.get("link"),
        status=request.form.get("status", "option"),
        reservation_ref=request.form.get("reservation_ref"),
        location_label=request.form.get("location_label"),
        lat=float(request.form["lat"]) if request.form.get("lat") else None,
        lng=float(request.form["lng"]) if request.form.get("lng") else None,
    )
    db.session.add(activity)
    db.session.flush()

    for f in request.files.getlist("documents"):
        if f and f.filename:
            original, stored = save_upload(f)
            db.session.add(Attachment(activity_id=activity.id, original_name=original, stored_name=stored, kind="document"))

    for f in request.files.getlist("photos"):
        if f and f.filename:
            _, stored = save_upload(f)
            db.session.add(Photo(activity_id=activity.id, caption=request.form.get("photo_caption"), stored_name=stored))

    db.session.commit()
    flash("Activité ajoutée.", "success")
    return redirect(url_for("index"))


@app.route("/reservations")
@login_required
def reservations():
    activities = Activity.query.order_by(Activity.status.asc(), Activity.day_id.asc()).all()
    return render_template("reservations.html", activities=activities)


@app.route("/map")
@login_required
def map_view():
    activities = Activity.query.filter(Activity.lat.isnot(None), Activity.lng.isnot(None)).all()
    points = [
        {
            "title": a.title,
            "date": a.day.day_date.strftime("%d/%m/%Y"),
            "destination": a.day.destination,
            "lat": a.lat,
            "lng": a.lng,
            "status": a.status,
            "link": a.link,
            "location": a.location_label,
        }
        for a in activities
    ]
    return render_template("map.html", points=points)


@app.route("/uploads/<path:stored_name>")
@login_required
def private_file(stored_name: str):
    return send_from_directory(UPLOAD_DIR, stored_name, as_attachment=False)


@app.route("/api/geocode")
@login_required
def geocode():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])
    resp = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": query, "format": "json", "limit": 5},
        headers={"User-Agent": "seychelles2026-trip-planner"},
        timeout=10,
    )
    resp.raise_for_status()
    payload = [
        {
            "name": item.get("display_name"),
            "lat": item.get("lat"),
            "lon": item.get("lon"),
        }
        for item in resp.json()
    ]
    return jsonify(payload)


@app.route("/admin/users", methods=["GET", "POST"])
@login_required
def admin_users():
    if not require_admin():
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "participant")
        if not username or not password:
            flash("Username et mot de passe requis.", "error")
        elif User.query.filter_by(username=username).first():
            flash("Utilisateur déjà existant.", "error")
        else:
            db.session.add(User(username=username, password_hash=generate_password_hash(password), role=role))
            db.session.commit()
            flash("Utilisateur ajouté.", "success")

    users = User.query.order_by(User.username.asc()).all()
    return render_template("users.html", users=users)


@app.route("/admin/users/<int:user_id>/role", methods=["POST"])
@login_required
def update_role(user_id: int):
    if not require_admin():
        return redirect(url_for("admin_users"))

    user = db.session.get(User, user_id)
    if user:
        user.role = request.form.get("role", user.role)
        db.session.commit()
        flash("Rôle mis à jour.", "success")
    return redirect(url_for("admin_users"))


@app.cli.command("init-db")
def init_db_command():
    db.create_all()
    seed_data()
    print("Base initialisée.")


with app.app_context():
    db.create_all()
    seed_data()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
