# # routes/valeurs_metier_routes.py
# from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
# from utils.db_utils import query_db, execute_db

# valeurs_bp = Blueprint('valeurs_metier', __name__, url_prefix='/valeurs')


# # -----------------------
# # LISTE AVEC PAGINATION + RECHERCHE
# # -----------------------
# @valeurs_bp.route('/')
# def liste_valeurs():
#     page = request.args.get('page', 1, type=int)
#     per_page = 10
#     offset = (page - 1) * per_page
#     search = request.args.get('q', '').strip()

#     base_query = "SELECT * FROM valeur_metier"
#     args = []
#     if search:
#         base_query += """
#             WHERE libelle LIKE ?
#                OR type_libelle LIKE ?
#                OR valeur_libelle LIKE ?
#                OR CAST(ponderation AS TEXT) LIKE ?
#         """
#         like = f"%{search}%"
#         args.extend([like, like, like, like])

#     # total
#     total_row = query_db(f"SELECT COUNT(*) AS count FROM ({base_query}) AS t", args, one=True)
#     total = total_row['count'] if total_row else 0

#     # page
#     valeurs = query_db(
#         f"{base_query} ORDER BY idate DESC, udate DESC LIMIT ? OFFSET ?",
#         args + [per_page, offset]
#     )

#     total_pages = (total // per_page) + (1 if total % per_page else 0)
#     if total_pages == 0:
#         total_pages = 1

#     return render_template(
#         'valeur_metier_list.html',
#         valeurs=valeurs,
#         page=page,
#         total_pages=total_pages
#     )


# # -----------------------
# # AJOUTER
# # -----------------------
# @valeurs_bp.route('/ajouter', methods=['POST'])
# def ajouter_valeur():
#     libelle = request.form.get('libelle', '').strip()
#     type_libelle = request.form.get('type_libelle', '').strip()
#     valeur_libelle = request.form.get('valeur_libelle', '').strip()
#     ponderation = request.form.get('ponderation', '').strip()
#     if not libelle or not type_libelle or not valeur_libelle or not ponderation:
#         flash("❌ Merci de remplir tous les champs.", "error")
#         return redirect(url_for('valeurs_metier.liste_valeurs'))

#     user = session.get('user', {}).get('username', 'inconnu')

#     execute_db("""
#         INSERT INTO valeur_metier (libelle, type_libelle, valeur_libelle, ponderation, iuser, idate, uuser, udate)
#         VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, CURRENT_TIMESTAMP)
#     """, [libelle, type_libelle, valeur_libelle, ponderation, user, user])

#     flash("✅ Valeur métier ajoutée avec succès", "success")
#     return redirect(url_for('valeurs_metier.liste_valeurs'))


# # -----------------------
# # MODIFIER
# # -----------------------
# @valeurs_bp.route('/modifier/<id>', methods=['POST'])
# def modifier_valeur(id):
#     libelle = request.form.get('libelle', '').strip()
#     type_libelle = request.form.get('type_libelle', '').strip()
#     valeur_libelle = request.form.get('valeur_libelle', '').strip()
#     ponderation = request.form.get('ponderation', '').strip()
#     if not libelle or not type_libelle or not valeur_libelle or not ponderation:
#         flash("❌ Merci de remplir tous les champs.", "error")
#         return redirect(url_for('valeurs_metier.liste_valeurs'))

#     user = session.get('user', {}).get('username', 'inconnu')

#     execute_db("""
#         UPDATE valeur_metier
#            SET libelle = ?,
#                type_libelle = ?,
#                valeur_libelle = ?,
#                ponderation = ?,
#                uuser = ?,
#                udate = CURRENT_TIMESTAMP
#          WHERE id = ?
#     """, [libelle, type_libelle, valeur_libelle, ponderation, user, id])

#     flash("✅ Valeur métier mise à jour", "success")
#     return redirect(url_for('valeurs_metier.liste_valeurs'))


# # -----------------------
# # SUPPRIMER
# # -----------------------
# @valeurs_bp.route('/supprimer/<id>', methods=['POST'])
# def supprimer_valeur(id):
#     execute_db("DELETE FROM valeur_metier WHERE id = ?", [id])
#     flash("✅ Valeur métier supprimée", "success")
#     return redirect(url_for('valeurs_metier.liste_valeurs'))


# # -----------------------
# # ROUTES AJAX (DÉPENDANCES)
# # -----------------------

# # Types distincts pour un libellé donné
# @valeurs_bp.route('/get_types/<libelle>')
# def get_types(libelle):
#     rows = query_db(
#         "SELECT DISTINCT type_libelle FROM valeur_metier WHERE libelle = ? ORDER BY type_libelle",
#         [libelle]
#     )
#     return jsonify({"types": [r["type_libelle"] for r in rows]})

# # Valeurs distinctes pour un couple (libellé, type_libelle)
# @valeurs_bp.route('/get_valeurs/<libelle>/<type_libelle>')
# def get_valeurs(libelle, type_libelle):
#     rows = query_db(
#         "SELECT DISTINCT valeur_libelle FROM valeur_metier WHERE libelle = ? AND type_libelle = ? ORDER BY valeur_libelle",
#         [libelle, type_libelle]
#     )
#     return jsonify({"valeurs": [r["valeur_libelle"] for r in rows]})

# @valeurs_bp.route('/get_libelles')
# def get_libelles():
#     rows = query_db("SELECT DISTINCT libelle FROM valeur_metier ORDER BY libelle")
#     libelles = [row['libelle'] for row in rows]
#     return jsonify({"libelles": libelles})
