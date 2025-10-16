# services/wsjf_calculator.py

POINTS_CONFIG = {
    # Champs du numérateur (Valeur métier)
    'alignement_strategic': {'fortement_aligne': 55, 'aligne': 21, 'partiellement_aligne': 8, 'non_aligne': 2},
    'impact_pnb': {'gt_5m': 55, 'between_1m_5m': 21, 'between_500k_1m': 8, 'lt_500k': 2},
    'impact_satisfaction': {'impact_tres_eleve': 55, 'impact_eleve': 21, 'impact_modere': 8, 'impact_limite': 2},
    'conquerir_client': {'gt_10p': 55, 'between_5_10p': 21, 'proche_0': 8, 'negatif': 2},
    'maitrise_couts': {'gt_5m': 55, 'between_1m_5m': 21, 'between_500k_1m': 8, 'lt_500k': 2},
    'attenuation_menaces': {'tres_eleve': 55, 'elevee': 21, 'acceptable': 8, 'limitee': 2},
    'creation_opportunites': {'exceptionnelle': 55, 'pertinentes': 21, 'modestes': 8, 'impact_limite': 2},
    'conditions_techniques': {'diversifiee_robustes': 55, 'pertinentes': 21, 'modestes': 8, 'impact_limite': 2},
    'deadline_reglementaire': {'criticite_extreme_imm': 55, 'criticite_elevee_rapp': 21, 'criticite_moderee_ger': 8, 'criticite_faible_ger': 2},
    'pression_concurrence': {'criticite_extreme': 55, 'criticite_elevee': 21, 'modecriticite_moderee': 8, 'criticite_faible': 2},
    'echeances_strategiques': {'criticite_extreme': 55, 'criticite_elevee': 21, 'criticite_moderee': 8, 'criticite_faible': 2},
    'dependances_projets': {'essentielle': 55, 'significative': 21, 'moderee': 8, 'aucune': 2},
    'urgence_obsolescence': {'immediate': 55, 'court_terme': 21, 'moyen_terme': 8, 'long_terme': 2},
    # Champs du dénominateur (Coût d'implémentation)
    'q1': {'petit': 2, 'moyen': 8, 'large': 21, 'tres_large': 55},
    'q3': {'0': 0, '1': 3, '2': 5, '3': 5, '4-5': 21},
    'q4': {'1': 1, '2_3': 2, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, 'plus_9': 10},
    'q5': {'non': 0, 'tres_faible': 1, 'faible': 2, 'moyen': 3, 'fort': 4},
    'q6': {'1_5': 1, '6_10': 2, '11_20': 3, '21_50': 4, '51_100': 5, '101_200': 6, '201_500': 7, '501_1000': 8, 'plus_1000': 9},
    'q7': {'inexistant': 0, 'faible': 2, 'moyenne': 8, 'elevee': 21, 'tres_elevee': 55},
    'q8': {'inexistant': 0, 'faible': 2, 'moyenne': 8, 'elevee': 21, 'tres_elevee': 55},
    'q9': {'tres_faible': 0, 'faible': 2, 'moyen': 8, 'eleve': 21, 'tres_eleve': 55},
    'q10': {'evolution_systeme': 2, 'integration_partenaire': 13, 'creation_nouveau': 21}
}

def calculate_wsjf(form_data):
    # Liste des champs numérateur (Valeur métier)
    numerateur_fields = [
        'alignement_strategic', 'impact_pnb', 'impact_satisfaction',
        'conquerir_client', 'maitrise_couts', 'attenuation_menaces',
        'creation_opportunites', 'conditions_techniques', 'deadline_reglementaire',
        'pression_concurrence', 'echeances_strategiques', 'urgence_obsolescence'
    ]

    # Liste des champs dénominateur (Complexité / Coût d'implémentation)
    denominateur_fields = ['q1', 'q2', 'q3', 'q4', 'q5', 'q6', 'q7', 'q8', 'q9', 'q10']

    # Calcul du numérateur
    numerateur = sum(POINTS_CONFIG[field].get(form_data.get(field, ''), 0) for field in numerateur_fields)

    # Calcul du dénominateur
    denominateur = 0
    for field in denominateur_fields:
        if field == 'q2':
            try:
                denominateur += int(form_data.get(field, '0'))
            except ValueError:
                denominateur += 0
        else:
            denominateur += POINTS_CONFIG[field].get(form_data.get(field, ''), 0)

    # Éviter la division par zéro
    wsjf = numerateur * 2 / denominateur if denominateur != 0 else 0

    # Estimation de la complexité
    complexite_score = denominateur

    def get_complexite_label(score):
        if score < 50:
            return 1  # Faible
        elif 50 <= score <= 100:
            return 2  # Moyenne
        else:
            return 3  # Élevée

    complexite = get_complexite_label(complexite_score)

    # Estimation en Jours-Homme selon la complexité
    jh_estime = {
        1: 20,
        2: 40,
        3: 60
    }.get(complexite, 30)

    return {
        'score_wsjf': round(wsjf, 2),
        'complexite_score': complexite_score,
        'complexite': complexite,
        'jh_estime': jh_estime
    }