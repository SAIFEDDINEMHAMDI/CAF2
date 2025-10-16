#calculs.py
from datetime import datetime, timedelta

def get_semaine_key(date_str):
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d')
        mois = date.strftime('%B')
        semaine = (date.day - 1) // 7 + 1
        return f"{mois}_S{semaine}"
    except Exception as e:
        print(f"❌ Erreur sur date {date_str} : {e}")
        return None
def get_semaine_key(date_str):
    from datetime import datetime
    import calendar

    date = datetime.strptime(date_str, "%Y-%m-%d")
    month = calendar.month_name[date.month]
    week = (date.day - 1) // 7 + 1
    return f"{month}_S{week}"

def repartition_charge_par_phase(projet, phase_data):
    """ Appliquer les pourcentages de phase/profil """
    total_jh = projet['duree_estimee_jh'] or 0
    programme = projet['programme_nom']
    profil = projet['profil_nom']

    # Récupérer les phases du projet
    charges = {}
    for phase_info in phase_data:
        if phase_info['programme_nom'] == programme and phase_info['profil_nom'] == profil:
            semaines_cle = get_semaine_key(projet['date_debut'])
            if not semaines_cle:
                continue
            charges[semaines_cle] = charges.get(semaines_cle, 0) + total_jh * phase_info['pourcentage']
    return charges