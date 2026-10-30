import json
import unittest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7
import hashlib
from unittest.mock import patch

from iptv_lan import provider


class ProviderTests(unittest.TestCase):
    def test_unmarked_channel_quality_is_not_assumed_sd(self):
        self.assertEqual(provider.quality_for('Demo'), '')
        self.assertEqual(provider.quality_for('Demo HD'), 'HD')
        self.assertEqual(provider.quality_for('Demo 4K'), '4K')

    def test_complete_synthetic_authentication_and_programme_flow(self):
        replies = [
            '<form action="/auth"><input name="DynamicAuthIP" value="192.0.2.9"></form>',
            '''var encrytoken='challenge'; <form name="initform" action="/iptv3a/ottauth"><input name="authenticator"></form>''',
            '''var channelArray = ['UserChannelID="1",ChannelURL="igmp://239.1.1.1:1234"']; var usertoken='fresh-token'; var epggroup='demo'; "EPGDomain=http://epg.example.test/login"''',
            '''top.document.location='http://epg.example.test/balance';''',
            '<form action="/funcportalauth.jsp"><input name="UserToken"><input name="UserID"></form>',
            "jsSetConfig('IpPort','epg.example.test'); jsSetConfig('framecode','demo'); jsSetConfig('SessionID','synthetic-session');",
            '', json.dumps({'bimsUserToken': 'synthetic-bims', 'bimsTokenExp': 1800000000}),
            json.dumps({'data': [{'mixNo': 1, 'name': 'Demo', 'code': 'demo-code', 'ID': 'demo-id'}]}),
            *[json.dumps({'data': []}) for _ in range(len(provider.CATEGORIES) - 1)],
            json.dumps({'data': [{'name': 'Demo programme', 'startTime': 1800000000000, 'endTime': 1800003600000}]}),
        ]
        calls = []
        class FakeTransport(provider.Transport):
            def request(self, url, data=None, referer=''):
                calls.append((url, data, referer))
                return replies.pop(0)
        cfg = {'user_id': 'demo@example.invalid', 'protocol_sn': 'SAMPLE-SN', 'mac': '02:00:00:00:00:01',
               'interface': 'demo0', 'auth_host': 'auth.example.test'}
        with patch.object(provider, 'Transport', FakeTransport), patch.object(provider, 'interface_ipv4', return_value='192.0.2.20'), patch.object(provider.time, 'sleep'):
            result = provider.fetch(cfg, lambda *_: None)
        self.assertEqual(calls[5][1]['UserToken'], 'fresh-token')
        self.assertEqual(calls[5][1]['UserID'], cfg['user_id'])
        self.assertEqual(result['channels'][0]['quality'], '')
        self.assertEqual(result['programmes']['1'][0]['start'], 1800000000)
        self.assertFalse(replies)

    def test_authenticator_contains_fresh_challenge_and_configured_identity(self):
        cfg = {'user_id': 'demo@example.invalid', 'protocol_sn': 'SAMPLE-SN', 'mac': '02:00:00:00:00:01'}
        encrypted = provider.authenticator('fresh-challenge', cfg, '192.0.2.20')
        dec = Cipher(algorithms.AES(hashlib.md5(b'123456').digest()), modes.ECB()).decryptor()
        raw = dec.update(bytes.fromhex(encrypted)) + dec.finalize()
        unpad = PKCS7(128).unpadder()
        body = json.loads(unpad.update(raw) + unpad.finalize())
        self.assertEqual(body['EncryToken'], 'fresh-challenge')
        self.assertEqual(body['UserID'], cfg['user_id'])
        self.assertEqual(body['IP'], '192,000,002,020')
        self.assertNotEqual(encrypted, provider.authenticator('fresh-challenge', cfg, '192.0.2.20'))

    def test_forms_use_html_parser_and_decode_entities(self):
        form = provider.pick_form('<form action="/login?a=1&amp;b=2"><input name="UserID" value="demo"></form>')
        self.assertEqual(form['action'], '/login?a=1&b=2')
        self.assertEqual(form['inputs'], {'UserID': 'demo'})

    def test_chinese_response_encoding_is_not_replaced(self):
        text = '\u65b0\u95fb\u7efc\u5408'
        self.assertEqual(provider.decode_body(text.encode('gb18030')), text)
        self.assertEqual(provider.decode_body(text.encode()), text)

    def test_channel_array_is_data_not_executed(self):
        body = '''var channelArray = ['ChannelID="opaque",UserChannelID="12",ChannelURL="igmp://239.1.1.2:1234"'];'''
        self.assertEqual(provider.parse_channels(body)[0]['UserChannelID'], '12')


if __name__ == '__main__':
    unittest.main()
