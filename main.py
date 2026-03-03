from flask import Flask, render_template, request, redirect, session, url_for
from tinydb import TinyDB, Query
import requests
from jinja2 import ChoiceLoader, FileSystemLoader
import traceback

app = Flask(__name__)
app.config["SECRET_KEY"] = "hulkulkal"

app.jinja_loader = ChoiceLoader([
    FileSystemLoader("templates"),
    FileSystemLoader("admin-templates")
])

db_users = TinyDB("users.json")
db_reservations = TinyDB("reservations.json")

User = Query()
Reservation = Query()

ADMIN_FIRST_NAME = "Mai"
ADMIN_LAST_NAME = "Kolerič"
ADMIN_PASSWORD = "admin123"


def get_current_user():
    uid = session.get("user_id")
    if uid is None:
        return None
    return db_users.get(doc_id=uid)


def require_admin():
    return session.get("is_admin") is True


@app.route("/")
def landing():
    quote = {"text": "Vztrajaj, tudi ko je težko.", "author": "Neznan"}
    try:
        r = requests.get("https://zenquotes.io/api/random", timeout=2)
        data = r.json()
        if isinstance(data, list) and data:
            quote["text"] = data[0].get("q", quote["text"])
            quote["author"] = data[0].get("a", quote["author"])
    except Exception:
        pass
    return render_template("index.html", quote=quote)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        new_user = {
            "first_name": request.form["first_name"],
            "last_name": request.form["last_name"],
            "age": int(request.form["age"]),
            "experience": request.form["experience"],
            "split": request.form["split"],
            "gym_name": request.form["gym_name"],
            "location": request.form["location"],
            "password": request.form["password"],
            "contact": request.form["contact"],
            "goals": ""
        }
        user_id = db_users.insert(new_user)
        session.clear()
        session["user_id"] = user_id
        session["is_admin"] = False
        return redirect(url_for("dashboard"))
    return render_template("register.html")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        first = request.form.get("first_name", "")
        last = request.form.get("last_name", "")
        password = request.form.get("password", "")

        if first == ADMIN_FIRST_NAME and last == ADMIN_LAST_NAME and password == ADMIN_PASSWORD:
            session.clear()
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))

        return render_template("a-login.html", error="Napačni podatki.")

    return render_template("a-login.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        first = request.form["first_name"]
        last = request.form["last_name"]
        password = request.form["password"]

        if first == ADMIN_FIRST_NAME and last == ADMIN_LAST_NAME and password == ADMIN_PASSWORD:
            session.clear()
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))

        users = db_users.search(
            (User.first_name == first) &
            (User.last_name == last) &
            (User.password == password)
        )
        if users:
            user = users[0]
            session.clear()
            session["user_id"] = user.doc_id
            session["is_admin"] = False
            return redirect(url_for("dashboard"))

        return "Napaka pri prijavi."
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/dashboard")
def dashboard():
    if require_admin():
        return redirect(url_for("admin_dashboard"))
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))
    return render_template("dashboard.html", user=user)


@app.route("/admin")
def admin_dashboard():
    if not require_admin():
        return redirect(url_for("admin_login"))
    return render_template("a-dashboard.html")


@app.route("/users", methods=["GET", "POST"])
def users():
    if require_admin():
        return redirect(url_for("admin_users"))
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    all_users = db_users.all()
    for u in all_users:
        u["id"] = u.doc_id
    filtered = all_users

    if request.method == "POST":
        split = request.form.get("split")
        loc = request.form.get("location")
        age = request.form.get("age")

        if split:
            filtered = [u for u in filtered if u.get("split") == split]
        if loc:
            filtered = [u for u in filtered if u.get("location") == loc]
        if age:
            tmp = []
            for u in filtered:
                a = u.get("age", 0)
                if age == "14-18" and 14 <= a <= 18:
                    tmp.append(u)
                if age == "18-25" and 18 < a <= 25:
                    tmp.append(u)
                if age == "25+" and a > 25:
                    tmp.append(u)
            filtered = tmp

    return render_template("users.html", users=filtered)


@app.route("/goals", methods=["GET", "POST"])
def goals():
    if require_admin():
        return redirect(url_for("admin_dashboard"))
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":
        db_users.update({"goals": request.form.get("goals", "")}, doc_ids=[user.doc_id])
        return redirect(url_for("dashboard"))
    return render_template("goals.html", user=user)


@app.route("/reservations", methods=["GET", "POST"])
def reservations():
    if require_admin():
        return redirect(url_for("admin_reservations"))
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":
        db_reservations.insert({
            "user_id": user.doc_id,
            "name": f"{user['first_name']} {user['last_name']}",
            "gym_name": user.get("gym_name", ""),
            "location": user.get("location", ""),
            "date": request.form["date"],
            "time": request.form["time"],
            "note": request.form.get("note", "")
        })
        return redirect(url_for("reservations"))

    res = db_reservations.search(Reservation.user_id == user.doc_id)
    return render_template("reservations.html", user=user, reservations=res)


@app.route("/settings", methods=["GET", "POST"])
def settings():
    if require_admin():
        return redirect(url_for("admin_dashboard"))
    user = get_current_user()
    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":
        db_users.update({
            "contact": request.form.get("contact", ""),
            "gym_name": request.form.get("gym_name", ""),
            "location": request.form.get("location", "")
        }, doc_ids=[user.doc_id])
        return redirect(url_for("dashboard"))

    return render_template("settings.html", user=user)


@app.route("/admin/settings", methods=["GET"])
def admin_settings():
    if not require_admin():
        return redirect(url_for("admin_login"))
    return render_template("a-settings.html")


@app.route("/admin/users")
def admin_users():
    if not require_admin():
        return redirect(url_for("admin_login"))
    return render_template("a-users.html", users=db_users.all())


@app.route("/admin/gyms")
def admin_gyms():
    if not require_admin():
        return redirect(url_for("admin_login"))

    gyms_map = {}
    for u in db_users.all():
        key = (u.get("gym_name"), u.get("location"))
        if key[0]:
            gyms_map.setdefault(key, {"gym_name": key[0], "location": key[1], "count": 0})
            gyms_map[key]["count"] += 1

    return render_template("gyms.html", gyms=list(gyms_map.values()))


@app.route("/admin/reservations")
def admin_reservations():
    if not require_admin():
        return redirect(url_for("admin_login"))
    return render_template("a-reservations.html", reservations=db_reservations.all())


@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(500)
def internal_error(e):
    return "<pre>" + traceback.format_exc() + "</pre>", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0")
