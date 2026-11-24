"""Exercise the real PHP endpoint with isolated private storage."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


class CampaignRedirectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        php = shutil.which('php') or '/opt/homebrew/bin/php'
        cls.temp = tempfile.TemporaryDirectory()
        cls.private = Path(cls.temp.name) / 'private'
        cls.private.mkdir()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        cls.base = f'http://127.0.0.1:{port}/go.php'
        root = Path(__file__).resolve().parents[1] / 'web'
        cls.server = subprocess.Popen([php, '-S', f'127.0.0.1:{port}', '-t', str(root)],
            env={**os.environ, 'AEMAX_METRICS_DIR':str(cls.private)},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.client = build_opener(NoRedirect)
        for _ in range(50):
            try:
                cls.request('to=app-store&test=1')
                break
            except URLError:
                time.sleep(.1)
        else:
            raise RuntimeError('PHP test server did not start')

    @classmethod
    def tearDownClass(cls):
        cls.server.terminate()
        cls.server.wait(timeout=5)
        cls.temp.cleanup()

    def setUp(self):
        (self.private / 'counts.json').unlink(missing_ok=True)

    @classmethod
    def request(cls, query, headers=None, method='GET'):
        try:
            return cls.client.open(Request(cls.base+'?'+query, headers=headers or {}, method=method), timeout=5)
        except HTTPError as response:
            return response

    def test_allowlist_prevents_external_redirect_and_array_parameters(self):
        for query in ['to=https://evil.example', 'to[]=app-store', 'to=%0d%0aLocation:evil']:
            response = self.request(query)
            self.assertEqual(response.code, 400)
            self.assertIsNone(response.headers.get('Location'))
        response = self.request('to=app-store&source[]=secret&campaign=secret&placement=secret')
        self.assertEqual(response.code, 302)
        self.assertEqual(response.headers['Location'], 'https://apps.apple.com/app/audioenhancermax/id6791591803?pt=118694520&ct=aemax-202611-unknown&mt=8')
        data = json.loads((self.private/'counts.json').read_text())
        self.assertEqual(next(iter(next(iter(data['days'].values())))), 'unknown|launch-2026-11|app-store|other')
        self.assertNotIn('secret', json.dumps(data))

    def test_aggregate_count_and_private_file(self):
        for _ in range(2):
            response = self.request('to=dmg&source=linkedin&placement=post', {'User-Agent':'Human Test', 'X-Forwarded-For':'198.51.100.5', 'Referer':'https://private.example/secret'})
            self.assertEqual(response.headers['X-AEMAX-Measurement'], 'recorded')
        raw = (self.private/'counts.json').read_text()
        data = json.loads(raw)
        self.assertEqual(next(iter(data['days'].values()))['linkedin|launch-2026-11|dmg|post'], 2)
        for forbidden in ['198.51.100.5','Human Test','private.example','secret']:
            self.assertNotIn(forbidden, raw)
        self.assertEqual((self.private/'counts.json').stat().st_mode & 0o777, 0o600)

    def test_opt_out_bots_prefetch_and_test_requests_are_not_counted(self):
        cases = [({'DNT':'1'},'opt-out'),({'Sec-GPC':'1'},'opt-out'),({'User-Agent':'Slackbot'},'automated'),({'Sec-Purpose':'prefetch'},'automated')]
        for headers, expected in cases:
            response = self.request('to=app-store', headers)
            self.assertEqual(response.headers['X-AEMAX-Measurement'], expected)
        for query, method in [('to=app-store&test=1','GET'),('to=app-store','HEAD')]:
            self.assertEqual(self.request(query, method=method).headers['X-AEMAX-Measurement'], 'test')
        self.assertFalse((self.private/'counts.json').exists())
        self.assertEqual(self.request('to=app-store', method='POST').code, 405)

    def test_retention_and_storage_failure_preserve_navigation(self):
        file = self.private/'counts.json'
        file.write_text(json.dumps({'schema_version':1,'metric':'navigation_requests','timezone':'UTC','days':{'2000-01-01':{'old':9}}}))
        self.request('to=download&source=gearspace&campaign=field-test-2026-11')
        self.assertNotIn('2000-01-01', json.loads(file.read_text())['days'])
        file.write_text('corrupt data preserved')
        response = self.request('to=feedback&source=gearspace')
        self.assertEqual(response.code, 302)
        self.assertEqual(response.headers['X-AEMAX-Measurement'], 'unavailable')
        self.assertIn('utm_source=gearspace', response.headers['Location'])
        self.assertEqual(file.read_text(), 'corrupt data preserved')


if __name__ == '__main__':
    unittest.main()
