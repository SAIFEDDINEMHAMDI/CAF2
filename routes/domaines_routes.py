# ==========================================
# routes/domaines_routes.py
# ==========================================
from flask import Blueprint, render_template, request, redirect, url_for, flash
from utils.db_utils import query_db, get_db
from utils.calcul_utils import calculer_charge_estimee

domaines_bp = Blueprint("domaines", __name__, url_prefix="/domaines")


@domaines_bp.route("/", methods=["GET"])
def liste_domaines():
    search = request.args.get("q", "").strip()
    page = int(request.args.get("page", 1))
    per_page = 10
    offset = (page - 1) * per_page

    base_query = 'SELECT * FROM "domaines"'
    args = []

    if search:
        base_query += " WHERE nom LIKE ?"
        args.append(f"%{search}%")

    total = query_db(f"SELECT COUNT(*) AS count FROM ({base_query})", args, one=True)["count"]
    total_pages = (total // per_page) + (1 if total % per_page else 0)

    domaines = query_db(f"{base_query} ORDER BY id DESC LIMIT ? OFFSET ?", args + [per_page, offset])
    return render_template("domaines_liste.html", domaines=domaines, page=page, total_pages=total_pages)


@domaines_bp.route("/ajouter", methods=["POST"])
def ajouter_domaine():
    nom = request.form.get("nom")
    coefficient = request.form.get("coefficient", 0)

    if not nom:
        flash("❌ Le nom du domaine est obligatoire.", "error")
        return redirect(url_for("domaines.liste_domaines"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO "domaines" (nom, coefficient, idate, iuser)
        VALUES (?, ?, DATETIME('now'), 1)
    """, (nom, coefficient))
    conn.commit()

    flash("✅ Domaine ajouté avec succès.", "success")
    return redirect(url_for("domaines.liste_domaines"))


@domaines_bp.route("/modifier/<int:id>", methods=["POST"])
def modifier_domaine(id):
    nom = request.form.get("nom")
    coefficient = request.form.get("coefficient", 0)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE "domaines"
        SET nom = ?, coefficient = ?, udate = DATETIME('now'), uuser = 1
        WHERE id = ?
    """, (nom, coefficient, id))
    conn.commit()

    projets = query_db("""
        SELECT id, score_complexite
        FROM "Projet"
        WHERE id_domaine = ?
    """, [id])

    nb_recalcules = 0
    for p in projets:
        score = p["score_complexite"]
        if not score:
            continue

        resultat = calculer_charge_estimee(score, id)
        estimation_jh = resultat.get("charge_estimee", 0) if isinstance(resultat, dict) else 0

        cur.execute("""
            UPDATE "Projet"
            SET estimation_jh = ?, uuser = 1, udate = DATETIME('now')
            WHERE id = ?
        """, (estimation_jh, p["id"]))
        nb_recalcules += 1

    conn.commit()

    if nb_recalcules > 0:
        flash(f"♻️ {nb_recalcules} projet(s) recalculé(s) suite à la mise à jour du domaine.", "info")
    else:
        flash("✅ Domaine modifié (aucun projet à recalculer).", "success")

    return redirect(url_for("domaines.liste_domaines"))


@domaines_bp.route("/supprimer/<int:id>", methods=["POST"])
def supprimer_domaine(id):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE "Projet"
            SET id_domaine = NULL, estimation_jh = 0, uuser = 1, udate = DATETIME('now')
            WHERE id_domaine = ?
        """, [id])

        cur.execute('DELETE FROM "domaines" WHERE id = ?', [id])
        conn.commit()

        flash("🗑️ Domaine supprimé et projets associés réinitialisés.", "success")
    except Exception as e:
        flash(f"❌ Erreur lors de la suppression : {e}", "error")

    return redirect(url_for("domaines.liste_domaines"))
