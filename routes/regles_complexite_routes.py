# ==========================================
# routes/regles_complexite_routes.py
# ==========================================
from math import ceil
from flask import Blueprint, render_template, request, redirect, url_for, flash
from utils.db_utils import query_db, get_db
from utils.calcul_utils import calculer_charge_estimee

regles_complexite_bp = Blueprint("regles_complexite", __name__, url_prefix="/regles_complexite")


# ===============================
# 🔹 1) Liste + Recherche + Pagination
# ===============================
@regles_complexite_bp.route("/")
def liste_regles():
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
        WHERE CAST(fibo AS TEXT) LIKE ?
           OR CAST(score_min AS TEXT) LIKE ?
           OR CAST(score_max AS TEXT) LIKE ?
           OR CAST(valeur_base AS TEXT) LIKE ?
        """
        term = f"%{q}%"
        params = [term, term, term, term]

    total_row = query_db(f'SELECT COUNT(*) AS c FROM "regle_complexite" {where}', params, one=True)
    total = total_row["c"] if total_row else 0
    total_pages = max(1, ceil(total / per_page))
    if page > total_pages:
        page = total_pages
        offset = (page - 1) * per_page

    regles = query_db(
        f'''
        SELECT id, fibo, score_min, score_max, valeur_base
        FROM "regle_complexite"
        {where}
        ORDER BY fibo ASC, score_min ASC
        LIMIT ? OFFSET ?
        ''',
        params + [per_page, offset]
    )

    return render_template("regles_complexite_liste.html", regles=regles, page=page, total_pages=total_pages)


# ===============================
# 🔹 2) Ajouter
# ===============================
@regles_complexite_bp.route("/ajouter", methods=["POST"])
def ajouter_regle():
    fibo = request.form.get("fibo")
    score_min = request.form.get("score_min")
    score_max = request.form.get("score_max")
    valeur_base = request.form.get("valeur_base")

    if not (fibo and score_min and score_max and valeur_base):
        flash("⚠️ Tous les champs sont obligatoires.", "warning")
        return redirect(url_for("regles_complexite.liste_regles"))

    try:
        fibo = int(fibo)
        score_min = int(score_min)
        score_max = int(score_max)
        valeur_base = float(valeur_base)
    except ValueError:
        flash("⚠️ Valeurs numériques invalides.", "warning")
        return redirect(url_for("regles_complexite.liste_regles"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO "regle_complexite" (fibo, score_min, score_max, valeur_base, idate, iuser)
        VALUES (?, ?, ?, ?, DATETIME('now'), 1)
    """, (fibo, score_min, score_max, valeur_base))
    conn.commit()

    # ✅ Mise à jour automatique des projets impactés par cette nouvelle règle
    projets = query_db("""
        SELECT id, score_complexite, id_domaine
        FROM "Projet"
        WHERE score_complexite BETWEEN ? AND ?
    """, [score_min, score_max])

    nb_recalcules = 0
    for p in projets:
        score = p["score_complexite"]
        id_domaine = p["id_domaine"]
        if not id_domaine or not score:
            continue

        resultat = calculer_charge_estimee(score, id_domaine)
        estimation_jh = resultat.get("charge_estimee", 0) if isinstance(resultat, dict) else 0

        cur.execute("""
            UPDATE "Projet"
            SET estimation_jh = ?, uuser = 1, udate = DATETIME('now')
            WHERE id = ?
        """, (estimation_jh, p["id"]))
        nb_recalcules += 1

    conn.commit()

    flash(f"✅ Règle ajoutée et {nb_recalcules} projet(s) recalculé(s).", "success")
    return redirect(url_for("regles_complexite.liste_regles"))


# ===============================
# 🔹 3) Modifier
# ===============================
@regles_complexite_bp.route("/modifier/<int:id>", methods=["POST"])
def modifier_regle(id):
    fibo = request.form.get("fibo")
    score_min = request.form.get("score_min")
    score_max = request.form.get("score_max")
    valeur_base = request.form.get("valeur_base")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE "regle_complexite"
        SET fibo = ?, score_min = ?, score_max = ?, valeur_base = ?,
            udate = DATETIME('now'), uuser = 1
        WHERE id = ?
    """, (fibo, score_min, score_max, valeur_base, id))
    conn.commit()

    projets = query_db("""
        SELECT id, score_complexite, id_domaine
        FROM "Projet"
        WHERE score_complexite BETWEEN ? AND ?
    """, [score_min, score_max])

    nb_recalcules = 0
    for p in projets:
        score = p["score_complexite"]
        id_domaine = p["id_domaine"]

        if not id_domaine or not score:
            continue

        resultat = calculer_charge_estimee(score, id_domaine)
        estimation_jh = resultat.get("charge_estimee", 0) if isinstance(resultat, dict) else 0

        cur.execute("""
            UPDATE "Projet"
            SET estimation_jh = ?, uuser = 1, udate = DATETIME('now')
            WHERE id = ?
        """, (estimation_jh, p["id"]))
        nb_recalcules += 1

    conn.commit()

    flash(f"♻️ Règle modifiée et {nb_recalcules} projet(s) recalculé(s).", "info")
    return redirect(url_for("regles_complexite.liste_regles"))


# ===============================
# 🔹 4) Supprimer
# ===============================
@regles_complexite_bp.route("/supprimer/<int:id>", methods=["POST"])
def supprimer_regle(id):
    conn = get_db()
    cur = conn.cursor()
    try:
        regle = query_db('SELECT score_min, score_max FROM "regle_complexite" WHERE id = ?', [id], one=True)
        score_min, score_max = regle["score_min"], regle["score_max"]

        cur.execute('DELETE FROM "regle_complexite" WHERE id = ?', [id])

        projets = query_db("""
            SELECT id, id_domaine, score_complexite
            FROM "Projet"
            WHERE score_complexite BETWEEN ? AND ?
        """, [score_min, score_max])

        nb_modifies = 0
        for p in projets:
            id_domaine = p["id_domaine"]
            score = p["score_complexite"]
            if not id_domaine or not score:
                continue

            resultat = calculer_charge_estimee(score, id_domaine)
            estimation_jh = resultat.get("charge_estimee", 0) if isinstance(resultat, dict) else 0

            cur.execute("""
                UPDATE "Projet"
                SET estimation_jh = ?, uuser = 1, udate = DATETIME('now')
                WHERE id = ?
            """, (estimation_jh, p["id"]))
            nb_modifies += 1

        conn.commit()
        flash(f"🗑️ Règle supprimée. ♻️ {nb_modifies} projet(s) réévalué(s).", "success")

    except Exception as e:
        flash(f"❌ Erreur lors de la suppression : {e}", "error")

    return redirect(url_for("regles_complexite.liste_regles"))
