"""Build only the publication allowlist from a relocated source checkout.

Requires normal build prerequisites (Python, Node, requirements-dev and the
separately downloaded official Full archive). No game or model starts.
The environment may later clean its temporary directory. Durable test evidence
and the child release summary are captured in build/ before returning.
"""
from pathlib import Path
import argparse
import json
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream-archive', type=Path, required=True)
    parser.add_argument('--node', default=shutil.which('node'))
    parser.add_argument('--destination', type=Path, help='A new empty source-copy directory; default OS temporary drive')
    args = parser.parse_args()
    destination = args.destination or Path(tempfile.mkdtemp(prefix='companion-addons-日本語-'))
    destination.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink() or any(destination.iterdir()):
        raise ValueError('The destination must be a new empty directory')
    rows = json.loads((ROOT / '.publication-files.json').read_text(encoding='utf-8-sig'))['files']
    for relative in rows:
        source = ROOT / relative
        if Path(relative).is_absolute() or '..' in Path(relative).parts or source.is_symlink() or not source.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError('Unsafe publication source path')
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    assert not any((destination / name).exists() for name in ['build','audit','manual_resolutions','releases'])
    run = subprocess.run([sys.executable,'-X','utf8','-B',str(destination / 'build_auto.py'),
        '--upstream-archive',str(args.upstream_archive.resolve()),'--node',args.node], cwd=destination,
        capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=240)
    (ROOT / 'build/portable-build.log').write_text(run.stdout+'\n'+run.stderr,encoding='utf-8')
    if run.returncode:
        raise RuntimeError('Relocated build failed; see build/portable-build.log')
    release = json.loads((destination / 'releases/release-summary.json').read_text(encoding='utf-8-sig'))
    functional = json.loads((destination / 'build/functional-report.json').read_text(encoding='utf-8-sig'))
    report = {'allPassed':True,'sourceFiles':len(rows),'differentDrive':ROOT.drive.lower()!=destination.drive.lower(),
              'sourceCopy':str(destination),'unicodeSourcePath':any(ord(c)>127 for c in str(destination)),
              'sourceOnlyAllowlist':True,'upstreamArchiveSuppliedByArgument':True,'modelCalls':0,'gameStarted':False,
              'childArchives':release['archives'],'childDeploymentCases':len(functional['scenarios']),
              'childMixedReleaseCases':len(functional['mixedReleaseCases']),
              'liveGameWritten':False,'archiveWideHashScan':False}
    (ROOT / 'build/portable-build.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':
    main()
