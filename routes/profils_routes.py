# ==========================================
# routes/profils_routes.py
# ==========================================
from math import ceil
from flask import Blueprint, render_template, request, redirect, url_for, flash
from utils.db_utils import query_db, get_db

profils_bp = Blueprint("profils", __name__, url_prefix="/profils")


# ===============================
# 🔹 1) Liste + Recherche + Pagination
# ===============================
@profils_bp.route("/")
def liste_profils():
    q = (request.args.get("q") or "").strip()
    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        page = 1

    per_page = 10
    offset = (page - 1) * per_page

    where = ""
    params = []
    if q:
        where = """
        WHERE nom LIKE ? OR description LIKE ?
           OR CAST(build_ratio AS TEXT) LIKE ?
           OR CAST(run_ratio AS TEXT) LIKE ?
           OR CAST(heures_base AS TEXT) LIKE ?
        """
        term = f"%{q}%"
        params = [term, term, term, term, term]

    total_row = query_db(f"SELECT COUNT(*) AS c FROM profils {where}", params, one=True)
    total = total_row["c"] if total_row else 0
    total_pages = max(1, ceil(total / per_page))
    if page > total_pages:
        page = total_pages
        offset = (page - 1) * per_page

    profils = query_db(
        f"""
        SELECT id, nom, description, build_ratio, run_ratio, heures_base
        FROM profils
        {where}
        ORDER BY id ASC
        LIMIT ? OFFSET ?
        """,
        params + [per_page, offset]
    )

    return render_template(
        "profils_list.html",
        profils=profils,
        page=page,
        total_pages=total_pages
    )


# ===============================
# 🔹 2) Ajouter un profil
# ===============================
@profils_bp.route("/ajouter", methods=["POST"])
def ajouter_profil():
    nom = request.form.get("nom")
    description = request.form.get("description")
    build_ratio = request.form.get("build_ratio", 70)
    run_ratio = request.form.get("run_ratio", 30)
    heures_base = request.form.get("heures_base", 35)

    if not nom:
        flash("❌ Le nom du profil est obligatoire.", "danger")
        return redirect(url_for("profils.liste_profils"))

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO profils (nom, description, build_ratio, run_ratio, heures_base, idate, iuser)
            VALUES (?, ?, ?, ?, ?, DATETIME('now'), 1)
        """, (nom, description, build_ratio, run_ratio, heures_base))
        conn.commit()
        flash("✅ Profil ajouté avec succès.", "success")
    except Exception as e:
        flash(f"❌ Erreur lors de l’ajout du profil : {e}", "danger")

    return redirect(url_for("profils.liste_profils"))


# ===============================
# 🔹 3) Modifier un profil
# ===============================
@profils_bp.route("/modifier/<int:id>", methods=["POST"])
def modifier_profil(id):
    nom = request.form.get("nom")
    description = request.form.get("description")
    build_ratio = request.form.get("build_ratio", 70)
    run_ratio = request.form.get("run_ratio", 30)
    heures_base = request.form.get("heures_base", 35)

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE profils
            SET nom=?, description=?, build_ratio=?, run_ratio=?, heures_base=?, udate=DATETIME('now'), uuser=1
            WHERE id=?
        """, (nom, description, build_ratio, run_ratio, heures_base, id))
        conn.commit()
        flash("✅ Profil modifié avec succès.", "success")
    except Exception as e:
        flash(f"❌ Erreur lors de la modification du profil : {e}", "danger")

    return redirect(url_for("profils.liste_profils"))


# ===============================
# 🔹 4) Supprimer un profil
# ===============================
# 📌 Supprimer un profil (+ suppression en cascade manuelle)
# 📌 Suppression avec détection automatique des dépendances réelles
@profils_bp.route("/supprimer/<int:id>", methods=["POST"])
def supprimer_profil(id):
    conn = get_db()
    cur = conn.cursor()

    tables_dependantes = {
        "collaborateurs": "Collaborateurs",
        "disponibilites": "Disponibilités",
        "phase_profils_programme": "Phases / Profils Programme",
        "hypotheses_profils": "Hypothèses Profils",
        "profil_hypotheses": "Profils Hypothèses",
        "programme_profil_hypotheses": "Programmes / Profils / Hypothèses",
        "programme_profils": "Programmes Profils"
    }

    dependances_trouvees = []

    for table, label in tables_dependantes.items():
        try:
            result = query_db(f"SELECT COUNT(*) AS total FROM {table} WHERE profil_id = ?", [id], one=True)
            if result and result["total"] > 0:
                dependances_trouvees.append(f"{label} ({result['total']})")
        except Exception:
            continue

    if dependances_trouvees:
        message = "⚠️ Impossible de supprimer ce profil : il est utilisé dans " + ", ".join(dependances_trouvees) + "."
        flash(message, "warning")
        return redirect(url_for("profils.liste_profils"))

    try:
        cur.execute("DELETE FROM profils WHERE id = ?", [id])
        conn.commit()
        flash("✅ Profil supprimé avec succès.", "success")
    except Exception as e:
        flash(f"❌ Erreur lors de la suppression du profil : {e}", "danger")

    return redirect(url_for("profils.liste_profils"))
