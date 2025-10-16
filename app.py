# app.py
from dotenv import load_dotenv
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime
import uuid
from werkzeug.utils import secure_filename
from services.wsjf_calculator import calculate_wsjf
from utils.db_utils import execute_db, init_db, query_db
from werkzeug.security import generate_password_hash, check_password_hash
from utils.decorators import readonly_if_user  # ✅ pour restreindre certaines actions

# ----------------- IMPORT DES BLUEPRINTS -----------------
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
from routes.statut_demande import  statut_demande_bp
from routes.phase_routes import phase_bp
from routes.domaines_routes import domaines_bp
from routes.programme_config_routes import programme_config_bp
from routes.regles_complexite_routes import regles_complexite_bp
from routes.affectation_routes import affectation_bp
from routes.accompagnement_routes import accompagnement_bp
from routes.recrutement_routes import recrutement_bp
# ----------------- CONFIGURATION -----------------
load_dotenv()
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'votre_cle_secrete_super_securisee')

# Enregistrement des Blueprints
app.register_blueprint(collab_bp)
app.register_blueprint(caf_bp)
app.register_blueprint(profils_bp)
app.register_blueprint(programmes_bp)
app.register_blueprint(projets_bp)
app.register_blueprint(complexite_bp)
app.register_blueprint(import_excel_bp)
app.register_blueprint(projet_bp)
app.register_blueprint(categorie_bp)
app.register_blueprint(statut_bp)
app.register_blueprint(phase_bp)
app.register_blueprint(domaines_bp)
app.register_blueprint(programme_config_bp)
app.register_blueprint(regles_complexite_bp)
app.register_blueprint(affectation_bp)
app.register_blueprint(accompagnement_bp)
app.register_blueprint(recrutement_bp)
app.register_blueprint(statut_demande_bp)
# Gestion des uploads
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialisation DB
init_db()

# ----------------- HELPERS / DÉCORATEURS -----------------
def login_required(func):
    """Décorateur simple pour protéger les routes."""
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'user' not in session:
            flash("🔒 Vous devez être connecté pour accéder à cette page.", "warning")
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    return wrapper


def has_role(required_roles):
    """Décorateur pour restreindre certaines routes à un ou plusieurs rôles."""
    from functools import wraps
    if isinstance(required_roles, str):
        roles = [required_roles]
    else:
        roles = list(required_roles)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = session.get('user')
            if not user or user.get('role') not in roles:
                flash("❌ Accès refusé (droits insuffisants).", "error")
                return redirect(url_for('home'))
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ----------------- ROUTES -----------------
@app.route('/home')
@login_required
def home():
    return render_template('home.html')


