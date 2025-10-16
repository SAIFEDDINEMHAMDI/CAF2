# ==========================================
# routes/projet_routes.py
# ==========================================
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from utils.db_utils import query_db, get_db
from utils.calcul_utils import calculer_charge_estimee

projet_bp = Blueprint("projet", __name__, url_prefix="/projet")


# ==========================================
# Liste des projets
# ==========================================
@projet_bp.route("/liste")
def liste_projets():
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
            IFNULL(d.nom, '-') AS domaine,
            IFNULL(cat.nom, '-') AS categorie,
            IFNULL(s.nom, '-') AS statut,
            IFNULL(p.score_complexite, 0) AS score_complexite,
            IFNULL(p.estimation_jh, 0) AS estimation_jh,
            IFNULL(p.date_mep, '-') AS date_mep
        FROM Projet p
        LEFT JOIN programme prog ON prog.id = p.id_programme
        LEFT JOIN domaines d ON d.id = p.id_domaine
        LEFT JOIN categorie cat ON cat.id = p.id_categorie
        LEFT JOIN statut s ON s.id = p.id_statut
        WHERE retenue = 1 and 1=1
    """
    args = []

    if search:
        base_query += " AND (p.titre_projet LIKE ? OR prog.nom LIKE ?)"
        args.extend([f"%{search}%", f"%{search}%"])

    if incomplets:
        base_query += " AND (p.id_programme IS NULL OR p.id_domaine IS NULL OR p.id_categorie IS NULL)"

    total = query_db(f"SELECT COUNT(*) as count FROM ({base_query})", args, one=True)["count"]
    projets = query_db(f"{base_query} ORDER BY p.id DESC LIMIT ? OFFSET ?", args + [per_page, offset])
    total_pages = (total // per_page) + (1 if total % per_page else 0)

    return render_template(
        "projets_liste.html",
        projets=projets,
        page=page,
        total_pages=total_pages,
        search=search,
        incomplets=incomplets
    )

@projet_bp.route("/liste_demandes")
def liste_demandes():
    page = request.args.get("page", 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page
    search = request.args.get("q", "").strip()
    incomplets = request.args.get("incomplets", False, type=bool)
    retenue_filter = request.args.get("retenue", "").strip().lower()  # 👈 Nouveau filtre

    # ============================
    # 🔹 Base query
    # ============================
    base_query = """
        SELECT 
            p.id,
            p.titre_projet AS titre,
            IFNULL(prog.nom, '-') AS programme,
            IFNULL(d.nom, '-') AS domaine,
            IFNULL(cat.nom, '-') AS categorie,
            IFNULL(s.nom, '-') AS statut,
            IFNULL(p.score_complexite, 0) AS score_complexite,
            IFNULL(p.estimation_jh, 0) AS estimation_jh,
            IFNULL(p.date_mep, '-') AS date_mep,
            p.retenue
        FROM Projet p
        LEFT JOIN programme prog ON prog.id = p.id_programme
        LEFT JOIN domaines d ON d.id = p.id_domaine
        LEFT JOIN categorie cat ON cat.id = p.id_categorie
        LEFT JOIN statut_demande s ON s.id = p.retenue
        WHERE 1=1
    """
    args = []

    # ============================
    # 🔍 Recherche
    # ============================
    if search:
        base_query += " AND (p.titre_projet LIKE ? OR prog.nom LIKE ? OR d.nom LIKE ?)"
        like = f"%{search}%"
        args.extend([like, like, like])

    # ============================
    # ⚠️ Filtre incomplets
    # ============================
    if incomplets:
        base_query += " AND (p.id_programme IS NULL OR p.id_domaine IS NULL OR p.id_categorie IS NULL)"

    # ============================
    # 🔽 Filtre retenue
    # ============================
    # 🔹 Filtrage selon le statut de retenue
    if retenue_filter == "1":
        # Retenue
        base_query += " AND p.retenue = 1"
    elif retenue_filter == "0":
        # Non retenue
        base_query += " AND p.retenue = 2"
    elif retenue_filter == "null":
        # À prévoir
        base_query += " AND p.retenue IS NULL"

    # ============================
    # 📄 Pagination
    # ============================
    total = query_db(f"SELECT COUNT(*) as count FROM ({base_query})", args, one=True)["count"]
    projets = query_db(f"{base_query} ORDER BY p.id DESC LIMIT ? OFFSET ?", args + [per_page, offset])
    total_pages = (total // per_page) + (1 if total % per_page else 0)

    # ============================
    # 🔁 Rendu HTML
    # ============================
    return render_template(
        "liste_demandes.html",
        projets=projets,
        page=page,
        total_pages=total_pages,
        search=search,
        incomplets=incomplets,
        retenue_filter=retenue_filter  # 👈 Passé au template
    )



# ==========================================
# Modifier un projet
# ==========================================
@projet_bp.route("/modifier/<projet_id>", methods=["GET", "POST"])
def modifier_projet(projet_id):
    conn = get_db()
    cur = conn.cursor()

    # --- Infos projet ---
    projet = query_db("SELECT * FROM Projet WHERE id = ?", [projet_id], one=True)
    if not projet:
        flash("❌ Projet introuvable.", "error")
        return redirect(url_for("projet.liste_projets"))

    # --- Affectations collaborateurs ---
    affectations = query_db("""
        SELECT 
            ap.id,
            c.nom || ' ' || c.prenom AS collaborateur,
            ap.role,
            ap.pourcentage_allocation
        FROM collaborateur_projet ap
        JOIN tmp_collaborateurs c ON c.matricule = ap.collaborateur_matricule
        WHERE ap.projet_id = ?
        ORDER BY ap.id DESC
    """, [projet_id])
    collaborateurs = query_db("""
        SELECT matricule, nom || ' ' || prenom AS nom_complet
        FROM tmp_collaborateurs
        ORDER BY nom
    """)
    # --- Données de référence ---
    programmes = query_db("SELECT id, nom FROM programme ORDER BY nom")
    domaines = query_db("SELECT id, nom FROM domaines ORDER BY nom")
    categories = query_db("SELECT id, nom FROM categorie ORDER BY nom")
    statuts = query_db("SELECT id, nom FROM statut ORDER BY nom")

    # --- Complexités disponibles ---
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
            complexites.append({"libelle": lib, "id_complexite": None, "type_libelle": None, "valeur_libelle": None})

    complexite_possibles = query_db("""
        SELECT DISTINCT libelle, id, type_libelle, valeur_libelle
        FROM complexite
        WHERE type_libelle IS NOT NULL AND type_libelle <> ''
        ORDER BY id
    """)
    dropdowns_complexite = {}
    for c in complexite_possibles:
        dropdowns_complexite.setdefault(c["libelle"], []).append(dict(c))

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

    # --- Enregistrement ---
    if request.method == "POST":
        titre = request.form.get("titre")
        description = request.form.get("description")
        id_programme = request.form.get("id_programme") or None
        id_domaine = request.form.get("id_domaine") or None
        id_categorie = request.form.get("id_categorie") or None
        id_statut = request.form.get("statut") or None
        date_mep = request.form.get("date_mep")

        # --- Mise à jour du projet ---
        cur.execute("""
            UPDATE Projet
            SET titre_projet = ?, description = ?, id_programme = ?, 
                id_domaine = ?, id_categorie = ?, id_statut = ?, 
                date_mep = ?, udate = DATETIME('now'), uuser = 1
            WHERE id = ?
        """, (titre, description, id_programme, id_domaine, id_categorie, id_statut, date_mep, projet_id))
        conn.commit()

        # --- 🔹 Mise à jour automatique des dates des phases selon la nouvelle MEP ---
        if date_mep and id_programme:
            try:
                # Vérifier si estimation_jh est renseignée
                estimation_info = query_db("""
                    SELECT estimation_jh
                    FROM Projet
                    WHERE id = ?
                """, [projet_id], one=True)

                estimation_jh = estimation_info["estimation_jh"] if estimation_info else None

                # ⚙️ Si estimation_jh est renseignée, on fait le calcul
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

                        # Utiliser l’estimation_jh comme durée totale du projet
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

                # ❌ Sinon, on ne fait rien
                else:
                    flash("⚠️ Dates des phases non recalculées — estimation JH non renseignée.", "warning")

            except Exception as e:
                flash(f"⚠️ Erreur lors de la mise à jour des phases : {e}", "warning")

        # --- Recalcul de l’estimation si domaine + complexité connus ---
        projet_updated = query_db("""
            SELECT id_domaine, score_complexite
            FROM Projet
            WHERE id = ?
        """, [projet_id], one=True)

        id_domaine = projet_updated["id_domaine"]
        score_complexite = projet_updated["score_complexite"]

        if id_domaine and score_complexite:
            resultat = calculer_charge_estimee(score_complexite, id_domaine)
            estimation_jh = resultat.get("charge_estimee", 0)
            cur.execute("""
                UPDATE Projet
                SET estimation_jh = ?, udate = DATETIME('now')
                WHERE id = ?
            """, (estimation_jh, projet_id))
            conn.commit()
            flash(f"✅ Informations enregistrées et estimation recalculée ({estimation_jh} JH).", "success")
        else:
            cur.execute("UPDATE Projet SET estimation_jh = 0 WHERE id = ?", [projet_id])
            conn.commit()
            flash("⚠️ Informations enregistrées — estimation non recalculée (domaine ou complexité manquants).",
                  "warning")

        return redirect(url_for("projet.modifier_projet", projet_id=projet_id))

    return render_template(
        "projets_modifier.html",
        projet=projet,
        programmes=programmes,
        domaines=domaines,
        categories=categories,
        statuts=statuts,
        complexites=complexites,
        dropdowns_complexite=dropdowns_complexite,
        phases_projet=phases_projet,
        affectations=affectations,
        collaborateurs=collaborateurs

    )
# ==========================================
# 🔹 Mise à jour des complexités + recalculs automatiques
# ==========================================
@projet_bp.route("/update_all_complexites/<projet_id>", methods=["POST"])
def update_all_complexites(projet_id):
    conn = get_db()
    cur = conn.cursor()

    # --- Mise à jour des complexités ---
    libelles_complexite = query_db("SELECT DISTINCT libelle FROM complexite WHERE libelle <> ''")
    for l in libelles_complexite:
        lib = l["libelle"]
        valeur_id = request.form.get(f"complexite_{lib}")
        if not valeur_id:
            continue

        existing = query_db("""
            SELECT cp.id_complexite FROM complexite_projet cp
            JOIN complexite c ON c.id = cp.id_complexite
            WHERE cp.id_projet = ? AND c.libelle = ?
        """, [projet_id, lib], one=True)

        if existing:
            cur.execute("""
                UPDATE complexite_projet
                SET id_complexite = ?, udate = DATETIME('now'), uuser = 1
                WHERE id_projet = ? AND id_complexite = ?
            """, (valeur_id, projet_id, existing["id_complexite"]))
        else:
            cur.execute("""
                INSERT INTO complexite_projet (id_projet, id_complexite, idate, iuser)
                VALUES (?, ?, DATETIME('now'), 1)
            """, (projet_id, valeur_id))
    conn.commit()

    # --- Recalcul du score total ---
    score_complexite = query_db("""
        SELECT SUM(c.valeur_libelle * c.ponderation) AS total
        FROM complexite_projet cp
        JOIN complexite c ON c.id = cp.id_complexite
        WHERE cp.id_projet = ?
    """, [projet_id], one=True)["total"] or 0

    projet = query_db("SELECT id_domaine, id_programme, date_mep FROM Projet WHERE id = ?", [projet_id], one=True)
    id_domaine = projet["id_domaine"]
    id_programme = projet["id_programme"]
    date_mep = projet["date_mep"]

    # --- Calcul estimation JH ---
    estimation_jh = 0
    if id_domaine:
        resultat = calculer_charge_estimee(score_complexite, id_domaine)
        estimation_jh = resultat.get("charge_estimee", 0)
    else:
        flash("⚠️ Domaine non renseigné — estimation non calculée.", "warning")

    cur.execute("""
        UPDATE Projet
        SET score_complexite = ?, estimation_jh = ?, udate = DATETIME('now'), uuser = 1
        WHERE id = ?
    """, (score_complexite, estimation_jh, projet_id))
    conn.commit()

    flash(f"✅ Complexités mises à jour (Score={score_complexite}, Estimation={estimation_jh} JH)", "success")
    return redirect(url_for("projet.modifier_projet", projet_id=projet_id))

@projet_bp.route("/<int:projet_id>/affectations")
def liste_affectations(projet_id):
    projet = query_db("SELECT id, titre_projet FROM Projet WHERE id = ?", [projet_id], one=True)
    affectations = query_db(""" ... """, [projet_id])
    collaborateurs = query_db(""" ... """)
    return render_template(
        "affectation_collaborateur_projet.html",
        projet=projet,
        affectations=affectations,
        collaborateurs=collaborateurs
    )

# ==========================================
# Mise à jour manuelle des dates des phases + recalcul estimation
# ==========================================
@projet_bp.route("/update_phases_dates/<int:projet_id>", methods=["POST"])
def update_phases_dates(projet_id):
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
        projet = query_db("SELECT id_domaine, score_complexite FROM Projet WHERE id = ?", [projet_id], one=True)
        id_domaine = projet["id_domaine"]
        score_complexite = projet["score_complexite"]

        # --- Recalcul de l’estimation si les infos sont complètes ---
        if id_domaine and score_complexite:
            resultat = calculer_charge_estimee(score_complexite, id_domaine)
            estimation_jh = resultat.get("charge_estimee", 0)

            cur.execute("""
                UPDATE Projet
                SET estimation_jh = ?, udate = DATETIME('now')
                WHERE id = ?
            """, (estimation_jh, projet_id))
            conn.commit()

            flash(f"✅ Dates mises à jour et estimation recalculée ({estimation_jh} JH).", "success")
        else:
            flash("⚠️ Dates mises à jour, mais estimation non recalculée (informations incomplètes).", "warning")

    except Exception as e:
        conn.rollback()
        flash(f"❌ Erreur lors de la mise à jour des phases : {e}", "error")

    return redirect(url_for("projet.modifier_projet", projet_id=projet_id))



# ==========================================
# Chargement dynamique des phases
# ==========================================
@projet_bp.route("/phases_programme/<programme_id>")
def phases_programme(programme_id):
    try:
        conn = get_db()
        cur = conn.cursor()

        # 🔹 Récupération du projet
        projet_id = request.args.get("projet_id")
        projet_info = query_db("""
            SELECT date_mep, estimation_jh
            FROM Projet
            WHERE id = ?
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
# Affectations des collaborateurs
# ==========================================
# ==========================================
# Affectations des collaborateurs (dans la page Modifier Projet)
# ==========================================

