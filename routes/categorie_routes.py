# routes/categorie_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from utils.db_utils import query_db, get_db

categorie_bp = Blueprint("categorie", __name__, url_prefix="/categorie")


# ===============================
# LISTE DES CATÉGORIES
# ===============================
@categorie_bp.route("/")
def liste_categories():
    q = (request.args.get("q", "") or "").strip()

    sql = """
        SELECT id, nom
        FROM Categorie
    """
    params = []

    if q:
        # filtre insensible à la casse
        sql += " WHERE nom LIKE ? COLLATE NOCASE"
        params.append(f"%{q}%")

    sql += " ORDER BY id DESC"

    rows = query_db(sql, params)
    categories = [dict(r) for r in rows]  # pour éviter les soucis Row → JSON si besoin

    return render_template("categorie_liste.html", categories=categories)

# ===============================
# AJOUTER UNE CATÉGORIE
# ===============================
@categorie_bp.route("/ajouter", methods=["POST"])
def ajouter_categorie():
    nom = request.form.get("nom")

    conn = get_db()
    cur = conn.cursor()

    if not nom:
        flash("⚠️ Le nom de la catégorie est obligatoire.", "warning")
        return redirect(url_for("categorie.liste_categories"))

    cur.execute("""
        INSERT INTO Categorie (nom, idate, iuser)
        VALUES (?, DATETIME('now'), 1)
    """, (nom,))  # ✅ tuple avec virgule

    conn.commit()
    flash("✅ Catégorie ajoutée avec succès.", "success")
    return redirect(url_for("categorie.liste_categories"))
# ===============================
# MODIFIER UNE CATÉGORIE
# ===============================
@categorie_bp.route("/modifier/<int:id>", methods=["POST"])
def modifier_categorie(id):
    nom = request.form.get("nom")
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE Categorie
        SET nom = ?, udate = DATETIME('now'), uuser = 1
        WHERE id = ?
    """, (nom, id))
    conn.commit()

    flash("✏️ Catégorie mise à jour avec succès.", "success")
    return redirect(url_for("categorie.liste_categories"))
# ===============================
# SUPPRIMER UNE CATÉGORIE
# ===============================
@categorie_bp.route("/supprimer/<int:id>", methods=["POST"])
def supprimer_categorie(id):
    conn = get_db()
    cur = conn.cursor()

    # Vérifier si la catégorie existe
    existing = query_db("SELECT id FROM Categorie WHERE id = ?", [id], one=True)
    if not existing:
        flash("⚠️ Catégorie introuvable.", "warning")
        return redirect(url_for("categorie.liste_categories"))

    # Supprimer la catégorie
    cur.execute("DELETE FROM Categorie WHERE id = ?", (id,))
    conn.commit()

    flash("🗑️ Catégorie supprimée avec succès.", "success")
    return redirect(url_for("categorie.liste_categories"))
