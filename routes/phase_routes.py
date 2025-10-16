# routes/phase_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from utils.db_utils import query_db, get_db

phase_bp = Blueprint("phase", __name__, url_prefix="/phase")

# ===============================
# LISTE DES PHASES AVEC RECHERCHE + PAGINATION
# ===============================
@phase_bp.route("/")
def liste_phases():
    page = request.args.get("page", 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page
    q = (request.args.get("q", "") or "").strip()

    base_query = "SELECT id, nom FROM Phase"
    args = []

    if q:
        base_query += " WHERE nom LIKE ? COLLATE NOCASE"
        args.append(f"%{q}%")

    # total
    total_row = query_db(f"SELECT COUNT(*) as total FROM ({base_query})", args, one=True)
    total = total_row["total"] if total_row else 0
    total_pages = (total // per_page) + (1 if total % per_page else 0)

    # données paginées
    phases = query_db(
        f"{base_query} ORDER BY id DESC LIMIT ? OFFSET ?",
        args + [per_page, offset]
    )
    phases = [dict(p) for p in phases]

    return render_template(
        "phase_liste.html",
        phases=phases,
        page=page,
        total_pages=total_pages,
    )


# ===============================
# AJOUTER UNE PHASE
# ===============================
@phase_bp.route("/ajouter", methods=["POST"])
def ajouter_phase():
    nom = request.form.get("nom")

    if not nom:
        flash("⚠️ Le nom de la phase est obligatoire.", "warning")
        return redirect(url_for("phase.liste_phases"))

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO Phase (nom, idate, iuser)
            VALUES (?, DATETIME('now'), 1)
        """, (nom,))
        conn.commit()
        flash("✅ Phase ajoutée avec succès.", "success")
    except Exception as e:
        flash(f"❌ Erreur : {e}", "error")

    return redirect(url_for("phase.liste_phases"))


# ===============================
# MODIFIER UNE PHASE
# ===============================
@phase_bp.route("/modifier/<int:id>", methods=["POST"])
def modifier_phase(id):
    nom = request.form.get("nom")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE Phase
        SET nom = ?, udate = DATETIME('now'), uuser = 1
        WHERE id = ?
    """, (nom, id))
    conn.commit()
    flash("✏️ Phase mise à jour avec succès.", "success")
    return redirect(url_for("phase.liste_phases"))


# ===============================
# SUPPRIMER UNE PHASE
# ===============================
@phase_bp.route("/supprimer/<int:id>", methods=["POST"])
def supprimer_phase(id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM Phase WHERE id = ?", (id,))
    conn.commit()
    flash("🗑️ Phase supprimée avec succès.", "success")
    return redirect(url_for("phase.liste_phases"))
