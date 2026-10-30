"""Validated, atomic guide snapshots and compatibility exports."""

from datetime import datetime, timedelta
import ipaddress
import json
import os
from pathlib import Path
import re
import time
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Asia/Shanghai')


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, separators=(',', ':'))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def validate_snapshot(data, min_channels=1):
    channels = data.get('channels', [])
    if len(channels) < min_channels:
        raise ValueError('Too few channels; previous snapshot retained')
    ids = set()
    for channel in channels:
        cid = str(channel['id'])
        if not re.fullmatch(r'\d{1,8}', cid) or cid in ids:
            raise ValueError('Invalid or duplicate channel identifier')
        ids.add(cid)
        host, port = channel['multicast'].rsplit(':', 1)
        if not ipaddress.IPv4Address(host).is_multicast or not 1 <= int(port) <= 65535:
            raise ValueError('Invalid multicast destination')
        if not channel.get('name') or '\ufffd' in channel['name']:
            raise ValueError('Invalid channel name encoding')
    count = 0
    for cid, programmes in data.get('programmes', {}).items():
        if cid not in ids:
            raise ValueError('Programme refers to an unknown channel')
        for p in programmes:
            if not p.get('title') or '\ufffd' in p['title'] or not 0 < p['start'] < p['end']:
                raise ValueError('Invalid programme')
            count += 1
    if count == 0:
        raise ValueError('Empty programme guide; previous snapshot retained')


class SnapshotStore:
    def __init__(self, directory, min_channels=80):
        self.directory = Path(directory)
        self.min_channels = min_channels
        self.path = self.directory / 'snapshot.json'

    def load(self):
        if self.path.exists():
            return json.loads(self.path.read_text(encoding='utf-8'))
        return {'channels': [], 'programmes': {}, 'updated_at': None}

    def publish(self, data, now=None):
        validate_snapshot(data, self.min_channels)
        # Store only the fields the service needs, never raw authentication responses.
        clean = {
            'channels': [{k: c[k] for k in ('id', 'name', 'group', 'quality', 'multicast')} for c in data['channels']],
            'programmes': {cid: sorted([{'title': p['title'], 'start': p['start'], 'end': p['end']} for p in ps], key=lambda p: p['start']) for cid, ps in data['programmes'].items()},
            'updated_at': now if now is not None else time.time(),
        }
        if self.path.exists():
            atomic_json(self.directory / 'previous.json', self.load())
        atomic_json(self.path, clean)
        return clean


def channel_identity(cid, legacy):
    old = legacy.get(cid, {})
    return {'epg_id': old.get('epg_id', 'shct.' + cid),
            'stream_id': old.get('stream_id', 'shct-' + cid),
            'number': str(old.get('number', cid))}


def attribute(value):
    return str(value).replace('"', "'").replace('\r', ' ').replace('\n', ' ')


def make_m3u(data, base_url, legacy):
    lines = [f'#EXTM3U x-tvg-url="{base_url}/xmltv/xteve.xml"']
    for c in data['channels']:
        ident = channel_identity(c['id'], legacy)
        lines.append(f'#EXTINF:-1 tvg-id="{attribute(ident["epg_id"])}" tvg-name="{attribute(c["name"])}" tvg-chno="{attribute(ident["number"])}" group-title="{attribute(c["group"])}",{attribute(c["name"])}')
        lines.append(f'{base_url}/stream/{ident["stream_id"]}')
    return ('\n'.join(lines) + '\n').encode('utf-8')


def make_xmltv(data, legacy):
    root = ET.Element('tv', {'generator-info-name': 'HomeCast Shanghai Telecom'})
    for c in data['channels']:
        cid = channel_identity(c['id'], legacy)['epg_id']
        node = ET.SubElement(root, 'channel', {'id': cid})
        ET.SubElement(node, 'display-name', {'lang': 'zh'}).text = c['name']
        for p in data['programmes'].get(c['id'], []):
            attrs = {'channel': cid}
            for key in ('start', 'end'):
                attrs['stop' if key == 'end' else key] = datetime.fromtimestamp(p[key], TZ).strftime('%Y%m%d%H%M%S %z')
            programme = ET.SubElement(root, 'programme', attrs)
            ET.SubElement(programme, 'title', {'lang': 'zh'}).text = p['title']
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def public_channels(data, now=None):
    now = time.time() if now is None else now
    result = []
    for c in data['channels']:
        programmes = data['programmes'].get(c['id'], [])
        row = {k: c[k] for k in ('id', 'name', 'group', 'quality')}
        row['programme_count'] = len(programmes)
        row['current'] = next((p for p in programmes if p['start'] <= now < p['end']), None)
        row['next'] = next((p for p in programmes if p['start'] > now), None)
        result.append(row)
    return result


def validate_time(value):
    if not isinstance(value, str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', value):
        raise ValueError('Expected HH:MM in Asia/Shanghai')
    return value


def next_refresh(now, refresh_time):
    hour, minute = map(int, validate_time(refresh_time).split(':'))
    dt = datetime.fromtimestamp(now, TZ)
    target = dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target.timestamp() <= now:
        target += timedelta(days=1)
    return target.timestamp()
