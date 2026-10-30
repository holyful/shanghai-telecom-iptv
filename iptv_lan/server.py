"""Trusted-LAN web UI and xTeVe-compatible subscription endpoints."""

from datetime import datetime, timedelta
import gzip
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import mimetypes
import os
from pathlib import Path
import signal
import threading
import time
from urllib.parse import parse_qs, urlsplit

from .core import TZ, channel_identity, make_m3u, make_xmltv, public_channels
from .service import Service


def make_server(service, bind, port):
    static = Path(__file__).parent / 'static'
    config = service.config
    base = config.get('public_url', f'http://{bind}:{port}').rstrip('/')
    networks = [ipaddress.ip_network(n) for n in config.get('allowed_networks', ['127.0.0.0/8'])]

    class Handler(BaseHTTPRequestHandler):
        server_version = 'HomeCast'

        def log_message(self, fmt, *args):
            # Default access logs can contain query strings. Operational logs use safe events.
            pass

        def permitted(self):
            try:
                ip = ipaddress.ip_address(self.client_address[0])
                host = urlsplit('http://' + self.headers.get('Host', '')).hostname
                allowed_hosts = {urlsplit(base).hostname, self.server.server_address[0], 'localhost', '127.0.0.1'}
                allowed_hosts.update(config.get('allowed_hosts', []))
                return any(ip in net for net in networks) and host in allowed_hosts
            except ValueError:
                return False

        def send(self, status, body=b'', mime='application/json; charset=utf-8', extra=None):
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            if self.command != 'HEAD':
                try:
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            if not self.permitted():
                return self.send(403, {'error': 'Trusted LAN only'})
            path = urlsplit(self.path).path
            query = parse_qs(urlsplit(self.path).query)
            data = service.snapshot
            if path in ('/health', '/api/status'):
                return self.send(200, service.status())
            if path == '/api/channels':
                return self.send(200, {'channels': public_channels(data)})
            if path == '/api/logs':
                return self.send(200, {'logs': list(reversed(service.logs))})
            if path == '/api/settings':
                return self.send(200, service.settings)
            if path.startswith('/api/channels/') and path.endswith('/programmes'):
                cid = path.split('/')[3]
                channel = next((c for c in public_channels(data) if c['id'] == cid), None)
                if not channel:
                    return self.send(404, {'error': 'Unknown channel'})
                date = query.get('date', [datetime.now(TZ).date().isoformat()])[0]
                try:
                    begin = datetime.strptime(date, '%Y-%m-%d').replace(tzinfo=TZ)
                except ValueError:
                    return self.send(400, {'error': 'Invalid date'})
                end = (begin + timedelta(days=1)).timestamp()
                rows = [p for p in data['programmes'].get(cid, []) if p['start'] < end and p['end'] > begin.timestamp()]
                return self.send(200, {'channel': channel, 'date': date, 'programmes': rows})
            if path in ('/m3u/xteve.m3u', '/playlist.m3u', '/m3u/jellyfin.m3u', '/xmltv/jellyfin.xml', '/xmltv/xteve.xml', '/xmltv/xteve.xml.gz', '/epg.xml'):
                if not data['channels']:
                    return self.send(503, {'error': 'No validated snapshot yet'})
                jellyfin = path in ('/m3u/jellyfin.m3u', '/xmltv/jellyfin.xml')
                if path.endswith('.m3u'):
                    return self.send(200, make_m3u(data, base, service.legacy, jellyfin), 'audio/x-mpegurl; charset=utf-8')
                body = make_xmltv(data, service.legacy, jellyfin)
                if path.endswith('.gz'):
                    return self.send(200, gzip.compress(body), 'application/gzip')
                return self.send(200, body, 'application/xml; charset=utf-8')
            if path.startswith('/stream/') or path.startswith('/auto/v'):
                value = path.rsplit('/', 1)[1]
                for c in data['channels']:
                    ident = channel_identity(c['id'], service.legacy)
                    if value == ident['stream_id'] or (path.startswith('/auto/v') and value == 'v' + ident['number']):
                        url = config['udpxy_url'].rstrip('/') + '/udp/' + c['multicast']
                        return self.send(302, b'', extra={'Location': url})
                return self.send(404, {'error': 'Channel is no longer in the official lineup'})
            if path == '/lineup.json':
                rows = []
                for c in data['channels']:
                    ident = channel_identity(c['id'], service.legacy)
                    rows.append({'GuideNumber': ident['number'], 'GuideName': c['name'], 'URL': base + '/stream/' + ident['stream_id']})
                return self.send(200, rows)
            if path == '/lineup_status.json':
                return self.send(200, {'ScanInProgress': 0, 'ScanPossible': 0, 'Source': 'Cable', 'SourceList': ['Cable']})
            if path == '/discover.json':
                return self.send(200, {'FriendlyName': 'HomeCast', 'Manufacturer': 'HomeCast', 'ModelNumber': 'HDHR',
                                       'FirmwareName': 'homecast', 'FirmwareVersion': '0.1.0',
                                       'DeviceID': config.get('device_id', '12345678'), 'DeviceAuth': 'homecast',
                                       'BaseURL': base, 'LineupURL': base + '/lineup.json', 'TunerCount': config.get('tuner_count', 4)})
            if path in ('/', '/web', '/web/'):
                path = '/index.html'
            if path.startswith('/static/'):
                path = path.removeprefix('/static')
            if path in ('/index.html', '/app.js', '/styles.css', '/style.css') or path.startswith(('/assets/', '/vendor/')):
                candidate = (static / path.lstrip('/')).resolve()
                if candidate.is_relative_to(static.resolve()) and candidate.is_file():
                    mime = mimetypes.guess_type(candidate.name)[0] or 'application/octet-stream'
                    return self.send(200, candidate.read_bytes(), mime + ('; charset=utf-8' if mime.startswith('text/') else ''))
            self.send(404, {'error': 'Not found'})

        def do_POST(self):
            if not self.permitted():
                return self.send(403, {'error': 'Trusted LAN only'})
            origin = self.headers.get('Origin')
            if origin and urlsplit(origin).netloc != self.headers.get('Host'):
                return self.send(403, {'error': 'Cross-origin changes rejected'})
            if self.headers.get('X-Requested-With') != 'HomeCast' or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.send(403, {'error': 'Explicit JSON request required'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 4096:
                    raise ValueError()
                body = json.loads(self.rfile.read(length))
                path = urlsplit(self.path).path
                if path == '/api/refresh':
                    return self.send(202, {'started': service.refresh()})
                if path == '/api/settings':
                    return self.send(200, service.update_settings(body))
                return self.send(404, {'error': 'Not found'})
            except (ValueError, TypeError, AttributeError):
                self.send(400, {'error': 'Invalid request'})

    server = ThreadingHTTPServer((bind, port), Handler)
    server.daemon_threads = True
    return server


def main():
    path = Path(os.environ.get('HOMECAST_CONFIG', '/config/config.json'))
    config = json.loads(path.read_text(encoding='utf-8'))
    required = ('user_id', 'protocol_sn', 'mac', 'interface', 'auth_host', 'public_url', 'udpxy_url', 'bind_address')
    if any(not config.get(key) or 'CHANGE_ME' in config[key] for key in required):
        raise SystemExit('Complete the private configuration before starting HomeCast')
    service = Service(config)
    server = make_server(service, config['bind_address'], int(config.get('port', 34400)))
    stop = threading.Event()
    threading.Thread(target=service.scheduler, args=(stop,), daemon=True).start()
    def shutdown(*_):
        stop.set()
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    print('HomeCast started; subscriber identity is not logged', flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
