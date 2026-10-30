import json
import unittest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7
import hashlib

from iptv_lan import provider


class ProviderTests(unittest.TestCase):
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
