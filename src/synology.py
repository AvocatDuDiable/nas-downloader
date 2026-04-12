import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class SynologyClient:

    def __init__(self, host: str, username: str, password: str):
        self.host = host.rstrip('/')
        self.sid  = self._authenticate(username, password)

    # ── Auth ──────────────────────────────────────────────────────────────────

    def _authenticate(self, username: str, password: str) -> str:
        data = self._request('/webapi/auth.cgi', {
            'api':     'SYNO.API.Auth',
            'version': '3',
            'method':  'login',
            'account': username,
            'passwd':  password,
            'session': 'DownloadStation',
            'format':  'sid',
        })
        if not data.get('success'):
            code = data.get('error', {}).get('code', '?')
            raise RuntimeError(f'Authentification Synology échouée (code: {code})')
        return data['data']['sid']

    # ── Download Station ──────────────────────────────────────────────────────

    def list_tasks(self) -> dict:
        return self._request('/webapi/DownloadStation/task.cgi', {
            'api':        'SYNO.DownloadStation.Task',
            'version':    '1',
            'method':     'list',
            'additional': 'detail,transfer',
            '_sid':       self.sid,
        })

    def delete_tasks(self, ids: list[str]) -> dict:
        return self._request('/webapi/DownloadStation/task.cgi', {
            'api':            'SYNO.DownloadStation.Task',
            'version':        '1',
            'method':         'delete',
            'id':             ','.join(ids),
            'force_complete': 'false',
            '_sid':           self.sid,
        })

    def create_task(self, uri: str, destination: str = '') -> dict:
        params = {
            'api':     'SYNO.DownloadStation.Task',
            'version': '1',
            'method':  'create',
            'uri':     uri,
            '_sid':    self.sid,
        }
        if destination:
            params['destination'] = destination
        return self._request('/webapi/DownloadStation/task.cgi', params)

    # ── HTTP ─────────────────────────────────────────────────────────────────

    def _request(self, path: str, params: dict) -> dict:
        resp = requests.get(
            f'{self.host}{path}',
            params=params,
            verify=False,
            timeout=30,
            headers={'User-Agent': 'nas-downloader/1.0'},
        )
        resp.raise_for_status()
        return resp.json()
