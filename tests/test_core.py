import json
from pathlib import Path
import tempfile
import unittest

from iptv_lan import core


def fixture():
    return {"channels": [{"id": "1", "name": "Demo HD", "group": "Demo",
                          "quality": "HD", "multicast": "239.1.1.1:1234"}],
            "programmes": {"1": [{"title": "News & Weather", "start": 1800000000,
                                   "end": 1800003600}]}}


class SnapshotTests(unittest.TestCase):
    def test_invalid_refresh_preserves_last_good(self):
        with tempfile.TemporaryDirectory() as d:
            store = core.SnapshotStore(Path(d), min_channels=1)
            store.publish(fixture(), now=1800000000)
            with self.assertRaises(ValueError):
                store.publish({"channels": [], "programmes": {}}, now=1800000001)
            self.assertEqual(core.SnapshotStore(Path(d), min_channels=1).load()["updated_at"], 1800000000)

    def test_rejects_private_stream_and_invalid_epg(self):
        data = fixture()
        data['channels'][0]['multicast'] = '127.0.0.1:22'
        with self.assertRaises(ValueError):
            core.validate_snapshot(data, 1)
        data = fixture()
        data['programmes']['1'][0]['end'] = 1
        with self.assertRaises(ValueError):
            core.validate_snapshot(data, 1)

    def test_exports_keep_legacy_channel_ids_and_escape_xml(self):
        data = fixture()
        legacy = {"1": {"epg_id": "x-ID.3", "number": "1003", "stream_id": "oldhash"}}
        m3u = core.make_m3u(data, 'http://example.test:34400', legacy).decode()
        xml = core.make_xmltv(data, legacy).decode()
        self.assertIn('/stream/oldhash', m3u)
        self.assertIn('tvg-id="x-ID.3"', m3u)
        self.assertIn('channel="x-ID.3"', xml)
        self.assertIn('News &amp; Weather', xml)

    def test_public_channels_never_leak_authentication(self):
        data = fixture()
        data['channels'][0]['AuthInfo'] = 'SENSITIVE'
        public = core.public_channels(data, now=1800000100)
        self.assertNotIn('SENSITIVE', json.dumps(public))
        self.assertEqual(public[0]['current']['title'], 'News & Weather')

    def test_default_exports_match_pre_grouping_byte_baseline(self):
        data = fixture()
        data['channels'] = [
            dict(data['channels'][0], id='2', name='CCTV-2 HD', group='\u592e\u89c6'),
            dict(data['channels'][0], name='\u65b0\u95fb & "HD"', group='\u5730\u65b9'),
        ]
        data['programmes']['1'][0]['title'] = 'News & <Weather>'
        legacy = {'2': {'epg_id': 'x-ID.7', 'number': '1007', 'stream_id': 'oldhash'}}
        # Captured from commit 7f9022d, before the optional Jellyfin exporter.
        m3u = (
            '#EXTM3U x-tvg-url="http://example.test:34400/xmltv/xteve.xml"\n'
            '#EXTINF:-1 tvg-id="x-ID.7" tvg-name="CCTV-2 HD" tvg-chno="1007" group-title="\u592e\u89c6",CCTV-2 HD\n'
            'http://example.test:34400/stream/oldhash\n'
            '#EXTINF:-1 tvg-id="shct.1" tvg-name="\u65b0\u95fb & \'HD\'" tvg-chno="1" group-title="\u5730\u65b9",\u65b0\u95fb & \'HD\'\n'
            'http://example.test:34400/stream/shct-1\n'
        )
        xml = (
            "<?xml version='1.0' encoding='utf-8'?>\n"
            '<tv generator-info-name="HomeCast Shanghai Telecom">'
            '<channel id="x-ID.7"><display-name lang="zh">CCTV-2 HD</display-name></channel>'
            '<channel id="shct.1"><display-name lang="zh">\u65b0\u95fb &amp; "HD"</display-name></channel>'
            '<programme channel="shct.1" start="20270115160000 +0800" stop="20270115170000 +0800">'
            '<title lang="zh">News &amp; &lt;Weather&gt;</title></programme></tv>'
        )
        self.assertEqual(core.make_m3u(data, 'http://example.test:34400', legacy), m3u.encode())
        self.assertEqual(core.make_xmltv(data, legacy), xml.encode())

    def test_next_refresh_uses_shanghai_day(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        now = datetime(2026, 1, 2, 5, 0, tzinfo=ZoneInfo('Asia/Shanghai')).timestamp()
        self.assertEqual(core.next_refresh(now, '05:00'), now + 86400)


if __name__ == '__main__':
    unittest.main()
