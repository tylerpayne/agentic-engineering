#!/usr/bin/env python3
"""Build the Pages catalog from the repository's marketplace (stdlib only)."""

import argparse
import html
import json
import hashlib
import shutil
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(output, repository, ref):
    marketplace = json.loads((ROOT / '.claude-plugin/marketplace.json').read_text())
    metadata = json.loads((ROOT / 'site/plugins.json').read_text())
    cards = []
    owner, repo = repository.split('/')
    url = f'https://{owner}.github.io/' + ('' if repo.lower() == f'{owner}.github.io'.lower() else f'{repo}/')
    output.mkdir(parents=True, exist_ok=True)
    (output / 'downloads').mkdir(exist_ok=True)
    index = {'schema_version': 1, 'revision': ref, 'plugins': []}
    for plugin in marketplace['plugins']:
        details = metadata[plugin['name']]
        agent = details['agent']
        if type(agent['download']) is not bool or not agent['reason'].strip():
            raise ValueError(f'Invalid agent metadata: {plugin["name"]}')
        source = plugin['source']
        if isinstance(source, str):
            path = (ROOT / source).resolve()
            if not source.startswith('./') or not path.is_relative_to(ROOT / 'plugins'):
                raise ValueError(f'Invalid local plugin source: {source}')
            manifest = json.loads((path / '.claude-plugin/plugin.json').read_text())
            if manifest['name'] != plugin['name']:
                raise ValueError(f'Plugin name mismatch: {source}')
            files = []
            for file in sorted(path.rglob('*')):
                relative = file.relative_to(path)
                if not file.is_file() or file.is_symlink() or '__pycache__' in relative.parts:
                    continue
                if relative.parts[0] not in {'skills', 'bin', 'lib', 'commands', 'hooks', 'README.md',
                                             'pyproject.toml', 'uv.lock', '.python-version',
                                             '.pre-commit-config.yaml', 'tests'}:
                    continue
                if file.suffix in {'.pyc', '.db'} or not file.resolve().is_relative_to(path):
                    continue
                target = output / 'plugins' / plugin['name'] / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(file, target)
                target.chmod(0o755 if relative.parts[0] == 'bin' else 0o644)
                files.append({'path': relative.as_posix(), 'url': url + target.relative_to(output).as_posix(),
                              'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
            license_path = output / 'plugins' / plugin['name'] / 'LICENSE'
            shutil.copyfile(ROOT / 'LICENSE', license_path)
            files.append({'path': 'LICENSE', 'url': url + license_path.relative_to(output).as_posix(),
                          'sha256': hashlib.sha256(license_path.read_bytes()).hexdigest()})
            archive = output / 'downloads' / f'{plugin["name"]}.tar.gz'
            with tarfile.open(archive, 'w:gz') as bundle:
                for entry in files:
                    bundle.add(output / 'plugins' / plugin['name'] / entry['path'],
                               arcname=f'{plugin["name"]}/{entry["path"]}')
            index['plugins'].append({'name': plugin['name'], 'description': details['description'],
                                     'agent': agent,
                                     'archive': url + archive.relative_to(output).as_posix(),
                                     'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                                     'skills': [f['path'] for f in files if f['path'].endswith('/SKILL.md')],
                                     'binaries': [f['path'] for f in files if f['path'].startswith('bin/')],
                                     'files': files})
            plugin['source'] = {
                'source': 'git-subdir',
                'url': f'https://github.com/{repository}.git',
                'path': path.relative_to(ROOT).as_posix(),
                'ref': ref,
            }
        name = html.escape(plugin['name'])
        link = html.escape(plugin.get('homepage', f'https://github.com/{repository}'), quote=True)
        download = f'<a href="downloads/{name}.tar.gz">Download</a> · ' if agent['download'] else ''
        audience = 'Agent download' if agent['download'] else 'Claude Code · user-facing'
        cards.append(f'<article><h2>{name}</h2><p>{html.escape(details["description"])}</p>'
                     f'<p class="audience">{audience}</p><p>{html.escape(agent["reason"])}</p>'
                     f'<p>{download}<a href="{link}">Documentation</a></p></article>')
    template = (ROOT / 'site/index.html').read_text()
    page = template.replace('{{CARDS}}', '\n'.join(cards)).replace('{{MARKETPLACE_URL}}', html.escape(url + 'marketplace.json'))
    page = page.replace('{{REPOSITORY_URL}}', html.escape(f'https://github.com/{repository}'))
    output.mkdir(parents=True, exist_ok=True)
    (output / 'index.html').write_text(page)
    catalog = json.dumps(marketplace, indent=2) + '\n'
    (output / 'marketplace.json').write_text(catalog)
    (output / '.claude-plugin').mkdir(exist_ok=True)
    (output / '.claude-plugin/marketplace.json').write_text(catalog)
    (output / '.nojekyll').touch()
    (output / 'index.json').write_text(json.dumps(index, indent=2) + '\n')
    guide = (ROOT / 'site/llms.txt').read_text().replace('{{BASE_URL}}', url)
    for entry in index['plugins']:
        guide += f'\n## {entry["name"]}\n\n{entry["description"]}\n'
        guide += f'Agent download: {str(entry["agent"]["download"]).lower()}\n{entry["agent"]["reason"]}\n'
        if not entry['agent']['download']:
            continue
        guide += f'Bundle: {entry["archive"]}\n'
        guide += 'Skills: ' + (', '.join(entry['skills']) or 'None; CLI utility with README and command documentation.') + '\n'
        guide += 'Binaries: ' + (', '.join(entry['binaries']) or 'None.') + '\n'
        for file in entry['files']:
            if file['path'].endswith('/SKILL.md') or file['path'] == 'README.md':
                guide += f'- {file["url"]}\n'
    (output / 'llms.txt').write_text(guide)
    print(f'Built {len(cards)} plugins in {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / '_site')
    parser.add_argument('--repository', default='tylerpayne/agentic-engineering')
    parser.add_argument('--ref', default='main')
    args = parser.parse_args()
    build(args.output, args.repository, args.ref)
