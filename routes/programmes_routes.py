#programmes_routes.py
import sqlite3
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash
from utils.db_utils import query_db, execute_db

programmes_bp = Blueprint('programmes', __name__, url_prefix='/programmes')


# ✅ 1. Liste tous les programmes
@programmes_bp.route('/')
def liste_programmes():
    """Affiche la liste de tous les programmes"""
    programmes = query_db("SELECT * FROM programmes ORDER BY nom")
    return render_template('programmes/liste.html', programmes=programmes)


# ✅ 2. Ajouter un programme
@programmes_bp.route('/ajouter', methods=['GET', 'POST'])
def ajouter_programme():
    if request.method == 'POST':
        nom = request.form['nom'].strip()
        if not nom:
            flash("❌ Le nom du programme est requis.", "danger")
        else:
            try:
                execute_db("INSERT INTO programmes (nom) VALUES (?)", [nom])
                flash("✅ Programme ajouté avec succès", "success")
                return redirect(url_for('programmes.liste_programmes'))
            except sqlite3.IntegrityError:
                flash("❌ Un programme avec ce nom existe déjà.", "danger")
            except Exception as e:
                flash(f"❌ Erreur inattendue : {e}", "danger")
    return render_template('programmes/ajouter.html')


@programmes_bp.route('/<int:id>/gerer', methods=['GET', 'POST'])
def gerer_programme(id):
    # Récupérer le programme
    programme = query_db("SELECT * FROM programmes WHERE id = ?", [id], one=True)
    if not programme:
        flash("❌ Programme introuvable", "danger")
        return redirect(url_for('priorites'))

    phases = list(range(1, 9))  # 8 phases
    profils = query_db("SELECT * FROM profils")

    if request.method == 'POST':
        action = request.form.get('action')

        # --- Étape 1 : Sauvegarder les poids des phases ---
        if action == 'poids_phases':
            total = 0
            updates = []
            for i in phases:
                value = request.form.get(f'poids_phase_{i}', '0').strip()
                try:
                    poids = float(value)
                except ValueError:
                    poids = 0
                total += poids
                updates.append((id, i, poids))

            if abs(total - 100.0) > 0.1:
                flash(f"⚠️ Total = {total:.1f} % – Veuillez ajuster à 100 %", "warning")
            else:
                execute_db("DELETE FROM programme_poids_phases WHERE programme_id = ?", [id])
                execute_db("""
                    INSERT INTO programme_poids_phases (programme_id, phase_num, poids)
                    VALUES (?, ?, ?)
                """, updates, many=True)
                flash("✅ Poids des phases sauvegardés", "success")

        # --- Étape 2 : Sauvegarder les hypothèses par profil ---
        elif action == 'hypotheses_profils':
            updates = []
            for profil in profils:
                value = request.form.get(f'hypothese_{profil["id"]}', '100').strip()
                try:
                    hypothese = float(value)
                except ValueError:
                    hypothese = 100
                updates.append((id, profil['id'], hypothese))  # ✅ Ajout de programme_id

            # ✅ Supprimer les anciennes hypothèses pour ce programme
            execute_db("DELETE FROM programme_profil_hypotheses WHERE programme_id = ?", [id])
            # ✅ Insérer les nouvelles
            execute_db("""
                INSERT INTO programme_profil_hypotheses (programme_id, profil_id, hypothese)
                VALUES (?, ?, ?)
            """, updates, many=True)
            flash("✅ Hypothèses des profils sauvegardées pour ce programme", "success")

    # --- Récupérer les données pour affichage ---
    # Poids des phases
    poids_db = query_db("""
        SELECT phase_num, poids FROM programme_poids_phases
        WHERE programme_id = ?
    """, [id])
    poids = {row['phase_num']: row['poids'] for row in poids_db}

    # ✅ Hypothèses des profils (par programme)
    hypotheses_db = query_db("""
        SELECT p.id, p.nom, COALESCE(h.hypothese, 100) AS hypothese
        FROM profils p
        LEFT JOIN programme_profil_hypotheses h ON p.id = h.profil_id AND h.programme_id = ?
    """, [id])
    hypotheses = {row['id']: dict(row) for row in hypotheses_db}

    # Calcul du tableau final
    tableau_final = []
    for i in phases:
        ligne = {'phase': f"Phase {i}", 'poids': poids.get(i, 0), 'profils': {}}
        for profil in profils:
            p = poids.get(i, 0)
            h = hypotheses.get(profil['id'], {}).get('hypothese', 100)
            charge = (p * h) / 100  # Formule Excel : =$B$42*$B4*$C$3
            ligne['profils'][profil['id']] = round(charge, 2)
        tableau_final.append(ligne)

    return render_template(
        'programmes/gerer.html',
        programme=dict(programme),
        phases=phases,
        profils=profils,
        poids=poids,
        hypotheses=hypotheses,
        tableau_final=tableau_final
    )


# ✅ 4. Gérer les projets d'un programme
@programmes_bp.route('/<int:id>/projets')
def gerer_projets(id):  # ✅ Renommé ici
    # Récupérer le programme
    programme = query_db("SELECT * FROM programmes WHERE id = ?", [id], one=True)
    if not programme:
        flash("❌ Programme introuvable", "danger")
        return redirect(url_for('priorites'))

    # Récupérer les projets liés au programme
    projets = query_db("""
        SELECT p.id, p.titre, p.description, p.date_mep, p.statut, p.score_wsjf, c.nom AS categorie_nom
        FROM projets p
        LEFT JOIN categorie c ON p.categorie_id = c.id
        WHERE p.programme_id = ?
        ORDER BY p.score_wsjf DESC
    """, [id])

    return render_template(
        'programmes/gerer_projets.html',
        programme=programme,
        projets=projets
    )