# ----------------- LOGIN / LOGOUT -----------------
@app.route('/', methods=['GET', 'POST'])
def login():
    """Page de connexion."""
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        user = query_db("SELECT * FROM users WHERE username = ?", [username], one=True)
        if user:
            stored = user['password'] or ''
            ok = False
            try:
                ok = check_password_hash(stored, password)
            except Exception:
                ok = False

            # ✅ fallback pour tests avec mot de passe non haché
            if not ok and stored == password:
                ok = True

            if ok:
                # ✅ Conversion Row → dict pour éviter AttributeError
                user_dict = dict(user)

                # ✅ Stocker proprement le rôle dans la session
                session['user'] = {
                    'id': user_dict.get('id'),
                    'username': user_dict.get('username'),
                    'role': user_dict.get('role', 'user')
                }

                flash("✅ Connexion réussie", "success")
                return redirect(url_for('projet.liste_demandes'))
            else:
                flash("❌ Nom d'utilisateur ou mot de passe incorrect", "danger")
        else:
            flash("❌ Nom d'utilisateur ou mot de passe incorrect", "danger")

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Déconnexion"""
    session.pop('user', None)
    flash("ℹ️ Vous êtes déconnecté.", "info")
    return redirect(url_for('login'))


# ----------------- INTERFACES MULTI-ÉTAPES -----------------
@app.route('/interface1', methods=['GET', 'POST'])
@login_required
def interface1():
    categorie = query_db("SELECT * FROM categorie")
    if request.method == 'POST':
        date_mep = datetime.strptime(request.form['date_mep'], '%Y-%m-%d').date()
        session['form1'] = {
            'titre': request.form['titre'],
            'description': request.form['description'],
            'type_demande': request.form['type_demande'],
            'date_mep': date_mep.strftime('%Y-%m-%d'),
            'release': request.form['release'],
            'categorie_id': request.form['categorie_id']
        }
        return redirect(url_for('interface2'))
    return render_template('interface1.html', now=datetime.now(), categorie=categorie)


@app.route('/interface2', methods=['GET', 'POST'])
@login_required
def interface2():
    if 'form1' not in session:
        return redirect(url_for('interface1'))
    if request.method == 'POST':
        session['form2'] = request.form.to_dict()
        return redirect(url_for('interface3'))
    return render_template('interface2.html')


@app.route('/interface3', methods=['GET', 'POST'])
@login_required
def interface3():
    if 'form1' not in session or 'form2' not in session:
        return redirect(url_for('interface1'))

    if request.method == 'POST':
        project_id = str(uuid.uuid4())
        form1 = session.pop('form1', {})
        form2 = session.pop('form2', {})
        form3 = request.form.to_dict()
        all_data = {**form1, **form2, **form3, 'project_id': project_id}

        resultats = calculate_wsjf(all_data)
        score_wsjf, complexite, jh_estime = resultats['score_wsjf'], resultats['complexite'], resultats['jh_estime']

        date_mep = all_data.get('date_mep')
        release_info = query_db("""
            SELECT id FROM releases WHERE ? BETWEEN debut AND fin ORDER BY debut DESC LIMIT 1
        """, [date_mep], one=True)
        release_id = release_info['id'] if release_info else None

        try:
            execute_db('''INSERT INTO projets (
                id, titre, description, alignement_strategic, impact_pnb, impact_satisfaction, date_mep,
                conquerir_client, maitrise_couts, attenuation_menaces, creation_opportunites,
                conditions_techniques, deadline_reglementaire, pression_concurrence, echeances_strategiques,
                urgence_obsolescence, dependances_projets, q1, q2, q3, q4, q5, q6, q7, q8, q9, q10,
                score_wsjf, release_id, categorie_id, statut, duree_estimee_jh, complexite)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (project_id, all_data['titre'], all_data['description'], all_data.get('alignement_strategic'),
                 all_data.get('impact_pnb'), all_data.get('impact_satisfaction'), all_data['date_mep'],
                 all_data.get('conquerir_client'), all_data.get('maitrise_couts'),
                 all_data.get('attenuation_menaces'), all_data.get('creation_opportunites'),
                 all_data.get('conditions_techniques'), all_data.get('deadline_reglementaire'),
                 all_data.get('pression_concurrence'), all_data.get('echeances_strategiques'),
                 all_data.get('urgence_obsolescence'), all_data.get('dependances_projets'),
                 all_data.get('q1'), all_data.get('q2'), all_data.get('q3'), all_data.get('q4'),
                 all_data.get('q5'), all_data.get('q6'), all_data.get('q7'), all_data.get('q8'),
                 all_data.get('q9'), all_data.get('q10'),
                 score_wsjf, release_id, all_data.get('categorie_id'),
                 all_data.get('statut', 'En attente'), jh_estime, complexite))
            session['project_id'] = project_id
        except Exception as e:
            return f"Erreur : {e}", 500

        return redirect(url_for('resultat'))

    return render_template('interface3.html')


# ----------------- RESULTATS -----------------
@app.route('/resultat')
@login_required
def resultat():
    project_id = session.get('project_id')
    if not project_id:
        return redirect(url_for('interface1'))
    projet = query_db('SELECT * FROM projets WHERE id = ?', [project_id], one=True)
    if not projet:
        return "Projet non trouvé", 404
    try:
        date_affichee = datetime.strptime(projet['date_mep'], '%Y-%m-%d').strftime('%d/%m/%Y')
    except Exception:
        date_affichee = projet['date_mep']
    return render_template('resultat.html', result=projet, date_mep=date_affichee)


# ----------------- PRIORITES -----------------
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
@readonly_if_user  # ✅ les users ne peuvent plus modifier
def toggle_retenu(projet_id):
    projet = query_db("SELECT retenu FROM projets WHERE id = ?", [projet_id], one=True)
    if projet is None:
        flash("❌ Projet introuvable", "danger")
    else:
        nouveau_statut = 0 if projet['retenu'] else 1
        execute_db("UPDATE projets SET retenu = ? WHERE id = ?", [nouveau_statut, projet_id])
        flash("✅ Statut 'retenu' mis à jour", "success")
    return redirect(url_for('priorites'))


# ----------------- UTILITAIRES ADMIN -----------------
@app.route('/create_admin', methods=['GET', 'POST'])
@login_required
@has_role(['superadmin', 'admin'])
def create_admin():
    """Créer un administrateur via interface (protégé par role)."""
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


# ----------------- MAIN -----------------
if __name__ == '__main__':
    host = "127.0.0.1"
    port = 5000
    print(f"[APP] 🚀 Projet lancé sur : http://{host}:{port}")
    print(f"[APP] 📂 Dossier uploads : {UPLOAD_FOLDER}")
    app.config["TEMPLATES_AUTO_RELOAD"] = True  # 🔁 Recharge auto des templates HTML
    app.run(host=host, port=port, debug=True, use_reloader=True)
