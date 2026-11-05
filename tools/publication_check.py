"""Review explicitly public source files and release ZIPs without reading secrets.

The default source inventory is .publication-files.json (schema 1, files array),
or this repository's own Git tracked files. No recursive all-disk/source scan is
performed. Reports contain rule names and locations, never matched secret text.
This is a bounded heuristic review, not a guarantee of absence of secrets.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
from urllib.parse import unquote
import zipfile


EXCLUDED = {'.git', '.venv', '.pytest_cache', '__pycache__', 'node_modules',
            'build', 'audit', 'releases', '_private', 'manual_resolutions', 'upstream-local'}
TEXT_EXTENSIONS = {'.py', '.mjs', '.js', '.cjs', '.lua', '.ps1', '.psm1', '.psd1',
                   '.cmd', '.bat', '.vbs', '.json', '.jsonl', '.md', '.txt', '.rst',
                   '.yaml', '.yml', '.toml', '.ini', '.cfg', '.csv', '.tsv', '.svg',
                   '.html', '.css', '.xml', '.sha256', '.example', '.gitignore',
                   '.gitattributes', '.editorconfig'}
ALLOWED_ZIP_EXTENSIONS = TEXT_EXTENSIONS | {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.ico'}
FORBIDDEN_EXTENSIONS = {'.wem', '.wav', '.mp3', '.ogg', '.opus', '.flac', '.archive',
                        '.exe', '.dll', '.pyd', '.so', '.dylib', '.sav', '.save',
                        '.ess', '.dmp', '.log', '.sqlite', '.sqlite3', '.db',
                        '.bak', '.zip', '.7z', '.rar', '.tar', '.gz', '.xz', '.pfx', '.p12'}
PRIVATE_NAMES = {'config.json', 'auth.json', 'credentials.json', 'secrets.json',
                 'token.json', 'tokens.json', 'local-token.json', 'auth-cache.json',
                 'authcache.json', 'history.json', 'conversation-history.json',
                 'chat-history.json', 'conversations.json', 'player-memory.json',
                 'player-voices.json', 'character-overrides.json', 'world-rules.json',
                 'settings.json', '.npmrc', '.pypirc', 'id_rsa', 'id_ed25519'}
LEGAL_NAMES = {'license', 'licence', 'notice', 'authors', 'copyright'}
PROVIDER_PATTERNS = [
    ('anthropic-key', re.compile(r'(?<![\w-])sk-ant-[A-Za-z0-9_-]{20,}')),
    ('openai-key', re.compile(r'(?<![\w-])sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}')),
    ('google-api-key', re.compile(r'(?<![\w-])AIza[0-9A-Za-z_-]{30,}')),
    ('github-token', re.compile(r'(?<![\w-])(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})')),
    ('huggingface-token', re.compile(r'(?<![\w-])hf_[A-Za-z0-9]{20,}')),
    ('slack-token', re.compile(r'(?<![\w-])xox[baprs]-[A-Za-z0-9-]{20,}')),
    ('aws-access-id', re.compile(r'(?<![A-Z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])')),
]
CREDENTIAL_VALUE = re.compile(
    r'''(?ix)["']?(?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|authorization|password|secret[_-]?key)["']?\s*[:=]\s*["']([^"'\r\n]{16,})["']''')
WINDOWS_PATH = re.compile(r'(?<![A-Za-z0-9])([A-Za-z]):(?:\\{1,2}|/)([^\s\r\n"\'<>`|]+)')
POSIX_HOME = re.compile(r'(?<![A-Za-z0-9:])/(?:home|Users)/([^/\s"\'<>]+)/[^\s"\'<>]+')
EMAIL = re.compile(r'(?<![\w.+-])[A-Za-z0-9.+_-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![\w.-])')
LINK = re.compile(r'!?\[[^\]\n]*\]\(\s*(<[^>]+>|[^\s)]+)(?:\s+["\'][^)]*)?\)')

# The startup copier needs this byte-identical upstream source as its restore
# anchor. Only its one original fallback may be classified as a documented
# warning. Effective add-on variants must use game-root-relative resolution.
RESTORE_CODE_ROOT = 'red4ext/plugins/AiNpcCyberpunkCode/'
RESTORE_SOURCE = RESTORE_CODE_ROOT + 'app/bridge/convai-bridge.mjs'
RESTORE_SOURCE_SHA256 = '1b7f7c1dec5b14931f7d03d6e735db153dcad8adfdcc22c7079d45ceda33294d'
RESTORE_COMMIT = '52c8a210c35df94512ace0578eabb68bf7d6e406'


def original_restore_line() -> str:
    # Construct the historical literal in parts so the scanner itself does not
    # contain a fixed installation path or an exception to its source rules.
    drive = chr(69) + ':'
    tail = r'\\SteamLibrary\\steamapps\\common\\Cyberpunk 2077'
    return "const game = process.env.CYBERPUNK_CONVAI_GAME || '" + drive + tail + "';"


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    path: str
    message: str
    line: int | None = None


def safe_relative(name: str) -> bool:
    if not isinstance(name, str) or not name or '\\' in name or ':' in name:
        return False
    if any(ord(char) < 32 or ord(char) == 127 or char in '\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069' for char in name):
        return False
    if name.startswith('/') or '//' in name:
        return False
    parts = name.rstrip('/').split('/')
    return bool(parts) and all(part not in {'', '.', '..'} and not part.endswith((' ', '.'))
                               and not re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', part)
                               for part in parts)


def exemplar(name: str) -> bool:
    name = name.casefold()
    return bool(re.search(r'(?:^|[._-])(?:example|sample|template)(?:[._-]|$)', name))


def placeholder(value: str) -> bool:
    # Do not exempt entire test directories: real tokens accidentally committed
    # to a fixture are still sensitive. Only clearly artificial values are skipped.
    value = value.strip()
    if re.match(r'(?i)^(?:Bearer |Basic )?(?:test|fixture|dummy|fake|example|placeholder|not-a-real)[ _-]', value):
        return True
    if re.search(r'(?i)(your[_ -]|replace[_ -]|placeholder|example(?:[_ -]|$)|<[^>]+>|\$\{|process\.env|os\.environ)', value):
        return True
    suffix = re.sub(r'^(?:sk-(?:proj-|svcacct-|ant-)?|AIza|hf_|gh[pousr]_)', '', value)
    return not suffix or len(set(suffix)) <= 2 or bool(re.fullmatch(r'(?i)(?:x+|0+|dummy|fake|test|not[_-]a[_-]real[_-]key)', suffix))


def secretish(value: str) -> bool:
    if placeholder(value) or len(value) < 24:
        return False
    if not re.fullmatch(r'[A-Za-z0-9+/=_ .:-]+', value) or ' ' in value.replace('Bearer ', '').replace('Basic ', ''):
        return False
    counts = {char: value.count(char) for char in set(value)}
    entropy = -sum((count / len(value)) * math.log2(count / len(value)) for count in counts.values())
    return entropy >= 3.2


def path_findings(name: str) -> list[Finding]:
    path = PurePosixPath(name)
    lower = path.name.casefold()
    findings = []
    if path.suffix.casefold() in FORBIDDEN_EXTENSIONS:
        findings.append(Finding('error', 'private-or-binary-file', name, 'Game/audio/binary/state/archive content is outside this source add-on distribution.'))
    if not exemplar(lower) and (lower in PRIVATE_NAMES or lower.startswith('.env')
                                or re.fullmatch(r'(?:rollout|conversation|session)[-_].*\.jsonl', lower)):
        findings.append(Finding('error', 'private-state-filename', name, 'Credential, configuration or conversation-state filename; use a deliberately named example instead.'))
    if any(part.casefold() in {'.codex', '.ssh', '.aws', 'authcache', 'auth-cache', 'sessions', 'saves'} for part in path.parts):
        findings.append(Finding('error', 'private-state-directory', name, 'Private authentication/session/save directory is not a publication source.'))
    return findings


def inspect_text(name: str, text: str) -> list[Finding]:
    findings = []
    seen = set()
    def add(code, offset, message, severity='error'):
        line = text.count('\n', 0, offset) + 1
        if (code, line) not in seen:
            findings.append(Finding(severity, code, name, message, line))
            seen.add((code, line))
    for code, pattern in PROVIDER_PATTERNS:
        for matched in pattern.finditer(text):
            if not placeholder(matched.group()):
                add(code, matched.start(), 'Possible provider credential value. The matched value is deliberately omitted.')
    for matched in CREDENTIAL_VALUE.finditer(text):
        if secretish(matched.group(1)):
            add('credential-value', matched.start(), 'A credential field contains a non-placeholder opaque value; review and remove it.')
    if '-----BEGIN ' in text:
        for matched in re.finditer(r'-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----', text):
            add('private-key', matched.start(), 'Private key material must not be published.')
    for matched in WINDOWS_PATH.finditer(text):
        if re.match(r'(?i)[A-Za-z]:(?:\\{1,2}|/)Users(?:\\{1,2}|/)(?:<[^>]+>|%[^%]+%|\{[^}]+\})', text[matched.start():]):
            continue
        tail = matched.group(2).replace('\\\\', '/').replace('\\', '/').casefold().rstrip('.,;:)')
        # Standard installation locations and documented placeholders are not a
        # developer workspace. Explicit user profiles are never accepted here.
        first = tail.split('/')[0]
        if first in {'program', 'program files', 'program files (x86)', 'windows', 'games', 'tmp', 'temp', 'path', 'example', 'fixture'}:
            continue
        if re.search(r'(?i)(%[^%]+%|\{[^}]+\}|\$env:|your[_ -]|example[_ -]|username|user_name)', tail):
            continue
        if tail.startswith(('users/public/', 'users/default/')):
            continue
        add('fixed-absolute-path', matched.start(), 'Fixed machine/user/workspace path; use a relative path, environment value or explicit placeholder.')
    for matched in POSIX_HOME.finditer(text):
        if matched.group(1).casefold() not in {'user', 'username', 'example', 'test'}:
            add('fixed-user-home', matched.start(), 'Fixed user home path; use a portable path.')
    legal = any(part.casefold().split('.')[0] in LEGAL_NAMES or part.casefold() in {'licenses', 'licences'} for part in PurePosixPath(name).parts)
    if not legal:
        for matched in EMAIL.finditer(text):
            if not re.search(r'(?i)@(?:example\.(?:com|org|net)|[^@]+\.invalid|[^@]+\.test)$', matched.group()):
                add('email-review', matched.start(), 'Email-like contact outside a license/notice; confirm it is intended public attribution/contact.', 'warning')
    return findings


def binary_findings(name: str, data: bytes) -> list[Finding]:
    """Recognize forbidden payload headers without loading a large asset."""
    if (data.startswith(b'MZ') and len(data) > 64) or (data[:4] == b'RIFF' and data[8:12] == b'WAVE') or data[:4] == b'RDAR':
        return [Finding('error', 'disguised-binary', name, 'Executable or game/audio asset signature, regardless of filename.')]
    return []


def textual_name(name: str) -> bool:
    path = PurePosixPath(name)
    return path.suffix.casefold() in TEXT_EXTENSIONS or path.name.casefold() in TEXT_EXTENSIONS or path.name.casefold().split('.')[0] in LEGAL_NAMES


def inspect_bytes(name: str, data: bytes, max_text: int) -> tuple[list[Finding], str | None]:
    findings = path_findings(name) + binary_findings(name, data)
    if not textual_name(name):
        return findings, None
    if len(data) > max_text:
        findings.append(Finding('warning', 'large-text-not-inspected', name, 'Text exceeds the configured bounded content scan; review separately.'))
        return findings, None
    try:
        text = data.decode('utf-16') if data.startswith((b'\xff\xfe', b'\xfe\xff')) else data.decode('utf-8-sig')
    except UnicodeError:
        findings.append(Finding('error', 'text-encoding', name, 'Expected UTF-8 or BOM-marked UTF-16 text; unable to inspect content safely.'))
        return findings, None
    findings.extend(inspect_text(name, text))
    return findings, text


def public_inventory(root: Path, allowlist: Path | None = None) -> tuple[list[str], list[Finding]]:
    manifest = allowlist or root / '.publication-files.json'
    findings = []
    if manifest.is_file():
        value = json.loads(manifest.read_text(encoding='utf-8-sig'))
        if not isinstance(value, dict) or value.get('schema') != 1 or not isinstance(value.get('files'), list):
            raise ValueError('Publication allowlist must have schema:1 and files:[relative paths].')
        names = value['files']
    elif allowlist is not None:
        raise ValueError('The supplied publication allowlist does not exist.')
    else:
        top = subprocess.run(['git', '-C', str(root), 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
        if top.returncode or Path(top.stdout.strip()).resolve() != root.resolve():
            raise ValueError('No .publication-files.json and this root is not its own Git repository; refusing a recursive scan.')
        listed = subprocess.run(['git', '-C', str(root), 'ls-files', '-z'], capture_output=True, check=True)
        names = listed.stdout.decode('utf-8').rstrip('\0').split('\0') if listed.stdout else []
    selected = []
    seen = set()
    for name in names:
        if not safe_relative(name):
            findings.append(Finding('error', 'unsafe-source-path', '<inventory>', 'Publication inventory contains an unsafe relative path.'))
            continue
        if any(part.casefold() in EXCLUDED for part in PurePosixPath(name).parts):
            continue
        folded = name.casefold()
        if folded in seen:
            findings.append(Finding('error', 'duplicate-source-path', name, 'Duplicate/case-colliding publication inventory entry.'))
            continue
        seen.add(folded)
        selected.append(name)
    return selected, findings


def check_repository(root: Path, allowlist: Path | None = None, strict_links: bool = False,
                     max_text: int = 2 * 1024 * 1024) -> dict:
    root = root.resolve()
    names, findings = public_inventory(root, allowlist)
    texts = {}
    for name in names:
        file = root.joinpath(*PurePosixPath(name).parts)
        chain = [root.joinpath(*PurePosixPath(name).parts[:index]) for index in range(1, len(PurePosixPath(name).parts) + 1)]
        if any(part.is_symlink() for part in chain) or not file.resolve().is_relative_to(root):
            findings.append(Finding('error', 'source-symlink', name, 'Symbolic link or resolved path outside the publication root.'))
            continue
        if not file.is_file():
            findings.append(Finding('error', 'missing-source-file', name, 'Selected publication file is absent or is not a regular file.'))
            continue
        # Do not open private state merely to demonstrate that it is private.
        problems = path_findings(name)
        if any(problem.code in {'private-state-filename', 'private-state-directory'} for problem in problems):
            findings.extend(problems)
            continue
        if file.stat().st_size > max_text:
            findings.extend(problems)
            with file.open('rb') as stream:
                findings.extend(binary_findings(name, stream.read(65)))
            if textual_name(name):
                findings.append(Finding('warning', 'large-text-not-inspected', name, 'Text exceeds the bounded content scan; review separately.'))
            continue
        issues, text = inspect_bytes(name, file.read_bytes(), max_text)
        findings.extend(issues)
        if text is not None:
            texts[name] = text
    selected = set(names)
    for name, text in texts.items():
        if PurePosixPath(name).suffix.casefold() != '.md':
            continue
        for match in LINK.finditer(text):
            target = unquote(match.group(1).strip('<>')).split('#', 1)[0].split('?', 1)[0]
            if not target or re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', target) or target.startswith('//'):
                continue
            destination = root / target.lstrip('/') if target.startswith('/') else root / PurePosixPath(name).parent / target
            location = destination.resolve()
            severity = 'error' if strict_links else 'warning'
            if not location.is_relative_to(root):
                findings.append(Finding(severity, 'external-relative-link', name, 'Relative Markdown link escapes the public source root.', text.count('\n', 0, match.start()) + 1))
            elif not location.exists():
                findings.append(Finding(severity, 'broken-relative-link', name, 'Relative Markdown target is absent.', text.count('\n', 0, match.start()) + 1))
            elif location.is_file() and location.relative_to(root).as_posix() not in selected:
                findings.append(Finding(severity, 'unpublished-relative-link', name, 'Relative Markdown target is outside the publication inventory.', text.count('\n', 0, match.start()) + 1))
    return result('source', len(names), findings)


def classify_original_restore(archive: zipfile.ZipFile, name: str, data: bytes,
                              text: str | None, findings: list[Finding]) -> list[Finding]:
    """Single-file provenance check, not an archive-wide digest scan.

    A manifest merely claiming to be upstream is insufficient: the known
    official 0.4.6 file digest, exact source line and matching official metadata
    are all required. Every other finding remains an error.
    """
    if name != RESTORE_SOURCE or text is None or sha256(data).hexdigest() != RESTORE_SOURCE_SHA256:
        return findings
    original = original_restore_line()
    lines = text.splitlines()
    if lines.count(original) != 1:
        return findings
    manifest_name = RESTORE_CODE_ROOT + 'code.json'
    if sum(row.filename == manifest_name for row in archive.infolist()) != 1:
        return findings
    try:
        member = archive.getinfo(manifest_name)
        if member.file_size > 1024 * 1024 or member.flag_bits & 1 or stat.S_ISLNK(member.external_attr >> 16):
            return findings
        manifest = json.loads(archive.read(member).decode('utf-8-sig'))
        expected = {'version': 1, 'product': 'AI-NPC-Cyberpunk-Mod', 'package': 'scripts-code',
                    'release': '0.4.6', 'game': '2.5', 'commit': RESTORE_COMMIT}
        if not isinstance(manifest, dict) or any(manifest.get(key) != value for key, value in expected.items()):
            return findings
        rows = manifest.get('files')
        if not isinstance(rows, list):
            return findings
        matched = [row for row in rows if isinstance(row, dict) and row.get('path') == 'bridge/convai-bridge.mjs']
        if len(matched) != 1 or matched[0].get('sha256') != RESTORE_SOURCE_SHA256 or matched[0].get('size') != len(data):
            return findings
    except (KeyError, ValueError, UnicodeError, OSError, RuntimeError, NotImplementedError):
        return findings
    number = lines.index(original) + 1
    return [Finding('warning', 'verified-upstream-restore-fallback', row.path,
                    'Known byte-identical official 0.4.6 restore source retains its original single fallback. Official digest, Code manifest and exact environment/literal line verified; effective add-on code must remain portable.', row.line)
            if row.code == 'fixed-absolute-path' and row.line == number else row for row in findings]


def check_zip(file: Path, max_text: int = 2 * 1024 * 1024) -> dict:
    findings = []
    seen = set()
    regular = set()
    checked = 0
    try:
        with zipfile.ZipFile(file) as archive:
            for member in archive.infolist():
                name = member.filename
                checked += 1
                if not safe_relative(name):
                    findings.append(Finding('error', 'unsafe-zip-path', '<zip-member>', 'ZIP member is absolute, traversing or unsafe on Windows.'))
                    continue
                folded = name.rstrip('/').casefold()
                if folded in seen:
                    findings.append(Finding('error', 'duplicate-zip-path', name, 'Duplicate or case-colliding ZIP member.'))
                seen.add(folded)
                if any(parent.as_posix().casefold() in regular for parent in PurePosixPath(name).parents if parent.as_posix() != '.'):
                    findings.append(Finding('error', 'zip-file-directory-collision', name, 'A ZIP file is also used as a parent directory.'))
                if member.is_dir():
                    continue
                regular.add(folded)
                if stat.S_ISLNK(member.external_attr >> 16):
                    findings.append(Finding('error', 'zip-symlink', name, 'ZIP symbolic links are not allowed.'))
                    continue
                if member.flag_bits & 1:
                    findings.append(Finding('error', 'encrypted-zip-member', name, 'Encrypted members cannot be inspected.'))
                    continue
                suffix = PurePosixPath(name).suffix.casefold()
                if suffix not in ALLOWED_ZIP_EXTENSIONS and PurePosixPath(name).name.casefold() not in TEXT_EXTENSIONS and PurePosixPath(name).name.casefold().split('.')[0] not in LEGAL_NAMES:
                    findings.append(Finding('error', 'zip-extension', name, 'Extension is not in the text/source/media release allowlist.'))
                if any(part.casefold() in EXCLUDED | {'.codex', '.ssh', '.aws'} for part in PurePosixPath(name).parts):
                    findings.append(Finding('error', 'zip-private-directory', name, 'Generated/private/dependency directory is not a public release member.'))
                problems = path_findings(name)
                if any(problem.code in {'private-state-filename', 'private-state-directory'} for problem in problems):
                    findings.extend(problems)
                    continue
                if member.file_size > max_text:
                    findings.extend(problems)
                    with archive.open(member) as stream:
                        findings.extend(binary_findings(name, stream.read(65)))
                    if textual_name(name):
                        findings.append(Finding('warning', 'large-text-not-inspected', name, 'ZIP text exceeds bounded content scan; review separately or raise --max-text-bytes.'))
                    continue
                data = archive.read(member)
                issues, text = inspect_bytes(name, data, max_text)
                issues = classify_original_restore(archive, name, data, text, issues)
                findings.extend(issues)
            # Also detect inverse ordering: child precedes its file parent.
            for name in seen:
                for parent in PurePosixPath(name).parents:
                    if parent.as_posix().casefold() in regular:
                        findings.append(Finding('error', 'zip-file-directory-collision', parent.as_posix(), 'A ZIP file is also used as a parent directory.'))
    except (OSError, zipfile.BadZipFile, RuntimeError, NotImplementedError):
        findings.append(Finding('error', 'zip-read-failed', file.name, 'ZIP could not be opened/decrypted/decoded safely.'))
    return result('zip:' + file.name, checked, findings)


def result(scope: str, checked: int, findings: list[Finding]) -> dict:
    unique = list(dict.fromkeys(findings))
    return {'scope': scope, 'checkedFiles': checked, 'passed': not any(row.severity == 'error' for row in unique),
            'errors': sum(row.severity == 'error' for row in unique),
            'warnings': sum(row.severity == 'warning' for row in unique),
            'findings': [asdict(row) for row in unique]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--allowlist', type=Path)
    parser.add_argument('--zip', type=Path, action='append', default=[], help='Exact release ZIP; repeat as needed. No directory search.')
    parser.add_argument('--skip-source', action='store_true')
    parser.add_argument('--strict-links', action='store_true', help='Treat relative Markdown link warnings as errors after docs freeze.')
    parser.add_argument('--max-text-bytes', type=int, default=2 * 1024 * 1024)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    if args.max_text_bytes < 1 or (args.skip_source and not args.zip):
        parser.error('A positive scan limit and at least one source/ZIP scope are required.')
    results = []
    if not args.skip_source:
        try:
            results.append(check_repository(args.root, args.allowlist, args.strict_links, args.max_text_bytes))
        except (ValueError, OSError, json.JSONDecodeError, subprocess.SubprocessError):
            results.append(result('source', 0, [Finding('error', 'source-inventory-failed', '<inventory>', 'No valid safe publication inventory; use .publication-files.json schema 1 or this root own Git tracked files.')]))
    results.extend(check_zip(file, args.max_text_bytes) for file in args.zip)
    report = {'passed': all(row['passed'] for row in results), 'results': results,
              'limits': 'Heuristic bounded inspection of explicitly selected files; does not prove absence of all private content. Matched values are never printed.'}
    if args.json:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    else:
        for row in results:
            print(f"{row['scope']}: {'PASS' if row['passed'] else 'FAIL'} ({row['checkedFiles']} files, {row['errors']} errors, {row['warnings']} warnings)")
            for finding in row['findings']:
                line = ':' + str(finding['line']) if finding['line'] else ''
                print(f"  {finding['severity']} {finding['code']} {finding['path']}{line}: {finding['message']}")
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
