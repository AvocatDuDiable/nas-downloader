import os
import sys
import time
import importlib.util

import requests
import urllib3
from flask import Flask, jsonify, request, send_from_directory

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Config ────────────────────────────────────────────────────────────────────

def _load_config():
    candidates = [
        os.environ.get('CONFIG_PATH', ''),
        os.path.join(os.path.dirname(__file__), '..', 'config', 'config.py'),
        '/app/config/config.py',
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            spec = importlib.util.spec_from_file_location('config', os.path.abspath(path))
            mod  = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise FileNotFoundError(
        'config.py introuvable. Vérifiez que config/config.py existe ou '
        'définissez la variable d\'environnement CONFIG_PATH.'
    )

config = _load_config()

sys.path.insert(0, os.path.dirname(__file__))
from synology import SynologyClient

# ── Flask ─────────────────────────────────────────────────────────────────────

STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path='')
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 Mo max

AGENT = 'nas-downloader'

# ── Routes statiques ──────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory(STATIC_DIR, 'index.html')

# ── API : destinations ────────────────────────────────────────────────────────

@app.route('/api/destinations')
def api_destinations():
    return jsonify({'success': True, 'destinations': config.DESTINATIONS})

# ── API : list ────────────────────────────────────────────────────────────────

@app.route('/api/list')
def api_list():
    try:
        client = SynologyClient(
            config.NAS['host'], config.NAS['username'], config.NAS['password']
        )
        result = client.list_tasks()
        if not result.get('success'):
            code = result.get('error', {}).get('code', '?')
            raise RuntimeError(f'Impossible de lister les tâches (code: {code})')
        return jsonify({
            'success': True,
            'tasks':   result['data'].get('tasks', []),
            'total':   result['data'].get('total', 0),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ── API : delete ──────────────────────────────────────────────────────────────

@app.route('/api/delete', methods=['POST'])
def api_delete():
    try:
        data = request.get_json()
        if not data or not isinstance(data.get('ids'), list) or not data['ids']:
            raise ValueError('Paramètre "ids" manquant ou invalide')

        ids = [
            str(i) for i in data['ids']
            if str(i).replace('-', '').replace('_', '').isalnum()
        ]
        if not ids:
            raise ValueError('Aucun ID valide fourni')

        client = SynologyClient(
            config.NAS['host'], config.NAS['username'], config.NAS['password']
        )
        result = client.delete_tasks(ids)
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ── AllDebrid helpers ─────────────────────────────────────────────────────────

_FATAL = {
    5: 'Upload échoué',
    6: 'Erreur interne AllDebrid',
    7: 'Non téléchargé',
    8: 'Fichier introuvable',
    9: 'Virus détecté',
    10: 'Quota dépassé',
}


def ad_upload(api_key: str, file_storage) -> tuple[int, bool]:
    resp = requests.post(
        'https://api.alldebrid.com/v4/magnet/upload/file',
        params={'agent': AGENT, 'apikey': api_key},
        files={'files[]': (file_storage.filename, file_storage.stream,
                           'application/x-bittorrent')},
        timeout=30,
    )
    data = resp.json()
    if data.get('status') != 'success':
        msg = data.get('error', {}).get('message', 'Erreur upload AllDebrid')
        raise RuntimeError(f'AllDebrid: {msg}')
    entry = (data.get('data', {}).get('files') or [{}])[0]
    if not entry.get('id'):
        raise RuntimeError(
            f"AllDebrid n'a pas retourné d'ID magnet. Réponse: {data}"
        )
    return int(entry['id']), bool(entry.get('ready', False))


def ad_wait_ready(api_key: str, magnet_id: int, max_wait: int = 90) -> None:
    start = time.time()
    while True:
        resp = requests.get(
            'https://api.alldebrid.com/v4/magnet/status',
            params={'agent': AGENT, 'apikey': api_key, 'id': magnet_id},
            timeout=15,
        )
        data = resp.json()
        if data.get('status') != 'success':
            raise RuntimeError(f'Statut AllDebrid: {data}')

        magnet      = data['data']['magnets']
        status_code = int(magnet.get('statusCode', -1))

        if status_code == 4:
            return
        if status_code in _FATAL:
            raise RuntimeError(f"AllDebrid: {_FATAL[status_code]}")
        if time.time() - start >= max_wait:
            raise RuntimeError(
                f"Timeout : AllDebrid n'a pas terminé en {max_wait}s. "
                "Le torrent est peut-être en cours de téléchargement, "
                "réessayez dans quelques minutes."
            )
        time.sleep(3)


def ad_get_links(api_key: str, magnet_id: int) -> list[str]:
    resp = requests.get(
        'https://api.alldebrid.com/v4/magnet/files',
        params={'agent': AGENT, 'apikey': api_key, 'id[]': magnet_id},
        timeout=15,
    )
    data = resp.json()
    if data.get('status') != 'success':
        raise RuntimeError(f'AllDebrid files: {data}')

    links: list[str] = []
    for magnet in data.get('data', {}).get('magnets', []):
        _extract_links(magnet.get('files', []), links)

    if not links:
        raise RuntimeError(
            f"AllDebrid n'a retourné aucun lien. Réponse: {data}"
        )
    return links


def _extract_links(files: list, out: list) -> None:
    for f in files:
        if f.get('l'):
            out.append(f['l'])
        elif f.get('e'):
            _extract_links(f['e'], out)


def ad_unlock(api_key: str, link: str) -> str:
    resp = requests.get(
        'https://api.alldebrid.com/v4/link/unlock',
        params={'agent': AGENT, 'apikey': api_key, 'link': link},
        timeout=30,
    )
    data = resp.json()
    if data.get('status') != 'success':
        msg = data.get('error', {}).get('message', 'Erreur débridage')
        raise RuntimeError(f'AllDebrid unlock [{link}]: {msg}')
    direct = data.get('data', {}).get('link', '')
    if not direct:
        raise RuntimeError(
            f"AllDebrid unlock: pas de lien direct retourné. Réponse: {data}"
        )
    return direct

# ── API : add ─────────────────────────────────────────────────────────────────

@app.route('/api/add', methods=['POST'])
def api_add():
    try:
        if 'torrent' not in request.files:
            raise ValueError('Aucun fichier torrent reçu')

        torrent = request.files['torrent']
        if not torrent.filename.lower().endswith('.torrent'):
            raise ValueError("Le fichier doit avoir l'extension .torrent")

        destination = request.form.get('destination', '').strip()
        if destination:
            allowed = [d['path'] for d in config.DESTINATIONS]
            if destination not in allowed:
                raise ValueError('Destination non autorisée')

        # 1. Upload vers AllDebrid
        magnet_id, ready = ad_upload(config.ALLDEBRID['api_key'], torrent)

        # 2. Attendre si pas encore prêt
        if not ready:
            ad_wait_ready(config.ALLDEBRID['api_key'], magnet_id)

        # 3. Récupérer les liens hébergeurs
        links = ad_get_links(config.ALLDEBRID['api_key'], magnet_id)

        # 4. Débrider + envoyer au NAS
        client = SynologyClient(
            config.NAS['host'], config.NAS['username'], config.NAS['password']
        )
        added  = 0
        errors = []
        for link in links:
            try:
                direct = ad_unlock(config.ALLDEBRID['api_key'], link)
                result = client.create_task(direct, destination)
                if result.get('success'):
                    added += 1
                else:
                    code = result.get('error', {}).get('code', '?')
                    errors.append(f'NAS error code: {code}')
            except Exception as ex:
                errors.append(str(ex))

        if added == 0:
            raise RuntimeError(
                f"Aucun fichier ajouté au NAS. {' | '.join(errors)}"
            )

        return jsonify({
            'success': True,
            'added':   added,
            'total':   len(links),
            'errors':  errors,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ── Entrée ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=getattr(config, 'PORT', 8080), debug=False, threaded=True)
