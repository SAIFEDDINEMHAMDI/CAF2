# routes/affectation_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from utils.db_utils import query_db, execute_db

affectation_bp = Blueprint('affectation', __name__, url_prefix='/affectation')


# -----------------------
# LISTE AVEC PAGINATION + RECHERCHE
# -----------------------
@affectation_bp.route('/')
def liste_affectation():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page
    search = request.args.get('q', '').strip()

    base_query = "SELECT * FROM affectation"
    args = []

    if search:
        base_query += " WHERE nom LIKE ?"
        args.append(f"%{search}%")

    total_row = query_db(f"SELECT COUNT(*) AS count FROM ({base_query}) AS t", args, one=True)
    total = total_row['count'] if total_row else 0

    affectations = query_db(
        f"{base_query} ORDER BY id DESC LIMIT ? OFFSET ?",
        args + [per_page, offset]
    )

    total_pages = (total // per_page) + (1 if total % per_page else 0)
    if total_pages == 0:
        total_pages = 1

    return render_template(
        'affectation_list.html',
        affectations=affectations,
        page=page,
        total_pages=total_pages
    )


# -----------------------
# AJOUTER
# -----------------------
@affectation_bp.route('/ajouter', methods=['POST'])
def ajouter_affectation():
    nom = request.form.get('nom', '').strip()

    if not nom:
        flash("❌ Merci de renseigner un nom.", "error")
        return redirect(url_for('affectation.liste_affectation'))

    user = session.get('user', {}).get('username', 'inconnu')

    execute_db("""
        INSERT INTO affectation (nom)
        VALUES (?)
    """, [nom])

    flash("✅ Affectation ajoutée avec succès", "success")
    return redirect(url_for('affectation.liste_affectation'))


# -----------------------
# MODIFIER
# -----------------------
@affectation_bp.route('/modifier/<id>', methods=['POST'])
def modifier_affectation(id):
    nom = request.form.get('nom', '').strip()
    if not nom:
        flash("❌ Merci de renseigner un nom.", "error")
        return redirect(url_for('affectation.liste_affectation'))

    execute_db("""
        UPDATE affectation
           SET nom = ?
         WHERE id = ?
    """, [nom, id])

    flash("✅ Affectation modifiée avec succès", "success")
    return redirect(url_for('affectation.liste_affectation'))


# -----------------------
# SUPPRIMER
# -----------------------
@affectation_bp.route('/supprimer/<id>', methods=['POST'])
def supprimer_affectation(id):
    execute_db("DELETE FROM affectation WHERE id = ?", [id])
    flash("✅ Affectation supprimée", "success")
    return redirect(url_for('affectation.liste_affectation'))
