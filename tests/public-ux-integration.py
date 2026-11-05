"""Check clean-user UX defaults and the actual JP Lua -> JS money boundary.

Needs the official 0.4.6 Full archive and Lupa. Only code/data modules are
temporarily extracted; no upstream binaries, game assets or audio are executed.
Fixtures are removed on completion. Optional --lupa-path allows a workspace-only
test dependency instead of installing anything in the game or system Python.
"""
from pathlib import Path
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent
APP = 'red4ext/plugins/AiNpcCyberpunkCode/app/'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream-archive', type=Path, required=True)
    parser.add_argument('--lupa-path', type=Path)
    parser.add_argument('--node', default=shutil.which('node'))
    args = parser.parse_args()
    if args.lupa_path:
        sys.path.insert(0, str(args.lupa_path.resolve()))
    from lupa.lua54 import LuaRuntime
    from lupa.luajit21 import LuaRuntime as LuaJitRuntime

    engine_results = []
    snapshots = None
    for engine in [LuaRuntime, LuaJitRuntime]:
        lua = engine(unpack_returned_tuples=True)
        checks = 0
        for variant in ['codex', 'combined']:
            folder = ROOT / 'overrides' / variant / 'mod'
            settings = lua.execute((folder / 'social-options.lua').read_text(encoding='utf-8'))
            default = settings.read(lua.table_from({}))
            assert default.socialRelations is False and default.socialVVoice is False
            assert default.socialVReplies == 'off' and default.socialMemory is True
            checks += 4
            explicit = settings.read(lua.table_from({'socialRelations': True, 'socialVVoice': True}))
            assert explicit.socialRelations is True and explicit.socialVVoice is True
            checks += 2
            # Actual dictionary loads, not a line-count assertion: source labels
            # match translated labels and the disclosure describes opt-in costs.
            locale = lua.execute((folder / 'locales/ja.lua').read_text(encoding='utf-8'))
            ui = (folder / 'manager-ui.lua').read_text(encoding='utf-8')
            for english in [
                'Off by default. When enabled, the selected conversation AI reviews heard exchanges',
                'Off by default. Speak accepted automatic V replies',
                'Off leaves V to you. When addressed considers companion questions',
            ]:
                import re
                matched = re.search(re.escape(english) + r"[^']*(?:V own[^']*)?", ui)
                # The full actual string is a literal, with no apostrophe in these three descriptions.
                assert matched is not None
                description = matched.group(0)
                assert locale[description] and '?' not in locale[description][:10]
                checks += 1
        source = ROOT / 'base_features/japanese/sources/cet/turn-context.lua'
        module = lua.execute(source.read_text(encoding='utf-8'))
        lua.globals().fixtureModule = module
        capture = lua.eval('''function(value, fails, moneyOn)
            local instance = fixtureModule.new({now=function() return 10 end,
                enabled=function(kind) return kind ~= 'money' or moneyOn ~= false end,
                native={player=function() return {} end,ready=function() return true end,
                    clock=function() return 12, 0 end,
                    money=function() if fails then error('unavailable native') end return value end}})
            return instance:capture()
        end''')
        current = capture(100123, False, True)
        assert current.moneyAmount == 100123 and current.money == 'comfortable'
        checks += 2
        assert module.moneyAmount(9007199254740991) == 9007199254740991
        assert module.moneyAmount(1.9) == 1
        checks += 2
        def snapshot(row):
            return {key: row[key] for key in ['version', 'status', 'hour', 'minute', 'money', 'moneyAmount'] if row[key] is not None}
        generated = {'current': snapshot(current), 'zero': snapshot(capture(0, False, True))}
        for name, value, fails, money_on in [
            ('missing', None, False, True), ('readFailure', 12, True, True),
            ('disabled', 100123, False, False), ('negative', -1, False, True),
            ('nan', float('nan'), False, True), ('infinity', float('inf'), False, True),
            ('unsafe', 9007199254740992, False, True),
        ]:
            row = capture(value, fails, money_on)
            assert row.moneyAmount is None and row.money is None, name
            checks += 2
            generated[name] = snapshot(row)
        if snapshots is not None:
            assert snapshots == generated
        snapshots = generated
        engine_results.append({'engine': engine.__module__, 'assertions': checks})

    (ROOT / 'build').mkdir(exist_ok=True)
    node_results = []
    with tempfile.TemporaryDirectory(prefix='public-ux-', dir=ROOT / 'build') as temporary:
        fixture = Path(temporary)
        with zipfile.ZipFile(args.upstream_archive) as archive:
            for name in archive.namelist():
                if name.startswith(APP) and name.endswith(('.mjs', '.json')) and '/runtime/' not in name:
                    relative = Path(name[len(APP):])
                    assert '..' not in relative.parts and not relative.is_absolute()
                    target = fixture / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(name))
        # JP-only source, with test-only VVoice/controller copied beside it.
        # This imports the public implementation but invokes no service code.
        source = ROOT / 'base_features/japanese/sources/code'
        for path in source.rglob('*.mjs'):
            target = fixture / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        snapshot_file = fixture / 'lua-snapshots.json'
        snapshot_file.write_text(json.dumps(snapshots), encoding='utf-8')
        for variant in ['codex', 'combined']:
            for name in ['v-voice.mjs', 'social-controller.mjs']:
                shutil.copyfile(ROOT / 'overrides' / variant / 'app/bridge' / name, fixture / 'bridge' / name)
            result = subprocess.run([args.node, str(ROOT / 'tests/public-ux-check.mjs'), str(fixture), str(snapshot_file), variant],
                                    capture_output=True, text=True, encoding='utf-8', check=True)
            node_results.append(json.loads(result.stdout))
    report = {'passed': True, 'lua': engine_results, 'node': node_results,
              'gameplayTested': False, 'cloudRequests': 0, 'voiceSynthesisCalled': False, 'liveWrites': 0}
    out = ROOT / 'audit/public-ux-validation.json'
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
