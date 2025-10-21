# ==========================================
# routes/demande_it.py
# ==========================================
import sqlite3
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from utils.db_utils import query_db, get_db
from utils.calcul_utils import calculer_charge_estimee

demande_it_bp = Blueprint("demande_it", __name__, url_prefix="/demande_it")


# ==========================================
# Liste des projets
# ==========================================
@demande_it_bp.route("/liste_projet_it")
def liste_projets_it():
    page = request.args.get("page", 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page
    search = request.args.get("q", "").strip()
    incomplets = request.args.get("incomplets", False, type=bool)

    base_query = """
        SELECT 
            p.id,
            p.titre_projet AS titre,
            IFNULL(prog.nom, '-') AS programme,
            IFNULL(prog.type, '-') AS type_programme, 
            IFNULL(d.nom, '-') AS domaine,
            IFNULL(cat.nom, '-') AS categorie,
            IFNULL(s.nom, '-') AS statut,
            IFNULL(p.score_complexite, 0) AS score_complexite,
            IFNULL(p.estimation_jh, 0) AS estimation_jh,
            IFNULL(p.date_mep, '-') AS date_mep,
             p.priority,p.score_wsjf
        FROM Projet p
        LEFT JOIN programme prog ON prog.id = p.id_programme
        LEFT JOIN domaines d ON d.id = p.id_domaine
        LEFT JOIN categorie cat ON cat.id = p.id_categorie
        LEFT JOIN statut s ON s.id = p.id_statut
        WHERE p.type = 'it' AND p.retenue = 1
    """
    args = []

    if search:
        base_query += " AND (p.titre_projet LIKE ? OR prog.nom LIKE ?)"
        args.extend([f"%{search}%", f"%{search}%"])

    if incomplets:
        base_query += " AND (p.id_programme IS NULL OR p.id_domaine IS NULL)"

    total = query_db(f"SELECT COUNT(*) AS count FROM ({base_query})", args, one=True)["count"]
    projets = query_db(f"{base_query} ORDER BY p.id DESC LIMIT ? OFFSET ?", args + [per_page, offset])
    total_pages = (total // per_page) + (1 if total % per_page else 0)

    return render_template(
        "projets_liste_it.html",
        projets=projets,
        page=page,
        total_pages=total_pages,
        search=search,
        incomplets=incomplets
    )


@demande_it_bp.route("/liste_demandes_it")
def liste_demandes_it():
    page = request.args.get("page", 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page
    search = request.args.get("q", "").strip()
    incomplets = request.args.get("incomplets", False, type=bool)
    retenue_filter = request.args.get("retenue", "").strip().lower()

    base_query = """
        SELECT 
            p.id,
            p.titre_projet AS titre,
            IFNULL(prog.nom, '-') AS programme,
            IFNULL(prog.type, '-') AS type_programme, 
            IFNULL(d.nom, '-') AS domaine,
            IFNULL(cat.nom, '-') AS categorie,
            IFNULL(s.nom, '-') AS statut,
            IFNULL(p.score_complexite, 0) AS score_complexite,
            IFNULL(p.estimation_jh, 0) AS estimation_jh,
            IFNULL(p.date_mep, '-') AS date_mep,
            p.retenue,
            p.priority,p.score_wsjf
        FROM Projet p
        LEFT JOIN programme prog ON prog.id = p.id_programme
        LEFT JOIN domaines d ON d.id = p.id_domaine
        LEFT JOIN categorie cat ON cat.id = p.id_categorie
        LEFT JOIN statut_demande s ON s.id = p.retenue
       WHERE p.type = 'it' 
    """
    args = []

    # 🔹 Sous-liste des demandes chiffrées IT
    demandes = query_db("""
        SELECT 
            p.id,
            p.titre_projet AS titre,
            p.score_complexite,
            p.estimation_jh,
            p.retenue
        FROM Projet p
        LEFT JOIN programme prog ON p.id_programme = prog.id
        LEFT JOIN domaines d ON p.id_domaine = d.id
        LEFT JOIN Statut_demande sd ON sd.id = p.id_statut_demande 
        WHERE sd.nom = 'Chiffré' AND p.type = 'it'
        ORDER BY p.id DESC
    """)

    # 🔍 Recherche
    if search:
        base_query += " AND (p.titre_projet LIKE ? OR prog.nom LIKE ? OR d.nom LIKE ?)"
        like = f"%{search}%"
        args.extend([like, like, like])

    # ⚠️ Filtre incomplets
    if incomplets:
        base_query += " AND (p.id_programme IS NULL OR p.id_domaine IS NULL)"

    # 🔽 Filtre retenue
    if retenue_filter == "1":
        base_query += " AND p.retenue = 1"
    elif retenue_filter == "0":
        base_query += " AND p.retenue = 2"
    elif retenue_filter == "null":
        base_query += " AND p.retenue IS NULL"

    # 📄 Pagination
    total = query_db(f"SELECT COUNT(*) AS count FROM ({base_query})", args, one=True)["count"]
    projets = query_db(f"{base_query} ORDER BY p.priority ASC LIMIT ? OFFSET ?", args + [per_page, offset])
    total_pages = (total // per_page) + (1 if total % per_page else 0)

    # 🔁 Rendu HTML
    return render_template(
        "liste_demandes_it.html",
        projets=projets,
        page=page,
        total_pages=total_pages,
        search=search,
        incomplets=incomplets,
        demandes=demandes,
        retenue_filter=retenue_filter
    )




# ==========================================
# Modifier un projet
# ==========================================
@demande_it_bp.route("/modifier_it/<projet_id>", methods=["GET", "POST"])
def modifier_projet_it(projet_id):
    conn = get_db()
    cur = conn.cursor()

    # --- Infos projet ---
    projet = query_db("""
        SELECT 
            p.id,
            p.titre_projet,
            p.description,
            p.date_mep,
            p.id_programme,
            p.id_domaine,
            prog.nom AS programme_nom,
            prog.type AS programme_type,
            d.nom AS domaine_nom,
            s.nom AS statut_nom,
            sd.nom AS statut_demande_nom
        FROM Projet p
        LEFT JOIN programme prog ON prog.id = p.id_programme
        LEFT JOIN domaines d ON d.id = p.id_domaine
        LEFT JOIN categorie c ON c.id = p.id_categorie
        LEFT JOIN statut s ON s.id = p.id_statut
        LEFT JOIN Statut_demande sd ON sd.id = p.id_statut_demande
        WHERE p.type = 'it' AND p.id = ?
    """, [projet_id], one=True)

    if not projet:
        flash("❌ Projet introuvable.", "error")
        return redirect(url_for("demande_it.liste_projets_it"))

    # --- Données de référence ---
    programmes = query_db("SELECT id, nom, type FROM programme ORDER BY nom")
    domaines = query_db("SELECT id, nom FROM domaines ORDER BY nom")
    categories = query_db("SELECT id, nom FROM categorie ORDER BY nom")
    statuts = query_db("SELECT id, nom FROM statut ORDER BY nom")

    # --- Gestion POST ---
    if request.method == "POST":
        id_programme = request.form.get("id_programme") or None
        date_mep = request.form.get("date_mep")

        # ✅ Si un nouveau programme est choisi, on vérifie son type
        if id_programme:
            programme_info = query_db("SELECT type FROM programme WHERE id = ?", [id_programme], one=True)
            if programme_info:
                if programme_info["type"] == "Build":
                    # 🧩 Si Build → remettre type projet à NULL
                    cur.execute("""
                        UPDATE Projet
                        SET type = NULL, udate = DATETIME('now')
                        WHERE id = ?
                    """, [projet_id])
                    conn.commit()
                    flash("🔄 Type du projet réinitialisé (programme de type 'Build').", "info")

        # --- 🔹 Mise à jour automatique des dates des phases selon la nouvelle MEP ---
        if date_mep and id_programme:
            try:
                estimation_info = query_db("""
                    SELECT estimation_jh
                    FROM Projet
                    WHERE id = ?
                """, [projet_id], one=True)

                estimation_jh = estimation_info["estimation_jh"] if estimation_info else None

                if estimation_jh and estimation_jh > 0:
                    phases = query_db("""
                        SELECT ph.id AS phase_id, pf.poids
                        FROM programme_phase pf
                        JOIN phase ph ON ph.id = pf.phase_id
                        WHERE pf.programme_id = ?
                        ORDER BY ph.id
                    """, [id_programme])

                    if phases:
                        mep_date = datetime.strptime(date_mep, "%Y-%m-%d")
                        total_poids = sum([p["poids"] for p in phases])
                        duree_totale = int(estimation_jh)
                        current_date = mep_date - timedelta(days=duree_totale)

                        for p in phases:
                            duree_phase = (p["poids"] / total_poids) * duree_totale
                            date_debut = current_date
                            date_fin = current_date + timedelta(days=duree_phase)
                            current_date = date_fin

                            cur.execute("""
                                UPDATE projet_phases
                                SET date_debut = ?, date_fin = ?
                                WHERE projet_id = ? AND phase_id = ?
                            """, (
                                date_debut.strftime("%Y-%m-%d"),
                                date_fin.strftime("%Y-%m-%d"),
                                projet_id,
                                p["phase_id"]
                            ))
                        conn.commit()
                        flash("🔁 Dates des phases réajustées selon la nouvelle date MEP et la charge estimée.", "info")

                else:
                    flash("⚠️ Dates des phases non recalculées — estimation JH non renseignée.", "warning")

            except Exception as e:
                flash(f"⚠️ Erreur lors de la mise à jour des phases : {e}", "warning")

    # --- Phases du projet ---
    phases_projet = []
    if projet["id_programme"]:
        phases_projet = query_db("""
            SELECT pp.id, ph.nom AS phase_nom, pp.date_debut, pp.date_fin, pf.poids
            FROM projet_phases pp
            JOIN phase ph ON ph.id = pp.phase_id
            JOIN programme_phase pf ON pf.phase_id = ph.id AND pf.programme_id = ?
            WHERE pp.projet_id = ?
            ORDER BY ph.id
        """, [projet["id_programme"], projet_id])

    # --- Rendu du template ---
    return render_template(
        "projets_modifier_it.html",
        projet=projet,
        programmes=programmes,
        domaines=domaines,
        statuts=statuts,
        phases_projet=phases_projet,
    )


# ==========================================
# Mise à jour manuelle des dates des phases + recalcul estimation
# ==========================================
@demande_it_bp.route("/update_phases_dates_it/<int:projet_id>", methods=["POST"])
def update_phases_dates_it(projet_id):
    conn = get_db()
    cur = conn.cursor()
    try:
        # --- Mise à jour des dates ---
        for key, value in request.form.items():
            if key.startswith("date_debut_") or key.startswith("date_fin_"):
                parts = key.split("_")
                champ = parts[1]      # "debut" ou "fin"
                phase_id = parts[2]   # id de la phase
                cur.execute(f"""
                    UPDATE projet_phases
                    SET date_{champ} = ?
                    WHERE id = ? AND projet_id = ?
                """, (value, phase_id, projet_id))
        conn.commit()

        # --- Récupération du projet ---
        projet = query_db("SELECT id_domaine, score_complexite FROM Projet WHERE type ='it' and id = ?", [projet_id], one=True)
        id_domaine = projet["id_domaine"]
        score_complexite = projet["score_complexite"]

        # --- Recalcul de l’estimation si les infos sont complètes ---
        if id_domaine and score_complexite:
            resultat = calculer_charge_estimee(score_complexite, id_domaine)
            estimation_jh = resultat.get("charge_estimee", 0)

            cur.execute("""
                UPDATE Projet
                SET estimation_jh = ?, udate = DATETIME('now')
                WHERE type ='it' and id = ?
            """, (estimation_jh, projet_id))
            conn.commit()

            flash(f"✅ Dates mises à jour et estimation recalculée ({estimation_jh} JH).", "success")
        else:
            flash("⚠️ Dates mises à jour, mais estimation non recalculée (informations incomplètes).", "warning")

    except Exception as e:
        conn.rollback()
        flash(f"❌ Erreur lors de la mise à jour des phases : {e}", "error")

    return redirect(url_for("demande_it.modifier_projet_it", projet_id=projet_id))



# ==========================================
# Chargement dynamique des phases
# ==========================================
@demande_it_bp.route("/phases_programme/<programme_id>")
def phases_programme_it(programme_id):
    try:
        conn = get_db()
        cur = conn.cursor()

        # 🔹 Récupération du projet
        projet_id = request.args.get("projet_id")
        projet_info = query_db("""
            SELECT date_mep, estimation_jh
            FROM Projet
            WHERE type ='it' and id = ?
        """, [projet_id], one=True)

        if not projet_info:
            return jsonify({"success": False, "message": "❌ Projet introuvable.", "phases": []})

        if not projet_info["estimation_jh"]:
            return jsonify({"success": False, "message": "⚠️ Ce projet n’a pas encore d’estimation JH.", "phases": []})

        estimation_jh = int(projet_info["estimation_jh"])
        date_mep = (
            datetime.strptime(projet_info["date_mep"], "%Y-%m-%d")
            if projet_info["date_mep"]
            else datetime.now() + timedelta(days=estimation_jh)
        )

        # 🔹 Récupération des phases du programme
        phases = query_db("""
            SELECT ph.id AS phase_id, ph.nom AS phase_nom, pf.poids
            FROM programme_phase pf
            JOIN phase ph ON ph.id = pf.phase_id
            WHERE pf.programme_id = ?
            ORDER BY ph.id
        """, [programme_id])

        if not phases or len(phases) == 0:
            return jsonify({"success": False, "message": "⚠️ Ce programme ne contient aucune phase.", "phases": []})

        # 🔹 Supprimer les anciennes phases du projet
        cur.execute("DELETE FROM projet_phases WHERE projet_id = ?", [projet_id])

        total_poids = sum(p["poids"] for p in phases) or 1
        current_date = date_mep - timedelta(days=estimation_jh)
        phases_data = []

        for p in phases:
            duree_phase = int((p["poids"] / total_poids) * estimation_jh)
            date_debut = current_date.strftime("%Y-%m-%d")
            date_fin = (current_date + timedelta(days=duree_phase)).strftime("%Y-%m-%d")
            current_date += timedelta(days=duree_phase)

            cur.execute("""
                INSERT INTO projet_phases (projet_id, phase_id, date_debut, date_fin)
                VALUES (?, ?, ?, ?)
            """, (projet_id, p["phase_id"], date_debut, date_fin))

            phases_data.append({
                "phase_id": p["phase_id"],
                "phase_nom": p["phase_nom"],
                "poids": p["poids"],
                "date_debut": date_debut,
                "date_fin": date_fin
            })

        conn.commit()

        return jsonify({
            "success": True,
            "message": "✅ Phases enregistrées et calculées avec succès.",
            "phases": phases_data
        })

    except Exception as e:
        print("❌ Erreur phases_programme :", e)
        return jsonify({"success": False, "message": f"❌ Erreur interne : {e}", "phases": []})

# ==========================================
# Supprimer un projet
# ==========================================
@demande_it_bp.route("/supprimer/<projet_id>", methods=["POST"])
def supprimer_projet_it(projet_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM Projet WHERE type ='it' and id = ?", [projet_id])
    conn.commit()
    flash("🗑️ Projet supprimé avec succès.", "success")
    return redirect(url_for("demande_it.liste_projets_it"))


# ==========================================
# 🟦 Modifier une demande
# ==========================================
@demande_it_bp.route("/modifier_demande_it/<projet_id>", methods=["GET", "POST"])
def modifier_demande_it(projet_id):
    conn = get_db()
    cur = conn.cursor()

    # --- 🔹 Récupération des infos actuelles du projet
    demande = query_db("SELECT * FROM Projet WHERE type ='it' and id = ?", [projet_id], one=True)
    if not demande:
        flash("❌ Demande introuvable.", "error")
        return redirect(url_for("demande_it.liste_demandes_it"))

    # 🔸 Sauvegarder les anciennes valeurs pour comparaison
    ancien_domaine = demande["id_domaine"]
    ancien_score_complexite = demande["score_complexite"]

    # --- 🔹 Données de référence
    programmes = query_db("SELECT id, nom FROM programme ORDER BY nom")
    domaines = query_db("SELECT id, nom FROM domaines ORDER BY nom")
    # categories = query_db("SELECT id, nom FROM categorie ORDER BY nom")
    statuts = query_db("SELECT id, nom FROM statut_demande where nom in ('Retenu','Non Retenue') ORDER BY nom")
    statut_demande = query_db("""
        SELECT p.*, s.nom AS nom_statut_demande
        FROM Projet p
        LEFT JOIN Statut_demande s ON s.id = p.id_statut_demande
        WHERE p.id = ?
    """, [projet_id], one=True)
    # 🔹 Valeurs métier associées au projet
    valeurs = query_db("""
            SELECT 
                vmp.id_valeur_metier,
                vm.libelle,
                vm.type_libelle,
                vm.valeur_libelle,
                vmp.id AS id_lien
            FROM valeur_metier_projet vmp
            JOIN valeur_metier vm ON vm.id = vmp.id_valeur_metier
            WHERE vmp.id_projet = ?
            ORDER BY vm.libelle
        """, [projet_id])

    # 🔹 Dropdowns : toutes les options disponibles groupées par libellé
    all_options = query_db("""
            SELECT id, libelle, type_libelle, valeur_libelle
            FROM valeur_metier
            ORDER BY libelle, type_libelle, valeur_libelle
        """)

    # On crée un dictionnaire : { "libelle" : [liste des options correspondantes] }
    dropdowns = {}
    for opt in all_options:
        lib = opt["libelle"]
        dropdowns.setdefault(lib, []).append(opt)
    # --- 🔹 Complexités disponibles
    libelles_complexite = query_db("""
        SELECT DISTINCT libelle FROM complexite
        WHERE libelle IS NOT NULL AND libelle <> ''
        ORDER BY libelle
    """)
    complexites = []
    for l in libelles_complexite:
        lib = l["libelle"]
        valeur_existante = query_db("""
            SELECT c.id AS id_complexite, c.libelle, c.type_libelle, c.valeur_libelle
            FROM complexite_projet cp
            JOIN complexite c ON c.id = cp.id_complexite
            WHERE cp.id_projet = ? AND c.libelle = ?
            LIMIT 1
        """, [projet_id, lib], one=True)
        if valeur_existante:
            complexites.append(valeur_existante)
        else:
            complexites.append({
                "libelle": lib,
                "id_complexite": None,
                "type_libelle": None,
                "valeur_libelle": None
            })

    complexite_possibles = query_db("""
        SELECT DISTINCT libelle, id, type_libelle, valeur_libelle
        FROM complexite
        WHERE type_libelle IS NOT NULL AND type_libelle <> ''
        ORDER BY id
    """)
    dropdowns_complexite = {}
    for c in complexite_possibles:
        dropdowns_complexite.setdefault(c["libelle"], []).append(dict(c))

    # --- 🔹 Enregistrement
    if request.method == "POST":
        titre = request.form.get("titre")
        description = request.form.get("description")
        id_programme = request.form.get("id_programme") or None
        id_domaine = request.form.get("id_domaine") or None
        retenue = request.form.get("statut")  or None
        date_mep = request.form.get("date_mep")

        # --- 🔸 Mise à jour du projet principal
        cur.execute("""
            UPDATE Projet
            SET titre_projet = ?, description = ?, id_programme = ?, 
                id_domaine = ?, retenue = ?, 
                date_mep = ?, udate = DATETIME('now'), uuser = 1
            WHERE  type ='it' and  id = ?
        """, (titre, description, id_programme, id_domaine, retenue, date_mep, projet_id))
        conn.commit()
        ancien_programme_id = demande["id_programme"]
        nouveau_programme_id = id_programme  # déjà récupéré ci-dessus

        if ancien_programme_id != nouveau_programme_id and nouveau_programme_id:
            # 🧹 Supprimer les anciennes phases du projet
            cur.execute("DELETE FROM projet_phases WHERE projet_id = ?", [projet_id])
            conn.commit()
            # 🆕 Insérer les phases du nouveau programme
            phases_nouveau = query_db("""
                    SELECT phase_id, poids FROM programme_phase WHERE programme_id = ?
                """, [nouveau_programme_id])

            for p in phases_nouveau:
                cur.execute("""
                        INSERT INTO projet_phases (projet_id, phase_id, date_debut, date_fin)
                        VALUES (?, ?, NULL, NULL)
                    """, [projet_id, p["phase_id"]])
            conn.commit()
            flash("✅ Phases mises à jour selon le nouveau programme.", "info")
        # --- 🔹 Recalcul conditionnel de l’estimation
        projet_updated = query_db("""
            SELECT id_domaine, score_complexite
            FROM Projet
            WHERE id = ?
        """, [projet_id], one=True)

        nouveau_domaine = projet_updated["id_domaine"]
        nouveau_score_complexite = projet_updated["score_complexite"]

        # ⚙️ Recalcul uniquement si le domaine ou la complexité ont changé
        if (nouveau_domaine != ancien_domaine) or (nouveau_score_complexite != ancien_score_complexite):
            if nouveau_domaine and nouveau_score_complexite:
                resultat = calculer_charge_estimee(nouveau_score_complexite, nouveau_domaine)
                estimation_jh = resultat.get("charge_estimee", 0)

                cur.execute("""
                    UPDATE Projet
                    SET estimation_jh = ?, udate = DATETIME('now')
                    WHERE id = ?
                """, (estimation_jh, projet_id))
                conn.commit()

                flash(f"✅ Estimation recalculée (nouveau domaine ou complexité modifiée → {estimation_jh} JH).", "success")
            else:
                cur.execute("UPDATE Projet SET estimation_jh = 0 WHERE type ='it' and id = ?", [projet_id])
                conn.commit()
                flash("⚠️ Domaine ou complexité manquants — estimation non recalculée.", "warning")
        else:
            flash("ℹ️ Aucune modification détectée sur le domaine ou la complexité — pas de recalcul.", "info")

        return redirect(url_for("demande_it.modifier_demande_it", projet_id=projet_id))




    # --- 🔹 Affichage du template
    return render_template(
        "modifier_demande_it.html",
        demande=demande,
        programmes=programmes,
        domaines=domaines,
        statuts=statuts,
        statut_demande=statut_demande,
        complexites=complexites,
        dropdowns_complexite=dropdowns_complexite,
        valeurs=valeurs,
        dropdowns=dropdowns
    )
@demande_it_bp.route("/update_all_complexites_demande_it/<projet_id>", methods=["POST"])
def update_all_complexites_demande_it(projet_id):
    conn = get_db()
    cur = conn.cursor()

    # --- 🔹 Récupération des complexités
    libelles_complexite = query_db("SELECT DISTINCT libelle FROM complexite WHERE libelle <> ''")
    nb_total = len(libelles_complexite)
    nb_remplies = 0
    toutes_remplies = True
    changements = False

    for l in libelles_complexite:
        lib = l["libelle"]
        valeur_id = request.form.get(f"complexite_{lib}")
        print(f"➡️  {lib} → valeur_id = {valeur_id}")

        if not valeur_id:
            toutes_remplies = False
            continue
        else:
            nb_remplies += 1

        # Vérifie si déjà présent
        existing = query_db("""
            SELECT cp.id_complexite 
            FROM complexite_projet cp
            JOIN complexite c ON c.id = cp.id_complexite
            WHERE cp.id_projet = ? AND c.libelle = ?
        """, [projet_id, lib], one=True)

        if existing:
            if str(existing["id_complexite"]) != str(valeur_id):
                changements = True
                cur.execute("""
                    UPDATE complexite_projet
                    SET id_complexite = ?, udate = DATETIME('now'), uuser = 1
                    WHERE id_projet = ? AND id_complexite = ?
                """, (valeur_id, projet_id, existing["id_complexite"]))
        else:
            changements = True
            cur.execute("""
                INSERT INTO complexite_projet (id_projet, id_complexite, idate, iuser)
                VALUES (?, ?, DATETIME('now'), 1)
            """, (projet_id, valeur_id))

    conn.commit()

    partiellement_remplies = 0 < nb_remplies < nb_total

    somme_valeur_metier = query_db("""
        SELECT SUM(vm.valeur_libelle * vm.ponderation) AS total
        FROM valeur_metier_projet vmp
        JOIN valeur_metier vm ON vm.id = vmp.id_valeur_metier
        WHERE vmp.id_projet = ?
    """, [projet_id], one=True)["total"] or 0

    # --- 🔹 Recalcul du score total
    score_complexite = query_db("""
        SELECT AVG(c.valeur_libelle * c.ponderation) AS total
        FROM complexite_projet cp
        JOIN complexite c ON c.id = cp.id_complexite
        WHERE cp.id_projet = ?
    """, [projet_id], one=True)["total"] or 0

    # Calcul final
    score_wsjf = round(somme_valeur_metier / score_complexite, 2)

    # --- 🔹 Calcul de l'estimation JH
    demande = query_db("SELECT id_domaine FROM Projet WHERE id = ?", [projet_id], one=True)
    id_domaine = demande["id_domaine"]
    estimation_jh = 0
    if id_domaine:
        resultat = calculer_charge_estimee(score_complexite, id_domaine)
        estimation_jh = resultat.get("charge_estimee", 0)

    cur.execute("""
        UPDATE Projet
        SET score_complexite = ?, score_wsjf = ?, estimation_jh = ?, udate = DATETIME('now'), uuser = 1
        WHERE id = ?
    """, (score_complexite, score_wsjf, estimation_jh, projet_id))
    conn.commit()

    # --- 🔹 Gestion du statut
    statut_chiffre = query_db(
        "SELECT id FROM Statut_demande WHERE LOWER(nom) LIKE '%chiffré%' AND nom NOT LIKE '%partiel%'", one=True)
    statut_partiel = query_db("SELECT id FROM Statut_demande WHERE LOWER(nom) LIKE '%partiel%chiffré%'", one=True)
    statut_non = query_db("SELECT id FROM Statut_demande WHERE LOWER(nom) LIKE '%non%encore%chiffré%'", one=True)

    id_statut_demande = None

    if toutes_remplies and statut_chiffre:
        id_statut_demande = statut_chiffre["id"]
        flash("✅ Toutes les complexités sont renseignées — statut *Chiffré*.", "success")
    elif partiellement_remplies and statut_partiel:
        id_statut_demande = statut_partiel["id"]
        flash("⚠️ Chiffrage partiel — statut *Partiellement chiffré*.", "warning")
    elif not toutes_remplies and not partiellement_remplies and statut_non:
        id_statut_demande = statut_non["id"]
        flash("ℹ️ Chiffrage incomplet — statut *Non encore chiffré*.", "info")
    else:
        flash("⚠️ Aucun statut mis à jour (vérifie les libellés dans Statut_demande).", "warning")

    if id_statut_demande:
        cur.execute("UPDATE Projet SET id_statut_demande = ? WHERE id = ?", [id_statut_demande, projet_id])
    else:
        print("⚠️ id_statut_demande est None → aucune mise à jour effectuée (évite IntegrityError).")

    conn.commit()

    # --- 🔹 🔥 Nouvelle étape : mise à jour automatique de la priorité
    print(f"[LOG] 🔄 Recalcul des priorités basé sur score_wsjf pour le projet {projet_id}")

    tous_projets = query_db("""
        SELECT id, score_wsjf
        FROM Projet
        WHERE score_wsjf IS NOT NULL
        ORDER BY score_wsjf DESC
    """)

    for index, p in enumerate(tous_projets, start=1):
        cur.execute("""
            UPDATE Projet
            SET priority = ?
            WHERE id = ?
        """, (index, p["id"]))

    conn.commit()

    priority_actuelle = query_db("SELECT priority FROM Projet WHERE id = ?", [projet_id], one=True)
    if priority_actuelle:
        flash(f"🏅 Priorité du projet mise à jour : {priority_actuelle['priority']}", "success")

    flash(f"🔄 Score total = {score_complexite}, Estimation = {estimation_jh} JH", "info")

    return redirect(url_for("demande_it.modifier_demande_it", projet_id=projet_id))


@demande_it_bp.route("/supprimer_demande/<int:projet_id>", methods=["POST"])
def supprimer_demande_it(projet_id):
    conn = get_db()
    cur = conn.cursor()

    try:
        # Supprimer d’abord les dépendances

        cur.execute("DELETE FROM complexite_projet WHERE type ='it' and id_projet = ?", [projet_id])

        # Puis le projet lui-même
        cur.execute("DELETE FROM Projet WHERE id = ?", [projet_id])
        conn.commit()
        flash("✅ Projet supprimé avec succès.", "success")

    except sqlite3.IntegrityError:
        flash("❌ Impossible de supprimer : le projet est encore référencé dans d'autres tables.", "error")

    except Exception as e:
        flash(f"⚠️ Erreur inattendue : {e}", "error")

    finally:
        conn.close()

    return redirect(url_for("demande_it.liste_demandes_it"))



@demande_it_bp.route("/get_valeurs_complexite_it", methods=["POST"])
def get_valeurs_complexite_it():
    data = request.get_json()
    libelle = data.get("libelle")
    type_libelle = data.get("type_libelle")

    if not libelle or not type_libelle:
        return jsonify([])

    valeurs = query_db("""
        SELECT id, valeur_libelle
        FROM complexite
        WHERE LOWER(libelle) = LOWER(?) AND LOWER(type_libelle) = LOWER(?)
        ORDER BY id
    """, [libelle, type_libelle])

    # ✅ Conversion Row → dict pour chaque enregistrement
    valeurs_dict = [dict(v) for v in valeurs]

    return jsonify(valeurs_dict)
# @demande_it_bp.route("/toggle_retenue/<int:projet_id>", methods=["POST"])
# def toggle_retenue_it(projet_id):
#     conn = get_db()
#     cur = conn.cursor()
#
#     # --- 🔹 Récupérer l’état actuel
#     projet = query_db("""
#         SELECT retenue, id_programme, date_mep, estimation_jh
#         FROM Projet
#         WHERE type ='it' and id = ?
#     """, [projet_id], one=True)
#
#     if not projet:
#         flash("❌ Demande introuvable.", "error")
#         return redirect(url_for("demande_it.liste_demandes_it"))
#     retenu = query_db("SELECT id FROM statut_demande where nom ='Retenu'", one=True)
#     non_retenu = query_db("SELECT id FROM statut_demande where nom ='Non Retenue'", one=True)
#     retenu_id = retenu["id"]
#     non_retenu_id = non_retenu["id"]
#     # --- 🔹 Inverser la valeur du champ retenue
#     nouvelle_valeur = non_retenu_id if projet["retenue"] == retenu_id else retenu_id
#
#     # --- 🔸 Mettre à jour la table Projet
#     cur.execute("""
#         UPDATE Projet
#         SET retenue = ?, udate = DATETIME('now'), uuser = 1
#         WHERE type ='it' and id = ?
#     """, (nouvelle_valeur, projet_id))
#     conn.commit()
#
#     # --- 🧮 Si la demande devient retenue → recalculer les phases
#     if nouvelle_valeur == retenu_id:
#         id_programme = projet["id_programme"]
#         date_mep = projet["date_mep"]
#         estimation_jh = projet["estimation_jh"]
#
#         if id_programme and date_mep and estimation_jh:
#             try:
#                 # 🟢 Récupérer les phases et leurs poids
#                 phases = query_db("""
#                     SELECT ph.id AS phase_id, ph.nom, pf.poids
#                     FROM programme_phase pf
#                     JOIN phase ph ON ph.id = pf.phase_id
#                     WHERE pf.programme_id = ?
#                     ORDER BY ph.id
#                 """, [id_programme])
#
#                 if not phases:
#                     flash("⚠️ Aucune phase définie pour ce programme.", "warning")
#                 else:
#                     total_poids = sum([p["poids"] for p in phases])
#                     mep_date = datetime.strptime(date_mep, "%Y-%m-%d")
#                     duree_totale = int(estimation_jh)
#                     current_date = mep_date - timedelta(days=duree_totale)
#
#                     # 🔁 Mise à jour des dates des phases
#                     for p in phases:
#                         duree_phase = (p["poids"] / total_poids) * duree_totale
#                         date_debut = current_date
#                         date_fin = current_date + timedelta(days=duree_phase)
#                         current_date = date_fin
#
#                         cur.execute("""
#                             UPDATE projet_phases
#                             SET date_debut = ?, date_fin = ?
#                             WHERE projet_id = ? AND phase_id = ?
#                         """, (
#                             date_debut.strftime("%Y-%m-%d"),
#                             date_fin.strftime("%Y-%m-%d"),
#                             projet_id,
#                             p["phase_id"]
#                         ))
#
#                     conn.commit()
#                     flash("📅 Phases du projet planifiées automatiquement selon la MEP et la charge estimée.", "info")
#
#             except Exception as e:
#                 flash(f"⚠️ Erreur lors du calcul des phases : {e}", "warning")
#         else:
#             flash("⚠️ Impossible de calculer les phases — programme, estimation JH ou MEP manquants.", "warning")
#
#     flash(f"✅ La demande #{projet_id} a été marquée comme {'Retenue' if nouvelle_valeur == 1 else 'Non retenue'}.", "success")
#     return redirect(url_for("demande_it.liste_demandes_it"))
# ===============================
# Bloc 2️⃣ - Mettre à jour une valeur métier à la fois
# ===============================
@demande_it_bp.route("/update_all_valeurs_metier_it/<projet_id>", methods=["POST"])
def update_all_valeurs_metier_it(projet_id):
    conn = get_db()
    cur = conn.cursor()

    # --- 🔹 Récupération des libellés de valeurs métier
    libelles_vm = query_db("SELECT DISTINCT libelle FROM valeur_metier WHERE libelle <> ''")
    nb_total = len(libelles_vm)
    nb_remplies = 0
    toutes_remplies = True
    changements = False

    for l in libelles_vm:
        lib = l["libelle"]
        valeur_id = request.form.get(f"valeur_{lib}")
        print(f"➡️ {lib} → valeur_id = {valeur_id}")

        if not valeur_id:
            toutes_remplies = False
            continue
        else:
            nb_remplies += 1

        # Vérifie si déjà présente
        existing = query_db("""
            SELECT vmp.id_valeur_metier
            FROM valeur_metier_projet vmp
            JOIN valeur_metier vm ON vm.id = vmp.id_valeur_metier
            WHERE vmp.id_projet = ? AND vm.libelle = ?
        """, [projet_id, lib], one=True)

        if existing:
            if str(existing["id_valeur_metier"]) != str(valeur_id):
                changements = True
                cur.execute("""
                    UPDATE valeur_metier_projet
                    SET id_valeur_metier = ?, udate = DATETIME('now'), uuser = 1
                    WHERE id_projet = ? 
                      AND id_valeur_metier = ?
                """, (valeur_id, projet_id, existing["id_valeur_metier"]))
        else:
            changements = True
            cur.execute("""
                INSERT INTO valeur_metier_projet (id_projet, id_valeur_metier, idate, iuser)
                VALUES (?, ?, DATETIME('now'), 1)
            """, (projet_id, valeur_id))

    conn.commit()

    partiellement_remplies = 0 < nb_remplies < nb_total

    # --- 🔹 Calcul du score global (facultatif, si tu veux un total VM)
    score_valeur_metier = query_db("""
        SELECT SUM(vm.valeur_libelle * vm.ponderation) AS total
        FROM valeur_metier_projet vmp
        JOIN valeur_metier vm ON vm.id = vmp.id_valeur_metier
        WHERE vmp.id_projet = ?
    """, [projet_id], one=True)["total"] or 0

    # --- 🔹 Mise à jour du projet (pour stocker score VM)
    cur.execute("""
        UPDATE Projet
        SET score_valeur_metier = ?, udate = DATETIME('now'), uuser = 1
        WHERE id = ?
    """, (score_valeur_metier, projet_id))
    conn.commit()

    # --- 🔹 Messages d’état utilisateur
    if toutes_remplies:
        flash("✅ Toutes les valeurs métier ont été renseignées.", "success")
    elif partiellement_remplies:
        flash("⚠️ Certaines valeurs métier sont manquantes (partiel).", "warning")
    else:
        flash("ℹ️ Aucune valeur métier renseignée.", "info")

    flash(f"🔄 Score total des valeurs métier : {score_valeur_metier}", "info")

    return redirect(url_for("demande_it.modifier_demande_it", projet_id=projet_id))



@demande_it_bp.route("/get_valeurs_metier_it", methods=["POST"])
def get_valeurs_metier_it():
    data = request.get_json()
    libelle = data.get("libelle")
    type_libelle = data.get("type_libelle")
    rows = query_db("""
        SELECT id, valeur_libelle
        FROM valeur_metier
        WHERE lower(libelle) = lower(?) AND lower(type_libelle) = lower(?)
        ORDER BY valeur_libelle
    """, [libelle, type_libelle])
    return jsonify(rows)