# routes/import_excel_it_routes.py
from datetime import datetime
import os
import pandas as pd
from flask import Blueprint, render_template, request, flash, redirect, url_for
from werkzeug.utils import secure_filename
import unicodedata
from difflib import SequenceMatcher
from utils.db_utils import get_db

# ------------------------------------------------------------
# 📦 Blueprint & dossier uploads
# ------------------------------------------------------------
import_excel_it_bp = Blueprint("import_excel_it", __name__, url_prefix="/import_excel_it")
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ------------------------------------------------------------
# 🔠 Fonctions utilitaires
# ------------------------------------------------------------
def normalize_text(text):
    """Nettoie et normalise les textes (accents, espaces, majuscules...)."""
    if text is None:
        return ""
    text = str(text).strip()
    if text.lower() == "nan":
        return ""
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.replace("_", " ").replace("-", " ").replace("’", "'").replace("œ", "oe")
    text = " ".join(text.split())
    return text


def similar(a, b, seuil=0.9):
    """Retourne True si deux chaînes sont suffisamment similaires."""
    if not a or not b:
        return False
    return SequenceMatcher(None, a, b).ratio() >= seuil


# ------------------------------------------------------------
# 🔧 ROUTE PRINCIPALE : Import Excel IT
# ------------------------------------------------------------
@import_excel_it_bp.route("/", methods=["GET", "POST"])
def import_excel_it():
    if request.method == "POST":
        file = request.files.get("file")
        if not file:
            flash("❌ Aucun fichier sélectionné.", "error")
            return redirect(url_for("import_excel_it.import_excel_it"))

        # ✅ Nom unique pour éviter les collisions
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = secure_filename(file.filename)
        name, ext = os.path.splitext(filename)
        unique_name = f"{name}_{timestamp}{ext}"

        filepath = os.path.join(UPLOAD_FOLDER, unique_name)
        file.save(filepath)

        # 📖 Lecture Excel
        try:
            df = pd.read_excel(filepath)
        except Exception as e:
            flash(f"❌ Erreur de lecture Excel : {e}", "error")
            return redirect(url_for("import_excel_it.import_excel_it"))

        log_path = os.path.join(UPLOAD_FOLDER, f"import_debug_it_{timestamp}.txt")
        with open(log_path, "w", encoding="utf-8") as debug:
            debug.write("=== DEBUG IMPORT IT ===\n\n")

            # ------------------------------------------------------------
            # 🧩 Normalisation colonnes
            # ------------------------------------------------------------
            df.columns = [normalize_text(c) for c in df.columns]
            debug.write(f"🔎 Colonnes normalisées : {df.columns.tolist()}\n\n")

            required = [
                "ref ogp",
                "nomencalture du projet",
                "description du projet",
                "date de mep prevue",
            ]
            missing = [r for r in required if r not in df.columns]
            if missing:
                flash(f"❌ Colonnes manquantes : {', '.join(missing)}", "error")
                debug.write(f"❌ Colonnes manquantes : {missing}\n")
                return redirect(url_for("import_excel_it.import_excel_it"))

            # ------------------------------------------------------------
            # 🧠 Détection des blocs projet (1 projet = 3 lignes)
            # ------------------------------------------------------------
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
                return redirect(url_for("import_excel_it.import_excel_it"))

            # ------------------------------------------------------------
            # 💾 Insertion des projets + valeurs métier
            # ------------------------------------------------------------
            conn = get_db()
            cur = conn.cursor()
            cur.execute("PRAGMA foreign_keys = ON")

            # Charger toutes les valeurs métier
            vm = pd.read_sql_query(
                "SELECT id, libelle, type_libelle, valeur_libelle FROM valeur_metier",
                conn,
            )
            for col in ["libelle", "type_libelle", "valeur_libelle"]:
                vm[col] = vm[col].astype(str).apply(normalize_text)
            debug.write(f"📚 {len(vm)} valeurs métier chargées.\n\n")

            inserted_count = 0
            total_links = 0

            for p_idx, chunk in enumerate(projects, start=1):
                meta = chunk.iloc[0]
                ref_opg = str(meta.get("ref ogp", "")).strip()
                titre = str(meta.get("nomencalture du projet", "")).strip()
                desc = str(meta.get("description du projet", "")).strip()

                # ✅ Conversion de la date Excel
                date_raw = meta.get("date de mep prevue")
                if pd.notna(date_raw):
                    if isinstance(date_raw, pd.Timestamp):
                        date_mep = date_raw.strftime("%Y-%m-%d")
                    else:
                        date_mep = str(date_raw)
                else:
                    date_mep = None

                debug.write(f"\n--- Projet {p_idx} : {titre} ({ref_opg}) ---\n")

                # 🔹 Insertion du projet
                try:
                    cur.execute(
                        """
                        INSERT INTO Projet (ref_opg, titre_projet, description, date_mep, idate,type)
                        VALUES (?, ?, ?, ?, DATETIME('now'),'it')
                        """,
                        (ref_opg, titre, desc, date_mep),
                    )
                    conn.commit()
                    id_projet = cur.lastrowid
                    inserted_count += 1
                except Exception as e:
                    debug.write(f"❌ Erreur insertion projet : {e}\n")
                    continue

                # --------------------------------------------------------
                # 🔍 Lecture des valeurs métier
                # --------------------------------------------------------
                for col in df.columns:
                    if col in required or col in ["nom du departement", "type de la demande"]:
                        continue

                    # ligne 0 → type (texte)
                    # ligne 2 → valeur (numérique)
                    type_vals = [
                        str(v).strip()
                        for v in chunk.iloc[0:1][col].tolist()
                        if str(v).strip() and str(v).strip().lower() != "nan"
                    ]

                    valeur_vals = [
                        str(v).strip()
                        for v in chunk.iloc[2:3][col].tolist()
                        if str(v).strip() and str(v).strip().lower() != "nan"
                    ]

                    type_libelle = " ".join(type_vals)
                    valeur_libelle = " ".join(valeur_vals)

                    lib_n = normalize_text(col)
                    type_n = normalize_text(type_libelle)
                    val_n = normalize_text(valeur_libelle)

                    if not type_n and not val_n:
                        continue

                    # Recherche exacte
                    match = vm[
                        vm.apply(
                            lambda r: (
                                r["libelle"] == lib_n
                                and (r["type_libelle"] == type_n or not type_n)
                                and (r["valeur_libelle"] == val_n or not val_n)
                            ),
                            axis=1,
                        )
                    ]

                    # Recherche floue si rien trouvé
                    if match.empty:
                        match = vm[
                            vm.apply(
                                lambda r: (
                                    similar(r["libelle"], lib_n)
                                    and (not type_n or similar(r["type_libelle"], type_n))
                                    and (not val_n or similar(r["valeur_libelle"], val_n))
                                ),
                                axis=1,
                            )
                        ]

                    if not match.empty:
                        vm_id = int(match.iloc[0]["id"])
                        cur.execute(
                            """
                            INSERT OR IGNORE INTO valeur_metier_projet (id_projet, id_valeur_metier, idate)
                            VALUES (?, ?, DATETIME('now'))
                            """,
                            (id_projet, vm_id),
                        )
                        total_links += 1
                        debug.write(f"🟩 match valeur_metier id={vm_id}\n")
                    else:
                        debug.write(f"❌ Aucun match pour {col}\n")

                conn.commit()

            debug.write(f"\n✅ Import terminé : {inserted_count} projets, {total_links} liens créés.\n")

        flash(f"✅ Import terminé : {inserted_count} projets, {total_links} liens créés.", "success")
        return redirect(url_for("projet.liste_projets"))

    return render_template("import_excel_it.html")
