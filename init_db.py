# init_db.py
import os
import sqlite3
from werkzeug.security import generate_password_hash

# Chemin vers la base SQLite
database_path = os.path.join(os.path.dirname(__file__), 'database', 'projets.db')
os.makedirs(os.path.dirname(database_path), exist_ok=True)
DB_PATH = database_path

# Schéma SQL
# principal
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
    q1 TEXT,
    q2 TEXT,
    q3 TEXT,
    q4 TEXT,
    q5 TEXT,
    q6 TEXT,
    q7 TEXT,
    q8 TEXT,
    q9 TEXT,
    q10 TEXT,
    score_wsjf INTEGER,
    statut TEXT DEFAULT 'En attente',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    categorie_id INTEGER,
    duree_estimee_jh REAL DEFAULT 0,
    collaborateur_matricule TEXT,
    programme_id INTEGER REFERENCES programmes(id)
);

-- Table des catégories
CREATE TABLE IF NOT EXISTS categorie (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT UNIQUE NOT NULL
);

-- Utilisateurs
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

-- Répartition phase-profil-programme
CREATE TABLE IF NOT EXISTS phase_profils_programme (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    programme_id INTEGER NOT NULL,
    phase_id INTEGER NOT NULL,
    profil_id INTEGER NOT NULL,
    pourcentage REAL NOT NULL,
    FOREIGN KEY (programme_id) REFERENCES programmes(id),
    FOREIGN KEY (phase_id) REFERENCES phases(id),
    FOREIGN KEY (profil_id) REFERENCES profils(id)
);

-- Table programme_profil_hypotheses (gardée une seule fois)
CREATE TABLE IF NOT EXISTS programme_profil_hypotheses (
    programme_id INTEGER NOT NULL,
    profil_id INTEGER NOT NULL,
    hypothese REAL NOT NULL DEFAULT 100,
    PRIMARY KEY (programme_id, profil_id),
    FOREIGN KEY (programme_id) REFERENCES programmes(id) ON DELETE CASCADE,
    FOREIGN KEY (profil_id) REFERENCES profils(id)
);

-- === Tables issues de ton diagramme de classe ===
CREATE TABLE IF NOT EXISTS Type (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name NVARCHAR(200),
    nom_type NVARCHAR(200),
    idate DATE,
    iuser INTEGER,
    uuser INTEGER,
    udate DATE
);

CREATE TABLE IF NOT EXISTS Programme (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    Nom_programmme NVARCHAR(200),
    idate DATE,
    iuser INTEGER,
    uuser INTEGER,
    udate DATE
);

CREATE TABLE IF NOT EXISTS Projet (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ref_opg INTEGER,
    titre_projet NVARCHAR(200),
    description NVARCHAR(300),
    id_release INTEGER,
    id_programme INTEGER,
    score_wsjf_projet REAL,
    date_mep DATE,
    retenue INTEGER,
    idate DATE,
    iuser INTEGER,
    uuser INTEGER,
    udate DATE,
    FOREIGN KEY (id_programme) REFERENCES Programme(id)
);

CREATE TABLE IF NOT EXISTS Type_projet (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type_id INTEGER,
    projet_id INTEGER,
    idate DATE,
    iuser INTEGER,
    uuser INTEGER,
    udate DATE,
    FOREIGN KEY (type_id) REFERENCES Type(id),
    FOREIGN KEY (projet_id) REFERENCES Projet(id)
);
CREATE TABLE IF NOT EXISTS valeur_metier (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    libelle NVARCHAR(200),
    type_libelle NVARCHAR(200),
    valeur_libelle INTEGER,
    ponderation INTEGER,
    idate DATE,
    iuser NVARCHAR(200), 
    uuser NVARCHAR(200),
    udate DATE
);

CREATE TABLE IF NOT EXISTS Valeur_metier_projet (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_valeur_metier INTEGER,
    id_projet INTEGER,
    idate DATE,
    iuser INTEGER,
    uuser INTEGER,
    udate DATE,
    FOREIGN KEY (id_valeur_metier) REFERENCES Valeur_metier(id),
    FOREIGN KEY (id_projet) REFERENCES Projet(id)
);

CREATE TABLE IF NOT EXISTS Complexite (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    libelle NVARCHAR(200),
    type_libelle NVARCHAR(200),
    valeur_libelle INTEGER,
    ponderation INTEGER,
    macro_estimation INTEGER,
    idate DATE,
    iuser INTEGER,
    uuser INTEGER,
    udate DATE
);

CREATE TABLE IF NOT EXISTS Complexite_projet (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_complexite INTEGER,
    id_projet INTEGER,
    idate DATE,
    iuser INTEGER,
    uuser INTEGER,
    udate DATE,
    FOREIGN KEY (id_complexite) REFERENCES Complexite(id),
    FOREIGN KEY (id_projet) REFERENCES Projet(id)
);
"""

def log_step(message):
    print(f"[INIT] {message}")

def add_missing_columns(cursor, table_name, columns):
    cursor.execute(f"PRAGMA table_info({table_name});")
    existing_cols = [col[1] for col in cursor.fetchall()]
    for col_name, col_def in columns.items():
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def};")
            log_step(f"✅ Colonne `{col_name}` ajoutée à `{table_name}`.")
        else:
            log_step(f"ℹ️ Colonne `{col_name}` existe déjà.")

def init_db():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            log_step("✅ Connexion à la base réussie.")
            cursor.execute("PRAGMA foreign_keys = ON;")
            cursor.executescript(SCHEMA)
            log_step("✅ Tables de base créées.")

            # Exemple : Ajout de colonnes manquantes si nécessaire
            add_missing_columns(cursor, "projets", {
                "categorie_id": "INTEGER REFERENCES categorie(id)",
                "duree_estimee_jh": "REAL DEFAULT 0",
                "collaborateur_matricule": "TEXT REFERENCES collaborateurs(matricule)"
            })

            # ✅ Commit final
            conn.commit()
            log_step("✅ Base initialisée avec succès.")

    except Exception as e:
        log_step(f"❌ Erreur lors de l'initialisation : {e}")
        raise

if __name__ == "__main__":
    init_db()
