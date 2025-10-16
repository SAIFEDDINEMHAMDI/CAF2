# routes/statut_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from utils.db_utils import query_db, get_db

statut_bp = Blueprint("statut", __name__, url_prefix="/statut")

# ===============================
# LISTE DES STATUTS
# ===============================
@statut_bp.route("/")
def liste_statuts():
    q = (request.args.get("q", "") or "").strip()

    sql = "SELECT id, nom FROM Statut"
    params = []

    if q:
        sql += " WHERE nom LIKE ? COLLATE NOCASE"
        params.append(f"%{q}%")

    sql += " ORDER BY id DESC"

    rows = query_db(sql, params)
    statuts = [dict(r) for r in rows]
    return render_template("statut_liste.html", statuts=statuts)


# ===============================
# AJOUTER UN STATUT
# ===============================
@statut_bp.route("/ajouter", methods=["POST"])
def ajouter_statut():
    nom = request.form.get("nom")
    if not nom:
        flash("⚠️ Le nom du statut est obligatoire.", "warning")
        return redirect(url_for("statut.liste_statuts"))

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO Statut (nom, idate, iuser)
            VALUES (?, DATETIME('now'), 1)
        """, (nom,))
        conn.commit()
        flash("✅ Statut ajouté avec succès.", "success")
    except Exception as e:
        flash(f"❌ Erreur : {e}", "error")
    return redirect(url_for("statut.liste_statuts"))


# ===============================
# MODIFIER UN STATUT
# ===============================
@statut_bp.route("/modifier/<int:id>", methods=["POST"])
def modifier_statut(id):
    nom = request.form.get("nom")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE Statut
        SET nom = ?, udate = DATETIME('now'), uuser = 1
        WHERE id = ?
    """, (nom, id))
    conn.commit()
    flash("✏️ Statut mis à jour avec succès.", "success")
    return redirect(url_for("statut.liste_statuts"))


# ===============================
# SUPPRIMER UN STATUT
# ===============================
@statut_bp.route("/supprimer/<int:id>", methods=["POST"])
def supprimer_statut(id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM Statut WHERE id = ?", (id,))
    conn.commit()
    flash("🗑️ Statut supprimé avec succès.", "success")
    return redirect(url_for("statut.liste_statuts"))
