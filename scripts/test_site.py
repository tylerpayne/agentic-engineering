"""Verify published downloads, index integrity, and standalone CLI dependencies."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

from build_site import ROOT, build


class SiteTest(unittest.TestCase):
    def test_downloads(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'site'
            build(output, 'tylerpayne/agentic-engineering', 'test-revision')
            base = 'https://tylerpayne.github.io/agentic-engineering/'
            index = json.loads((output / 'index.json').read_text())
            self.assertEqual(index['revision'], 'test-revision')
            plugins = {p['name']: p for p in index['plugins']}
            self.assertEqual(index['schema_version'], 2)
            expected = {'backlog': (True, True), 'later': (False, True),
                        'python': (True, False), 'plain-english': (True, False)}
            for name, flags in expected.items():
                self.assertEqual((plugins[name]['agent_invoked'], plugins[name]['user_invoked']), flags)
                self.assertNotIn('agent', plugins[name])
            page = (output / 'index.html').read_text()
            self.assertIn('href="downloads/later.tar.gz"', page)
            self.assertIn('Invoked by: Agent, User', page)
            self.assertNotIn('downloads/later.tar.gz', (output / 'llms.txt').read_text())
            manifest = json.loads((ROOT / '.claude-plugin/marketplace.json').read_text())
            self.assertEqual({p['name'] for p in index['plugins']},
                             {p['name'] for p in manifest['plugins'] if isinstance(p['source'], str)})
            for plugin in index['plugins']:
                archive = output / plugin['archive'].removeprefix(base)
                self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), plugin['sha256'])
                extracted = Path(temp) / plugin['name']
                with tarfile.open(archive) as bundle:
                    self.assertEqual(set(bundle.getnames()), {f'{plugin["name"]}/{f["path"]}' for f in plugin['files']})
                    self.assertTrue(all(f.isfile() and '..' not in Path(f.name).parts and not f.name.startswith('/') for f in bundle))
                    bundle.extractall(extracted)
                for file in plugin['files']:
                    published = output / file['url'].removeprefix(base)
                    self.assertEqual(hashlib.sha256(published.read_bytes()).hexdigest(), file['sha256'])
                    self.assertEqual(published.read_bytes(), (extracted / plugin['name'] / file['path']).read_bytes())
                if (extracted / plugin['name'] / 'pyproject.toml').exists():
                    subprocess.run(['uv', 'sync', '--locked', '--project', str(extracted / plugin['name'])],
                                   check=True, capture_output=True, cwd=temp)
                for binary in plugin['binaries']:
                    subprocess.run([sys.executable, str(extracted / plugin['name'] / binary), '--help'],
                                   check=True, capture_output=True, cwd=temp)
            self.assertNotIn('{{', (output / 'index.html').read_text())
            self.assertNotIn('{{', (output / 'llms.txt').read_text())
            marketplace = json.loads((output / 'marketplace.json').read_text())
            self.assertTrue(all(p['source']['source'] == 'git-subdir' for p in marketplace['plugins']))


if __name__ == '__main__':
    unittest.main()
