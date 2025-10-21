import os
import sqlite3
import pandas as pd
from datetime import datetime
from io import BytesIO
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file
from werkzeug.utils import secure_filename
from utils.db_utils import query_db, execute_db
from utils.decorators import readonly_if_user
import unicodedata, re, glob

collab_bp = Blueprint('collaborateurs', __name__, url_prefix='/collaborateurs')

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
LOGS_FOLDER = "logs"
os.makedirs(LOGS_FOLDER, exist_ok=True)


# ================================================================
# 🔹 FONCTIONS UTILES
# ================================================================
def _normalize_col(col: str) -> str:
    col = ''.join(c for c in unicodedata.normalize('NFD', str(col)) if unicodedata.category(c) != 'Mn')
    col = re.sub(r'[\s_]+', '', col)
    return col.strip().lower()

def _parse_percentage(x, default=0):
    if x is None:
        return int(default)
    s = str(x).strip().replace(',', '.')
    if s.endswith('%'):
        s = s[:-1].strip()
    try:
        v = float(s)
    except Exception:
        return int(default)
    if v <= 1:
        v *= 100.0
    v = max(0.0, min(100.0, round(v, 2)))
    return int(round(v))

def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _get_user():
    return session.get('user', {}).get('username', 'system')

def _get_heures_base(profil_id: int) -> int:
    row = query_db("SELECT heures_base FROM profils WHERE id = ?", [profil_id], one=True)
    return int(row['heures_base']) if row and row['heures_base'] is not None else 0

def _sanitize_percentage(val, default=0):
    try:
        v = float(val)
    except Exception:
        return float(default)
    if v < 0: v = 0
    if v > 100: v = 100
    return v


