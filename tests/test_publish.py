import base64
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('publish', ROOT / 'scripts/publish.py')
publish = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publish)

FAKE_GH_AXI = '''#!/usr/bin/env python3
import base64, json, os, sys
path = sys.argv[2]
releases = json.load(open(os.environ['FAKE_RELEASES']))
if '/releases/tags/' in path:
    sys.exit(1)
page = int(path.split('&page=')[1])
body = releases[(page - 1) * 100:page * 100]
print('  body: "' + base64.b64encode(json.dumps(body).encode()).decode() + '"')
'''


class FindReleaseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        tool = Path(self.tmp.name) / 'gh-axi'
        tool.write_text(FAKE_GH_AXI)
        tool.chmod(tool.stat().st_mode | stat.S_IEXEC)
        self.releases = Path(self.tmp.name) / 'releases.json'
        old = {key: os.environ.get(key) for key in ('PATH', 'FAKE_RELEASES')}
        os.environ['PATH'] = self.tmp.name + os.pathsep + old['PATH']
        os.environ['FAKE_RELEASES'] = str(self.releases)
        self.addCleanup(lambda: [os.environ.__setitem__(k, v) if v is not None else os.environ.pop(k, None)
                                 for k, v in old.items()])

    def write(self, releases):
        self.releases.write_text(json.dumps(releases))

    def test_finds_a_draft_release(self):
        self.write([{'tag_name': 'setup-v1.0.0', 'draft': True, 'assets': []}])
        self.assertTrue(publish.find_release('o/r', 'setup-v1.0.0')['draft'])

    def test_finds_release_beyond_the_first_page(self):
        others = [{'tag_name': f'setup-v0.0.{i}', 'draft': False} for i in range(100)]
        self.write(others + [{'tag_name': 'setup-v1.0.0', 'draft': True}])
        self.assertEqual(publish.find_release('o/r', 'setup-v1.0.0')['tag_name'], 'setup-v1.0.0')

    def test_refuses_missing_or_ambiguous_release(self):
        self.write([{'tag_name': 'setup-v1.0.1', 'draft': True}])
        with self.assertRaises(ValueError):
            publish.find_release('o/r', 'setup-v1.0.0')
        self.write([{'tag_name': 'setup-v1.0.0', 'draft': True}, {'tag_name': 'setup-v1.0.0', 'draft': False}])
        with self.assertRaises(ValueError):
            publish.find_release('o/r', 'setup-v1.0.0')


if __name__ == '__main__':
    unittest.main()
