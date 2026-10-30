"""Single-flight refresh lifecycle, scheduler and persistent status."""

import json
from pathlib import Path
import threading
import time

from . import __version__
from .core import SnapshotStore, atomic_json, next_refresh, validate_snapshot, validate_time
from .provider import ProviderError, fetch


class Service:
    def __init__(self, config, fetcher=fetch):
        self.config = config
        self.directory = Path(config.get('data_dir', '/data'))
        self.store = SnapshotStore(self.directory, config.get('min_channels', 80))
        self.snapshot = self.store.load()
        self.settings = {'refresh_time': config.get('refresh_time', '05:00'),
                         'auto_refresh': config.get('auto_refresh', True)}
        if (self.directory / 'settings.json').exists():
            self.settings.update(json.loads((self.directory / 'settings.json').read_text()))
        self.managed_settings = sorted(key for key in config.get('_environment_settings', [])
                                       if key in ('refresh_time', 'auto_refresh'))
        self.settings.update({key: config[key] for key in self.managed_settings})
        self.legacy = {}
        if config.get('legacy_file') and Path(config['legacy_file']).exists():
            self.legacy = json.loads(Path(config['legacy_file']).read_text())
        self.fetcher = fetcher
        self.lock = threading.RLock()
        self.worker = None
        self.running = False
        self.stage = 'idle'
        self.progress = 0
        self.last_error = None
        self.last_attempt = None
        self.storage_warning = None
        self.logs = []
        state = self.directory / 'status.json'
        if state.exists():
            saved = json.loads(state.read_text(encoding='utf-8'))
            self.logs = saved.get('logs', [])[-100:]
            self.last_error = saved.get('last_error')
            self.last_attempt = saved.get('last_attempt')
        self.next_run = next_refresh(time.time(), self.settings['refresh_time'])

    def log(self, message, level='info'):
        with self.lock:
            self.logs.append({'time': time.time(), 'level': level, 'message': message})
            self.logs = self.logs[-100:]
            try:
                atomic_json(self.directory / 'status.json', {'logs': self.logs, 'last_error': self.last_error, 'last_attempt': self.last_attempt})
                self.storage_warning = None
            except OSError:
                self.storage_warning = 'Status could not be saved; check data volume space and permissions'
                self.logs.append({'time': time.time(), 'level': 'error', 'message': self.storage_warning})
                self.logs = self.logs[-100:]

    def status(self):
        with self.lock:
            data = self.snapshot
            programmes = [p for ps in data['programmes'].values() for p in ps]
            return {'state': 'refreshing' if self.running else ('error' if self.last_error else 'idle'),
                    'stage': self.stage, 'progress': self.progress, 'last_success': data.get('updated_at'),
                    'last_attempt': self.last_attempt, 'last_error': self.last_error,
                    'storage_warning': self.storage_warning,
                    'next_refresh': self.next_run if self.settings['auto_refresh'] else None,
                    'channel_count': len(data['channels']), 'programme_count': len(programmes),
                    'coverage_end': max((p['end'] for p in programmes), default=None),
                    'cache_available': bool(data['channels']), 'source': 'Shanghai Telecom',
                    'version': __version__, 'timezone': 'Asia/Shanghai',
                    'managed_settings': self.managed_settings, **self.settings}

    def update_settings(self, settings):
        value = {'refresh_time': validate_time(settings.get('refresh_time')),
                 'auto_refresh': settings.get('auto_refresh')}
        if not isinstance(value['auto_refresh'], bool):
            raise ValueError('auto_refresh must be boolean')
        with self.lock:
            if any(value[key] != self.config[key] for key in self.managed_settings):
                raise ValueError('Schedule setting is managed by the container environment')
            atomic_json(self.directory / 'settings.json', value)
            self.settings = value
            self.next_run = next_refresh(time.time(), value['refresh_time'])
            self.log('Refresh schedule updated')
        return value

    def refresh(self, force=False):
        with self.lock:
            if self.running or (not force and self.last_attempt and time.time() - self.last_attempt < 60):
                return False
            self.running = True
            self.last_attempt = time.time()
            self.last_error = None
            self.progress = 0
            self.stage = 'starting'
            self.log('Official refresh started')
            self.worker = threading.Thread(target=self._refresh, daemon=True)
            self.worker.start()
            return True

    def _refresh(self):
        def progress(stage, value):
            with self.lock:
                self.stage, self.progress = stage, value
        try:
            result = self.fetcher(self.config, progress)
            validate_snapshot(result, self.store.min_channels)
            old_count = len(self.snapshot['channels'])
            if old_count and len(result['channels']) < old_count * 0.75:
                raise ProviderError('Channel count dropped over 25%; previous snapshot retained')
            now = time.time()
            def coverage(snapshot):
                rows = snapshot['programmes'].values()
                return (sum(any(p['end'] > now for p in ps) for ps in rows),
                        sum(p['end'] > now and p['start'] < now + 86400 for ps in rows for p in ps))
            old_covered, old_day = coverage(self.snapshot)
            covered, day = coverage(result)
            end = max(p['end'] for ps in result['programmes'].values() for p in ps)
            if covered < max(len(result['channels']) * 0.5, old_covered * 0.75) or day < old_day * 0.5 or end < now + 3600:
                raise ProviderError('Programme coverage incomplete; previous snapshot retained')
            with self.lock:
                progress('publishing', 98)
                self.snapshot = self.store.publish(result)
                self.progress = 100
                self.stage = 'idle'
                self.log('Published %d channels and %d programmes' % (len(result['channels']), sum(map(len, result['programmes'].values()))))
        except Exception as exc:
            with self.lock:
                self.last_error = str(exc) if isinstance(exc, ProviderError) else 'Refresh failed validation or processing; previous snapshot retained'
                self.stage = 'error'
                self.log(self.last_error, 'error')
        finally:
            with self.lock:
                self.running = False

    def tick(self):
        with self.lock:
            if self.settings['auto_refresh'] and time.time() >= self.next_run:
                if self.refresh():
                    self.next_run = next_refresh(time.time(), self.settings['refresh_time'])

    def scheduler(self, stop):
        if self.settings['auto_refresh'] and (not self.snapshot['channels'] or time.time() - (self.snapshot.get('updated_at') or 0) > 86400):
            self.refresh()
        while not stop.wait(15):
            self.tick()
