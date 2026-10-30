from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from iptv_lan.service import Service
from test_core import fixture


class ServiceTests(unittest.TestCase):
    def setUp(self):
        clock = patch('iptv_lan.service.time.time', return_value=1799999900)
        clock.start()
        self.addCleanup(clock.stop)

    def test_log_storage_failure_does_not_stick_refresh(self):
        with tempfile.TemporaryDirectory() as d:
            service = Service({'data_dir': d, 'min_channels': 1}, fetcher=lambda *_: fixture())
            with patch('iptv_lan.service.atomic_json', side_effect=OSError('disk full')):
                self.assertTrue(service.refresh())
                service.worker.join(3)
            self.assertFalse(service.running)
            self.assertTrue(service.refresh(force=True))
            service.worker.join(3)
            self.assertEqual(service.status()['state'], 'idle')

    def test_sparse_epg_never_replaces_complete_snapshot(self):
        import copy
        with tempfile.TemporaryDirectory() as d:
            complete = fixture()
            complete['channels'] = [{**complete['channels'][0], 'id': str(i)} for i in range(10)]
            complete['programmes'] = {str(i): copy.deepcopy(complete['programmes']['1']) for i in range(10)}
            partial = copy.deepcopy(complete)
            partial['programmes'] = {'0': partial['programmes']['0']}
            service = Service({'data_dir': d, 'min_channels': 1}, fetcher=lambda *_: partial)
            service.snapshot = service.store.publish(complete, now=123)
            service.refresh()
            service.worker.join(3)
            self.assertEqual(service.snapshot['updated_at'], 123)
            self.assertEqual(service.status()['state'], 'error')

    def test_due_refresh_not_lost_during_cooldown(self):
        with tempfile.TemporaryDirectory() as d:
            service = Service({'data_dir': d, 'min_channels': 1}, fetcher=lambda *_: fixture())
            service.snapshot = service.store.publish(fixture())
            service.next_run = 100
            service.last_attempt = 90
            with patch('iptv_lan.service.time.time', return_value=105):
                service.tick()
                self.assertEqual(service.next_run, 100)
            with patch('iptv_lan.service.time.time', return_value=155):
                service.tick()
                self.assertGreater(service.next_run, 155)
            service.worker.join(3)

    def test_concurrent_refresh_is_single_flight_and_failure_keeps_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            entered, release = threading.Event(), threading.Event()
            def fetch(config, progress):
                entered.set()
                release.wait(3)
                return fixture()
            service = Service({'data_dir': d, 'min_channels': 1, 'auto_refresh': False}, fetcher=fetch)
            self.assertTrue(service.refresh())
            self.assertTrue(entered.wait(1))
            self.assertFalse(service.refresh())
            release.set()
            service.worker.join(3)
            self.assertEqual(service.status()['channel_count'], 1)
            before = service.snapshot['updated_at']
            def broken(config, progress):
                raise RuntimeError('secret-from-remote-response')
            service.fetcher = broken
            self.assertTrue(service.refresh(force=True))
            service.worker.join(3)
            self.assertEqual(service.snapshot['updated_at'], before)
            self.assertNotIn('secret-from-remote-response', str(service.status()) + str(service.logs))
            self.assertEqual(service.status()['state'], 'error')

    def test_settings_are_persisted_and_validated(self):
        with tempfile.TemporaryDirectory() as d:
            service = Service({'data_dir': d, 'min_channels': 1})
            with self.assertRaises(ValueError):
                service.update_settings({'refresh_time': '25:00', 'auto_refresh': True})
            service.update_settings({'refresh_time': '06:15', 'auto_refresh': False})
            again = Service({'data_dir': d, 'min_channels': 1})
            self.assertEqual(again.settings['refresh_time'], '06:15')
            self.assertFalse(again.settings['auto_refresh'])

    def test_environment_schedule_wins_over_saved_settings(self):
        with tempfile.TemporaryDirectory() as d:
            service = Service({'data_dir': d})
            service.update_settings({'refresh_time': '07:00', 'auto_refresh': True})
            again = Service({'data_dir': d, 'refresh_time': '06:30', 'auto_refresh': False,
                             '_environment_settings': ['refresh_time', 'auto_refresh']})
            self.assertEqual(again.settings, {'refresh_time': '06:30', 'auto_refresh': False})
            self.assertEqual(again.status()['managed_settings'], ['auto_refresh', 'refresh_time'])
            with self.assertRaises(ValueError):
                again.update_settings({'refresh_time': '08:00', 'auto_refresh': False})
            self.assertEqual(again.settings['refresh_time'], '06:30')

    def test_only_explicit_environment_schedule_fields_are_locked(self):
        with tempfile.TemporaryDirectory() as d:
            service = Service({'data_dir': d, 'auto_refresh': False, '_environment_settings': ['auto_refresh']})
            service.update_settings({'refresh_time': '06:15', 'auto_refresh': False})
            self.assertEqual(service.settings['refresh_time'], '06:15')
            with self.assertRaises(ValueError):
                service.update_settings({'refresh_time': '06:15', 'auto_refresh': True})


if __name__ == '__main__':
    unittest.main()
