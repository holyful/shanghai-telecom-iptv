"""Shanghai Telecom protocol client. No account data is built into this module."""

from datetime import datetime
from html.parser import HTMLParser
import hashlib
import html
import json
import re
import secrets
import socket
import struct
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlsplit

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from .core import TZ

CATEGORIES = ('000406', '00040A', '000403', '000404', '000405', '000408', '000409', '000401', '00040B', '000400')


class ProviderError(RuntimeError):
    """A safe error which never embeds an account, cookie or remote response."""


class Forms(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form':
            self.current = {**attrs, 'inputs': {}}
            self.forms.append(self.current)
        elif tag == 'input' and self.current is not None:
            name = attrs.get('name') or attrs.get('id')
            if name:
                self.current['inputs'][name] = attrs.get('value') or ''

    def handle_endtag(self, tag):
        if tag == 'form':
            self.current = None


def pick_form(text, name=None):
    parser = Forms()
    parser.feed(text)
    for form in parser.forms:
        if name is None or form.get('name') == name or form.get('id') == name:
            return form
    raise ProviderError('Expected authentication form missing')


def js_string(text, name):
    match = re.search(r'\bvar\s+' + re.escape(name) + r'\s*=\s*([\'"])(.*?)\1', text, re.S)
    if not match:
        raise ProviderError('Expected authentication field missing')
    return html.unescape(match[2])


def parse_channels(text):
    match = re.search(r'\bvar\s+channelArray\s*=\s*\[(.*?)\]\s*;', text, re.S)
    if not match:
        raise ProviderError('Official channel table missing')
    rows = []
    for entry in re.findall(r"'([^']*)'", match[1]):
        fields = dict(re.findall(r'(\w+)="(.*?)"', entry))
        if fields.get('UserChannelID'):
            rows.append({k: html.unescape(v) for k, v in fields.items()})
    return rows


def authenticator(challenge, config, ip):
    fields = {'Random': f'{secrets.randbelow(100000000):08d}', 'EncryToken': challenge,
              'UserID': config['user_id'], 'SN': config['protocol_sn'],
              'IP': ','.join(f'{int(part):03d}' for part in ip.split('.')),
              'MAC': config['mac'].upper(), 'MagicCode': 'CTC',
              'UpdateTime': datetime.now(TZ).strftime('%Y%m%d%H%M%S')}
    raw = json.dumps(fields, separators=(',', ':')).encode()
    pad = PKCS7(128).padder()
    raw = pad.update(raw) + pad.finalize()
    encrypt = Cipher(algorithms.AES(hashlib.md5(b'123456').digest()), modes.ECB()).encryptor()
    return (encrypt.update(raw) + encrypt.finalize()).hex()


def decode_body(raw):
    try:
        return raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        return raw.decode('gb18030')


def interface_ipv4(interface):
    import fcntl
    if not re.fullmatch(r'[a-zA-Z0-9_.-]{1,15}', interface):
        raise ProviderError('Invalid IPTV interface')
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            result = fcntl.ioctl(sock, 0x8915, struct.pack('256s', interface.encode()))
        except OSError as exc:
            raise ProviderError('IPTV interface has no IPv4 address') from exc
    return socket.inet_ntoa(result[20:24])


class Transport:
    def __init__(self, interface, directory, deadline):
        self.interface = interface
        self.cookies = Path(directory) / 'cookies'
        self.cookies.touch(mode=0o600)
        self.deadline = deadline

    def request(self, url, data=None, referer=''):
        if time.monotonic() > self.deadline:
            raise ProviderError('Refresh exceeded its time budget')
        if urlsplit(url).scheme not in ('http', 'https'):
            raise ProviderError('Unsupported official endpoint scheme')
        args = ['curl', '--noproxy', '*', '--interface', self.interface,
                '--proto', '=http,https', '--proto-redir', '=http,https',
                '--connect-timeout', '8', '--max-time', '20', '--max-redirs', '5',
                '--max-filesize', '16777216', '--compressed', '-sS', '-L',
                '-b', str(self.cookies), '-c', str(self.cookies),
                '-A', 'webkit;Resolution(PAL,720P,1080P)',
                '-H', 'X-Requested-With: com.android.smart.terminal.ctsh.iptv',
                '-w', '\n%{http_code}']
        if referer:
            args += ['-e', referer]
        body = None
        if data is not None:
            args += ['-H', 'Content-Type: application/x-www-form-urlencoded', '--data-binary', '@-']
            body = urlencode(data).encode()
        args += [url]
        try:
            result = subprocess.run(args, input=body, capture_output=True, timeout=25)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProviderError('IPTV network request could not complete') from exc
        if result.returncode:
            raise ProviderError('IPTV network request failed; check VLAN and interface')
        raw, status = result.stdout.rsplit(b'\n', 1)
        if status != b'200':
            raise ProviderError('Official endpoint returned HTTP ' + status.decode('ascii', errors='ignore'))
        return decode_body(raw)

    def cookie(self, name, value, url):
        if not isinstance(value, (str, int)):
            raise ProviderError('Invalid session cookie type')
        value = str(value)
        if any(c in value for c in '\r\n\t'):
            raise ProviderError('Invalid session cookie')
        with self.cookies.open('a', encoding='utf-8') as f:
            f.write(f'{urlsplit(url).hostname}\tFALSE\t/\tFALSE\t0\t{name}\t{value}\n')


def group_for(name):
    if name.startswith(('CCTV', 'CGTN')):
        return '\u592e\u89c6'
    if '\u536b\u89c6' in name:
        return '\u536b\u89c6'
    if name.startswith(('SiTV', 'CHC')):
        return '\u4e13\u9898'
    return '\u5730\u65b9\u4e0e\u5176\u4ed6'


def quality_for(name):
    upper = name.upper()
    if '4K' in upper:
        return '4K'
    if 'HD' in upper or '\u9ad8\u6e05' in name:
        return 'HD'
    if upper.endswith('SD') or '\u6807\u6e05' in name:
        return 'SD'
    return ''


def fetch(config, progress):
    ip = interface_ipv4(config['interface'])
    progress('authenticating', 2)
    with tempfile.TemporaryDirectory(prefix='homecast-') as directory:
        http = Transport(config['interface'], directory, time.monotonic() + 1200)
        entry = f'http://{config["auth_host"]}/iptv3a/4kLogAuth.do?' + urlencode({
            'UserID': config['user_id'], 'Action': 'Login', 'SN': config['protocol_sn'],
            'Type': 'iptv4k', 'Mode': 'MENU.SMG-4K', 'FCCSupport': '1'})
        form = pick_form(http.request(entry))
        dynamic_ip = form['inputs'].get('DynamicAuthIP', '')
        url = urljoin(entry, form['action'])
        body = http.request(url, form['inputs'], entry)
        form = pick_form(body, 'initform')
        form['inputs']['authenticator'] = authenticator(js_string(body, 'encrytoken'), config, ip)
        ott = urljoin(url, form.get('action', '/iptv3a/ottauth'))
        body = http.request(ott, form['inputs'], url)
        channels_raw = parse_channels(body)
        token = js_string(body, 'usertoken')
        group = js_string(body, 'epggroup')
        domain = re.search(r'EPGDomain=([^"\']+)', body)
        if not domain:
            raise ProviderError('EPG domain missing')
        epg = domain[1].replace('\\/', '/')
        body = http.request(epg, {'UserID': config['user_id'], 'Action': 'Login', 'UserToken': token,
                                 'UserGroupNMB': '8888', 'EPGGroupNMB': group, 'stbid': '0',
                                 'Mode': 'MENU.SMG', 'EPGProviderDomain': '', 'DynamicAuthIP': dynamic_ip}, ott)
        balanced = re.search(r'top\.document\.location\s*=\s*([\'"])(.*?)\1', body, re.S)
        if not balanced:
            raise ProviderError('EPG redirect missing')
        url = urljoin(epg, html.unescape(balanced[2]))
        form = pick_form(http.request(url, referer=epg))
        form['inputs'].update({'UserToken': token, 'UserID': config['user_id']})
        for key, value in {'STBID': '0', 'stbinfo': '', 'prmid': '', 'stbtype': '', 'drmsupplier': ''}.items():
            form['inputs'].setdefault(key, value)
        auth_url = urljoin(url, form.get('action', 'funcportalauth.jsp'))
        body = http.request(auth_url, form['inputs'], url)
        fields = {m[1]: m[3] for m in re.findall(r'jsSetConfig\(\s*([\'"])(.*?)\1\s*,\s*([\'"])(.*?)\3', body, re.S)}
        try:
            root = f'http://{fields["IpPort"]}/iptvepg/{fields["framecode"]}'
            http.cookie('JSESSIONID', fields['SessionID'], root)
        except KeyError as exc:
            raise ProviderError('EPG session fields missing') from exc
        http.request(root + '/portal.jsp', referer=auth_url)
        bims = json.loads(http.request(root + '/service/auth/AuthByAjax.jsp?action=auth', referer=root + '/portal.jsp'))
        for name, value in {'bims_user_token': bims.get('bimsUserToken', ''), 'bims_token_exp': bims.get('bimsTokenExp', ''), 'BimsAuthenticationFlag': 'SUCCESS', 'PRE_ADVERTISEMENT_FLAG': '1'}.items():
            if value:
                http.cookie(name, value, root)

        def ajax(payload):
            result = json.loads(http.request(root + '/function/ajax/epg7getChannelByAjax.jsp', payload, root + '/portal.jsp'))
            rows = result.get('data')
            if not isinstance(rows, list):
                raise ProviderError('Unexpected EPG response')
            return rows

        progress('channels', 10)
        infos = {}
        for category in CATEGORIES:
            for row in ajax({'action': 'getChannelList', 'cateID': category, 'type': ''}):
                cid = str(row.get('mixNo', ''))
                if cid:
                    infos[cid] = row
            time.sleep(0.15)
        raw_by_id = {str(row['UserChannelID']): row for row in channels_raw}
        channels, programmes = [], {}
        for cid, info in sorted(infos.items(), key=lambda pair: int(pair[0])):
            raw = raw_by_id.get(cid, {})
            if not raw.get('ChannelURL', '').startswith('igmp://'):
                continue
            name = info['name']
            channels.append({'id': cid, 'name': name, 'group': group_for(name),
                             'quality': quality_for(name),
                             'multicast': raw['ChannelURL'].removeprefix('igmp://')})
        now = int(time.time() * 1000)
        for index, channel in enumerate(channels):
            info = infos[channel['id']]
            rows = ajax({'action': 'getChannelProg', 'code': info['code'], 'channelID': info['ID'],
                         'startTime': str(now - 86400000), 'endTime': str(now + 3 * 86400000),
                         'offset': '0', 'limit': '2000'})
            programmes[channel['id']] = [{'title': str(p['name']), 'start': int(p['startTime']) // 1000,
                                          'end': int(p['endTime']) // 1000} for p in rows]
            progress('programmes', 20 + int(75 * (index + 1) / max(1, len(channels))))
            time.sleep(0.2)
        return {'channels': channels, 'programmes': programmes}
