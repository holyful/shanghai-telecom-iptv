import http.client
import json
import tempfile
import threading
import unittest

from iptv_lan.server import make_server
from iptv_lan.service import Service
from test_core import fixture


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = Service({'data_dir': self.temp.name, 'min_channels': 1,
                                'public_url': 'http://example.test:34400',
                                'udpxy_url': 'http://example.test:4022',
                                'allowed_hosts': ['router.local'],
                                'allowed_networks': ['127.0.0.0/8']})
        self.service.snapshot = self.service.store.publish(fixture())
        self.server = make_server(self.service, '127.0.0.1', 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.temp.cleanup()

    def request(self, path, method='GET', body=None, headers=None):
        connection = http.client.HTTPConnection(*self.server.server_address)
        connection.request(method, path, body, headers or {})
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def test_legacy_exports_and_stream_redirect(self):
        self.assertIn(b'#EXTM3U', self.request('/m3u/xteve.m3u')[2])
        self.assertIn(b'<tv ', self.request('/xmltv/xteve.xml')[2])
        status, headers, _ = self.request('/stream/shct-1')
        self.assertEqual(status, 302)
        self.assertEqual(headers['Location'], 'http://example.test:4022/udp/239.1.1.1:1234')

    def test_no_private_file_or_rebinding_access(self):
        self.assertEqual(self.request('/config.json')[0], 404)
        self.assertEqual(self.request('/api/status', headers={'Host': 'attacker.invalid'})[0], 403)

    def test_explicit_legacy_hostname_alias(self):
        self.assertEqual(self.request('/m3u/xteve.m3u?group-title=legacy', headers={'Host': 'router.local:34400'})[0], 200)

    def test_frontend_assets_and_traversal(self):
        for path in ('/static/styles.css', '/static/app.js', '/static/vendor/lucide-0.468.0.min.js', '/static/assets/homecast.png'):
            self.assertEqual(self.request(path)[0], 200, path)
        self.assertEqual(self.request('/static/assets/../../server.py')[0], 404)

    def test_cross_origin_mutation_rejected(self):
        result = self.request('/api/refresh', 'POST', '{}', {'Content-Type': 'application/json', 'X-Requested-With': 'HomeCast', 'Origin': 'https://attacker.invalid'})
        self.assertEqual(result[0], 403)

    def test_status_and_guide_contract(self):
        status = json.loads(self.request('/api/status')[2])
        self.assertEqual(status['channel_count'], 1)
        self.assertNotIn('user_id', status)
        channels = json.loads(self.request('/api/channels')[2])['channels']
        self.assertEqual(channels[0]['name'], 'Demo HD')
        self.assertEqual(self.request('/api/channels/1/programmes?date=not-a-date')[0], 400)


if __name__ == '__main__':
    unittest.main()
