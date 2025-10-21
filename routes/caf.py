# routes/caf.py

from datetime import date, timedelta
import calendar
from flask import Blueprint, send_file, request, render_template, flash, redirect, url_for, jsonify
from io import BytesIO
import pandas as pd
from datetime import datetime
from utils.db_utils import query_db
import calendar

caf_bp = Blueprint('caf', __name__, url_prefix='/caf')


# ============================================================
# 🧮 UTILITAIRE : Récupère l'année courante ou celle du paramètre
# ============================================================
def get_annee():
    """Retourne l'année à utiliser (paramètre GET ou année courante)."""
    try:
        return int(request.args.get("annee", datetime.now().year))
    except ValueError:
        return datetime.now().year


# ============================================================
# 🔹 CAF AUTOMATIQUE (total dynamique selon mois sélectionné)
# ============================================================
@caf_bp.route("/automatique")
def caf_automatique():
    annee = get_annee()

    # 📅 Liste des mois (français)
    mois_labels = [
        "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
        "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
    ]
    mois_filtre = request.args.get("mois", "all")

    # 🔹 Premier lundi de l’année
    start = date(annee, 1, 1)
    while start.weekday() != 0:
        start += timedelta(days=1)

    # 🔹 Nombre de semaines
    num_weeks = 53 if date(annee, 12, 31).isocalendar()[1] == 53 else 52
    week_labels = [f"S{i}" for i in range(1, num_weeks + 1)]

    # 🔹 Mapping semaine ↔ mois
    semaine_to_mois = {}
    mois_to_semaines = {m: [] for m in mois_labels}
    for i, semaine in enumerate(week_labels, start=1):
        debut_semaine = start + timedelta(weeks=i - 1)
        mois_nom = mois_labels[debut_semaine.month - 1]
        semaine_to_mois[semaine] = mois_nom
        mois_to_semaines[mois_nom].append(semaine)

    # 🔹 Semaines à afficher
    if mois_filtre != "all" and mois_filtre in mois_to_semaines:
        semaines_affichees = mois_to_semaines[mois_filtre]
    else:
        semaines_affichees = week_labels

    # ======================================================
    # 🔹 Récupération des collaborateurs
    # ======================================================
    collaborateurs = query_db("""
        SELECT 
            c.matricule,
            p.nom AS profil,
            c.caf_disponible_build
        FROM collaborateurs c
        JOIN profils p ON c.profil_id = p.id
    """)

    # ======================================================
    # 🔹 Agrégation BUILD par profil
    # ======================================================
    profils_data = {}
    for c in collaborateurs:
        profil = c["profil"]
        if profil not in profils_data:
            profils_data[profil] = {"build": 0.0, "nb_collab": set()}
        caf_build = float(c["caf_disponible_build"] or 0)
        profils_data[profil]["build"] += caf_build
        profils_data[profil]["nb_collab"].add(c["matricule"])

    # ======================================================
    # 🔹 Construction du tableau
    # ======================================================
    data = []
    total_general = 0.0

    for profil, val in profils_data.items():
        total_build = val["build"]
        nb_collab = len(val["nb_collab"])
        build_par_semaine = total_build / num_weeks if num_weeks > 0 else 0

        row = {
            "profil": profil,
            "nb_collab": nb_collab,
            "total_annuel": 0  # sera calculé selon filtre
        }

        # Ajout des semaines
        for s in week_labels:
            row[s] = round(build_par_semaine, 2)

        # 🔹 Si filtre mensuel, on somme seulement les semaines du mois sélectionné
        if mois_filtre != "all" and mois_filtre in mois_to_semaines:
            total_mois = sum(row[s] for s in mois_to_semaines[mois_filtre])
            row["total_annuel"] = round(total_mois, 2)
        else:
            row["total_annuel"] = round(total_build, 2)

        data.append(row)
        total_general += row["total_annuel"]

    # ======================================================
    # 🔹 TOTAL GÉNÉRAL
    # ======================================================
    total_row = {
        "profil": "TOTAL GÉNÉRAL",
        "nb_collab": "-",
        "total_annuel": round(total_general, 2)
    }
    for s in week_labels:
        total_row[s] = round(sum(d[s] for d in data if s in d), 2)
    data.append(total_row)

    # ======================================================
    # 🔹 Rendu final
    # ======================================================
    return render_template(
        "caf_automatique.html",
        week_labels=week_labels,
        semaines_affichees=semaines_affichees,
        semaine_to_mois=semaine_to_mois,
        mois_labels=mois_labels,
        data=data,
        mois_filtre=mois_filtre,
        annee=annee
    )

