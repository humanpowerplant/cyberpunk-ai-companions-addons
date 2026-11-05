"""Create a source ZIP and a Nexus publishing kit from explicit public inputs.

Runtime installers must already have passed the build's finalizer. This tool
never reads game folders, credentials or ignored developer audit/log folders.
"""
from pathlib import Path, PurePosixPath
import argparse
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def selected_source():
    value = json.loads((ROOT / '.publication-files.json').read_text(encoding='utf-8-sig'))
    if value.get('schema') != 1:
        raise ValueError('Unknown publication list')
    seen, files = set(), []
    for relative in value['files']:
        path = PurePosixPath(relative)
        source = ROOT / relative
        if path.is_absolute() or '..' in path.parts or '\\' in relative or ':' in relative or relative.casefold() in seen:
            raise ValueError('Unsafe or duplicate publication name')
        if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError('Publication source is missing or outside the source root')
        seen.add(relative.casefold())
        files.append((relative, source))
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='A new publishing-kit directory')
    args = parser.parse_args()
    output = args.output.resolve()
    if output == ROOT.resolve() or output in ROOT.resolve().parents or output.exists():
        raise ValueError('Use a new output directory, not the source root or its parent')
    outer = output.parent / (output.name + '.zip')
    if outer.exists():
        raise ValueError('Outer publishing-kit ZIP already exists')
    source_files = selected_source()
    release = json.loads((ROOT / 'releases/release-summary.json').read_text(encoding='utf-8-sig'))
    if release.get('upstreamRelease') != '0.4.6' or len(release.get('archives', [])) != 2:
        raise ValueError('Expected finalized 0.4.6 runtime installers')
    inputs = []
    for row in release['archives']:
        if PurePosixPath(row['file']).name != row['file'] or '\\' in row['file']:
            raise ValueError('Invalid installer name')
        source = ROOT / 'releases' / row['file']
        if not source.is_file() or source.stat().st_size != row['bytes']:
            raise ValueError('Finalized installer is missing or its size changed')
        inputs.append((source, row))
    output.mkdir(parents=True, exist_ok=False)
    (output / 'installers').mkdir()
    (output / 'source').mkdir()
    source_zip = output / 'source/ai-companions-addons-source-046-rc1.zip'
    with zipfile.ZipFile(source_zip, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative, source in source_files:
            archive.write(source, 'companion-addons/' + relative)
    for source, _ in inputs:
        shutil.copy2(source, output / 'installers' / source.name)
    for relative, source in source_files:
        if relative.startswith(('docs/', 'nexus/', 'media/', 'licenses/')) or relative in {'README.md','README.ja.md','README.en.md','LICENSE','THIRD_PARTY_NOTICES.md','SECURITY.md'}:
            target = output / 'project' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    manifest = {'schema': 1, 'upstreamRelease': '0.4.6', 'gameVersion': '2.5',
                'installers': release['archives'], 'sourceArchive': source_zip.relative_to(output).as_posix(),
                'sourceFiles': len(source_files), 'publishedToNexus': False, 'liveGameUpdated': False,
                'gameplayVerified': False, 'sensitiveStateRead': False}
    (output / 'KIT_MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    start = '''# Nexusアップロード準備キット

まず [公開手順](project/nexus/UPLOAD_GUIDE.ja.md) と [最終レビュー](project/docs/RELEASE_REVIEW.md) を開いてください。

- `installers/`：Nexusの各ページへ載せるインストール用ZIP2本。
- `source/`：GitHubや開発者向け追加ファイルに使えるソースZIP。
- `project/nexus/`：日本語/英語BBCode説明、概要・版・要件・タグ、許諾とAI開示。
- `project/docs/`：導入・更新・削除・プライバシー・対処・実プレイ確認表。
- `project/media/`：カバー、サムネイル、SVGとスクリーンショット案。

この外側のキット全体をVortexへ入れないでください。導入にはinstallers内の該当ZIPを使います。
本体0.4.6 Full install・ゲーム2.5用と、その依存Modが必要です。公開候補はRCで、実ゲーム/実認証の確認はチェックリストに残しています。
個人の認証、会話履歴、ゲーム音声、抽出台本、元ModのFull runtimeは含めません。Nexusへのアップロード操作自体は行っていません。
'''
    (output / 'START_HERE.ja.md').write_text(start, encoding='utf-8')
    with zipfile.ZipFile(outer, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for file in sorted(output.rglob('*')):
            if file.is_file():
                if file.is_symlink() or not file.resolve().is_relative_to(output):
                    raise ValueError('Unsafe kit output')
                method = zipfile.ZIP_STORED if file.suffix.lower() == '.zip' else zipfile.ZIP_DEFLATED
                archive.write(file, output.name + '/' + file.relative_to(output).as_posix(), compress_type=method)
    print(json.dumps({'output': str(output), 'kitZip': str(outer), 'sourceFiles': len(source_files),
                      'installers': len(inputs), 'gameStarted': False, 'liveGameWritten': False}))


if __name__ == '__main__':
    main()
