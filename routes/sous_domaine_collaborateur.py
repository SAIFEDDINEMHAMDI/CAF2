# routes/sous_domaine_collaborateur.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from utils.db_utils import query_db, get_db

sous_domaine_bp = Blueprint("sous_domaine", __name__, url_prefix="/sous_domaine")

# 🔹 Liste des sous-domaines
@sous_domaine_bp.route("/")
def liste_sous_domaines():
    q = (request.args.get("q", "") or "").strip()
    sql = "SELECT id, nom, description, coefficient FROM sous_domaine_collaborateur"
    params = []

    if q:
        sql += " WHERE nom LIKE ? OR description LIKE ?"
        params.extend([f"%{q}%", f"%{q}%"])

    sql += " ORDER BY id DESC"
    rows = query_db(sql, params)
    sous_domaines = [dict(r) for r in rows]
    return render_template("sous_domaine_liste.html", sous_domaines=sous_domaines)

# 🔹 Ajouter un sous-domaine
@sous_domaine_bp.route("/ajouter", methods=["POST"])
def ajouter_sous_domaine():
    nom = request.form.get("nom")
    description = request.form.get("description")
    coefficient = request.form.get("coefficient", 1)
    if not nom:
        flash("⚠️ Le nom est obligatoire.", "warning")
        return redirect(url_for("sous_domaine.liste_sous_domaines"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO sous_domaine_collaborateur (nom, description, coefficient, idate, iuser)
        VALUES (?, ?, ?, DATETIME('now'), 1)
    """, (nom, description, coefficient))
    conn.commit()
    flash("✅ Sous-domaine ajouté avec succès.", "success")
    return redirect(url_for("sous_domaine.liste_sous_domaines"))

# 🔹 Modifier un sous-domaine
@sous_domaine_bp.route("/modifier/<int:id>", methods=["POST"])
def modifier_sous_domaine(id):
    nom = request.form.get("nom")
    description = request.form.get("description")
    coefficient = request.form.get("coefficient")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE sous_domaine_collaborateur
        SET nom = ?, description = ?, coefficient = ?, udate = DATETIME('now'), uuser = 1
        WHERE id = ?
    """, (nom, description, coefficient, id))
    conn.commit()
    flash("✏️ Sous-domaine mis à jour avec succès.", "success")
    return redirect(url_for("sous_domaine.liste_sous_domaines"))

# 🔹 Supprimer un sous-domaine
@sous_domaine_bp.route("/supprimer/<int:id>", methods=["POST"])
def supprimer_sous_domaine(id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM sous_domaine_collaborateur WHERE id = ?", (id,))
    conn.commit()
    flash("🗑️ Sous-domaine supprimé avec succès.", "success")
    return redirect(url_for("sous_domaine.liste_sous_domaines"))
