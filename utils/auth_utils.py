# ==========================================
# 🔐 utils/auth_utils.py
# ==========================================
import os
from datetime import timedelta
from functools import wraps
from flask import (
    request, redirect, url_for, flash, g, make_response, session
)
from flask_jwt_extended import (
    JWTManager,
    verify_jwt_in_request,
    get_jwt,
    get_jwt_identity,
    create_access_token,
    set_access_cookies,
    unset_jwt_cookies,
)


# ==========================================
# ⚙️ Initialisation du JWT
# ==========================================
def init_jwt(app):
    """
    Configure Flask-JWT-Extended pour gérer les tokens JWT
    dans des cookies HttpOnly sécurisés.
    """
    app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", app.secret_key or "jwt-dev-secret")
    app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
    app.config["JWT_COOKIE_SECURE"] = False   # ⚠️ Mettre True en production HTTPS
    app.config["JWT_COOKIE_SAMESITE"] = "Lax"
    app.config["JWT_COOKIE_CSRF_PROTECT"] = False
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(
        minutes=int(os.environ.get("JWT_ACCESS_MINUTES", 15))  # ⏰ Durée : 15 minutes
    )

    jwt = JWTManager(app)

    # ---------- Gestion des erreurs ----------
    @jwt.unauthorized_loader
    def unauthorized_callback(reason):
        flash("⚠️ Session requise. Veuillez vous reconnecter.", "warning")
        resp = make_response(redirect(url_for("auth.login", expired="true")))
        unset_jwt_cookies(resp)
        session.clear()
        return resp

    @jwt.invalid_token_loader
    def invalid_callback(reason):
        flash("⚠️ Jeton invalide. Veuillez vous reconnecter.", "warning")
        resp = make_response(redirect(url_for("auth.login", expired="true")))
        unset_jwt_cookies(resp)
        session.clear()
        return resp

    @jwt.expired_token_loader
    def expired_callback(jwt_header, jwt_payload):
        """
        Appelé automatiquement quand le JWT est expiré.
        """
        # 1️⃣ Toast + Flash
        flash("⏰ Votre session a expiré. Veuillez vous reconnecter.", "warning")

        # 2️⃣ Redirection vers /auth/login avec paramètre visible
        login_url = url_for("auth.login", expired="true")

        # 3️⃣ Supprime le cookie JWT + redirige proprement
        resp = make_response(redirect(login_url))
        unset_jwt_cookies(resp)
        session.clear()
        return resp

    return jwt


# ==========================================
# 🧱 Décorateur login_required
# ==========================================
def login_required(view_func):
    """
    Vérifie la validité du JWT avant d'autoriser l'accès à la route.
    Si le token est invalide ou expiré -> redirige vers /auth/login
    """
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        try:
            # Vérifie présence + validité du JWT
            verify_jwt_in_request()
            identity = get_jwt_identity()
            claims = get_jwt()

            # Injecter les infos utilisateur dans g.user + session
            g.user = {
                "username": identity,
                "prenom": claims.get("prenom"),
                "nom": claims.get("nom"),
                "email": claims.get("email"),
                "role": claims.get("role", "user"),
            }

            # Synchroniser avec session pour affichage UI
            session["user"] = g.user
            return view_func(*args, **kwargs)

        except Exception:
            flash("⚠️ Session expirée ou non authentifiée. Veuillez vous reconnecter.", "warning")
            resp = make_response(redirect(url_for("auth.login", expired="true")))
            unset_jwt_cookies(resp)
            session.clear()
            return resp

    return wrapper


# ==========================================
# 🪪 Création du token + login
# ==========================================
def make_login_response(target_url: str, identity: str, claims: dict):
    """
    Crée un token JWT et le stocke dans un cookie HttpOnly.
    """
    token = create_access_token(identity=identity, additional_claims=claims)
    resp = make_response(redirect(target_url))
    set_access_cookies(resp, token)

    # Garder aussi les infos dans la session (pour l’UI)
    session["user"] = {
        "username": claims.get("username", identity),
        "prenom": claims.get("prenom", ""),
        "nom": claims.get("nom", ""),
        "email": claims.get("email", ""),
        "role": claims.get("role", "user"),
    }

    return resp


# ==========================================
# 🚪 Déconnexion (suppression du token)
# ==========================================
def make_logout_response(login_url: str):
    """
    Supprime le cookie JWT et redirige vers la page de login.
    """
    resp = make_response(redirect(login_url))
    unset_jwt_cookies(resp)
    session.clear()
    return resp


# ==========================================
# 🌐 Middleware global
# ==========================================
def register_jwt_protection(app):
    """
    Bloque automatiquement toutes les routes sauf /auth/*
    si l'utilisateur n'est pas authentifié.
    """
    @app.before_request
    def global_auth_protection():
        # Routes publiques
        public_paths = [
            "/auth/login",
            "/auth/token_info",
            "/auth/logout",
            "/static",
            "/favicon.ico",
        ]
        if any(request.path.startswith(p) for p in public_paths):
            return

        # Vérifie JWT avant d’entrer dans la route
        try:
            verify_jwt_in_request(optional=False)
        except Exception:
            flash("⚠️ Veuillez vous reconnecter pour continuer.", "warning")
            session.clear()
            resp = make_response(redirect(url_for("auth.login", expired="true")))
            unset_jwt_cookies(resp)
            return resp
