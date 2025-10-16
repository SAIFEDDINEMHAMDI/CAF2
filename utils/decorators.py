# utils/decorators.py
from functools import wraps
from flask import session, redirect, url_for, flash, request

def role_required(*roles):
    """Permet de restreindre une route à certains rôles (admin, superadmin, etc.)."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = session.get("user")
            if not user:
                flash("⚠️ Vous devez être connecté.", "warning")
                return redirect(url_for("login"))

            role = user.get("role")
            if role not in roles:
                flash("🚫 Accès non autorisé.", "danger")
                return redirect(url_for("home"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def readonly_if_user(f):
    """Empêche le rôle 'user' d'exécuter les routes POST/DELETE (lecture seule)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = session.get("user", {})
        role = user.get("role", "")
        if request.method in ['POST', 'DELETE'] and role == 'user':
            flash("🚫 Action non autorisée pour votre profil (lecture seule).", "danger")
            return redirect(request.referrer or url_for("home"))
        return f(*args, **kwargs)
    return decorated_function
