# ==========================================
# routes/recrutement_routes.py
# ==========================================
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, make_response
from utils.db_utils import query_db, execute_db
from datetime import date

recrutement_bp = Blueprint("recrutement", __name__, url_prefix="/recrutement")


# ==========================================
# LISTE DES RECRUTEMENTS (avec pagination)
# ==========================================
@recrutement_bp.route("/")
def liste_recrutement():
    q = (request.args.get("q") or "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    where = []
    args = []
    if q:
        where.append("""
            (r.matricule LIKE ? OR r.nom LIKE ? OR r.prenom LIKE ? 
             OR EXISTS (SELECT 1 FROM profils p WHERE p.id = r.profil_id AND p.nom LIKE ?))
        """)
        like = f"%{q}%"
        args.extend([like, like, like, like])

    where_sql = "WHERE " + " AND ".join(where) if where else ""

    total_row = query_db(f"SELECT COUNT(*) AS c FROM recrutement r {where_sql}", args, one=True)
    total = total_row["c"] if total_row else 0
    total_pages = (total // per_page) + (1 if total % per_page else 0)

    ressources = query_db(f"""
        SELECT r.id, r.matricule, r.nom, r.prenom, p.nom AS profil, r.profil_id,
               r.date_debut, r.periode_valeur, r.periode_unite,
               CASE
                   WHEN r.date_debut IS NULL THEN NULL
                   WHEN r.periode_unite='jours' THEN date(r.date_debut, '+'||r.periode_valeur||' day')
                   WHEN r.periode_unite='semaines' THEN date(r.date_debut, '+'||(r.periode_valeur*7)||' day')
                   WHEN r.periode_unite='mois' THEN date(r.date_debut, '+'||r.periode_valeur||' month')
                   ELSE date(r.date_debut, '+90 day')
               END AS date_productivite
        FROM recrutement r
        LEFT JOIN profils p ON p.id = r.profil_id
        {where_sql}
        ORDER BY r.id DESC
        LIMIT ? OFFSET ?
    """, args + [per_page, offset])

    profils = query_db("SELECT id, nom FROM profils ORDER BY nom")

    return render_template(
        "recrutement_list.html",
        ressources=ressources,
        profils=profils,
        page=page,
        total_pages=total_pages,
        q=q
    )


# ==========================================
# AJOUTER UN RECRUTEMENT
# ==========================================
@recrutement_bp.route("/ajouter", methods=["POST"])
def ajouter_recrutement():
    try:
        matricule = request.form["matricule"].strip().upper()
        nom = request.form["nom"].strip()
        prenom = request.form["prenom"].strip()
        profil_id = request.form.get("profil_id") or None
        date_debut = request.form.get("date_debut")
        periode_valeur = int(request.form.get("periode_valeur") or 0)
        periode_unite = request.form.get("periode_unite") or "jours"

        # ✅ Vérification unicité matricule
        exists = query_db("""
            SELECT 1 FROM (
                SELECT matricule FROM collaborateurs
                UNION ALL
                SELECT matricule FROM recrutement
            ) WHERE matricule = ?
        """, [matricule], one=True)

        if exists:
            session['_flashes'] = []
            flash("❌ Ce matricule existe déjà.", "error")
            return redirect(url_for("recrutement.liste_recrutement"))

        # ✅ Calcul de la date de productivité
        dp_row = query_db("""
            SELECT CASE
                WHEN ? IS NULL THEN NULL
                WHEN ? = 'jours' THEN date(?, '+' || ? || ' day')
                WHEN ? = 'semaines' THEN date(?, '+' || (? * 7) || ' day')
                WHEN ? = 'mois' THEN date(?, '+' || ? || ' month')
                ELSE date(?, '+90 day')
            END AS dp
        """, [
            date_debut,                # 1
            periode_unite,             # 2
            date_debut,                # 3
            periode_valeur,            # 4
            periode_unite,             # 5
            date_debut,                # 6
            periode_valeur,            # 7
            periode_unite,             # 8
            date_debut,                # 9
            periode_valeur,            # 10
            date_debut                 # 11 ✅ ajouté
        ], one=True)

        date_productivite = dp_row["dp"] if dp_row else None

        # ✅ Insertion
        execute_db("""
            INSERT INTO recrutement (matricule, nom, prenom, profil_id, date_debut, periode_valeur, periode_unite)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [matricule, nom, prenom, profil_id, date_debut, periode_valeur, periode_unite])

        session['_flashes'] = []
        flash("✅ Recrutement ajouté avec succès.", "success")

        # ✅ Si période = 0 → transfert direct dans collaborateurs
        if periode_valeur == 0:
            execute_db("""
                INSERT OR IGNORE INTO collaborateurs (matricule, nom, prenom, profil_id, affectation_id)
                VALUES (?, ?, ?, ?, 1)
            """, [matricule, nom, prenom, profil_id])
            flash("⚡ 0 jour : transféré immédiatement vers les collaborateurs.", "success")
            return redirect(url_for("collaborateurs.liste_collaborateurs"))

        # ✅ Si productif aujourd’hui → transfert immédiat
        if date_productivite and date_productivite == str(date.today()):
            execute_db("""
                INSERT OR IGNORE INTO collaborateurs (matricule, nom, prenom, profil_id, affectation_id)
                VALUES (?, ?, ?, ?, 1)
            """, [matricule, nom, prenom, profil_id])
            flash("🎯 Ressource devenue productive.", "success")
            return redirect(url_for("collaborateurs.liste_collaborateurs"))

    except Exception as e:
        session['_flashes'] = []
        flash(f"❌ Erreur lors de l’ajout : {e}", "error")

    return redirect(url_for("recrutement.liste_recrutement"))


# ==========================================
# MODIFIER UN RECRUTEMENT
# ==========================================
@recrutement_bp.route("/modifier/<int:id>", methods=["POST"])
def modifier_recrutement(id):
    try:
        matricule = request.form["matricule"].strip().upper()
        nom = request.form["nom"].strip()
        prenom = request.form["prenom"].strip()
        profil_id = request.form.get("profil_id") or None
        date_debut = request.form.get("date_debut")
        periode_valeur = int(request.form.get("periode_valeur") or 0)
        periode_unite = request.form.get("periode_unite") or "jours"

        exists = query_db("""
            SELECT 1 FROM (
                SELECT matricule FROM collaborateurs
                UNION ALL
                SELECT matricule FROM recrutement WHERE id != ?
            ) WHERE matricule = ?
        """, [id, matricule], one=True)

        if exists:
            session['_flashes'] = []
            flash("❌ Matricule déjà utilisé.", "error")
            return redirect(url_for("recrutement.liste_recrutement"))

        execute_db("""
            UPDATE recrutement
            SET matricule = ?, nom = ?, prenom = ?, profil_id = ?, date_debut = ?, 
                periode_valeur = ?, periode_unite = ?
            WHERE id = ?
        """, [matricule, nom, prenom, profil_id, date_debut, periode_valeur, periode_unite, id])

        session['_flashes'] = []
        flash("✅ Recrutement modifié avec succès.", "success")

        # transfert si productif
        if periode_valeur == 0:
            execute_db("""
                INSERT OR IGNORE INTO collaborateurs (matricule, nom, prenom, profil_id, affectation_id)
                VALUES (?, ?, ?, ?, 1)
            """, [matricule, nom, prenom, profil_id])
            flash("⚡ Ressource transférée vers collaborateurs.", "success")
            return redirect(url_for("collaborateurs.liste_collaborateurs"))

    except Exception as e:
        session['_flashes'] = []
        flash(f"❌ Erreur lors de la modification : {e}", "error")

    return redirect(url_for("recrutement.liste_recrutement"))


# ==========================================
# SUPPRIMER UN RECRUTEMENT
# ==========================================
@recrutement_bp.route("/supprimer/<int:id>", methods=["POST"])
def supprimer_recrutement(id):
    try:
        execute_db("DELETE FROM recrutement WHERE id = ?", [id])
        session['_flashes'] = []
        flash("✅ Recrutement supprimé avec succès.", "success")
    except Exception as e:
        session['_flashes'] = []
        flash(f"❌ Erreur lors de la suppression : {e}", "error")

    return redirect(url_for("recrutement.liste_recrutement"))


# ==========================================
# TÉLÉCHARGER MODÈLE EXCEL
# ==========================================
@recrutement_bp.route("/modele-excel")
def modele_excel():
    csv_content = (
        "matricule,nom,prenom,profil,date_debut,periode_valeur,periode_unite\n"
        "C00001,Doe,John,Data Engineer,2025-10-14,0,jours\n"
        "C00002,Smith,Anna,QA,2025-10-20,3,mois\n"
    )
    resp = make_response(csv_content)
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = "attachment; filename=recrutement_modele.csv"
    return resp
