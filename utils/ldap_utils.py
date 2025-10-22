import os

import ldap3


def ldap_authenticate(username: str, password: str):
    """

    Authentifie un utilisateur via Active Directory (LDAP).

    """

    # 🔹 Chargement des variables d’environnement

    ldap_url = os.getenv("LDAP_URL")

    bind_dn = os.getenv("LDAP_BIND_DN")

    bind_password = os.getenv("LDAP_BIND_PASSWORD")

    base_dn = os.getenv("LDAP_BASE_DN")

    # 🔍 Vérification des paramètres essentiels

    if not ldap_url or not bind_dn or not bind_password or not base_dn:
        print("❌ Erreur : les variables LDAP ne sont pas correctement chargées depuis le fichier ..env")

        print(f"LDAP_URL={ldap_url}, BIND_DN={bind_dn}, BASE_DN={base_dn}")

        return None

    print(f"🔗 Tentative de connexion LDAP au serveur {ldap_url} …")

    # ✅ Connexion au serveur LDAP avec le compte technique

    server = ldap3.Server(ldap_url, get_info=ldap3.ALL)

    try:

        conn = ldap3.Connection(server, user=bind_dn, password=bind_password, auto_bind=True)

    except Exception as e:

        print(f"❌ Impossible d’établir la connexion LDAP technique : {e}")

        return None

    # 🔍 Recherche de l’utilisateur dans le répertoire AD

    search_filter = f"(sAMAccountName={username})"

    try:

        conn.search(base_dn, search_filter, attributes=["cn", "mail", "sAMAccountName", "distinguishedName"])

    except Exception as e:

        print(f"❌ Erreur lors de la recherche de l’utilisateur {username} : {e}")

        conn.unbind()

        return None

    if not conn.entries:
        print(f"❌ Utilisateur {username} introuvable dans {base_dn}")

        conn.unbind()

        return None

    user_entry = conn.entries[0]

    user_dn = user_entry.entry_dn

    print(f"✅ Utilisateur trouvé : {user_dn}")

    # ✅ Vérification du mot de passe utilisateur (authentification réelle)

    try:

        user_conn = ldap3.Connection(server, user=user_dn, password=password, auto_bind=True)

        print(f"✅ Authentification réussie pour {username}")

        return {

            "username": str(user_entry.sAMAccountName),

            "fullname": str(user_entry.cn),

            "email": str(user_entry.mail) if "mail" in user_entry else ""

        }

    except ldap3.core.exceptions.LDAPBindError:

        print(f"❌ Mot de passe incorrect pour {username}")

        return None

    except Exception as e:

        print(f"❌ Erreur inattendue lors de l’authentification de {username} : {e}")

        return None

    finally:

        conn.unbind()

