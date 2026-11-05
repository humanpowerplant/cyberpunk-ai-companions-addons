"""Generated fixtures only. Never opens a real credential or game directory."""
import importlib.util
from hashlib import sha256
import json
from pathlib import Path
import random
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

TOOL = Path(__file__).resolve().parents[1] / 'tools/publication_check.py'
spec = importlib.util.spec_from_file_location('publication_check', TOOL)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def invented_secret():
    # Construct on demand so this test's own source has no credential-looking value.
    rng = random.Random(71)
    alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    return 'sk' + '-proj-' + ''.join(rng.choice(alphabet) for _ in range(48))


class PublicationCheckTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='publication-fixture-')
        self.root = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)

    def put(self, name, value):
        file = self.root / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(value if isinstance(value, bytes) else value.encode('utf-8'))
        return file

    def inventory(self, names):
        self.put('.publication-files.json', json.dumps({'schema': 1, 'files': names}))

    def codes(self, report):
        return {row['code'] for row in report['findings']}

    def package(self, members):
        file = self.root / 'fixture.zip'
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(file, 'w') as archive:
                for name, value in members:
                    archive.writestr(name, value)
        return file

    def test_clean_source_placeholders_public_attribution_and_links(self):
        self.put('README.md', '[Install](docs/install.md)\n')
        self.put('docs/install.md', 'Use the install folder or an environment variable.\n')
        self.put('licenses/LICENSE.txt', 'Copyright Contributor <author@maintainer.org>\n')
        self.put('config.example.json', '{"apiKey":"YOUR_API_KEY","authorization":"Bearer <token>"}\n')
        self.put('tests/exemplar.json', '{"api_key":"REPLACE_WITH_YOUR_API_KEY","email":"user@example.com"}')
        self.put('tests/synthetic.json', '{"api_key":"fixture-not-a-real-provider-key-for-tests"}')
        self.put('docs/paths.md', 'Use ' + 'C' + ':/Users/<username>/an-install-folder or ' + 'C' + ':/Program Files/Example.\n')
        self.inventory(['README.md', 'docs/install.md', 'licenses/LICENSE.txt', 'config.example.json', 'tests/exemplar.json', 'tests/synthetic.json', 'docs/paths.md'])
        report = module.check_repository(self.root, strict_links=True)
        self.assertTrue(report['passed'], report)
        self.assertEqual(report['warnings'], 0)

    def test_real_looking_generated_key_fails_and_output_never_contains_value(self):
        secret = invented_secret()
        self.put('source.mjs', 'const token=' + json.dumps(secret) + ';\n')
        self.inventory(['source.mjs'])
        report = module.check_repository(self.root)
        self.assertFalse(report['passed'])
        self.assertIn('openai-key', self.codes(report))
        self.assertNotIn(secret, json.dumps(report))

    def test_generic_opaque_credential_detected_without_provider_prefix(self):
        value = invented_secret().split('-')[-1]
        self.put('sample.json', json.dumps({'api_key': value}))
        self.inventory(['sample.json'])
        report = module.check_repository(self.root)
        self.assertIn('credential-value', self.codes(report))
        self.assertFalse(report['passed'])

    def test_oversized_source_media_still_checks_forbidden_header(self):
        self.put('media/cover.png',b'MZ' + b'\0' * 200)
        self.inventory(['media/cover.png'])
        report = module.check_repository(self.root,max_text=64)
        self.assertFalse(report['passed'])
        self.assertIn('disguised-binary',self.codes(report))

    def test_oversized_zip_media_still_checks_forbidden_header(self):
        file = self.package([('media/cover.png',b'RIFF' + b'\0' * 4 + b'WAVE' + b'\0' * 200)])
        report = module.check_zip(file,max_text=64)
        self.assertFalse(report['passed'])
        self.assertIn('disguised-binary',self.codes(report))

    def test_inventory_excludes_private_generated_roots_and_unselected_file(self):
        self.put('source.py', 'print("portable")\n')
        self.put('build/config.json', 'not opened')
        self.put('_private/auth.json', 'not opened')
        self.put('unselected-secret.json', json.dumps({'api_key': invented_secret()}))
        self.inventory(['source.py', 'build/config.json', '_private/auth.json'])
        original = Path.read_bytes
        def guarded(path):
            self.assertEqual(path.name, 'source.py', 'only selected public source may be read')
            return original(path)
        with patch.object(Path, 'read_bytes', guarded):
            report = module.check_repository(self.root)
        self.assertTrue(report['passed'], report)
        self.assertEqual(report['checkedFiles'], 1)

    def test_selected_private_state_filename_is_rejected_without_open(self):
        self.put('config.json', 'do not read')
        self.inventory(['config.json'])
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('private state must not be read')):
            report = module.check_repository(self.root)
        self.assertIn('private-state-filename', self.codes(report))
        self.assertFalse(report['passed'])

    def test_inventory_traversal_and_case_collision_rejected(self):
        self.put('source.py', 'pass\n')
        self.inventory(['../outside.py', 'source.py', 'SOURCE.py'])
        report = module.check_repository(self.root)
        self.assertIn('unsafe-source-path', self.codes(report))
        self.assertIn('duplicate-source-path', self.codes(report))

    def test_fixed_user_workspace_path_is_detected_without_username_constants(self):
        fixed = 'Q' + ':/PersonalWorkspace/project'
        self.put('source.py', 'root=' + json.dumps(fixed) + '\n')
        self.inventory(['source.py'])
        report = module.check_repository(self.root)
        self.assertIn('fixed-absolute-path', self.codes(report))
        self.assertNotIn(fixed, json.dumps(report))

    def test_link_warnings_become_errors_only_after_explicit_freeze_flag(self):
        self.put('README.md', '[In progress](docs/later.md)\n')
        self.inventory(['README.md'])
        report = module.check_repository(self.root)
        self.assertTrue(report['passed'])
        self.assertIn('broken-relative-link', self.codes(report))
        self.assertFalse(module.check_repository(self.root, strict_links=True)['passed'])

    def test_clean_zip_text_media_license_and_dotfile(self):
        file = self.package([('README.md', 'Public release'), ('.gitignore', '/build/\n'),
                             ('config.example.json', '{"apiKey":"YOUR_API_KEY"}'),
                             ('licenses/LICENSE', 'Author <author@maintainer.org>'),
                             ('media/icon.png', b'\x89PNG\r\n\x1a\nfixture')])
        report = module.check_zip(file)
        self.assertTrue(report['passed'], report)
        self.assertEqual(report['warnings'], 0)

    def test_zip_traversal_duplicates_and_voice_rejected(self):
        file = self.package([('../escape.py', 'pass'), ('safe.lua', 'return {}'),
                             ('SAFE.lua', 'return {}'), ('voice/reference.wav', b'RIFF0000WAVEfixture')])
        report = module.check_zip(file)
        self.assertFalse(report['passed'])
        self.assertTrue({'unsafe-zip-path', 'duplicate-zip-path', 'private-or-binary-file', 'disguised-binary'} <= self.codes(report))

    def test_zip_control_characters_are_unsafe(self):
        report = module.check_zip(self.package([('hidden\nname.lua', 'return {}')]))
        self.assertIn('unsafe-zip-path', self.codes(report))

    def test_zip_symlink_extension_and_private_state_rejected(self):
        link = zipfile.ZipInfo('shortcut.lua')
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        file = self.package([(link, 'elsewhere'), ('app/something.bin', b'fixture'),
                             ('app/local-token.json', '{"token":"not-read"}')])
        report = module.check_zip(file)
        self.assertTrue({'zip-symlink', 'zip-extension', 'private-state-filename'} <= self.codes(report))

    def test_zip_file_directory_collision_rejected_in_either_order(self):
        for members in [[('folder', 'file'), ('folder/a.lua', 'return {}')],
                        [('folder/a.lua', 'return {}'), ('folder', 'file')]]:
            self.assertIn('zip-file-directory-collision', self.codes(module.check_zip(self.package(members))))

    def test_zip_generated_secret_rejected_without_value_in_json_report(self):
        secret = invented_secret()
        report = module.check_zip(self.package([('source.json', json.dumps({'token':secret}))]))
        self.assertFalse(report['passed'])
        self.assertIn('openai-key', self.codes(report))
        self.assertNotIn(secret, json.dumps(report))

    def test_cli_exit_code_and_redaction(self):
        secret = invented_secret()
        self.put('source.mjs', 'const key=' + json.dumps(secret))
        self.inventory(['source.mjs'])
        run = subprocess.run([sys.executable, str(TOOL), '--root', str(self.root), '--json'], capture_output=True, text=True)
        self.assertEqual(run.returncode, 1)
        self.assertFalse(json.loads(run.stdout)['passed'])
        self.assertNotIn(secret, run.stdout + run.stderr)

    def restore_package(self, source, *, target=None, change=None):
        data = source.encode('utf-8')
        digest = sha256(data).hexdigest()
        manifest = {'version':1,'product':'AI-NPC-Cyberpunk-Mod','package':'scripts-code',
                    'release':'0.4.6','game':'2.5','commit':module.RESTORE_COMMIT,
                    'files':[{'path':'bridge/convai-bridge.mjs','size':len(data),'sha256':digest}]}
        if change:
            change(manifest)
        file = self.package([(module.RESTORE_CODE_ROOT + 'code.json',json.dumps(manifest)),
                             (target or module.RESTORE_SOURCE,data)])
        return file, digest

    def test_only_known_original_digest_metadata_and_exact_fallback_get_warning(self):
        source = module.original_restore_line() + '\nexport const fixture=true;\n'
        file, digest = self.restore_package(source)
        # Arbitrary self-consistent metadata alone cannot claim official origin.
        self.assertFalse(module.check_zip(file)['passed'])
        with patch.object(module,'RESTORE_SOURCE_SHA256',digest):
            report = module.check_zip(file)
        self.assertTrue(report['passed'],report)
        self.assertIn('verified-upstream-restore-fallback',self.codes(report))
        self.assertEqual(report['warnings'],1)

    def test_restore_exception_requires_matching_manifest_release_hash_and_size(self):
        source = module.original_restore_line() + '\n'
        for change in [lambda j:j.update(release='0.4.5'),
                       lambda j:j['files'][0].update(sha256='0' * 64),
                       lambda j:j['files'][0].update(size=1),
                       lambda j:j.update(commit='not-the-reviewed-release')]:
            file,digest=self.restore_package(source,change=change)
            with patch.object(module,'RESTORE_SOURCE_SHA256',digest):
                report=module.check_zip(file)
            self.assertFalse(report['passed'])
            self.assertNotIn('verified-upstream-restore-fallback',self.codes(report))

    def test_restore_exception_rejects_other_path_drive_user_and_environment(self):
        original=module.original_restore_line()
        cases=[
            (original,module.RESTORE_CODE_ROOT+'app/bridge/other.mjs'),
            (original.replace(chr(69)+':',chr(68)+':'),None),
            (original.replace('CYBERPUNK_CONVAI_GAME','OTHER_ENVIRONMENT'),None),
            ("const game = process.env.CYBERPUNK_CONVAI_GAME || '" + chr(67) + ':/Users/' + 'private-fixture/profile' + "';",None),
        ]
        for source,target in cases:
            file,digest=self.restore_package(source+'\n',target=target)
            with patch.object(module,'RESTORE_SOURCE_SHA256',digest):
                report=module.check_zip(file)
            self.assertFalse(report['passed'])
            self.assertIn('fixed-absolute-path',self.codes(report))
            self.assertNotIn('verified-upstream-restore-fallback',self.codes(report))

    def test_restore_classification_never_suppresses_other_secret_findings(self):
        secret=invented_secret()
        source=module.original_restore_line()+'\nconst key='+json.dumps(secret)+';\n'
        file,digest=self.restore_package(source)
        with patch.object(module,'RESTORE_SOURCE_SHA256',digest):
            report=module.check_zip(file)
        self.assertFalse(report['passed'])
        self.assertIn('verified-upstream-restore-fallback',self.codes(report))
        self.assertIn('openai-key',self.codes(report))
        self.assertNotIn(secret,json.dumps(report))


if __name__ == '__main__':
    unittest.main()
