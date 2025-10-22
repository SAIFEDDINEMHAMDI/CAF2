# ==========================================
# app.py — Application principale Flask BIAT (JWT) — version finale fusionnée
# ==========================================
from dotenv import load_dotenv
import os
from flask import Flask, request, redirect, url_for, session, flash, render_template
from datetime import datetime
import uuid
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash

# ----------------- IMPORT UTILITAIRES -----------------
from utils.db_utils import execute_db, init_db, query_db
from utils.auth_utils import login_required, init_jwt, register_jwt_protection
from services.wsjf_calculator import calculate_wsjf
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt

# 🔒 Décorateurs utilitaires
from utils.decorators import readonly_if_user  # protège certaines actions (lecture seule)

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

# 🔁 Sessions
app.config["SESSION_PERMANENT"] = False
app.config["PERMANENT_SESSION_LIFETIME"] = 0
app.config["SESSION_COOKIE_DURATION"] = False

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
# 🔹 BLUEPRINTS
# ==========================================
for bp in [
    auth_bp, collab_bp, caf_bp, profils_bp, programmes_bp, projets_bp,
    import_excel_bp, complexite_bp, projet_bp, categorie_bp, statut_bp,
    statut_demande_bp, phase_bp, domaines_bp, programme_config_bp,
    regles_complexite_bp, affectation_bp, accompagnement_bp, recrutement_bp,
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
            user = session.get('user')
            role = (user or {}).get('role')
            if role not in roles:
                flash("❌ Accès refusé (droits insuffisants).", "error")
                return redirect(url_for('projet.liste_demandes'))
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
# 🔹 INTERFACES DE FORMULAIRES
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

@app.route("/interface2", methods=["GET", "POST"])
@login_required
def interface2():
    if "form1" not in session:
        return redirect(url_for("interface1"))
    if request.method == "POST":
        session["form2"] = request.form.to_dict()
        return redirect(url_for("interface3"))
    return render_template("interface2.html")

@app.route("/interface3", methods=["GET", "POST"])
@login_required
def interface3():
    if "form1" not in session or "form2" not in session:
        return redirect(url_for("interface1"))

    if request.method == "POST":
        project_id = str(uuid.uuid4())
        form1 = session.pop("form1", {})
        form2 = session.pop("form2", {})
        form3 = request.form.to_dict()
        all_data = {**form1, **form2, **form3, "project_id": project_id}

        resultats = calculate_wsjf(all_data)
        score_wsjf = resultats["score_wsjf"]
        complexite = resultats["complexite"]
        jh_estime = resultats["jh_estime"]

        date_mep = all_data.get("date_mep")
        release_info = query_db("""
            SELECT id
            FROM releases
            WHERE ? BETWEEN debut AND fin
            ORDER BY debut DESC LIMIT 1
        """, [date_mep], one=True)
        release_id = release_info["id"] if release_info else None

        execute_db("""
            INSERT INTO projets (id, titre, description, date_mep, score_wsjf,
                                 release_id, categorie_id, statut, duree_estimee_jh, complexite)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            project_id, all_data["titre"], all_data["description"], all_data["date_mep"],
            score_wsjf, release_id, all_data.get("categorie_id"),
            all_data.get("statut", "En attente"), jh_estime, complexite
        ))

        session["project_id"] = project_id
        return redirect(url_for("resultat"))

    return render_template("interface3.html")

@app.route("/resultat")
@login_required
def resultat():
    project_id = session.get("project_id")
    if not project_id:
        return redirect(url_for("interface1"))
    projet = query_db("SELECT * FROM projets WHERE id = ?", [project_id], one=True)
    if not projet:
        return "Projet non trouvé", 404
    return render_template("resultat.html", result=projet)

# ==========================================
# 🔹 ADMINISTRATION / WSJF
# ==========================================
@app.route('/priorites')
@login_required
def priorites():
    filtre_retenu = request.args.get('retenu')
    query = """
        SELECT p.*, c.nom AS categorie 
        FROM projets p
        LEFT JOIN categorie c ON p.categorie_id = c.id
    """
    if filtre_retenu == '1':
        query += " WHERE p.retenu = 1 "
    query += " ORDER BY p.score_wsjf DESC LIMIT 50"
    projets = query_db(query)
    return render_template('priorites.html', projets=projets, filtre_retenu=filtre_retenu)

@app.route('/toggle_retenu/<string:projet_id>', methods=['POST'])
@login_required
@readonly_if_user
def toggle_retenu(projet_id):
    projet = query_db("SELECT retenu FROM projets WHERE id = ?", [projet_id], one=True)
    if projet is None:
        flash("❌ Projet introuvable", "danger")
    else:
        nouveau_statut = 0 if projet['retenu'] else 1
        execute_db("UPDATE projets SET retenu = ? WHERE id = ?", [nouveau_statut, projet_id])
        flash("✅ Statut 'retenu' mis à jour", "success")
    return redirect(url_for('priorites'))

@app.route('/create_admin', methods=['GET', 'POST'])
@login_required
@has_role(['superadmin', 'admin'])
def create_admin():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        role = request.form.get('role', 'admin')
        hashed_password = generate_password_hash(password)
        user_id = str(uuid.uuid4())

        try:
            execute_db("""
                INSERT INTO users (id, username, password, role)
                VALUES (?, ?, ?, ?)
            """, [user_id, username, hashed_password, role])
            flash("✅ Utilisateur créé avec succès.", "success")
            return redirect(url_for('priorites'))
        except Exception as e:
            flash(f"❌ Erreur lors de la création : {e}", "danger")
    return render_template('create_admin.html')

# ==========================================
# 🔹 LANCEMENT APP
# ==========================================
if __name__ == "__main__":
    host = "127.0.0.1"
    port = 5000
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    print(f"[APP] 🚀 Projet lancé sur : http://{host}:{port}")
    print(f"[APP] 📂 Dossier uploads : {UPLOAD_FOLDER}")
    app.run(host=host, port=port, debug=True, use_reloader=True)
