# utils/auth_utils.py
import sqlite3
import hashlib
from functools import wraps
from flask import session, redirect, url_for, flash
import os
from contextlib import closing

def hash_password(password):
    return 'sha256$' + hashlib.sha256(password.encode()).hexdigest()

def check_password(hashed, password):
    if hashed.startswith('sha256$'):
        return hashed == hash_password(password)
    return False

def get_user(username):
    database = os.path.join(os.path.dirname(__file__), '..', 'database', 'projets.db')
    with closing(sqlite3.connect(database)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ?", [username])
        return cur.fetchone()

def login_required(role=['user']):
    def decorator(f):
        @wraps(f)
        def wrap(*args, **kwargs):
            if 'user' not in session:
                flash("Veuillez vous connecter.", "danger")
                return redirect(url_for('login'))
            if session['user']['role'] not in role:
                flash("Accès refusé : permissions insuffisantes.", "danger")
                return redirect(url_for('home'))
            return f(*args, **kwargs)
        return wrap
    return decorator