@projet_bp.route("/<int:projet_id>/ajouter_collaborateur", methods=["POST"])
def ajouter_collaborateur_projet(projet_id):
    """Ajout d’un collaborateur à un projet (via le formulaire ou AJAX)"""
    matricule = request.form.get("collaborateur")
    role = request.form.get("role")
    pourcentage = request.form.get("pourcentage", 0)

    conn = get_db()
    cur = conn.cursor()

    exist = query_db("""
        SELECT id FROM collaborateur_projet
        WHERE projet_id = ? AND collaborateur_matricule = ?
    """, [projet_id, matricule], one=True)

    if exist:
        return jsonify({"success": False, "message": "⚠️ Ce collaborateur est déjà affecté à ce projet."})

    cur.execute("""
        INSERT INTO collaborateur_projet 
        (projet_id, collaborateur_matricule, role, pourcentage_allocation, idate, iuser)
        VALUES (?, ?, ?, ?, DATETIME('now'), 'admin')
    """, (projet_id, matricule, role, pourcentage))
    conn.commit()

    collab = query_db("""
        SELECT c.nom || ' ' || c.prenom AS collaborateur
        FROM tmp_collaborateurs c WHERE c.matricule = ?
    """, [matricule], one=True)

    return jsonify({
        "success": True,
        "collaborateur": collab["collaborateur"],
        "role": role,
        "pourcentage": pourcentage
    })


