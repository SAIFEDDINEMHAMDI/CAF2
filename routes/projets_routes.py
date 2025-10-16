# routes/projets_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from utils.db_utils import query_db, execute_db

projets_bp = Blueprint('projets', __name__, url_prefix='/projets')

@projets_bp.route('/<int:programme_id>/projets/<uuid:projet_id>/phases', methods=['GET', 'POST'])
def gerer_phases_projet(programme_id, projet_id):
    # Convertir UUID en str
    projet_id_str = str(projet_id)

    # Vérifier le projet
    projet = query_db("SELECT * FROM projets WHERE id = ?", [projet_id_str], one=True)
    if not projet:
        flash("❌ Projet introuvable", "danger")
        return redirect(url_for('programmes.gerer_projets', id=programme_id))

    # Récupérer les phases du programme
    phases = query_db("""
        SELECT p.id, p.nom 
        FROM phases p
        WHERE p.programme_id = ?
        ORDER BY p.id
    """, [programme_id])

    # Récupérer les phases déjà liées au projet
    projet_phases = query_db("""
        SELECT pp.*, ph.nom AS phase_nom
        FROM projet_phases pp
        JOIN phases ph ON pp.phase_id = ph.id
        WHERE pp.projet_id = ?
        ORDER BY ph.id
    """, [projet_id_str])  # ← str(projet_id)

    if request.method == 'POST':
        # Supprimer les anciennes phases
        execute_db("DELETE FROM projet_phases WHERE projet_id = ?", [projet_id_str])

        # Récupérer les nouvelles données
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