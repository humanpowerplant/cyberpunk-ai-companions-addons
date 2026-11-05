"""Release preflight guards use disposable packages, not real game files."""
from pathlib import Path
import importlib.util
import json
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SOURCE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release_finalizer', SOURCE / 'finalize_auto.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class FinalizeTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='addon-finalize-fixture-')
        self.root = Path(self.temporary.name)
        module.ROOT = self.root
        self.state = {}
        packages = []
        for feature in ['japanese','codex']:
            folder = self.root / 'build/packages' / feature
            folder.mkdir(parents=True)
            file = folder / 'notice.txt';file.write_text('fixture-only',encoding='utf-8')
            self.write('build/' + feature + '-members.json',['notice.txt'])
            self.state[feature] = {'notice.txt':[file.stat().st_size,file.stat().st_mtime_ns]}
            packages.append({'feature':feature,'package':'build/packages/'+feature,'archive':feature+'.zip','version':'fixture'})
        self.write('build/package-roots.json',packages)
        self.write('build/build-summary.json',{'buildId':'current'})
        self.report = {'allPassed':True,'buildId':'current','checkedPackageState':self.state,'scenarios':[]}
        self.write('build/functional-report.json',self.report)

    def tearDown(self):
        module.ROOT = SOURCE
        self.assertEqual(self.root.resolve().parent,Path(tempfile.gettempdir()).resolve())
        self.assertTrue(self.root.name.startswith('addon-finalize-fixture-'))
        self.temporary.cleanup()

    def write(self,relative,value):
        file=self.root/relative;file.parent.mkdir(parents=True,exist_ok=True)
        file.write_text(json.dumps(value),encoding='utf-8')

    def test_success_creates_both_explicit_packages(self):
        module.main()
        self.assertTrue((self.root/'releases/japanese.zip').is_file())
        self.assertTrue((self.root/'releases/codex.zip').is_file())

    def test_stale_build_report_is_rejected(self):
        self.report['buildId']='previous';self.write('build/functional-report.json',self.report)
        with self.assertRaisesRegex(ValueError,'current functional'):
            module.main()
        self.assertFalse((self.root/'releases').exists())

    def test_later_package_change_is_preflighted_before_any_zip(self):
        (self.root/'build/packages/codex/notice.txt').write_text('changed after checks',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'changed after functional'):
            module.main()
        self.assertFalse((self.root/'releases').exists())

    def test_failed_second_archive_preserves_both_previous_releases(self):
        destination = self.root/'releases';destination.mkdir()
        for feature in ['japanese','codex']:
            with zipfile.ZipFile(destination/(feature+'.zip'),'w') as output:
                output.writestr('previous.txt','previous usable release')
        self.write('releases/release-summary.json',{'previous':'keep until every new archive is ready'})
        before = {file.name:file.read_bytes() for file in destination.iterdir()}
        write = zipfile.ZipFile.writestr
        calls = 0
        def interrupted(output,*args,**kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('fixture: disk full while writing second archive')
            return write(output,*args,**kwargs)
        with patch.object(zipfile.ZipFile,'writestr',interrupted):
            with self.assertRaisesRegex(OSError,'disk full'):
                module.main()
        self.assertEqual({file.name:file.read_bytes() for file in destination.iterdir()},before)

if __name__=='__main__':
    unittest.main()