# ✅ 5. Ajouter un projet à un programme
@programmes_bp.route('/<int:programme_id>/ajouter-projet', methods=['GET', 'POST'])
def ajouter_projet(programme_id):
    # Vérifier que le programme existe
    programme = query_db("SELECT * FROM programmes WHERE id = ?", [programme_id], one=True)
    if not programme:
        flash("❌ Programme introuvable", "danger")
        return redirect(url_for('priorites'))

    # Récupérer tous les projets existants (triés par WSJF)
    projets = query_db("""
        SELECT p.id, p.titre, p.description, p.score_wsjf
        FROM projets p
        WHERE p.programme_id IS NULL OR p.programme_id = ''
        ORDER BY p.score_wsjf DESC
    """, one=False)

    if request.method == 'POST':
        projet_id = request.form['projet_id'].strip()

        if not projet_id:
            flash("❌ Veuillez sélectionner un projet", "danger")
        else:
            try:
                # Mettre à jour le projet pour lui affecter le programme
                execute_db("""
                    UPDATE projets SET programme_id = ?
                    WHERE id = ?
                """, [programme_id, projet_id])

                flash("✅ Projet affecté au programme", "success")
                return redirect(url_for('programmes.gerer_projets', id=programme_id))
            except Exception as e:
                flash(f"❌ Erreur : {e}", "danger")

    return render_template(
        'programmes/ajouter_projet.html',
        programme=programme,
        projets=projets
    )


# ✅ 6. Modifier un projet
@programmes_bp.route('/modifier-projet/<uuid:id>', methods=['GET', 'POST'])
def modifier_projet(id):
    projet = query_db("SELECT * FROM projets WHERE id = ?", [str(id)], one=True)
    if not projet:
        flash("❌ Projet introuvable", "danger")
        return redirect(url_for('priorites'))

    programme_id = projet['programme_id']
    programme = query_db("SELECT * FROM programmes WHERE id = ?", [programme_id], one=True)
    categories = query_db("SELECT * FROM categorie")

    if request.method == 'POST':
        titre = request.form['titre'].strip()
        description = request.form['description'].strip()
        date_mep = request.form['date_mep']
        statut = request.form['statut']
        categorie_id = request.form['categorie_id']

        if not titre:
            flash("❌ Le titre est requis.", "danger")
        else:
            try:
                execute_db("""
                    UPDATE projets SET titre = ?, description = ?, date_mep = ?, 
                                      statut = ?, categorie_id = ?
                    WHERE id = ?
                """, [titre, description, date_mep, statut, categorie_id, str(id)])
                flash("✅ Projet mis à jour", "success")
                return redirect(url_for('programmes.gerer_projets', id=programme_id))
            except Exception as e:
                flash(f"❌ Erreur : {e}", "danger")

    return render_template(
        'programmes/modifier_projet.html',
        projet=dict(projet),
        programme=dict(programme),
        categories=categories
    )


# ✅ 7. Supprimer un projet
@programmes_bp.route('/supprimer-projet/<uuid:id>', methods=['POST'])
def supprimer_projet(id):
    projet = query_db("SELECT programme_id FROM projets WHERE id = ?", [str(id)], one=True)
    if not projet:
        flash("❌ Projet introuvable", "danger")
    else:
        try:
            execute_db("DELETE FROM projets WHERE id = ?", [str(id)])
            flash("🗑️ Projet supprimé", "success")
        except Exception as e:
            flash(f"❌ Erreur : {e}", "danger")
    return redirect(url_for('programmes.gerer_projets', id=projet['programme_id']))


# ✅ 8. Gérer les phases d'un projet
@programmes_bp.route('/<int:programme_id>/projets/<uuid:projet_id>/phases', methods=['GET', 'POST'])
def gerer_phases_projet(programme_id, projet_id):
    projet_id_str = str(projet_id)

    projet = query_db("SELECT * FROM projets WHERE id = ?", [projet_id_str], one=True)
    if not projet:
        flash("❌ Projet introuvable", "danger")
        return redirect(url_for('programmes.gerer_projets', id=programme_id))

    phases = query_db("""
        SELECT p.id, p.nom 
        FROM phases p
        WHERE p.programme_id = ?
        ORDER BY p.id
    """, [programme_id])

    projet_phases = query_db("""
        SELECT pp.*, ph.nom AS phase_nom
        FROM projet_phases pp
        JOIN phases ph ON pp.phase_id = ph.id
        WHERE pp.projet_id = ?
        ORDER BY ph.id
    """, [projet_id_str])

    if request.method == 'POST':
        execute_db("DELETE FROM projet_phases WHERE projet_id = ?", [projet_id_str])

        phase_ids = request.form.getlist('phase_id')
        dates_debut = request.form.getlist('date_debut')
        dates_fin = request.form.getlist('date_fin')

        for i in range(len(phase_ids)):
            phase_id = phase_ids[i]
            debut = dates_debut[i]
            fin = dates_fin[i]
            if phase_id and debut and fin:
                try:
                    execute_db("""
                        INSERT INTO projet_phases (projet_id, phase_id, date_debut, date_fin)
                        VALUES (?, ?, ?, ?)
                    """, [projet_id_str, phase_id, debut, fin])
                except Exception as e:
                    flash(f"❌ Erreur pour la phase {phase_id}: {e}", "danger")

        flash("✅ Phases mises à jour", "success")
        return redirect(url_for('programmes.gerer_phases_projet', programme_id=programme_id, projet_id=projet_id))

    return render_template(
        'programmes/gerer_phases_projet.html',
        projet=projet,
        programme_id=programme_id,
        phases=phases,
        projet_phases=projet_phases
    )