@projet_bp.route("/modifier_collaborateur/<int:affectation_id>", methods=["POST"])
def modifier_collaborateur_projet(affectation_id):
    """Modification d’un collaborateur affecté à un projet (AJAX)"""
    role = request.form.get("role")
    pourcentage = request.form.get("pourcentage")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE collaborateur_projet
        SET role = ?, pourcentage_allocation = ?, udate = DATETIME('now'), uuser = 'admin'
        WHERE id = ?
    """, (role, pourcentage, affectation_id))
    conn.commit()
    return jsonify({"success": True, "message": "✅ Collaborateur mis à jour avec succès"})


@projet_bp.route("/supprimer_collaborateur/<int:affectation_id>", methods=["POST"])
def supprimer_collaborateur_projet(affectation_id):
    """Suppression d’un collaborateur du projet (AJAX)"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM collaborateur_projet WHERE id = ?", [affectation_id])
    conn.commit()
    return jsonify({"success": True, "message": "🗑️ Collaborateur supprimé avec succès"})

# ==========================================
# Supprimer un projet
# ==========================================
@projet_bp.route("/supprimer/<projet_id>", methods=["POST"])
def supprimer_projet(projet_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM Projet WHERE id = ?", [projet_id])
    conn.commit()
    flash("🗑️ Projet supprimé avec succès.", "success")
    return redirect(url_for("projet.liste_projets"))


# ==========================================
# 🟦 Modifier une demande
# ==========================================
@projet_bp.route("/modifier_demande/<projet_id>", methods=["GET", "POST"])
def modifier_demande(projet_id):
    conn = get_db()
    cur = conn.cursor()

    # --- 🔹 Récupération des infos actuelles du projet
    demande = query_db("SELECT * FROM Projet WHERE id = ?", [projet_id], one=True)
    if not demande:
        flash("❌ Demande introuvable.", "error")
        return redirect(url_for("projet.liste_demandes"))

    # 🔸 Sauvegarder les anciennes valeurs pour comparaison
    ancien_domaine = demande["id_domaine"]
    ancien_score_complexite = demande["score_complexite"]

    # --- 🔹 Données de référence
    programmes = query_db("SELECT id, nom FROM programme ORDER BY nom")
    domaines = query_db("SELECT id, nom FROM domaines ORDER BY nom")
    categories = query_db("SELECT id, nom FROM categorie ORDER BY nom")
    statuts = query_db("SELECT id, nom FROM statut_demande ORDER BY nom")

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
            WHERE id = ?
        """, (titre, description, id_programme, id_domaine, retenue, date_mep, projet_id))
        conn.commit()

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
                cur.execute("UPDATE Projet SET estimation_jh = 0 WHERE id = ?", [projet_id])
                conn.commit()
                flash("⚠️ Domaine ou complexité manquants — estimation non recalculée.", "warning")
        else:
            flash("ℹ️ Aucune modification détectée sur le domaine ou la complexité — pas de recalcul.", "info")

        return redirect(url_for("projet.modifier_demande", projet_id=projet_id))

    # --- 🔹 Affichage du template
    return render_template(
        "modifier_demande.html",
        demande=demande,
        programmes=programmes,
        domaines=domaines,
        statuts=statuts,
        complexites=complexites,
        dropdowns_complexite=dropdowns_complexite,
    )

@projet_bp.route("/update_all_complexites_demande/<projet_id>", methods=["POST"])
def update_all_complexites_demande(projet_id):
    conn = get_db()
    cur = conn.cursor()

    # --- Mise à jour des complexités ---
    libelles_complexite = query_db("SELECT DISTINCT libelle FROM complexite WHERE libelle <> ''")
    for l in libelles_complexite:
        lib = l["libelle"]
        valeur_id = request.form.get(f"complexite_{lib}")
        if not valeur_id:
            continue

        existing = query_db("""
            SELECT cp.id_complexite FROM complexite_projet cp
            JOIN complexite c ON c.id = cp.id_complexite
            WHERE cp.id_projet = ? AND c.libelle = ?
        """, [projet_id, lib], one=True)

        if existing:
            cur.execute("""
                UPDATE complexite_projet
                SET id_complexite = ?, udate = DATETIME('now'), uuser = 1
                WHERE id_projet = ? AND id_complexite = ?
            """, (valeur_id, projet_id, existing["id_complexite"]))
        else:
            cur.execute("""
                INSERT INTO complexite_projet (id_projet, id_complexite, idate, iuser)
                VALUES (?, ?, DATETIME('now'), 1)
            """, (projet_id, valeur_id))
    conn.commit()

    # --- Recalcul du score total ---
    score_complexite = query_db("""
        SELECT SUM(c.valeur_libelle * c.ponderation) AS total
        FROM complexite_projet cp
        JOIN complexite c ON c.id = cp.id_complexite
        WHERE cp.id_projet = ?
    """, [projet_id], one=True)["total"] or 0

    demande = query_db("SELECT id_domaine, id_programme, date_mep FROM Projet WHERE id = ?", [projet_id], one=True)
    id_domaine = demande["id_domaine"]
    id_programme = demande["id_programme"]
    date_mep = demande["date_mep"]

    # --- Calcul estimation JH ---
    estimation_jh = 0
    if id_domaine:
        resultat = calculer_charge_estimee(score_complexite, id_domaine)
        estimation_jh = resultat.get("charge_estimee", 0)
    else:
        flash("⚠️ Domaine non renseigné — estimation non calculée.", "warning")

    cur.execute("""
        UPDATE Projet
        SET score_complexite = ?, estimation_jh = ?, udate = DATETIME('now'), uuser = 1
        WHERE id = ?
    """, (score_complexite, estimation_jh, projet_id))
    conn.commit()

    flash(f"✅ Complexités mises à jour (Score={score_complexite}, Estimation={estimation_jh} JH)", "success")
    return redirect(url_for("projet.modifier_demande", projet_id=projet_id))


@projet_bp.route("/supprimer_demande/<projet_id>", methods=["POST"])
def supprimer_demande(projet_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM Projet WHERE id = ?", [projet_id])
    conn.commit()
    flash("🗑️ Projet supprimé avec succès.", "success")
    return redirect(url_for("projet.liste_demande"))

@projet_bp.route("/get_valeurs_complexite", methods=["POST"])
def get_valeurs_complexite():
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
