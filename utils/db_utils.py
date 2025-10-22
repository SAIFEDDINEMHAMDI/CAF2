import os
import sqlite3
import time

# --------------------------------------------------------------------
# 📁 Chemin vers la base SQLite
# --------------------------------------------------------------------
database_path = os.path.join(os.path.dirname(__file__), '..', 'database', 'projets.db')
os.makedirs(os.path.dirname(database_path), exist_ok=True)
DB_PATH = database_path


# --------------------------------------------------------------------
# 🔌 Connexion SQLite robuste (avec WAL, timeout, foreign keys)
# --------------------------------------------------------------------
def get_connection():
    """Retourne une connexion SQLite robuste."""
    conn = sqlite3.connect(
        DB_PATH,
        timeout=60,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 60000;")
    return conn


# --------------------------------------------------------------------
# 🧩 Alias pour compatibilité Flask
# --------------------------------------------------------------------
def get_db():
    return get_connection()


# --------------------------------------------------------------------
# 🔍 SELECT avec retry automatique
# --------------------------------------------------------------------
def query_db(query, args=(), one=False, retries=3, delay=1):
    for attempt in range(retries):
        try:
            conn = get_connection()
            cur = conn.execute(query, args)
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return (rows[0] if rows else None) if one else rows
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and attempt < retries - 1:
                time.sleep(delay)
                continue
            raise


# --------------------------------------------------------------------
# ✏️ INSERT / UPDATE / DELETE avec retry automatique
# --------------------------------------------------------------------
def execute_db(query, args=(), many=False, retries=3, delay=1):
    for attempt in range(retries):
        try:
            conn = get_connection()
            cur = conn.cursor()
            if many:
                cur.executemany(query, args)
            else:
                cur.execute(query, args)
            conn.commit()
            last_id = cur.lastrowid
            cur.close()
            conn.close()
            return last_id
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and attempt < retries - 1:
                time.sleep(delay)
                continue
            raise


# --------------------------------------------------------------------
# 🏗️ Initialisation de la base
# --------------------------------------------------------------------
def init_db():
    """Initialise la base et configure WAL."""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA synchronous=NORMAL;")
        cur.execute("PRAGMA foreign_keys = ON;")

        SCHEMA = """
        -- Table des projets
        CREATE TABLE IF NOT EXISTS projets (
            id TEXT PRIMARY KEY,
            titre TEXT,
            description TEXT,
            release_id INTEGER,
            type TEXT,
            alignement_strategic TEXT,
            impact_pnb TEXT,
            impact_satisfaction TEXT,
            date_mep DATE,
            conquerir_client TEXT,
            maitrise_couts TEXT,
            attenuation_menaces TEXT,
            creation_opportunites TEXT,
            conditions_techniques TEXT,
            deadline_reglementaire TEXT,
            pression_concurrence TEXT,
            echeances_strategiques TEXT,
            urgence_obsolescence TEXT,
            dependances_projets TEXT,
            q1 TEXT, q2 TEXT, q3 TEXT, q4 TEXT, q5 TEXT,
            q6 TEXT, q7 TEXT, q8 TEXT, q9 TEXT, q10 TEXT,
            score_wsjf INTEGER,
            statut TEXT DEFAULT 'En attente',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            categorie_id INTEGER,
            duree_estimee_jh REAL DEFAULT 0,
            collaborateur_matricule TEXT,
            complexite REAL
        );

        -- Table des catégories
        CREATE TABLE IF NOT EXISTS categorie (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT UNIQUE NOT NULL
        );

        -- Table des utilisateurs
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        -- Releases
        CREATE TABLE IF NOT EXISTS releases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT,
            debut DATE,
            fin DATE
        );

        -- Profils
        CREATE TABLE IF NOT EXISTS profils (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT UNIQUE NOT NULL,
            build_ratio INTEGER DEFAULT 70,
            run_ratio INTEGER DEFAULT 30,
            heures_base INTEGER DEFAULT 35,
            description TEXT
        );

        -- Affectation
        CREATE TABLE IF NOT EXISTS affectation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT UNIQUE NOT NULL
        );

        -- Collaborateurs
        CREATE TABLE IF NOT EXISTS collaborateurs (
            matricule TEXT PRIMARY KEY,
            nom TEXT NOT NULL,
            prenom TEXT NOT NULL,
            profil_id INTEGER NOT NULL,
            affectation_id INTEGER NOT NULL,
            build_ratio INTEGER DEFAULT 70,
            run_ratio INTEGER DEFAULT 30,
            caf_disponible_build REAL DEFAULT 0,
            caf_disponible_run REAL DEFAULT 0,
            FOREIGN KEY (profil_id) REFERENCES profils(id),
            FOREIGN KEY (affectation_id) REFERENCES affectation(id)
        );

        -- Disponibilités par semaine
        CREATE TABLE IF NOT EXISTS disponibilites_semaine (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collaborateur_matricule TEXT NOT NULL,
            mois TEXT NOT NULL,
            annee INTEGER NOT NULL,
            semaine VARCHAR(2) NOT NULL,
            jours_dispo REAL NOT NULL,
            FOREIGN KEY (collaborateur_matricule) REFERENCES collaborateurs(matricule)
        );

        -- Disponibilités par jour
        CREATE TABLE IF NOT EXISTS disponibilites_jour (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collaborateur_matricule TEXT NOT NULL,
            mois TEXT NOT NULL,
            annee INTEGER NOT NULL,
            jour INTEGER NOT NULL,
            jours_dispo REAL NOT NULL,
            FOREIGN KEY (collaborateur_matricule) REFERENCES collaborateurs(matricule)
        );

        -- Programmes
        CREATE TABLE IF NOT EXISTS programmes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT UNIQUE NOT NULL
        );

        -- Phases
        CREATE TABLE IF NOT EXISTS phases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            programme_id INTEGER NOT NULL,
            nom TEXT NOT NULL,
            FOREIGN KEY (programme_id) REFERENCES programmes(id)
        );

        -- Poids phases-programmes
        CREATE TABLE IF NOT EXISTS programme_poids_phases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            programme_id INTEGER NOT NULL,
            phase_num INTEGER NOT NULL,
            poids REAL NOT NULL,
            FOREIGN KEY (programme_id) REFERENCES programmes(id),
            UNIQUE(programme_id, phase_num)
        );

        -- Valeur métier
        CREATE TABLE IF NOT EXISTS valeur_metier (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            libelle TEXT NOT NULL,
            type_libelle TEXT,
            valeur_libelle TEXT,
            ponderation REAL NOT NULL,
            iuser TEXT,
            idate DATETIME DEFAULT CURRENT_TIMESTAMP,
            uuser TEXT,
            udate DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        -- Table sous-domaine collaborateur
        CREATE TABLE IF NOT EXISTS sous_domaine_collaborateur (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom NVARCHAR(100) NOT NULL,
            description NVARCHAR(300),
            coefficient REAL DEFAULT 1,
            idate DATETIME DEFAULT CURRENT_TIMESTAMP,
            udate DATETIME,
            iuser INTEGER,
            uuser INTEGER
        );

        -- Table recrutement
        CREATE TABLE IF NOT EXISTS recrutement (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matricule TEXT NOT NULL,
            nom TEXT NOT NULL,
            prenom TEXT NOT NULL,
            profil_id INTEGER,
            sous_domaine_id INTEGER,
            date_debut DATE,
            periode_valeur INTEGER DEFAULT 0,
            periode_unite TEXT DEFAULT 'mois',
            date_productivite DATE,
            FOREIGN KEY (profil_id) REFERENCES profils(id),
            FOREIGN KEY (sous_domaine_id) REFERENCES sous_domaine_collaborateur(id)
        );

        -- Table accompagnement externe
        CREATE TABLE IF NOT EXISTS accompagnement_externe (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profil_id INTEGER NOT NULL,
            nb_etp INTEGER NOT NULL DEFAULT 0,
            date_debut DATE NOT NULL,
            date_fin DATE NOT NULL,
            iuser TEXT,
            idate DATETIME DEFAULT CURRENT_TIMESTAMP,
            uuser TEXT,
            udate DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (profil_id) REFERENCES profils(id)
        );
        """

        cur.executescript(SCHEMA)

        # ================================================================
        # 🔹 Ajout automatique des colonnes manquantes (sécurisé)
        # ================================================================
        cur.execute("SELECT COUNT(*) FROM pragma_table_info('projets') WHERE name='retenu';")
        if cur.fetchone()[0] == 0:
            cur.execute("ALTER TABLE projets ADD COLUMN retenu INTEGER DEFAULT 0;")

        cur.execute("SELECT COUNT(*) FROM pragma_table_info('recrutement') WHERE name='sous_domaine_id';")
        if cur.fetchone()[0] == 0:
            cur.execute("ALTER TABLE recrutement ADD COLUMN sous_domaine_id INTEGER REFERENCES sous_domaine_collaborateur(id);")

        # --- 🔸 Accompagnement externe : colonnes manquantes ---
        cur.execute("SELECT COUNT(*) FROM pragma_table_info('accompagnement_externe') WHERE name='sous_domaine_id';")
        if cur.fetchone()[0] == 0:
            cur.execute("ALTER TABLE accompagnement_externe ADD COLUMN sous_domaine_id INTEGER REFERENCES sous_domaine_collaborateur(id);")

        cur.execute("SELECT COUNT(*) FROM pragma_table_info('accompagnement_externe') WHERE name='periode_valeur';")
        if cur.fetchone()[0] == 0:
            cur.execute("ALTER TABLE accompagnement_externe ADD COLUMN periode_valeur INTEGER DEFAULT 0;")

        cur.execute("SELECT COUNT(*) FROM pragma_table_info('accompagnement_externe') WHERE name='periode_unite';")
        if cur.fetchone()[0] == 0:
            cur.execute("ALTER TABLE accompagnement_externe ADD COLUMN periode_unite TEXT DEFAULT 'mois';")

        cur.execute("SELECT COUNT(*) FROM pragma_table_info('accompagnement_externe') WHERE name='date_productivite';")
        if cur.fetchone()[0] == 0:
            cur.execute("ALTER TABLE accompagnement_externe ADD COLUMN date_productivite DATE;")

        conn.commit()
        cur.close()
        conn.close()
        print("✅ Base initialisée et configurée avec succès (WAL activé).")

    except Exception as e:
        print(f"❌ Erreur init_db: {e}")
        raise
