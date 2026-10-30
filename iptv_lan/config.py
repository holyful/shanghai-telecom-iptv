"""Typed environment-only configuration."""

import ipaddress
import json
import os
import re
from urllib.parse import urlsplit

from .core import validate_time

DEFAULTS = {'interface': 'br-iptv', 'auth_host': '222.68.208.73:7001', 'port': 34400,
            'data_dir': '/data', 'refresh_time': '05:00', 'auto_refresh': True,
            'min_channels': 80, 'tuner_count': 4, 'allowed_hosts': []}
KEYS = set(DEFAULTS) | {'user_id', 'protocol_sn', 'mac', 'bind_address', 'public_url',
                        'udpxy_url', 'allowed_networks', 'legacy_file', 'device_id'}
INTEGER_LIMITS = {'port': (1, 65535), 'min_channels': (1, 10000), 'tuner_count': (1, 128)}


class ConfigError(ValueError):
    """Configuration errors name the setting but never include its value."""


def invalid(key, detail):
    raise ConfigError('HOMECAST_' + key.upper() + ': ' + detail)


def string(value, key):
    if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 for c in value):
        invalid(key, 'a non-empty single-line value is required')
    value = value.strip()
    if 'CHANGE_ME' in value:
        invalid(key, 'replace the example value')
    return value


def string_list(value, key):
    if isinstance(value, str):
        if value.lstrip().startswith('['):
            try:
                value = json.loads(value)
            except ValueError:
                invalid(key, 'expected a comma-separated list or JSON string array')
        else:
            value = [part.strip() for part in value.split(',')] if value.strip() else []
    if not isinstance(value, list) or any(not isinstance(v, str) or not v.strip() for v in value):
        invalid(key, 'expected a list of non-empty strings')
    return [string(v, key) for v in value]


def base_url(value, key):
    value = string(value, key)
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme in ('http', 'https') and parsed.hostname and
                 not parsed.username and not parsed.password and not parsed.query and
                 not parsed.fragment and parsed.path in ('', '/') and
                 not any(c.isspace() for c in value))
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            valid = False
    except ValueError:
        valid = False
    if not valid:
        invalid(key, 'expected an HTTP(S) origin without credentials, path or query')
    return value.rstrip('/')


def load_config(environ=None):
    env = dict(os.environ if environ is None else environ)
    names = {'HOMECAST_' + key.upper(): key for key in KEYS}
    for name in env:
        if name.startswith('HOMECAST_') and name not in names:
            raise ConfigError('Unknown configuration variable: ' + name)
    config = dict(DEFAULTS)
    managed = []
    for name, key in names.items():
        if name in env:
            config[key] = env[name]
            if key in ('refresh_time', 'auto_refresh'):
                managed.append(key)
    for key in ('user_id', 'protocol_sn', 'mac', 'bind_address', 'interface', 'auth_host', 'data_dir'):
        config[key] = string(config.get(key), key)
    for key, (minimum, maximum) in INTEGER_LIMITS.items():
        value = config[key]
        if isinstance(value, str) and re.fullmatch(r'[0-9]{1,5}', value.strip()):
            value = int(value)
        if type(value) is not int or not minimum <= value <= maximum:
            invalid(key, f'expected an integer between {minimum} and {maximum}')
        config[key] = value
    value = config['auto_refresh']
    if isinstance(value, str):
        booleans = {'true': True, '1': True, 'yes': True, 'on': True,
                    'false': False, '0': False, 'no': False, 'off': False}
        value = booleans.get(value.strip().lower())
    if type(value) is not bool:
        invalid('auto_refresh', 'expected true or false')
    config['auto_refresh'] = value
    try:
        config['refresh_time'] = validate_time(config['refresh_time'])
    except ValueError:
        invalid('refresh_time', 'expected HH:MM in Asia/Shanghai')
    if not re.fullmatch(r'[a-zA-Z0-9_.-]{1,15}', config['interface']):
        invalid('interface', 'expected a Linux network interface name')
    if not re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', config['mac']):
        invalid('mac', 'expected six colon-separated hexadecimal octets')
    config['mac'] = config['mac'].upper()
    try:
        address = ipaddress.IPv4Address(config['bind_address'])
        if address.is_unspecified or address.is_multicast:
            raise ValueError()
    except ValueError:
        invalid('bind_address', 'expected a specific local IPv4 address, not all interfaces')
    networks = string_list(config.get('allowed_networks'), 'allowed_networks')
    try:
        parsed_networks = [ipaddress.IPv4Network(n, strict=False) for n in networks]
        if not parsed_networks or any(n.prefixlen == 0 or n.is_multicast for n in parsed_networks):
            raise ValueError()
        if not any(address in n for n in parsed_networks):
            raise ValueError()
    except ValueError:
        invalid('allowed_networks', 'expected trusted IPv4 CIDRs including the listen address; /0 is not allowed')
    config['allowed_networks'] = list(dict.fromkeys(str(n) for n in parsed_networks))
    config['allowed_hosts'] = string_list(config['allowed_hosts'], 'allowed_hosts')
    if any(not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?', host) for host in config['allowed_hosts']):
        invalid('allowed_hosts', 'use hostnames without scheme, port or path')
    config['public_url'] = base_url(config.get('public_url', f'http://{address}:{config["port"]}'), 'public_url')
    config['udpxy_url'] = base_url(config.get('udpxy_url', f'http://{address}:4022'), 'udpxy_url')
    base_url('http://' + config['auth_host'], 'auth_host')
    for key in ('device_id', 'legacy_file'):
        if key in config:
            config[key] = string(config[key], key)
    config['_environment_settings'] = sorted(managed)
    return config