# ============================================================
# 🔹 CAF REQUISE
# ============================================================
@caf_bp.route('/caf-requise')
def caf_requise():
    annee = get_annee()

    num_weeks = 53 if date(annee, 12, 31).isocalendar()[1] == 53 else 52
    week_labels = [f"S{i}" for i in range(1, num_weeks + 1)]

    # 🔹 Premier lundi de l’année
    start = date(annee, 1, 1)
    while start.weekday() != 0:
        start += timedelta(days=1)

    # 🔹 Récupération des projets et profils
    projets = query_db("""
        SELECT 
            p.id, p.titre, p.duree_estimee_jh,
            pp.date_debut, pp.date_fin,
            pph.profil_id, pph.pourcentage
        FROM projets p
        JOIN projet_phases pp ON p.id = pp.projet_id
        JOIN phase_profils_programme pph ON pp.phase_id = pph.phase_id
        WHERE p.statut IN ('En attente', 'À planifier', 'En cours')
    """)

    profils = query_db("SELECT id, nom FROM profils")
    profil_dict = {p['id']: p['nom'] for p in profils}

    # Initialisation charge
    charge_semaine = {f"S{i}": {p['id']: 0 for p in profils} for i in range(1, num_weeks + 1)}
    for i in range(1, num_weeks + 1):
        charge_semaine[f"S{i}"]['Autre'] = 0

    for projet in projets:
        try:
            debut = datetime.strptime(projet['date_debut'], "%Y-%m-%d").date()
            fin = datetime.strptime(projet['date_fin'], "%Y-%m-%d").date()
            charge = projet['duree_estimee_jh'] or 0
            pourcentage = projet['pourcentage'] or 100
            profil_id = projet['profil_id']
            charge_projet = charge * (pourcentage / 100)
        except Exception as e:
            print(f"⚠️ Erreur parsing projet {projet.get('id')} : {e}")
            continue

        for i in range(1, num_weeks + 1):
            debut_semaine = start + timedelta(weeks=i - 1)
            fin_semaine = debut_semaine + timedelta(days=6)
            key = f"S{i}"

            if debut <= fin_semaine and fin >= debut_semaine:
                overlap = min(fin, fin_semaine) - max(debut, debut_semaine)
                jours = overlap.days + 1
                total_jours = (fin - debut).days + 1
                if total_jours > 0:
                    charge_semaine_projet = (charge_projet * jours) / total_jours

                    if profil_id in charge_semaine[key]:
                        charge_semaine[key][profil_id] += charge_semaine_projet
                    else:
                        charge_semaine[key]['Autre'] += charge_semaine_projet
                        print(f"⚠️ Profil {profil_id} inexistant → charge transférée dans 'Autre'")

    data = []
    for profil in profils:
        row = {'profil': profil['nom']}
        for s in week_labels:
            row[s] = charge_semaine[s][profil['id']]
        data.append(row)

    if any(charge_semaine[s]['Autre'] > 0 for s in week_labels):
        row_autre = {'profil': '🌀 Autre (profils supprimés)'}
        for s in week_labels:
            row_autre[s] = charge_semaine[s]['Autre']
        data.append(row_autre)

    return render_template('caf_requise.html', week_labels=week_labels, data=data, annee=annee)


