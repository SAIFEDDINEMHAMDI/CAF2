import os
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file
from utils.db_utils import query_db, execute_db
import pandas as pd
import io

accompagnement_bp = Blueprint("accompagnement", __name__, url_prefix="/accompagnement")

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ==============================================
# 🔹 LISTE ACCOMPAGNEMENTS (avec pagination)
# ==============================================
@accompagnement_bp.route("/")
def liste_accompagnement():
    q = (request.args.get("q") or "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    where = []
    args = []
    if q:
        where.append("(p.nom LIKE ? OR sd.nom LIKE ? OR ae.nb_etp LIKE ?)")
        like = f"%{q}%"
        args.extend([like, like, like])

    where_sql = "WHERE " + " AND ".join(where) if where else ""

    total_row = query_db(f"SELECT COUNT(*) AS c FROM accompagnement_externe ae {where_sql}", args, one=True)
    total = total_row["c"] if total_row else 0
    total_pages = (total // per_page) + (1 if total % per_page else 0)

    accompagnements = query_db(f"""
        SELECT ae.id, ae.nb_etp, ae.date_debut, ae.date_fin,
               ae.profil_id, p.nom AS profil,
               ae.sous_domaine_id, sd.nom AS sous_domaine,
               ae.periode_valeur, ae.periode_unite,
               CASE
                   WHEN ae.date_debut IS NULL THEN NULL
                   WHEN ae.periode_unite='jours' THEN date(ae.date_debut, '+'||ae.periode_valeur||' day')
                   WHEN ae.periode_unite='semaines' THEN date(ae.date_debut, '+'||(ae.periode_valeur*7)||' day')
                   WHEN ae.periode_unite='mois' THEN date(ae.date_debut, '+'||ae.periode_valeur||' month')
                   ELSE date(ae.date_debut, '+90 day')
               END AS date_productivite
        FROM accompagnement_externe ae
        LEFT JOIN profils p ON ae.profil_id = p.id
        LEFT JOIN sous_domaine_collaborateur sd ON ae.sous_domaine_id = sd.id
        {where_sql}
        ORDER BY ae.id DESC
        LIMIT ? OFFSET ?
    """, args + [per_page, offset])

    profils = query_db("SELECT id, nom FROM profils ORDER BY nom")
    sous_domaines = query_db("SELECT id, nom FROM sous_domaine_collaborateur ORDER BY nom")

    return render_template(
        "accompagnement_list.html",
        accompagnements=accompagnements,
        profils=profils,
        sous_domaines=sous_domaines,
        page=page,
        total_pages=total_pages,
        q=q,
    )


# ==============================================
# ➕ AJOUTER ACCOMPAGNEMENT
# ==============================================
@accompagnement_bp.route("/ajouter", methods=["POST"])
def ajouter_accompagnement():
    try:
        profil_id = request.form.get("profil_id")
        sous_domaine_id = request.form.get("sous_domaine_id")
        nb_etp = int(request.form.get("nb_etp") or 0)
        date_debut = request.form.get("date_debut")
        date_fin = request.form.get("date_fin")
        periode_valeur = int(request.form.get("periode_valeur") or 0)
        periode_unite = request.form.get("periode_unite") or "mois"
        iuser = session.get("user", {}).get("username", "system")

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
            date_debut,
            periode_unite,
            date_debut,
            periode_valeur,
            periode_unite,
            date_debut,
            periode_valeur,
            periode_unite,
            date_debut,
            periode_valeur,
            date_debut,
        ], one=True)
        date_productivite = dp_row["dp"] if dp_row else None

        execute_db("""
            INSERT INTO accompagnement_externe 
            (profil_id, sous_domaine_id, nb_etp, date_debut, date_fin, periode_valeur, periode_unite, iuser, idate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, [profil_id, sous_domaine_id, nb_etp, date_debut, date_fin, periode_valeur, periode_unite, iuser])

        flash("✅ Accompagnement ajouté avec succès.", "success")

    except Exception as e:
        flash(f"❌ Erreur lors de l’ajout : {e}", "error")

    return redirect(url_for("accompagnement.liste_accompagnement"))


# ==============================================
# ✏️ MODIFIER ACCOMPAGNEMENT
# ==============================================
@accompagnement_bp.route("/modifier/<int:id>", methods=["POST"])
def modifier_accompagnement(id):
    try:
        profil_id = request.form.get("profil_id")
        sous_domaine_id = request.form.get("sous_domaine_id")
        try:
            nb_etp = int(float(request.form.get("nb_etp") or 0))
        except ValueError:
            nb_etp = 0
        date_debut = request.form.get("date_debut")
        date_fin = request.form.get("date_fin")
        periode_valeur = int(request.form.get("periode_valeur") or 0)
        periode_unite = request.form.get("periode_unite") or "mois"
        uuser = session.get("user", {}).get("username", "system")

        execute_db("""
            UPDATE accompagnement_externe
            SET profil_id = ?, sous_domaine_id = ?, nb_etp = ?, 
                date_debut = ?, date_fin = ?, periode_valeur = ?, periode_unite = ?, 
                uuser = ?, udate = CURRENT_TIMESTAMP
            WHERE id = ?
        """, [profil_id, sous_domaine_id, nb_etp, date_debut, date_fin, periode_valeur, periode_unite, uuser, id])

        flash("✅ Accompagnement mis à jour avec succès.", "success")

    except Exception as e:
        flash(f"❌ Erreur lors de la modification : {e}", "error")

    return redirect(url_for("accompagnement.liste_accompagnement"))


# ==============================================
# 🗑️ SUPPRIMER
# ==============================================
@accompagnement_bp.route("/supprimer/<int:id>", methods=["POST"])
def supprimer_accompagnement(id):
    try:
        execute_db("DELETE FROM accompagnement_externe WHERE id = ?", [id])
        flash("✅ Accompagnement supprimé avec succès.", "success")
    except Exception as e:
        flash(f"❌ Erreur lors de la suppression : {e}", "error")
    return redirect(url_for("accompagnement.liste_accompagnement"))


# ==============================================
# 📄 TÉLÉCHARGER MODÈLE EXCEL
# ==============================================
@accompagnement_bp.route("/telecharger-modele")
def telecharger_modele():
    try:
        output = io.BytesIO()
        data = {
            "Profil": ["Développeur", "Chef de projet"],
            "Sous-domaine": ["Digital Banking", "Core Banking"],
            "Nb ETP": [1, 2],
            "Date Début": ["2025-01-01", "2025-02-15"],
            "Date Fin": ["2025-06-30", "2025-07-31"],
            "Période Valeur": [3, 0],
            "Période Unité": ["mois", "jours"],
        }
        df = pd.DataFrame(data)
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Accompagnement")
        output.seek(0)

        return send_file(
            output,
            as_attachment=True,
            download_name="modele_accompagnement_externe.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        flash(f"❌ Erreur lors du téléchargement du modèle : {e}", "error")
        return redirect(url_for("accompagnement.liste_accompagnement"))


# ==============================================
# 📥 IMPORTER FICHIER EXCEL
# ==============================================
@accompagnement_bp.route("/importer-excel", methods=["POST"])
def importer_excel():
    try:
        file = request.files.get("file")
        if not file:
            flash("⚠️ Aucun fichier sélectionné.", "warning")
            return redirect(url_for("accompagnement.liste_accompagnement"))

        df = pd.read_excel(file)

        for _, row in df.iterrows():
            profil_nom = str(row.get("Profil", "")).strip()
            sous_domaine_nom = str(row.get("Sous-domaine", "")).strip()
            nb_etp = int(row.get("Nb ETP", 0))
            date_debut = row.get("Date Début")
            date_fin = row.get("Date Fin")
            periode_valeur = int(row.get("Période Valeur", 0))
            periode_unite = str(row.get("Période Unité", "mois")).strip().lower()

            profil = query_db("SELECT id FROM profils WHERE nom = ?", [profil_nom], one=True)
            sous_domaine = query_db("SELECT id FROM sous_domaine_collaborateur WHERE nom = ?", [sous_domaine_nom], one=True)

            profil_id = profil["id"] if profil else None
            sous_domaine_id = sous_domaine["id"] if sous_domaine else None

            if not profil_id:
                flash(f"⚠️ Profil inconnu : {profil_nom}", "warning")
                continue

            execute_db("""
                INSERT INTO accompagnement_externe 
                (profil_id, sous_domaine_id, nb_etp, date_debut, date_fin, periode_valeur, periode_unite, iuser, idate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, [profil_id, sous_domaine_id, nb_etp, date_debut, date_fin, periode_valeur, periode_unite, "import_excel"])

        flash("✅ Import Excel effectué avec succès.", "success")

    except Exception as e:
        flash(f"❌ Erreur lors de l’import Excel : {e}", "error")

    return redirect(url_for("accompagnement.liste_accompagnement"))
