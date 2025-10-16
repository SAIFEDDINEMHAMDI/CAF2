# routes/accompagnement_routes.py
import os
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file
from utils.db_utils import query_db, execute_db
from werkzeug.utils import secure_filename
import pandas as pd
import io

accompagnement_bp = Blueprint('accompagnement', __name__, url_prefix='/accompagnement')

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ---------------------------------------------------
# 🔹 Liste avec pagination + recherche
# ---------------------------------------------------
@accompagnement_bp.route('/')
def liste_accompagnement():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page
    search = request.args.get('q', '').strip()

    base_query = """
        SELECT ae.id, ae.nb_etp, ae.date_debut, ae.date_fin,
               ae.profil_id, p.nom AS profil
        FROM accompagnement_externe ae
        LEFT JOIN profils p ON ae.profil_id = p.id
        WHERE 1=1
    """
    args = []

    if search:
        base_query += " AND (p.nom LIKE ? OR ae.nb_etp LIKE ?)"
        like = f"%{search}%"
        args.extend([like, like])

    total_row = query_db(f"SELECT COUNT(*) AS count FROM ({base_query})", args, one=True)
    total = total_row['count'] if total_row else 0

    accompagnements = query_db(f"{base_query} ORDER BY ae.id DESC LIMIT ? OFFSET ?", args + [per_page, offset])
    profils = query_db("SELECT * FROM profils ORDER BY nom")

    total_pages = (total // per_page) + (1 if total % per_page > 0 else 0)
    user_role = session.get('user', {}).get('role', '')

    return render_template(
        'accompagnement_list.html',
        accompagnements=accompagnements,
        profils=profils,
        page=page,
        total_pages=total_pages,
        search=search,
        user_role=user_role
    )


# ---------------------------------------------------
# ➕ Ajouter
# ---------------------------------------------------
@accompagnement_bp.route('/ajouter', methods=['POST'])
def ajouter_accompagnement():
    profil_id = request.form.get('profil_id')
    nb_etp = request.form.get('nb_etp')
    date_debut = request.form.get('date_debut')
    date_fin = request.form.get('date_fin')
    iuser = session.get('user', {}).get('username', 'system')
    idate = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if not profil_id or not nb_etp or not date_debut or not date_fin:
        flash("❌ Tous les champs sont obligatoires.", "error")
        return redirect(url_for('accompagnement.liste_accompagnement'))

    execute_db("""
        INSERT INTO accompagnement_externe (profil_id, nb_etp, date_debut, date_fin, iuser, idate)
        VALUES (?, ?, ?, ?, ?, ?)
    """, [profil_id, nb_etp, date_debut, date_fin, iuser, idate])

    flash("✅ Accompagnement ajouté avec succès.", "success")
    return redirect(url_for('accompagnement.liste_accompagnement'))


# ---------------------------------------------------
# ✏️ Modifier
# ---------------------------------------------------
@accompagnement_bp.route('/modifier/<int:id>', methods=['POST'])
def modifier_accompagnement(id):
    profil_id = request.form.get('profil_id')
    nb_etp = request.form.get('nb_etp')
    date_debut = request.form.get('date_debut')
    date_fin = request.form.get('date_fin')
    uuser = session.get('user', {}).get('username', 'system')
    udate = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    execute_db("""
        UPDATE accompagnement_externe
        SET profil_id = ?, nb_etp = ?, date_debut = ?, date_fin = ?, uuser = ?, udate = ?
        WHERE id = ?
    """, [profil_id, nb_etp, date_debut, date_fin, uuser, udate, id])

    flash("✅ Accompagnement mis à jour avec succès.", "success")
    return redirect(url_for('accompagnement.liste_accompagnement'))


# ---------------------------------------------------
# 🗑️ Supprimer
# ---------------------------------------------------
@accompagnement_bp.route('/supprimer/<int:id>', methods=['POST'])
def supprimer_accompagnement(id):
    try:
        execute_db("DELETE FROM accompagnement_externe WHERE id = ?", [id])
        flash("✅ Accompagnement supprimé avec succès.", "success")
    except Exception as e:
        flash(f"❌ Erreur lors de la suppression : {e}", "error")
    return redirect(url_for('accompagnement.liste_accompagnement'))


# ---------------------------------------------------
# 📥 Import Excel
# ---------------------------------------------------
@accompagnement_bp.route('/import-excel', methods=['POST'])
def import_excel():
    file = request.files.get('file')
    if not file:
        flash("❌ Aucun fichier sélectionné.", "error")
        return redirect(url_for('accompagnement.liste_accompagnement'))

    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        df = pd.read_excel(filepath)

        required_cols = {'Profil', 'Nb ETP', 'Date Début', 'Date Fin'}
        if not required_cols.issubset(df.columns):
            flash("❌ Le fichier ne contient pas les colonnes attendues.", "error")
            return redirect(url_for('accompagnement.liste_accompagnement'))

        for _, row in df.iterrows():
            profil_nom = str(row['Profil']).strip()
            profil = query_db("SELECT id FROM profils WHERE nom = ?", [profil_nom], one=True)
            if not profil:
                flash(f"⚠️ Profil '{profil_nom}' introuvable. Ligne ignorée.", "warning")
                continue

            execute_db("""
                INSERT INTO accompagnement_externe (profil_id, nb_etp, date_debut, date_fin, iuser, idate)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [
                profil['id'],
                row['Nb ETP'],
                pd.to_datetime(row['Date Début']).strftime('%Y-%m-%d'),
                pd.to_datetime(row['Date Fin']).strftime('%Y-%m-%d'),
                session.get('user', {}).get('username', 'import_excel'),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ])

        flash("✅ Importation Excel réussie.", "success")

    except Exception as e:
        flash(f"❌ Erreur lors de l'import : {e}", "error")

    return redirect(url_for('accompagnement.liste_accompagnement'))


# ---------------------------------------------------
# 📄 Télécharger modèle Excel
# ---------------------------------------------------
@accompagnement_bp.route('/telecharger-modele')
def telecharger_modele():
    try:
        output = io.BytesIO()
        data = {
            "Profil": ["Développeur", "Chef de projet", "Analyste"],
            "Nb ETP": [1.0, 0.5, 0.75],
            "Date Début": ["2025-01-01", "2025-02-15", "2025-03-01"],
            "Date Fin": ["2025-06-30", "2025-05-31", "2025-09-30"]
        }
        df = pd.DataFrame(data)
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Accompagnement')
        output.seek(0)

        return send_file(
            output,
            as_attachment=True,
            download_name="modele_accompagnement_externe.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        flash(f"❌ Erreur lors du téléchargement du modèle : {e}", "error")
        return redirect(url_for('accompagnement.liste_accompagnement'))