@caf_bp.route('/caf-disponibles')
def caf_disponibles():
    annee = date.today().year

    # 🔍 Recherche
    search = request.args.get("search", "").strip()

    # 📄 Pagination
    page = request.args.get("page", 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    # 🔹 Base query
    base_query = """
        SELECT 
            c.matricule,
            c.nom || ' ' || c.prenom AS nom_prenom,
            p.nom AS profil,
            a.nom AS affectation,
            c.build_ratio,
            c.run_ratio,
            c.caf_disponible_build,
            c.caf_disponible_run,
            pp.nom AS profil_repartition,
            cr.pourcentage_build,
            cr.pourcentage_run,
            cr.caf_disponible_build AS caf_repartition_build,
            cr.caf_disponible_run AS caf_repartition_run
        FROM collaborateurs c
        JOIN profils p ON c.profil_id = p.id
        JOIN affectation a ON c.affectation_id = a.id
        LEFT JOIN collaborateur_repartition cr ON cr.collaborateur_id = c.matricule
        LEFT JOIN profils pp ON pp.id = cr.profil_id
    """

    params = []
    if search:
        base_query += """
        WHERE 
            c.nom LIKE ? OR 
            c.prenom LIKE ? OR 
            p.nom LIKE ? OR 
            a.nom LIKE ?
        """
        like = f"%{search}%"
        params.extend([like, like, like, like])

    # 🔹 Total pour pagination
    total_query = "SELECT COUNT(DISTINCT c.matricule) AS cnt FROM collaborateurs c JOIN profils p ON c.profil_id=p.id JOIN affectation a ON c.affectation_id=a.id"
    if search:
        total_query += " WHERE c.nom LIKE ? OR c.prenom LIKE ? OR p.nom LIKE ? OR a.nom LIKE ?"
        total_row = query_db(total_query, [like, like, like, like], one=True)
    else:
        total_row = query_db(total_query, one=True)

    total = total_row["cnt"]
    total_pages = (total + per_page - 1) // per_page

    # 🔹 Ajout du tri et pagination
    base_query += """
        ORDER BY c.nom, c.prenom
        LIMIT ? OFFSET ?
    """
    params.extend([per_page, offset])

    collaborateurs = query_db(base_query, params)

    # 🔹 Regrouper par collaborateur
    data = {}
    for row in collaborateurs:
        m = row["matricule"]
        if m not in data:
            data[m] = {
                "matricule": m,
                "nom_prenom": row["nom_prenom"],
                "profil": row["profil"],
                "affectation": row["affectation"],
                "build_ratio": row["build_ratio"],
                "run_ratio": row["run_ratio"],
                "caf_disponible_build": row["caf_disponible_build"],
"caf_disponible_run": row["caf_disponible_run"],
                "repartitions": []
            }

        if row["profil_repartition"]:
            data[m]["repartitions"].append({
                "profil": row["profil_repartition"],
                "pct_build": row["pourcentage_build"] or 0,
                "pct_run": row["pourcentage_run"] or 0,
                "jh_build": row["caf_repartition_build"] or 0,
                "jh_run": row["caf_repartition_run"] or 0
            })

    return render_template(
        "caf_disponibles.html",
        collaborateurs=list(data.values()),
        page=page,
        total_pages=total_pages,
        search=search,
        annee=annee
    )



@caf_bp.route('/export-excel')
def export_excel():
    try:
        # 🔹 Requête : total CAF par profil
        data = query_db("""
            SELECT 
                p.nom AS profil,
                COUNT(c.matricule) AS nb_collab,
                ROUND(SUM(c.caf_disponible_build), 2) AS caf_build,
                ROUND(SUM(c.caf_disponible_run), 2) AS caf_run
            FROM collaborateurs c
            JOIN profils p ON p.id = c.profil_id
            GROUP BY p.nom
            ORDER BY p.nom
        """)

        if not data:
            flash("⚠️ Aucune donnée CAF disponible pour export", "warning")
            return redirect(url_for('caf.caf_disponible'))

        # 🔹 Conversion en DataFrame pandas
        df = pd.DataFrame(data)
        df.columns = ["Profil", "Nb collaborateurs", "CAF Build", "CAF Run"]

        # 🔹 Création du fichier Excel en mémoire
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='CAF Disponible')

            workbook = writer.book
            worksheet = writer.sheets['CAF Disponible']

            # ---------- Styles ----------
            header_fmt = workbook.add_format({
                'bold': True,
                'bg_color': '#004080',  # Bleu BIAT
                'font_color': 'white',
                'align': 'center',
                'valign': 'vcenter',
                'border': 1
            })
            cell_fmt = workbook.add_format({
                'border': 1,
                'align': 'left',
                'valign': 'vcenter'
            })
            num_fmt = workbook.add_format({
                'border': 1,
                'align': 'center',
                'valign': 'vcenter',
                'num_format': '0.00'
            })
            int_fmt = workbook.add_format({
                'border': 1,
                'align': 'center',
                'valign': 'vcenter',
                'num_format': '0'
            })

            # ---------- Largeur + formats ----------
            worksheet.set_column("A:A", 35, cell_fmt)   # Profil
            worksheet.set_column("B:B", 15, int_fmt)    # Nb collab
            worksheet.set_column("C:D", 15, num_fmt)    # CAF Build / Run

            # ---------- En-têtes ----------
            for col_num, value in enumerate(df.columns):
                worksheet.write(0, col_num, str(value), header_fmt)

            # ---------- AutoFilter + Freeze ----------
            worksheet.autofilter(0, 0, len(df), len(df.columns) - 1)
            worksheet.freeze_panes(1, 0)

        output.seek(0)
        file_name = f"CAF_Disponible_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        return send_file(
            output,
            as_attachment=True,
            download_name=file_name,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        print("❌ Erreur export CAF :", e)
        flash(f"Erreur export CAF : {e}", "error")
        return redirect(url_for('caf.caf_disponible'))
