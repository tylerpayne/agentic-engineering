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
            build(output, 'tylerpayne/claude-code-plugins', 'test-revision')
            base = 'https://tylerpayne.github.io/claude-code-plugins/'
            index = json.loads((output / 'index.json').read_text())
            self.assertEqual(index['revision'], 'test-revision')
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
                for binary in plugin['binaries']:
                    subprocess.run([sys.executable, str(extracted / plugin['name'] / binary), '--help'],
                                   check=True, capture_output=True, cwd=temp)
            self.assertNotIn('{{', (output / 'index.html').read_text())
            self.assertNotIn('{{', (output / 'llms.txt').read_text())
            marketplace = json.loads((output / 'marketplace.json').read_text())
            self.assertTrue(all(p['source']['source'] == 'git-subdir' for p in marketplace['plugins']))


if __name__ == '__main__':
    unittest.main()
