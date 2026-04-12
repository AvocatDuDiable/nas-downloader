# ── Serveur ───────────────────────────────────────────────────────────────────
PORT = 8080

# ── NAS Synology ──────────────────────────────────────────────────────────────
NAS = {
    'host':     'http://192.168.1.X:5000',
    'username': 'votre_utilisateur',
    'password': 'votre_mot_de_passe',
}

# ── AllDebrid ─────────────────────────────────────────────────────────────────
# Clé API : https://alldebrid.com/apikeys/
ALLDEBRID = {
    'api_key': 'VOTRE_CLE_API',
}

# ── Destinations de téléchargement ────────────────────────────────────────────
# name : affiché dans la liste déroulante
# path : chemin transmis à Download Station (relatif au volume Synology)
DESTINATIONS = [
    {'name': 'Films',  'path': 'Downloads/Films'},
    {'name': 'Séries', 'path': 'Downloads/Séries'},
    {'name': 'Autres', 'path': 'Downloads'},
]