@caf_bp.route('/dashboard')
def caf_dashboard():
    annee = get_annee()

    # ===============================
    # 📅 Préparation des semaines et mois
    # ===============================
    start = date(annee, 1, 1)
    while start.weekday() != 0:
        start += timedelta(days=1)

    num_weeks = 53 if date(annee, 12, 31).isocalendar()[1] == 53 else 52
    week_labels = [f"S{i}" for i in range(1, num_weeks + 1)]
    mois_labels = [calendar.month_name[i] for i in range(1, 13)]

    semaine_to_mois = {}
    mois_to_semaines = {m: [] for m in mois_labels}

    for i in range(1, num_weeks + 1):
        debut_semaine = start + timedelta(weeks=i - 1)
        mois = debut_semaine.strftime("%B")
        semaine = f"S{i}"
        semaine_to_mois[semaine] = mois
        mois_to_semaines[mois].append(semaine)

    # ===============================
    # 📘 Récupération des profils
    # ===============================
    profils = query_db("SELECT id, nom FROM profils ORDER BY nom")
    profil_dict = {p["id"]: p["nom"] for p in profils}

    # ===============================
    # ✅ CAF DISPONIBLE (profil principal + répartition)
    # ===============================
    collaborateurs = query_db("""
        SELECT 
            c.matricule,
            p.id AS profil_id,
            p.nom AS profil,
            c.caf_disponible_build,
            c.caf_disponible_run,
            pp.nom AS profil_repartition,
            cr.pourcentage_build,
            cr.pourcentage_run,
            cr.caf_disponible_build AS caf_repartition_build,
            cr.caf_disponible_run AS caf_repartition_run
        FROM collaborateurs c
        JOIN profils p ON c.profil_id = p.id
        LEFT JOIN collaborateur_repartition cr ON cr.collaborateur_id = c.matricule
        LEFT JOIN profils pp ON pp.id = cr.profil_id
    """)

    # 🔸 Initialisation dictionnaire profil → liste des semaines
    caf_dispo = {p["nom"]: [0] * num_weeks for p in profils}

    for collab in collaborateurs:
        # 🔹 Cas 1 : profil principal
        profil_nom = collab["profil"]
        total_jh = (collab["caf_disponible_build"] or 0) + (collab["caf_disponible_run"] or 0)
        jh_par_semaine = total_jh / num_weeks if num_weeks else 0
        for i in range(num_weeks):
            caf_dispo[profil_nom][i] += jh_par_semaine

        # 🔹 Cas 2 : répartition secondaire (si existe)
        if collab["profil_repartition"]:
            profil_rep = collab["profil_repartition"]
            pct_build = (collab["pourcentage_build"] or 0) / 100
            pct_run = (collab["pourcentage_run"] or 0) / 100
            jh_rep = ((collab["caf_repartition_build"] or 0) + (collab["caf_repartition_run"] or 0))

            # Si les valeurs CAF ne sont pas renseignées, on les déduit du CAF principal × pourcentage
            if jh_rep == 0:
                jh_rep = total_jh * (pct_build + pct_run)

            jh_par_semaine_rep = jh_rep / num_weeks if num_weeks else 0
            for i in range(num_weeks):
                caf_dispo[profil_rep][i] += jh_par_semaine_rep

    # ===============================
    # ⚙️ CAF REQUISE (par profil)
    # ===============================
    projets = query_db("""
        SELECT 
            p.id, p.duree_estimee_jh, pp.date_debut, pp.date_fin,
            pph.profil_id, pph.pourcentage
        FROM projets p
        JOIN projet_phases pp ON p.id = pp.projet_id
        JOIN phase_profils_programme pph ON pp.phase_id = pph.phase_id
        WHERE p.statut IN ('En attente', 'À planifier', 'En cours')
    """)

    caf_requise = {p["nom"]: [0] * num_weeks for p in profils}

    for projet in projets:
        try:
            debut = datetime.strptime(projet["date_debut"], "%Y-%m-%d").date()
            fin = datetime.strptime(projet["date_fin"], "%Y-%m-%d").date()
            charge = projet["duree_estimee_jh"] or 0
            pourcentage = projet["pourcentage"] or 100
            profil_nom = profil_dict.get(projet["profil_id"], "Autre")
            charge_projet = charge * (pourcentage / 100)
        except Exception as e:
            print(f"⚠️ Erreur parsing projet {projet.get('id')} : {e}")
            continue

        for i in range(num_weeks):
            debut_s = start + timedelta(weeks=i)
            fin_s = debut_s + timedelta(days=6)
            if debut <= fin_s and fin >= debut_s:
                overlap = min(fin, fin_s) - max(debut, debut_s)
                jours = overlap.days + 1
                total = (fin - debut).days + 1
                part = (charge_projet * jours / total) if total > 0 else 0
                caf_requise.setdefault(profil_nom, [0] * num_weeks)[i] += round(part, 2)

    # ===============================
    # 📊 Totaux globaux
    # ===============================
    caf_dispo["TOTAL"] = [sum(caf_dispo[p][i] for p in caf_dispo if p != "TOTAL") for i in range(num_weeks)]
    caf_requise["TOTAL"] = [sum(caf_requise[p][i] for p in caf_requise if p != "TOTAL") for i in range(num_weeks)]

    # ===============================
    # 🗓️ CAF PAR MOIS ET SEMAINE
    # ===============================
    caf_dispo_par_semaine = {}
    caf_requise_par_semaine = {}

    for profil in caf_dispo.keys():
        caf_dispo_par_semaine[profil] = {}
        caf_requise_par_semaine[profil] = {}
        for i, s in enumerate(week_labels):
            mois = semaine_to_mois[s]
            caf_dispo_par_semaine[profil].setdefault(mois, {})[s] = caf_dispo[profil][i]
            caf_requise_par_semaine[profil].setdefault(mois, {})[s] = caf_requise[profil][i]

    # ===============================
    # 📆 CAF MENSUELLE (somme par mois)
    # ===============================
    caf_dispo_mensuel = {}
    caf_requise_mensuel = {}

    for profil in profils:
        p_nom = profil["nom"]
        caf_dispo_mensuel[p_nom] = {m: 0 for m in mois_labels}
        caf_requise_mensuel[p_nom] = {m: 0 for m in mois_labels}

        for i, s in enumerate(week_labels):
            mois = semaine_to_mois[s]
            caf_dispo_mensuel[p_nom][mois] += caf_dispo[p_nom][i]
            caf_requise_mensuel[p_nom][mois] += caf_requise[p_nom][i]

    caf_dispo_mensuel["TOTAL"] = {m: sum(caf_dispo_mensuel[p["nom"]][m] for p in profils) for m in mois_labels}
    caf_requise_mensuel["TOTAL"] = {m: sum(caf_requise_mensuel[p["nom"]][m] for p in profils) for m in mois_labels}

    # ===============================
    # ✅ Envoi vers le template
    # ===============================
    return render_template(
        "caf_dashboard.html",
        annee=annee,
        week_labels=week_labels,
        mois_labels=mois_labels,
        mois_to_semaines=mois_to_semaines,
        profils=[p["nom"] for p in profils] + ["TOTAL"],
        caf_dispo=caf_dispo,
        caf_requise=caf_requise,
        caf_dispo_par_semaine=caf_dispo_par_semaine,
        caf_requise_par_semaine=caf_requise_par_semaine,
        caf_dispo_mensuel=caf_dispo_mensuel,
        caf_requise_mensuel=caf_requise_mensuel
    )
