import json
from pathlib import Path
import tempfile
import unittest

from iptv_lan.config import ConfigError, load_config


def environment():
    return {'HOMECAST_USER_ID': 'fictional@etv2', 'HOMECAST_PROTOCOL_SN': 'EXAMPLE1234',
            'HOMECAST_MAC': '02:00:00:00:00:01', 'HOMECAST_BIND_ADDRESS': '192.0.2.1',
            'HOMECAST_ALLOWED_NETWORKS': '192.0.2.0/24, 127.0.0.0/8'}


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def test_environment_only_has_usable_defaults_without_config_file(self):
        config = load_config(environment())
        self.assertEqual(config['port'], 34400)
        self.assertEqual(config['public_url'], 'http://192.0.2.1:34400')
        self.assertEqual(config['udpxy_url'], 'http://192.0.2.1:4022')
        self.assertEqual(config['data_dir'], '/data')
        self.assertEqual(config['interface'], 'br-iptv')
        self.assertEqual(config['refresh_time'], '05:00')
        self.assertTrue(config['auto_refresh'])
        self.assertEqual(config['_environment_settings'], [])

    def test_environment_overrides_defaults_and_sets_subscription_origin(self):
        config = load_config({**environment(), 'HOMECAST_PORT': '34600',
                              'HOMECAST_AUTO_REFRESH': 'false',
                              'HOMECAST_PUBLIC_URL': 'http://tv.example.test:34400/',
                              'HOMECAST_ALLOWED_HOSTS': 'router.local'})
        self.assertEqual(config['port'], 34600)
        self.assertFalse(config['auto_refresh'])
        self.assertEqual(config['allowed_hosts'], ['router.local'])
        self.assertEqual(config['public_url'], 'http://tv.example.test:34400')
        self.assertEqual(config['_environment_settings'], ['auto_refresh'])

    def test_lists_and_boolean_values_are_typed(self):
        for value, expected in [('false', False), ('0', False), ('off', False), ('true', True), ('1', True)]:
            env = {**environment(), 'HOMECAST_AUTO_REFRESH': value, 'HOMECAST_ALLOWED_HOSTS': '["router.local", "tv.local"]'}
            config = load_config(env)
            self.assertIs(config['auto_refresh'], expected)
            self.assertEqual(config['allowed_hosts'], ['router.local', 'tv.local'])
        self.assertEqual(load_config({**environment(), 'HOMECAST_ALLOWED_HOSTS': ''})['allowed_hosts'], [])

    def test_malformed_values_fail_without_echoing_values(self):
        bad = {'PORT': ['0', '65536', 'true', '9' * 5000], 'AUTO_REFRESH': ['maybe'], 'REFRESH_TIME': ['25:00'],
               'MIN_CHANNELS': ['0'], 'ALLOWED_NETWORKS': ['', 'not-a-cidr'],
               'BIND_ADDRESS': ['0.0.0.0', 'not-an-address'], 'MAC': ['secret-invalid-mac'],
               'UDPXY_URL': ['ftp://example.test', 'http://user:secret@example.test', 'http://example.test/udp/a'],
               'AUTH_HOST': ['example.test/path', 'http://example.test'], 'ALLOWED_HOSTS': ['http://example.test'],
               'INTERFACE': ['bad interface'], 'DATA_DIR': ['']}
        for key, values in bad.items():
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(ConfigError) as caught:
                    load_config({**environment(), 'HOMECAST_' + key: value})
                self.assertNotIn('secret', str(caught.exception))

    def test_missing_required_identity_is_clear_and_safe(self):
        env = environment()
        env.pop('HOMECAST_USER_ID')
        with self.assertRaisesRegex(ConfigError, 'HOMECAST_USER_ID'):
            load_config(env)
        with self.assertRaises(ConfigError):
            load_config({**env, 'HOMECAST_USER_ID': ''})

    def test_unknown_environment_names_and_file_based_config_are_rejected(self):
        with self.assertRaisesRegex(ConfigError, 'HOMECAST_PRTO'):
            load_config({**environment(), 'HOMECAST_PRTO': '34500'})
        file = Path(self.temp.name) / 'config.json'
        file.write_text(json.dumps({'user_id': 'secret-file-identity'}))
        with self.assertRaisesRegex(ConfigError, 'HOMECAST_CONFIG') as caught:
            load_config({**environment(), 'HOMECAST_CONFIG': str(file)})
        self.assertNotIn('secret-file-identity', str(caught.exception))

    def test_secret_file_variables_are_not_supported(self):
        with self.assertRaisesRegex(ConfigError, 'HOMECAST_USER_ID_FILE'):
            load_config({**environment(), 'HOMECAST_USER_ID_FILE': 'not-supported'})


if __name__ == '__main__':
    unittest.main()
