"""Generate the explicit source-publication allowlist; no game or archive access."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]

def generate():
    files = set()
    def add(path):
        file = ROOT / path
        if file.is_symlink() or not file.resolve().is_relative_to(ROOT.resolve()) or not file.is_file():
            raise ValueError('Missing or unsafe publication source: ' + str(path))
        files.add(file.relative_to(ROOT).as_posix())
    def tree(folder, extensions):
        for file in sorted((ROOT / folder).rglob('*')):
            if file.is_file() and '__pycache__' not in file.parts and file.suffix.lower() in extensions:
                add(file.relative_to(ROOT))
    for name in ['.gitignore', '.gitattributes', 'build_auto.py', 'finalize_auto.py', 'write_docs.py', 'source-overrides.json', 'requirements-dev.txt']:
        add(name)
    for file in ROOT.iterdir():
        if file.is_file() and (file.name.startswith(('README', 'LICENSE')) or file.name in ['CONTRIBUTING.md','SECURITY.md','THIRD_PARTY_NOTICES.md']):
            add(file.name)
    for owner in ['japanese', 'codex']:
        descriptor = Path('base_features') / owner / 'auto-feature.json'
        add(descriptor)
        doc = json.loads((ROOT / descriptor).read_text(encoding='utf-8-sig'))
        for row in doc['files'] + [row for rows in doc.get('combinations', {}).values() for row in rows]:
            add(Path('base_features') / owner / row['source'])
    mapping = json.loads((ROOT / 'source-overrides.json').read_text(encoding='utf-8-sig'))
    for rows in list(mapping.get('files', {}).values()) + list(mapping.get('combinations', {}).values()):
        for row in rows:
            add(row['sourceFile'])
    tree('common', {'.mjs','.lua'})
    for name in ['README.md', 'build_manifest.py', 'manifest.json']:
        add('codex_source/' + name)
    manifest = json.loads((ROOT / 'codex_source/manifest.json').read_text(encoding='utf-8-sig'))
    for row in manifest['files']:
        add('codex_source/payload/game/' + row['path'])
    tree('codex_source/tests', {'.py','.mjs'})
    tree('tests', {'.py','.mjs','.lua'})
    for name in ['render_profile.mjs','publication_files.py','publication_check.py','render_media.py','run_node_tests.mjs','package_public_kit.py']:
        if (ROOT / 'tools' / name).is_file():
            add('tools/' + name)
    for folder in ['docs', 'nexus', 'licenses']:
        tree(folder, {'.md','.txt','.json','.yml','.yaml'})
    tree('media', {'.md','.txt','.json','.png','.jpg','.jpeg','.webp','.svg'})
    if (ROOT / '.github').is_dir():
        tree('.github', {'.md','.yml','.yaml','.json'})
    files.add('.publication-files.json')
    value = {'schema': 1, 'files': sorted(files)}
    (ROOT / '.publication-files.json').write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return value

if __name__ == '__main__':
    value = generate()
    print(json.dumps({'publicationFiles': len(value['files']), 'gameWritten':False}))