from flask import jsonify
from utils.db_utils import query_db

from flask import jsonify
from utils.db_utils import query_db

@caf_bp.route("/profils_secondaires/<matricule>")
def profils_secondaires(matricule):
    rows = query_db("""
        SELECT 
            p.nom AS profil,
            cr.pourcentage_build AS pct_build,
            cr.pourcentage_run AS pct_run,
            cr.caf_disponible_build AS jh_build,
            cr.caf_disponible_run AS jh_run
        FROM collaborateur_repartition cr
        JOIN profils p ON p.id = cr.profil_id
        JOIN collaborateurs c ON c.matricule = cr.collaborateur_id
        WHERE c.matricule = ?
    """, [matricule])

    profils = []
    for r in rows:
        profils.append({
            "profil": r["profil"],
            "pct_build": int(r["pct_build"]) if r["pct_build"].is_integer() else round(r["pct_build"], 2),
            "pct_run": int(r["pct_run"]) if r["pct_run"].is_integer() else round(r["pct_run"], 2),
            "jh_build": int(r["jh_build"]) if r["jh_build"].is_integer() else round(r["jh_build"], 2),
            "jh_run": int(r["jh_run"]) if r["jh_run"].is_integer() else round(r["jh_run"], 2)
        })

    return jsonify({
        "success": True,
        "profils": profils
    })
