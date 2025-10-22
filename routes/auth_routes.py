from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    current_app,
    jsonify,
)
from utils.ldap_utils import ldap_authenticate
from utils.auth_utils import login_required, make_login_response, make_logout_response
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt
import os

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


# ------------------------------------------------------
# 🔐 Page de connexion (GET pour affichage, POST pour login)
# ------------------------------------------------------
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # ==============================
    # 🔹 GET → affiche la page
    # ==============================
    if request.method == "GET":
        # Récupère les raisons éventuelles d'affichage
        reason = request.args.get("reason") or None

        # ✅ Si aucune session → affiche juste la page login
        return render_template("login.html", reason=reason)

    # ==============================
    # 🔹 POST → tentative de connexion
    # ==============================
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    if not username or not password:
        flash("⚠️ Veuillez saisir vos identifiants.", "warning")
        return redirect(url_for("auth.login"))

    try:
        # 🔸 Mode d’authentification : AD (LDAP) ou LOCAL
        auth_mode = os.environ.get("AUTH_MODE", "AD").upper()
        user_info = None

        # ==============================
        # 🟢 MODE LDAP / AD
        # ==============================
        if auth_mode == "AD":
            try:
                user_info = ldap_authenticate(username, password)
            except Exception as e:
                current_app.logger.warning(f"⚠️ LDAP indisponible : {e}")
                flash("⚠️ Serveur AD indisponible. Mode LOCAL activé.", "warning")

        # ==============================
        # 🟡 MODE LOCAL (fallback)
        # ==============================
        if not user_info and auth_mode == "LOCAL":
            local_users = {
                "admin": {
                    "password": "admin123",
                    "prenom": "Admin",
                    "nom": "Local",
                    "email": "admin@local",
                },
                "ahmed": {
                    "password": "ahmed123",
                    "prenom": "Ahmed",
                    "nom": "Boukhtioua",
                    "email": "ahmed@biat.local",
                },
            }

            local_user = local_users.get(username)
            if local_user and local_user["password"] == password:
                user_info = {
                    "username": username,
                    "prenom": local_user["prenom"],
                    "nom": local_user["nom"],
                    "email": local_user["email"],
                    "role": "admin",
                }

        # ==============================
        # ✅ Connexion réussie
        # ==============================
        if user_info:
            payload = {
                "username": user_info.get("username", username),
                "prenom": user_info.get("prenom", ""),
                "nom": user_info.get("nom", ""),
                "email": user_info.get("email", ""),
                "role": user_info.get("role", "user"),
            }

            session["user"] = payload
            prenom = payload.get("prenom", "")
            nom = payload.get("nom", "")
            display_name = f"{prenom} {nom}".strip() or username

            flash(f"✅ Bienvenue {display_name} !", "success")

            # ✅ Création du JWT + Cookie sécurisé
            return make_login_response(
                target_url=url_for("projet.liste_demandes"),
                identity=payload["username"],
                claims=payload,
            )

        # ❌ Identifiants invalides
        flash("❌ Échec de la connexion. Identifiants invalides.", "error")
        return redirect(url_for("auth.login"))

    except Exception as e:
        current_app.logger.error(f"[AUTH] Erreur générale : {e}")
        flash("❌ Erreur lors de la connexion.", "error")
        return redirect(url_for("auth.login"))


# ------------------------------------------------------
# 🚪 Déconnexion utilisateur
# ------------------------------------------------------
@auth_bp.route("/logout")
@login_required
def logout():
    """
    Supprime la session et les cookies JWT,
    puis redirige vers la page de login avec le message 'Déconnexion réussie'.
    """
    session.clear()
    return make_logout_response(url_for("auth.login", reason="logout"))


# ------------------------------------------------------
# ⚠️ Redirection session expirée (appelée depuis middleware)
# ------------------------------------------------------
@auth_bp.route("/expired")
def expired():
    """
    Redirige vers la page de login avec le message 'Session expirée'.
    (Utilisée depuis app.before_request)
    """
    session.clear()
    return redirect(url_for("auth.login", reason="expired"))
# ------------------------------------------------------
# 🧪 Debug : Afficher contenu du token (facultatif)
# ------------------------------------------------------
@auth_bp.route("/token_info")
def token_info():
    """Affiche le contenu du JWT si présent, pour vérification rapide."""
    try:
        verify_jwt_in_request()
        identity = get_jwt_identity()
        claims = get_jwt()
        return (
            jsonify(
                {
                    "username": identity,
                    "prenom": claims.get("prenom"),
                    "nom": claims.get("nom"),
                    "email": claims.get("email"),
                    "role": claims.get("role"),
                    "exp": claims.get("exp"),
                }
            ),
            200,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 401
