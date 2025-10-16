from utils.db_utils import query_db

def calculer_charge_estimee(score_complexite, id_domaine):
    # 1️⃣ Trouver la règle correspondant au score
    regle = query_db("""
        SELECT * FROM regle_complexite
        WHERE ? BETWEEN score_min AND score_max
        LIMIT 1
    """, [score_complexite], one=True)

    if not regle:
        return {"erreur": "Aucune règle trouvée pour ce score"}

    # 2️⃣ Récupérer le coefficient du domaine
    domaine = query_db("SELECT coefficient FROM domaines WHERE id = ?", [id_domaine], one=True)
    coef = domaine["coefficient"] if domaine else 0

    # 3️⃣ Calcul
    charge = regle["valeur_base"] * (1 + coef / 100.0)

    return {
        "score": score_complexite,
        "fibonacci": regle["fibo"],
        "valeur_base": regle["valeur_base"],
        "coefficient": coef,
        "charge_estimee": round(charge, 0)
    }
