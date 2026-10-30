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

    def test_subscription_base_is_configured_not_the_browser_host(self):
        status, _, body = self.request('/api/status')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['public_url'], 'http://example.test:34400')

    def test_no_private_file_or_rebinding_access(self):
        self.assertEqual(self.request('/config.json')[0], 404)
        self.assertEqual(self.request('/api/status', headers={'Host': 'attacker.invalid'})[0], 403)

    def test_jellyfin_exports_are_separate_and_match_guide_ids(self):
        import xml.etree.ElementTree as ET
        original = self.request('/m3u/xteve.m3u')[2]
        status, _, body = self.request('/m3u/jellyfin.m3u')
        self.assertEqual(status, 200)
        self.assertIn(b'[Demo] Demo HD', body)
        self.assertIn(b'/xmltv/jellyfin.xml', body)
        self.assertIn(b'tvg-id="shct.1"', body)
        self.assertIn(b'/stream/shct-1', body)
        status, _, xml = self.request('/xmltv/jellyfin.xml')
        self.assertEqual(status, 200)
        root = ET.fromstring(xml)
        self.assertEqual(root.find('channel').attrib['id'], 'shct.1')
        self.assertEqual(root.find('channel/display-name').text, '[Demo] Demo HD')
        self.assertEqual(root.find('programme').attrib['channel'], 'shct.1')
        self.assertEqual(self.request('/m3u/xteve.m3u')[2], original)

    def test_jellyfin_exports_require_validated_snapshot(self):
        self.service.snapshot = {'channels': [], 'programmes': {}}
        for path in ('/m3u/jellyfin.m3u', '/xmltv/jellyfin.xml'):
            self.assertEqual(self.request(path)[0], 503)

    def test_jellyfin_group_sort_keeps_all_channels_and_legacy_identity(self):
        import re
        data = fixture()
        data['channels'] = [
            dict(data['channels'][0], id=cid, name=name, group=group)
            for cid, name, group in (
                ('90', 'Local', '\u5730\u65b9\u4e0e\u5176\u4ed6'),
                ('10', 'CCTV-10', '\u592e\u89c6'),
                ('80', 'Special', '\u4e13\u9898'),
                ('2', 'CCTV-2', '\u592e\u89c6'),
                ('40', 'Satellite', '\u536b\u89c6'),
                ('1', 'Other', 'Unknown'),
            )]
        self.service.snapshot = data
        self.service.legacy = {'2': {'epg_id': 'x-ID.7', 'number': '1007', 'stream_id': 'oldhash'}}
        original = self.request('/m3u/xteve.m3u')[2]
        status, _, body = self.request('/m3u/jellyfin.m3u')
        self.assertEqual(status, 200)
        text = body.decode()
        ids = re.findall(r'tvg-id="([^"]+)"', text)
        self.assertEqual(ids, ['x-ID.7', 'shct.10', 'shct.40', 'shct.80', 'shct.90', 'shct.1'])
        self.assertEqual(re.findall(r'tvg-chno="([^"]+)"', text), ['1', '2', '3', '4', '5', '6'])
        self.assertIn('/stream/oldhash', text)
        self.assertEqual(len(set(ids)), len(data['channels']))
        self.assertEqual(self.request('/m3u/xteve.m3u')[2], original)
        data['channels'].reverse()
        self.assertEqual(self.request('/m3u/jellyfin.m3u')[2], body)

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
