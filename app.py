import os
import sqlite3
from datetime import datetime
from functools import wraps

from authlib.integrations.flask_client import OAuth
from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
import stripe

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "database.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "troque-esta-chave")
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

PRICES = {
    "Solo": {"old": 25.0, "new": 22.5, "env": "STRIPE_PRICE_SOLO"},
    "Budget": {"old": 40.0, "new": 36.0, "env": "STRIPE_PRICE_BUDGET"},
    "Creator": {"old": 68.0, "new": 61.2, "env": "STRIPE_PRICE_CREATOR"},
    "Studio": {"old": 112.0, "new": 100.8, "env": "STRIPE_PRICE_STUDIO"},
}


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT,
            google_id TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS creations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            email TEXT NOT NULL,
            file_name TEXT NOT NULL,
            backup INTEGER DEFAULT 0,
            language TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            author_name TEXT NOT NULL,
            author_doc TEXT NOT NULL,
            owner_name TEXT NOT NULL,
            owner_doc TEXT NOT NULL,
            owner_share INTEGER NOT NULL,
            plan TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """
    )
    db.commit()


with app.app_context():
    init_db()


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return wrapper


oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


def brl(value):
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@app.context_processor
def inject_globals():
    return {"prices": PRICES, "brl": brl, "current_user": session.get("user_name")}


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/cadastro", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        db = get_db()
        exists = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if exists:
            flash("Este e-mail já está cadastrado.")
            return redirect(url_for("register"))
        db.execute(
            "INSERT INTO users(name,email,password_hash,created_at) VALUES(?,?,?,?)",
            (name, email, generate_password_hash(password), datetime.utcnow().isoformat()),
        )
        db.commit()
        flash("Conta criada com sucesso. Faça login.")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user or not user["password_hash"] or not check_password_hash(user["password_hash"], password):
            flash("Credenciais inválidas.")
            return redirect(url_for("login"))
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["user_email"] = user["email"]
        return redirect(url_for("protect_creation"))
    return render_template("login.html")


@app.route("/login/google")
def google_login():
    redirect_uri = url_for("google_callback", _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route("/auth/google/callback")
def google_callback():
    token = google.authorize_access_token()
    user_info = token.get("userinfo")
    if not user_info:
        flash("Falha no login com Google.")
        return redirect(url_for("login"))

    email = user_info["email"].lower()
    name = user_info.get("name", "Usuário Google")
    google_id = user_info.get("sub")
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

    if not user:
        db.execute(
            "INSERT INTO users(name,email,google_id,created_at) VALUES(?,?,?,?)",
            (name, email, google_id, datetime.utcnow().isoformat()),
        )
        db.commit()
        user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["user_email"] = user["email"]
    return redirect(url_for("protect_creation"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/proteja", methods=["GET", "POST"])
@login_required
def protect_creation():
    if request.method == "POST":
        db = get_db()
        plan = request.form["plan"]
        db.execute(
            """
            INSERT INTO creations(
                user_id,email,file_name,backup,language,title,description,
                author_name,author_doc,owner_name,owner_doc,owner_share,plan,created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                session.get("user_id"),
                request.form["email"],
                request.form["file_name"],
                1 if request.form.get("backup") else 0,
                request.form["language"],
                request.form["title"],
                request.form.get("description"),
                request.form["author_name"],
                request.form["author_doc"],
                request.form["owner_name"],
                request.form["owner_doc"],
                int(request.form["owner_share"]),
                plan,
                datetime.utcnow().isoformat(),
            ),
        )
        db.commit()

        price_id = os.getenv(PRICES[plan]["env"], "")
        if not stripe.api_key or not price_id:
            flash("Cadastro salvo. Configure Stripe no .env para redirecionar checkout.")
            return redirect(url_for("protect_creation"))

        checkout_session = stripe.checkout.Session.create(
            line_items=[{"price": price_id, "quantity": 1}],
            mode="payment",
            success_url=url_for("protect_creation", _external=True) + "?status=sucesso",
            cancel_url=url_for("protect_creation", _external=True) + "?status=cancelado",
            locale="pt-BR",
        )
        return redirect(checkout_session.url, code=303)

    return render_template("protect.html")


if __name__ == "__main__":
    app.run(debug=True)
