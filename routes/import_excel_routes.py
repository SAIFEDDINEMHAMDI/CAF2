# routes/import_excel_routes.py
from datetime import datetime
import os
import pandas as pd
import unicodedata
from flask import Blueprint, render_template, request, flash, redirect, url_for
from werkzeug.utils import secure_filename
from utils.db_utils import get_db

# ------------------------------------------------------------
# 📦 Blueprint & dossier uploads
# ------------------------------------------------------------
import_excel_bp = Blueprint("import_excel", __name__, url_prefix="/import")
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ------------------------------------------------------------
# 🔠 Fonction utilitaire : normalisation du texte
# ------------------------------------------------------------
def normalize_text(text):
    if text is None:
        return ""
    text = str(text).strip()
    if text.lower() == "nan":
        return ""
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.replace("_", " ").replace("-", " ").replace("’", "'")
    text = " ".join(text.split())
    return text


# ------------------------------------------------------------
# 📥 ROUTE IMPORT EXCEL (Projets uniquement)
# ------------------------------------------------------------
@import_excel_bp.route("/", methods=["GET", "POST"])
def import_excel():
    if request.method == "POST":
        file = request.files.get("file")
        if not file:
            flash("❌ Aucun fichier sélectionné.", "error")
            return redirect(url_for("import_excel.import_excel"))

        # ✅ Nom unique pour le fichier importé
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = secure_filename(file.filename)
        name, ext = os.path.splitext(filename)
        unique_name = f"{name}_{timestamp}{ext}"

        filepath = os.path.join(UPLOAD_FOLDER, unique_name)
        file.save(filepath)

        # ✅ Création d’un log spécifique à ce fichier
        log_name = f"import_debug_{name}_{timestamp}.txt"
        log_path = os.path.join(UPLOAD_FOLDER, log_name)

        with open(log_path, "w", encoding="utf-8") as debug:
            debug.write("=== LOG IMPORT PROJETS ===\n")
            debug.write(f"📅 Import effectué le : {timestamp}\n")
            debug.write(f"📁 Fichier importé : {unique_name}\n\n")

            # --------------------------------------------------------
            # 📖 Lecture Excel
            # --------------------------------------------------------
            try:
                df = pd.read_excel(filepath)
                debug.write(f"✅ Lecture Excel réussie ({len(df)} lignes)\n\n")
            except Exception as e:
                debug.write(f"❌ Erreur de lecture Excel : {e}\n")
                flash(f"❌ Erreur de lecture Excel : {e}", "error")
                return redirect(url_for("import_excel.import_excel"))

            # --------------------------------------------------------
            # 🧩 Normalisation des colonnes
            # --------------------------------------------------------
            df.columns = [normalize_text(c) for c in df.columns]
            debug.write(f"🔠 Colonnes détectées : {df.columns.tolist()}\n\n")

            required = [
                "ref ogp",
                "nomencalture du projet",
                "description du projet",
                "date de mep prevue",
            ]
            missing = [c for c in required if c not in df.columns]
            if missing:
                for m in missing:
                    debug.write(f"❌ Colonne manquante : {m}\n")
                flash(f"❌ Colonnes manquantes : {', '.join(missing)}", "error")
                return redirect(url_for("import_excel.import_excel"))

            # --------------------------------------------------------
            # 🧠 Détection des blocs projet (3 lignes = 1 projet)
            # --------------------------------------------------------
            projects = []
            i = 0
            while i < len(df):
                ref = str(df.iloc[i].get("ref ogp", "")).strip()
                if ref and ref.lower() != "nan":
                    projects.append(df.iloc[i:i + 3])
                    i += 3
                else:
                    i += 1
            debug.write(f"📊 {len(projects)} blocs projet détectés.\n\n")

            if not projects:
                flash("❌ Aucun projet détecté dans le fichier.", "error")
                debug.write("❌ Aucun bloc projet détecté.\n")
                return redirect(url_for("import_excel.import_excel"))

            # --------------------------------------------------------
            # 💾 Insertion dans la table Projet
            # --------------------------------------------------------
            conn = get_db()
            cur = conn.cursor()
            cur.execute("PRAGMA foreign_keys = ON")

            inserted_count = 0
            sans_domaine = 0

            for idx, chunk in enumerate(projects, start=1):
                meta = chunk.iloc[0]
                ref_opg = str(meta.get("ref ogp", "")).strip()
                titre = str(meta.get("nomencalture du projet", "")).strip()
                desc = str(meta.get("description du projet", "")).strip()

                # 🗓️ Gestion de la date MEP
                date_raw = meta.get("date de mep prevue")
                if pd.notna(date_raw):
                    if isinstance(date_raw, pd.Timestamp):
                        date_mep = date_raw.strftime("%Y-%m-%d")
                    else:
                        date_mep = str(date_raw)
                else:
                    date_mep = None

                # 🏢 Domaine / Département (table = domaines)
                domaine_nom = None
                for col in [
                    "nom du departement",
                    "nom de departement",
                    "nom du domaine",
                    "nom de domaine",
                    "nom du domaines",
                ]:
                    if col in meta and pd.notna(meta[col]) and str(meta[col]).strip():
                        domaine_nom = str(meta[col]).strip()
                        break

                id_domaine = None
                if domaine_nom:
                    try:
                        cur.execute("SELECT id FROM domaines WHERE lower(nom) = lower(?)", (domaine_nom,))
                        row = cur.fetchone()
                        if row:
                            id_domaine = row["id"]
                            debug.write(f"🔗 Domaine trouvé : {domaine_nom} (ID={id_domaine})\n")
                        else:
                            id_domaine = None
                            sans_domaine += 1
                            debug.write(f"⚠️ Domaine '{domaine_nom}' non trouvé → id_domaine=NULL\n")
                    except Exception as e:
                        debug.write(f"⚠️ Erreur recherche domaine ({domaine_nom}) : {e}\n")
                else:
                    sans_domaine += 1
                    debug.write("ℹ️ Aucun nom de domaine ou département fourni → id_domaine=NULL\n")

                debug.write(f"\n--- Bloc projet {idx} ---\n")
                debug.write(f"Ref OGP : {ref_opg}\n")
                debug.write(f"Titre    : {titre}\n")
                debug.write(f"Date MEP : {date_mep}\n")
                debug.write(f"id_domaine : {id_domaine}\n")

                if not ref_opg or not titre:
                    debug.write("⚠️  Ignoré (ref ou titre manquant)\n\n")
                    continue

                try:
                    cur.execute(
                        """
                        INSERT INTO Projet (ref_opg, titre_projet, description, date_mep, id_domaine, idate)
                        VALUES (?, ?, ?, ?, ?, DATETIME('now'))
                        """,
                        (ref_opg, titre, desc, date_mep, id_domaine),
                    )
                    inserted_count += 1
                    debug.write("✅ Projet inséré avec succès\n\n")
                except Exception as e:
                    debug.write(f"❌ Erreur insertion : {e}\n\n")

            conn.commit()
            debug.write(f"✅ Import terminé : {inserted_count} projets insérés.\n")
            debug.write(f"⚠️ {sans_domaine} projets sans domaine reconnu.\n")
            debug.write(f"📄 Log sauvegardé sous : {log_name}\n")

        # ✅ Message flash avec résumé clair
        if sans_domaine > 0:
            flash(f"✅ Import terminé : {inserted_count} projets insérés (dont {sans_domaine} sans domaine reconnu).", "warning")
        else:
            flash(f"✅ Import terminé : {inserted_count} projets insérés.", "success")

        return redirect(url_for("projet.liste_demandes"))

    return render_template("import_excel.html")