# ================================================================
# 🔹 LISTE COLLABORATEURS
# ================================================================
@collab_bp.route('/')
def liste_collaborateurs():
    profil_id = request.args.get('profil_id', type=int)
    search = request.args.get('search', '').strip()
    incomplets = request.args.get('incomplets')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    profils = query_db("SELECT * FROM profils ORDER BY nom")
    affectations = query_db("SELECT * FROM affectation ORDER BY nom")

    base_query = """
        SELECT 
            c.matricule, c.nom, c.prenom, c.profil_id, c.affectation_id,
            c.pourcentage_build, c.pourcentage_run,
            c.caf_disponible_build, c.caf_disponible_run,
            p.nom AS profil, a.nom AS affectation, c.heures_base
        FROM collaborateurs c
        LEFT JOIN profils p ON c.profil_id = p.id
        LEFT JOIN affectation a ON c.affectation_id = a.id
        WHERE 1=1
    """
    args = []

    if profil_id:
        base_query += " AND p.id = ?"
        args.append(profil_id)

    if search:
        base_query += " AND (c.matricule LIKE ? OR c.nom LIKE ? OR c.prenom LIKE ?)"
        args.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

    if incomplets:
        base_query += " AND (c.profil_id IS NULL OR c.affectation_id IS NULL)"

    total = query_db(f"SELECT COUNT(*) AS count FROM ({base_query})", args, one=True)['count']

    total_pages = (total // per_page) + (1 if total % per_page > 0 else 0)
    user_role = session.get('user', {}).get('role', '')
    collaborateurs = query_db(f"{base_query} ORDER BY c.rowid DESC LIMIT ? OFFSET ?", args + [per_page, offset])

    collaborateurs = [dict(c) for c in collaborateurs]
    for c in collaborateurs:
        c['repartitions'] = query_db("""
            SELECT cr.*, p.nom AS profil_nom
            FROM collaborateur_repartition cr
            LEFT JOIN profils p ON p.id = cr.profil_id
            WHERE cr.collaborateur_id = ?
        """, [c['matricule']])
    return render_template(
        'collaborateurs/liste.html',
        collaborateurs=collaborateurs,
        profils=profils,
        affectations=affectations,
        profil_id=profil_id,
        search=search,
        incomplets=incomplets,
        page=page,
        total_pages=total_pages,
        user_role=user_role
    )



# ================================================================
@collab_bp.route('/ajouter', methods=['POST'])
@readonly_if_user
def ajouter_collaborateur():
    matricule = request.form['matricule'].strip()
    nom = request.form['nom'].strip()
    prenom = request.form['prenom'].strip()
    profil_id = int(request.form['profil_id'])
    affectation_id = int(request.form['affectation_id'])

    # Heures base
    heures_base_saisie = request.form.get('heures_base', '').strip()
    heures_base = int(heures_base_saisie) if heures_base_saisie else _get_heures_base(profil_id)

    # Pourcentages principaux
    p_build = _sanitize_percentage(request.form.get('pourcentage_build', 70))
    p_run   = _sanitize_percentage(request.form.get('pourcentage_run', 30))

    # Calcul CAF principal
    caf_build = (p_build / 100.0) * heures_base
    caf_run   = (p_run / 100.0) * heures_base

    # Vérif doublon
    if query_db("SELECT 1 FROM collaborateurs WHERE matricule = ?", [matricule], one=True):
        flash("❌ Ce matricule existe déjà", "danger")
        return redirect(url_for('collaborateurs.liste_collaborateurs'))

    # Insertion du collaborateur principal
    execute_db("""
        INSERT INTO collaborateurs (
            matricule, nom, prenom, profil_id, affectation_id,
            heures_base, pourcentage_build, pourcentage_run,
            caf_disponible_build, caf_disponible_run,
            idate, iuser
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        matricule, nom, prenom, profil_id, affectation_id,
        heures_base, int(p_build), int(p_run),
        float(caf_build), float(caf_run),
        _now(), _get_user()
    ])

    # # ==============================
    # # Répartitions secondaires
    # # ==============================
    # rep_profils = request.form.getlist("rep_profil_id[]")
    # rep_builds  = request.form.getlist("rep_build[]")
    # rep_runs    = request.form.getlist("rep_run[]")
    #
    # collab = query_db("""
    #     SELECT caf_disponible_build, caf_disponible_run
    #     FROM collaborateurs
    #     WHERE matricule = ?
    # """, [matricule], one=True)
    #
    # caf_collab_build = float(collab["caf_disponible_build"]) if collab else 0
    # caf_collab_run   = float(collab["caf_disponible_run"]) if collab else 0
    #
    # total_build, total_run = 0, 0
    # rows_to_insert = []
    #
    # for i in range(len(rep_profils)):
    #     try:
    #         rep_pid = int(str(rep_profils[i]).strip() or 0)
    #         rb = _sanitize_percentage(rep_builds[i] if i < len(rep_builds) else 0, 0)
    #         rr = _sanitize_percentage(rep_runs[i]  if i < len(rep_runs)  else 0, 0)
    #
    #         if not rep_pid:
    #             continue
    #
    #         caf_build_rep = (rb / 100.0) * caf_collab_build
    #         caf_run_rep   = (rr / 100.0) * caf_collab_run
    #
    #         total_build += caf_build_rep
    #         total_run   += caf_run_rep
    #
    #         rows_to_insert.append((matricule, rep_pid, rb, rr, caf_build_rep, caf_run_rep))
    #     except Exception as e:
    #         print(f"[ERREUR] Répartition ignorée : {e}")
    #
    # # 🔹 Vérification de la somme des CAF
    # if total_build > caf_collab_build or total_run > caf_collab_run:
    #     flash(f"⚠️ Somme des CAF secondaires ({total_build:.2f} / {total_run:.2f}) "
    #           f"dépasse les CAF disponibles du collaborateur "
    #           f"({caf_collab_build:.2f} / {caf_collab_run:.2f}).", "warning")
    #     return redirect(url_for('collaborateurs.liste_collaborateurs'))
    #
    # # ✅ Insertion finale
    # for row in rows_to_insert:
    #     execute_db("""
    #         INSERT INTO collaborateur_repartition (
    #             collaborateur_id, profil_id, pourcentage_build, pourcentage_run,
    #             caf_disponible_build, caf_disponible_run
    #         ) VALUES (?, ?, ?, ?, ?, ?)
    #     """, row)

    flash("✅ Collaborateur et répartitions ajoutés avec succès", "success")
    return redirect(url_for('collaborateurs.liste_collaborateurs'))


# ================================================================
# 🔹 MODIFIER COLLABORATEUR
# ================================================================
@collab_bp.route('/modifier/<matricule>', methods=['POST'])
@readonly_if_user
def modifier_collaborateur(matricule):
    nom = request.form['nom'].strip()
    prenom = request.form['prenom'].strip()
    profil_id = int(request.form['profil_id'])
    affectation_id = int(request.form['affectation_id'])

    heures_base_saisie = request.form.get('heures_base', '').strip()
    heures_base = int(heures_base_saisie) if heures_base_saisie else _get_heures_base(profil_id)

    p_build = _sanitize_percentage(request.form.get('pourcentage_build', 70))
    p_run   = _sanitize_percentage(request.form.get('pourcentage_run', 30))

    caf_build = (p_build / 100.0) * heures_base
    caf_run   = (p_run / 100.0) * heures_base

    # 🔹 Mise à jour du collaborateur principal
    execute_db("""
        UPDATE collaborateurs
           SET nom = ?, prenom = ?, profil_id = ?, affectation_id = ?,
               heures_base = ?, pourcentage_build = ?, pourcentage_run = ?,
               caf_disponible_build = ?, caf_disponible_run = ?,
               udate = ?, uuser = ?
         WHERE matricule = ?
    """, [
        nom, prenom, profil_id, affectation_id,
        heures_base, int(p_build), int(p_run),
        float(caf_build), float(caf_run),
        _now(), _get_user(), matricule
    ])
    #
    # # Répartitions secondaires
    # rep_profils = request.form.getlist("rep_profil_id[]")
    # rep_builds  = request.form.getlist("rep_build[]")
    # rep_runs    = request.form.getlist("rep_run[]")
    #
    # execute_db("DELETE FROM collaborateur_repartition WHERE collaborateur_id = ?", [matricule])
    #
    # total_build, total_run = 0, 0
    # rows_to_insert = []
    #
    # for i in range(len(rep_profils)):
    #     try:
    #         rep_pid = int(str(rep_profils[i]).strip() or 0)
    #         rb = _sanitize_percentage(rep_builds[i] if i < len(rep_builds) else 0, 0)
    #         rr = _sanitize_percentage(rep_runs[i]  if i < len(rep_runs)  else 0, 0)
    #
    #         if not rep_pid:
    #             continue
    #
    #         caf_build_rep = (rb / 100.0) * caf_build
    #         caf_run_rep   = (rr / 100.0) * caf_run
    #
    #         total_build += caf_build_rep
    #         total_run   += caf_run_rep
    #
    #         rows_to_insert.append((matricule, rep_pid, rb, rr, caf_build_rep, caf_run_rep))
    #     except Exception as e:
    #         print(f"[ERREUR] Répartition ignorée : {e}")
    #
    # if total_build > caf_build or total_run > caf_run:
    #     flash(f"⚠️ Somme des CAF secondaires ({total_build:.2f} / {total_run:.2f}) "
    #           f"dépasse les CAF du collaborateur "
    #           f"({caf_build:.2f} / {caf_run:.2f}).", "warning")
    #     return redirect(url_for('collaborateurs.liste_collaborateurs'))
    #
    # for row in rows_to_insert:
    #     execute_db("""
    #         INSERT INTO collaborateur_repartition (
    #             collaborateur_id, profil_id, pourcentage_build, pourcentage_run,
    #             caf_disponible_build, caf_disponible_run
    #         ) VALUES (?, ?, ?, ?, ?, ?)
    #     """, row)

    flash("✅ Collaborateur  mis à jour avec succès", "success")
    return redirect(url_for('collaborateurs.liste_collaborateurs'))





# ================================================================
# 🔹 API : récupérer les répartitions secondaires d’un collaborateur
# ================================================================
# @collab_bp.route('/repartition/get/<matricule>')
# def get_repartitions_collaborateur(matricule):
#     data = query_db("""
#         SELECT cr.id, cr.profil_id, p.nom AS profil_nom,
#                cr.pourcentage_build, cr.pourcentage_run,
#                cr.caf_disponible_build, cr.caf_disponible_run
#         FROM collaborateur_repartition cr
#         LEFT JOIN profils p ON p.id = cr.profil_id
#         WHERE CAST(cr.collaborateur_id AS TEXT) = ?
#         ORDER BY cr.id
#     """, [str(matricule)])
#     return {"repartitions": [dict(r) for r in data]}


# ================================================================
# # 🔹 AJOUTER / METTRE À JOUR UNE RÉPARTITION SECONDAIRE
# # ================================================================
# @collab_bp.route('/repartition/ajouter/<matricule>', methods=['POST'])
# @readonly_if_user
# def ajouter_repartition(matricule):
#     try:
#         profil_id = request.form.get("profil_id") or request.form.get("rep_profil_id")
#         p_build = request.form.get("pourcentage_build") or request.form.get("rep_build")
#         p_run = request.form.get("pourcentage_run") or request.form.get("rep_run")
#
#         if not profil_id or not p_build or not p_run:
#             flash("⚠️ Tous les champs sont requis (profil, %Build, %Run).", "warning")
#             return redirect(url_for('collaborateurs.liste_collaborateurs'))
#
#         profil_id = int(profil_id)
#         p_build = _sanitize_percentage(p_build, 0)
#         p_run = _sanitize_percentage(p_run, 0)
#
#         # 🔹 Récupérer les CAF du collaborateur principal
#         collab = query_db("""
#             SELECT caf_disponible_build, caf_disponible_run
#             FROM collaborateurs
#             WHERE matricule = ?
#         """, [matricule], one=True)
#
#         if not collab:
#             flash("❌ Collaborateur introuvable.", "danger")
#             return redirect(url_for('collaborateurs.liste_collaborateurs'))
#
#         caf_collab_build = float(collab["caf_disponible_build"]) if collab else 0
#         caf_collab_run   = float(collab["caf_disponible_run"]) if collab else 0
#
#         # 🔹 Calcul CAF de cette répartition
#         caf_build_rep = (p_build / 100.0) * caf_collab_build
#         caf_run_rep   = (p_run / 100.0) * caf_collab_run
#
#         # 🔹 Vérifier si la répartition existe déjà pour ce profil
#         existing = query_db("""
#             SELECT id FROM collaborateur_repartition
#             WHERE collaborateur_id = ? AND profil_id = ?
#         """, [matricule, profil_id], one=True)
#
#         if existing:
#             # 🔁 Mettre à jour si déjà existante
#             execute_db("""
#                 UPDATE collaborateur_repartition
#                 SET pourcentage_build = ?, pourcentage_run = ?,
#                     caf_disponible_build = ?, caf_disponible_run = ?
#                 WHERE id = ?
#             """, [p_build, p_run, caf_build_rep, caf_run_rep, existing["id"]])
#             flash("♻️ Répartition mise à jour avec succès.", "success")
#         else:
#             # ➕ Sinon insérer une nouvelle
#             execute_db("""
#                 INSERT INTO collaborateur_repartition (
#                     collaborateur_id, profil_id,
#                     pourcentage_build, pourcentage_run,
#                     caf_disponible_build, caf_disponible_run
#                 ) VALUES (?, ?, ?, ?, ?, ?)
#             """, [matricule, profil_id, p_build, p_run, caf_build_rep, caf_run_rep])
#             flash("✅ Nouvelle répartition ajoutée avec succès.", "success")
#
#     except Exception as e:
#         print(f"[ERREUR] Ajout/MàJ répartition : {e}")
#         flash(f"❌ Erreur lors de la gestion de la répartition : {e}", "danger")
#
#     return redirect(url_for('collaborateurs.liste_collaborateurs'))
#
#
# # ================================================================
# # 🔹 MODIFIER UNE RÉPARTITION SECONDAIRE
# # ================================================================
# @collab_bp.route('/repartition/modifier/<int:id>', methods=['POST'])
# @readonly_if_user
# def modifier_repartition(id):
#     try:
#         p_build = _sanitize_percentage(request.form.get('pourcentage_build', 0))
#         p_run = _sanitize_percentage(request.form.get('pourcentage_run', 0))
#
#         rep = query_db("""
#             SELECT cr.id, c.matricule, c.heures_base
#             FROM collaborateur_repartition cr
#             JOIN collaborateurs c ON cr.collaborateur_id = c.matricule
#             WHERE cr.id = ?
#         """, [id], one=True)
#
#         if not rep:
#             flash("❌ Répartition introuvable", "danger")
#             return redirect(url_for('collaborateurs.liste_collaborateurs'))
#
#         heures_base = rep['heures_base'] or 0
#
#         execute_db("""
#             UPDATE collaborateur_repartition
#             SET pourcentage_build = ?, pourcentage_run = ?,
#                 caf_disponible_build = ?, caf_disponible_run = ?
#             WHERE id = ?
#         """, [
#             p_build, p_run,
#             (p_build / 100.0) * heures_base,
#             (p_run / 100.0) * heures_base,
#             id
#         ])
#
#         flash("♻️ Répartition mise à jour avec succès", "success")
#     except Exception as e:
#         print(f"[ERREUR] Modifier répartition : {e}")
#         flash(f"❌ Erreur lors de la modification de la répartition : {e}", "danger")
#
#     return redirect(url_for('collaborateurs.liste_collaborateurs'))
#
#
# # ================================================================
# # 🔹 SUPPRIMER UNE RÉPARTITION SECONDAIRE
# # ================================================================
# @collab_bp.route('/repartition/supprimer/<int:id>', methods=['POST'])
# @readonly_if_user
# def supprimer_repartition(id):
#     try:
#         execute_db("DELETE FROM collaborateur_repartition WHERE id = ?", [id])
#         flash("🗑️ Répartition supprimée avec succès.", "success")
#     except Exception as e:
#         print(f"[ERREUR] Suppression répartition : {e}")
#         flash(f"❌ Erreur lors de la suppression : {e}", "danger")
#
#     return redirect(url_for('collaborateurs.liste_collaborateurs'))
#


@collab_bp.route('/import-excel', methods=['POST'])
@readonly_if_user
def import_excel():
    import datetime, unicodedata, re, glob

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(LOGS_FOLDER, exist_ok=True)

    def normalize_col(col: str):
        col = ''.join(c for c in unicodedata.normalize('NFD', str(col)) if unicodedata.category(c) != 'Mn')
        col = re.sub(r'[\s_]+', '', col)
        return col.strip().lower()

    def parse_percentage(x, default=0):
        if x is None or str(x).strip() == "":
            return int(default)
        s = str(x).strip().replace(',', '.').replace('%', '')
        try:
            v = float(s)
        except Exception:
            return int(default)
        if v <= 1:
            v *= 100
        v = max(0, min(100, round(v, 2)))
        return int(round(v))

    # === Récupération du fichier ===
    file = request.files.get('file')
    if not file or not file.filename.endswith('.xlsx'):
        flash("❌ Veuillez importer un fichier Excel (.xlsx)", "danger")
        return redirect(url_for('collaborateurs.liste_collaborateurs'))

    filepath = os.path.join(UPLOAD_FOLDER, secure_filename(file.filename))
    file.save(filepath)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(LOGS_FOLDER, f"import_collaborateurs_{ts}.log")
    log = []
    def _log(msg): log.append(msg)

    _log(f"=== Import collaborateurs ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===")
    _log(f"Fichier importé : {file.filename}")
    _log("-" * 60)

    try:
        df = pd.read_excel(filepath)
        df.columns = [normalize_col(c) for c in df.columns]

        fix_map = {
            'penom': 'prenom',
            'prennom': 'prenom',
            'pourcentage_build': 'pourcentagebuild',
            'pourcentage_run': 'pourcentagerun',
            'pourcentage run': 'pourcentagerun'
        }
        for bad, good in fix_map.items():
            if bad in df.columns and good not in df.columns:
                df.rename(columns={bad: good}, inplace=True)

        # ✅ Nouvelle colonne optionnelle
        expected_min = {'matricule', 'nom', 'prenom', 'profil', 'affectation', 'pourcentagebuild', 'pourcentagerun'}
        missing = expected_min - set(df.columns)
        if missing:
            raise ValueError(f"❌ Colonnes manquantes : {', '.join(sorted(missing))}")

        has_heures_base = 'heuresbase' in df.columns

        profils = {p['nom'].strip().lower(): p for p in query_db("SELECT id, nom, heures_base FROM profils")}
        affectations = {a['nom'].strip().lower(): a['id'] for a in query_db("SELECT id, nom FROM affectation")}

        inserted, ignored = 0, 0

        for idx, row in df.iterrows():
            ligne = idx + 2
            matricule = str(row.get('matricule', '')).strip()
            nom = str(row.get('nom', '')).strip()
            prenom = str(row.get('prenom', '')).strip()
            profil_nom = str(row.get('profil', '')).strip().lower()
            affect_nom = str(row.get('affectation', '')).strip().lower()

            if not matricule or not matricule.isdigit():
                _log(f"⚠️ L{ligne}: ignorée — matricule manquant/invalide.")
                ignored += 1
                continue

            profil_data = profils.get(profil_nom)
            affectation_id = affectations.get(affect_nom)

            # 🔹 Si le fichier contient heures_base → on l’utilise, sinon hérité du profil
            if has_heures_base:
                try:
                    heures_base = int(row.get('heuresbase', 0))
                except Exception:
                    heures_base = 0
            else:
                heures_base = int(profil_data['heures_base']) if profil_data else 0

            pourcentage_build = parse_percentage(row.get('pourcentagebuild', 70))
            pourcentage_run = parse_percentage(row.get('pourcentagerun', 30))

            caf_build = round(heures_base * (pourcentage_build / 100.0), 2)
            caf_run = round(heures_base * (pourcentage_run / 100.0), 2)

            if query_db("SELECT 1 FROM collaborateurs WHERE matricule = ?", [matricule], one=True):
                _log(f"⚠️ L{ligne}: ignorée — matricule {matricule} déjà existant.")
                ignored += 1
                continue

            execute_db("""
                INSERT INTO collaborateurs (
                    matricule, nom, prenom,
                    profil_id, affectation_id, heures_base,
                    pourcentage_build, pourcentage_run,
                    caf_disponible_build, caf_disponible_run,
                    idate, iuser
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?)
            """, [
                matricule, nom, prenom,
                int(profil_data['id']) if profil_data else None,
                int(affectation_id) if affectation_id else None,
                heures_base,
                int(pourcentage_build), int(pourcentage_run),
                float(caf_build), float(caf_run),
                session.get('user', {}).get('username', 'system')
            ])

            if not profil_data or not affectation_id:
                _log(f"🔸 L{ligne}: ajouté INCOMPLET — {prenom} {nom} (profil/affectation manquant).")
            else:
                _log(f"✅ L{ligne}: ajouté — {prenom} {nom} (H={heures_base}, %B={pourcentage_build}, %R={pourcentage_run}).")

            inserted += 1

        _log("-" * 60)
        _log(f"Résultat : {inserted} ajoutés / {ignored} ignorés")

        with open(log_path, "w", encoding="utf-8") as f:
            f.write("\n".join(log))

        flash(f"✅ Import terminé : {inserted} ajoutés, {ignored} ignorés. Log : {os.path.basename(log_path)}", "success")

    except Exception as e:
        _log(f"❌ Erreur critique : {e}")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("\n".join(log))
        flash(f"❌ Erreur lors de l’import : {e}. Log : {os.path.basename(log_path)}", "danger")

    return redirect(url_for('collaborateurs.liste_collaborateurs'))

# ================================================================
# 🔹 SUPPRIMER COLLABORATEUR
# ================================================================
@collab_bp.route('/supprimer/<matricule>', methods=['POST'])
@readonly_if_user
def supprimer_collaborateur(matricule):
    try:
        # Supprimer d’abord les répartitions liées
        execute_db("DELETE FROM collaborateur_repartition WHERE collaborateur_id = ?", [matricule])
        # Puis supprimer le collaborateur
        execute_db("DELETE FROM collaborateurs WHERE matricule = ?", [matricule])
        flash("🗑️ Collaborateur supprimé avec succès.", "success")
    except Exception as e:
        flash(f"❌ Erreur lors de la suppression : {e}", "danger")

    return redirect(url_for('collaborateurs.liste_collaborateurs'))




# -----------------------
# 📄 TÉLÉCHARGER MODÈLE EXCEL (pourcentages uniquement)
# -----------------------
@collab_bp.route('/telecharger-modele')
def telecharger_modele():
    # On fournit les pourcentages, CAF sera calculé automatiquement côté serveur
    colonnes = ['Matricule', 'Nom', 'Prenom', 'Profil', 'Affectation',
                'Heures_Base', 'Pourcentage_Build', 'Pourcentage_Run']
    exemple = [
        ['1001', 'Dupont', 'Jean', 'Développeur', 'Digital Factory', 160, 70, 30],
        ['1002', 'Ben Ali', 'Karim', 'Analyste Risques', 'Direction Risques', 180, 60, 40],
        ['1003', 'Trabelsi', 'Sana', 'Chef de Projet IT', 'Direction Digitale', 150, 80, 20],
    ]

    df = pd.DataFrame(exemple, columns=colonnes)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Collaborateurs')
        workbook = writer.book
        ws = writer.sheets['Collaborateurs']

        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#CCE5FF', 'border': 1})
        for col_num, value in enumerate(df.columns.values):
            ws.write(0, col_num, value, header_fmt)
            ws.set_column(col_num, col_num, 24)

        ws.write('A6', '➡️ Remplissez les pourcentages. Les CAF sont calculés automatiquement selon le profil (heures_base).',
                 workbook.add_format({'italic': True, 'font_color': '#777777'}))
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name='modele_collaborateurs.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
