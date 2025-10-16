# routes/complexite_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from utils.db_utils import query_db, execute_db

complexite_bp = Blueprint('complexite', __name__, url_prefix='/complexite')


# -----------------------
# LISTE AVEC PAGINATION + RECHERCHE
# -----------------------
@complexite_bp.route('/')
def liste_complexite():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page
    search = request.args.get('q', '').strip()

    base_query = "SELECT * FROM complexite"
    args = []
    if search:
        base_query += """
            WHERE libelle LIKE ?
               OR type_libelle LIKE ?
               OR valeur_libelle LIKE ?
               OR CAST(ponderation AS TEXT) LIKE ?
        """
        like = f"%{search}%"
        args.extend([like, like, like, like])

    # total
    total_row = query_db(f"SELECT COUNT(*) AS count FROM ({base_query}) AS t", args, one=True)
    total = total_row['count'] if total_row else 0

    # page
    complexites = query_db(
        f"{base_query} ORDER BY idate DESC, udate DESC LIMIT ? OFFSET ?",
        args + [per_page, offset]
    )

    total_pages = (total // per_page) + (1 if total % per_page else 0)
    if total_pages == 0:
        total_pages = 1

    return render_template(
        'complexite_list.html',
        complexites=complexites,
        page=page,
        total_pages=total_pages
    )


# -----------------------
# AJOUTER
# -----------------------
@complexite_bp.route('/ajouter', methods=['POST'])
def ajouter_complexite():
    libelle = request.form.get('libelle', '').strip()
    type_libelle = request.form.get('type_libelle', '').strip()
    valeur_libelle = request.form.get('valeur_libelle', '').strip()
    ponderation = request.form.get('ponderation', '').strip()
    if not libelle or not type_libelle or not valeur_libelle or not ponderation:
        flash("❌ Merci de remplir tous les champs.", "error")
        return redirect(url_for('complexite.liste_complexite'))

    user = session.get('user', {}).get('username', 'inconnu')

    execute_db("""
        INSERT INTO complexite (libelle, type_libelle, valeur_libelle, ponderation, iuser, idate, uuser, udate)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, CURRENT_TIMESTAMP)
    """, [libelle, type_libelle, valeur_libelle, ponderation, user, user])

    flash("✅ Complexité ajoutée avec succès", "success")
    return redirect(url_for('complexite.liste_complexite'))


# -----------------------
# MODIFIER
# -----------------------
@complexite_bp.route('/modifier/<id>', methods=['POST'])
def modifier_complexite(id):
    libelle = request.form.get('libelle', '').strip()
    type_libelle = request.form.get('type_libelle', '').strip()
    valeur_libelle = request.form.get('valeur_libelle', '').strip()
    ponderation = request.form.get('ponderation', '').strip()
    if not libelle or not type_libelle or not valeur_libelle or not ponderation:
        flash("❌ Merci de remplir tous les champs.", "error")
        return redirect(url_for('complexite.liste_complexite'))

    user = session.get('user', {}).get('username', 'inconnu')

    execute_db("""
        UPDATE complexite
           SET libelle = ?,
               type_libelle = ?,
               valeur_libelle = ?,
               ponderation = ?,
               uuser = ?,
               udate = CURRENT_TIMESTAMP
         WHERE id = ?
    """, [libelle, type_libelle, valeur_libelle, ponderation, user, id])

    flash("✅ Complexité mise à jour", "success")
    return redirect(url_for('complexite.liste_complexite'))


# -----------------------
# SUPPRIMER
# -----------------------
@complexite_bp.route('/supprimer/<id>', methods=['POST'])
def supprimer_complexite(id):
    execute_db("DELETE FROM complexite WHERE id = ?", [id])
    flash("✅ Complexité supprimée", "success")
    return redirect(url_for('complexite.liste_complexite'))


# -----------------------
# ROUTES AJAX (DÉPENDANCES)
# -----------------------

# Types distincts pour un libellé donné
@complexite_bp.route('/get_types/<libelle>')
def get_types(libelle):
    rows = query_db(
        "SELECT DISTINCT type_libelle FROM complexite WHERE libelle = ? ORDER BY type_libelle",
        [libelle]
    )
    return jsonify({"types": [r["type_libelle"] for r in rows]})


# Valeurs distinctes pour un couple (libellé, type_libelle)
@complexite_bp.route('/get_valeurs/<libelle>/<type_libelle>')
def get_valeurs(libelle, type_libelle):
    rows = query_db(
        "SELECT DISTINCT valeur_libelle FROM complexite WHERE libelle = ? AND type_libelle = ? ORDER BY valeur_libelle",
        [libelle, type_libelle]
    )
    return jsonify({"valeurs": [r["valeur_libelle"] for r in rows]})


# Libellés distincts
@complexite_bp.route('/get_libelles')
def get_libelles():
    rows = query_db("SELECT DISTINCT libelle FROM complexite ORDER BY libelle")
    libelles = [row['libelle'] for row in rows]
    return jsonify({"libelles": libelles})
