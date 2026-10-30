"""Exercise the installed image with synthetic data; no IPTV service is contacted."""

import http.client
import json
import socket
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET


def docker(*args, input=None, timeout=90):
    result = subprocess.run(['docker', *args], input=input, text=True,
                            capture_output=True, timeout=timeout, check=True)
    return result.stdout.strip()


def request(port, path):
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
    try:
        connection.request('GET', path)
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


def check(image, mode):
    name = 'homecast-smoke-' + uuid.uuid4().hex[:12]
    volume = name + '-data'
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    config = {'user_id': 'fictional@etv2', 'protocol_sn': 'EXAMPLE1234',
              'mac': '02:00:00:00:00:01', 'interface': 'lo',
              'auth_host': '127.0.0.1:9', 'bind_address': '127.0.0.1', 'port': port,
              'allowed_networks': ['127.0.0.0/8'], 'data_dir': '/data',
              'min_channels': 1, 'auto_refresh': False, 'refresh_time': '06:45',
              'legacy_file': '/data/legacy.json'}
    now = time.time()
    snapshot = {'channels': [{'id': '1', 'name': 'Demo HD', 'group': 'Demo',
                              'quality': 'HD', 'multicast': '239.1.1.1:1234'}],
                'programmes': {'1': [{'title': 'Synthetic programme', 'start': now - 60,
                                      'end': now + 7200}]}}
    seed = {'snapshot': snapshot,
            'settings': {'auto_refresh': mode == 'environment', 'refresh_time': '04:30'},
            'legacy': {'1': {'epg_id': 'legacy.1', 'number': '1001', 'stream_id': 'oldhash'}}}
    docker('volume', 'create', volume)
    try:
        docker('run', '--rm', '-i', '--mount', f'type=volume,src={volume},dst=/data',
               '--entrypoint', 'python', '-w', '/tmp', image, '-c',
               'import json,sys; from pathlib import Path; from iptv_lan.core import SnapshotStore; '
               'v=json.load(sys.stdin); SnapshotStore(Path("/data"),1).publish(v["snapshot"]); '
               'Path("/data/settings.json").write_text(json.dumps(v["settings"])); '
               'Path("/data/legacy.json").write_text(json.dumps(v["legacy"]))', input=json.dumps(seed))
        args = ['run', '-d', '--name', name, '--network', 'host', '--read-only',
                    '--cap-drop', 'ALL', '--cap-add', 'NET_RAW', '--tmpfs', '/tmp:rw,noexec,nosuid,size=32m',
                    '--mount', f'type=volume,src={volume},dst=/data', '--workdir', '/tmp',
                    '--health-interval', '1s', '--health-start-period', '1s', '--health-timeout', '5s']
        for key, value in config.items():
            if mode == 'stored-schedule' and key in ('auto_refresh', 'refresh_time'):
                continue
            if isinstance(value, (list, bool)):
                value = json.dumps(value)
            args.extend(['-e', f'HOMECAST_{key.upper()}={value}'])
        docker(*args, image)
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            status = json.loads(docker('inspect', '--format', '{{json .State}}', name))
            if status.get('Health', {}).get('Status') == 'healthy':
                break
            if not status['Running']:
                raise AssertionError(docker('logs', name))
            time.sleep(0.25)
        else:
            raise AssertionError('Container did not become healthy: ' + json.dumps(status))
        code, _, body = request(port, '/api/status')
        status = json.loads(body)
        assert code == 200 and status['channel_count'] == 1, status
        assert status['state'] == 'idle' and status['last_attempt'] is None, status
        assert status['auto_refresh'] is False, status
        assert status['refresh_time'] == ('06:45' if mode == 'environment' else '04:30'), status
        assert status['managed_settings'] == (['auto_refresh', 'refresh_time'] if mode == 'environment' else []), status
        assert status['public_url'] == f'http://127.0.0.1:{port}', status
        code, _, playlist = request(port, '/m3u/xteve.m3u')
        assert code == 200 and b'tvg-id="legacy.1"' in playlist and b'/stream/oldhash' in playlist
        code, _, guide = request(port, '/xmltv/xteve.xml')
        assert code == 200 and ET.fromstring(guide).find('channel').get('id') == 'legacy.1'
        code, headers, _ = request(port, '/stream/oldhash')
        assert code == 302 and headers['Location'].endswith(':4022/udp/239.1.1.1:1234')
        code, _, page = request(port, '/')
        assert code == 200 and b'id="subscriptions-open"' in page
        docker('exec', name, 'python', '-m', 'iptv_lan.healthcheck')
        docker('exec', name, 'python', '-c', 'from pathlib import Path; assert not Path("/config/config.json").exists()')
        print(f'{mode}: healthy, installed assets, schedule, cached exports and stream IDs verified')
    finally:
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=30)
        docker('volume', 'rm', volume)


if __name__ == '__main__':
    for mode in ('environment', 'stored-schedule'):
        check(sys.argv[1] if len(sys.argv) > 1 else 'homecast-test', mode)
