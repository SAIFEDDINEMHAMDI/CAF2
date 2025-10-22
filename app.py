# ==========================================
# app.py — Application principale Flask BIAT (JWT)
# Version avec déconnexion après inactivité réelle (15 min)
# ==========================================
from dotenv import load_dotenv
import os
from flask import Flask, request, redirect, url_for, session, flash, render_template, jsonify
from datetime import datetime, timezone, timedelta
import uuid
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash

# ----------------- IMPORT UTILITAIRES -----------------
from utils.db_utils import execute_db, init_db, query_db
from utils.auth_utils import login_required, init_jwt, register_jwt_protection
from services.wsjf_calculator import calculate_wsjf
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt

# 🔒 Décorateurs utilitaires
from utils.decorators import readonly_if_user

# ----------------- IMPORT DES BLUEPRINTS -----------------
from routes.auth_routes import auth_bp
from routes.collaborateurs_routes import collab_bp
from routes.caf import caf_bp
from routes.programmes_routes import programmes_bp
from routes.projets_routes import projets_bp
from routes.import_excel_routes import import_excel_bp
from routes.complexite_routes import complexite_bp
from routes.profils_routes import profils_bp
from routes.projet_routes import projet_bp
from routes.categorie_routes import categorie_bp
from routes.statut_routes import statut_bp
from routes.statut_demande import statut_demande_bp
from routes.phase_routes import phase_bp
from routes.domaines_routes import domaines_bp
from routes.programme_config_routes import programme_config_bp
from routes.regles_complexite_routes import regles_complexite_bp
from routes.affectation_routes import affectation_bp
from routes.accompagnement_routes import accompagnement_bp
from routes.recrutement_routes import recrutement_bp
from routes.sous_domaine_collaborateur import sous_domaine_bp  # ✅ Nouveau blueprint

# ✅ Blueprints collaborateur
from routes.valeurs_metier_routes import valeurs_bp
from routes.demande_it import demande_it_bp
from routes.import_excel_it_routes import import_excel_it_bp

# ==========================================
# 🔹 CONFIGURATION APP
# ==========================================
load_dotenv()
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "votre_cle_secrete_super_securisee")

# 🔒 Cookies de session (UI)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE=os.environ.get("COOKIE_SAMESITE", "Lax"),
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "false").lower() == "true",
)

# ✅ Init DB
init_db()

# 🔐 Init JWT
jwt = init_jwt(app)

# 🔒 Protection automatique
register_jwt_protection(app)

# 📂 Uploads
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 🔁 Sessions — expiration après 15 min d’inactivité réelle
app.config["SESSION_PERMANENT"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=15)

# ==========================================
# 👤 Injecte automatiquement l’utilisateur dans les templates
# ==========================================
@app.context_processor
def inject_ui_user():
    try:
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
        if identity:
            claims = get_jwt()
            return {
                "ui_user": {
                    "username": identity,
                    "prenom": claims.get("prenom", ""),
                    "nom": claims.get("nom", ""),
                    "email": claims.get("email", ""),
                    "role": claims.get("role", "user"),
                }
            }
    except Exception:
        pass

    user = session.get("user")
    if user:
        return {"ui_user": user}
    return {"ui_user": None}


# ==========================================
# ⚠️ MIDDLEWARE — Gestion automatique des sessions expirées
# ==========================================
@app.before_request
def handle_expired_session():
    """
    Vérifie si le token JWT est expiré avant chaque requête.
    Si oui → redirige vers /auth/expired
    """
    exempt_routes = [
        "auth.login", "auth.logout", "auth.token_info",
        "auth.expired", "ping", "static"
    ]

    if request.endpoint in exempt_routes or request.endpoint is None:
        return

    try:
        verify_jwt_in_request(optional=True)
        claims = get_jwt()
        if claims:
            exp = claims.get("exp")
            if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
                session.clear()
                return redirect(url_for("auth.expired"))

        if not get_jwt_identity() and not session.get("user"):
            session.clear()
            return redirect(url_for("auth.expired"))
    except Exception:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"session_expired": True}), 401
        session.clear()
        return redirect(url_for("auth.expired"))


# ==========================================
# 🧭 ROUTE KEEPALIVE — maintient la session active si activité
# ==========================================
@app.route("/ping")
def ping():
    """Route appelée automatiquement par le front pour rafraîchir la session."""
    session.modified = True
    return "", 204


# ==========================================
# 🔹 BLUEPRINTS
# ==========================================
for bp in [
    auth_bp, collab_bp, caf_bp, profils_bp, programmes_bp, projets_bp,
    import_excel_bp, complexite_bp, projet_bp, categorie_bp, statut_bp,
    statut_demande_bp, phase_bp, domaines_bp, programme_config_bp,
    regles_complexite_bp, affectation_bp, accompagnement_bp, recrutement_bp,
    sous_domaine_bp,  # ✅ Ajout du blueprint ici
    valeurs_bp, demande_it_bp, import_excel_it_bp,
]:
    app.register_blueprint(bp)


# ==========================================
# 🔸 Gestion des rôles
# ==========================================
def has_role(required_roles):
    from functools import wraps
    roles = [required_roles] if isinstance(required_roles, str) else list(required_roles)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = session.get("user")
            role = (user or {}).get("role")
            if role not in roles:
                flash("❌ Accès refusé (droits insuffisants).", "error")
                return redirect(url_for("projet.liste_demandes"))
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ==========================================
# 🔹 ROUTES GÉNÉRALES
# ==========================================
@app.route("/")
def index():
    try:
        verify_jwt_in_request(optional=True)
        if get_jwt_identity():
            return redirect(url_for("projet.liste_demandes"))
    except Exception:
        pass
    return redirect(url_for("auth.login"))


@app.route("/home")
def home():
    """Page d'accueil redirigeant selon connexion"""
    try:
        verify_jwt_in_request(optional=True)
        if get_jwt_identity():
            return redirect(url_for("projet.liste_demandes"))
    except Exception:
        pass
    return redirect(url_for("auth.login"))


@app.route("/base")
@login_required
def base():
    return render_template("base.html", now=datetime.now)


# ==========================================
# 🔹 INTERFACES DE FORMULAIRES (démo WSJF)
# ==========================================
@app.route("/interface1", methods=["GET", "POST"])
@login_required
def interface1():
    categories = query_db("SELECT * FROM categorie")
    if request.method == "POST":
        date_mep = datetime.strptime(request.form["date_mep"], "%Y-%m-%d").date()
        session["form1"] = {
            "titre": request.form["titre"],
            "description": request.form["description"],
            "type_demande": request.form["type_demande"],
            "date_mep": date_mep.strftime("%Y-%m-%d"),
            "release": request.form["release"],
            "categorie_id": request.form["categorie_id"],
        }
        return redirect(url_for("interface2"))
    return render_template("interface1.html", categorie=categories, now=datetime.now())


# ==========================================
# 🚀 LANCEMENT APP
# ==========================================
if __name__ == "__main__":
    host = "127.0.0.1"
    port = 5000
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    print(f"[APP] 🚀 Projet lancé sur : http://{host}:{port}")
    print(f"[APP] 📂 Dossier uploads : {UPLOAD_FOLDER}")
    app.run(host=host, port=port, debug=True, use_reloader=True)
