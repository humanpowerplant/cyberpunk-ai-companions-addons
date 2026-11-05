"""Execute the deployed startup path in a disposable game-shaped fixture.

The normal start-service target is replaced with a marker-only module. The
actual install-code entrypoint, composer, Code copier and CET selector execute;
no game, cloud API, Codex CLI or conversation server starts.
"""
from pathlib import Path
from hashlib import sha256
import json
import shutil
import subprocess
import sys
import time
import zipfile
import argparse
import os

ROOT = Path(__file__).resolve().parent.parent
CODE = "red4ext/plugins/AiNpcCyberpunkCode"
CET = "bin/x64/plugins/cyber_engine_tweaks/mods/AiNpcCyberpunkMod"
RUNTIME = "red4ext/plugins/AiNpcCyberpunkMod/app"
FOLDERS = {"japanese": "AiNpcJapaneseOptimization", "codex": "AiNpcCodexBridge"}


def read(file):
    return json.loads(file.read_text(encoding="utf-8-sig"))


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def lua_selection(game, active, targets, fallback=False):
    # The official 0.4.6 init.lua exceeds stock LuaJIT's 60-upvalue compiler
    # limit, so real payload syntax is checked with Lua 5.4 here. The separate
    # selector unit fixtures also execute on LuaJIT with small fixture sources.
    from lupa.lua54 import LuaRuntime
    lua = LuaRuntime(unpack_returned_tuples=True)
    def to_lua(value):
        if isinstance(value, dict):
            return lua.table_from({key: to_lua(item) for key, item in value.items()})
        if isinstance(value, list):
            return lua.table_from([to_lua(item) for item in value])
        return value
    main = game / CET
    def text(relative):
        file = main / relative
        return file.read_text(encoding="utf-8-sig") if file.is_file() else None
    lua.globals().fixtureRead = text
    lua.globals().json = lua.table_from({"decode": lambda raw: to_lua(json.loads(raw))})
    lua.execute("""
        fixtureCompiled=0;fixtureExecuted=0
        local compiler=loadstring or load
        io={open=function(path,mode)
            assert(mode=='rb' or mode=='r')
            local value=fixtureRead(path)
            if value==nil then return nil,'fixture missing',2 end
            return {read=function(self,amount) if type(amount)=='number' then return value:sub(1,amount) end return value end,
                    close=function()return true end}
        end}
        loadfile=function(path)
            local value=fixtureRead(path)
            if value==nil then return nil,'fixture missing' end
            local compiled,problem=compiler(value,'@'..path)
            if not compiled then return nil,problem end
            fixtureCompiled=fixtureCompiled+1
            return function()fixtureExecuted=fixtureExecuted+1;return path end
        end
        dofile=function(path)
            local source=assert(fixtureRead(path),'fixture helper missing')
            return assert(compiler(source,'@'..path))()
        end
        fixtureShim=function(source) return assert(compiler(source,'@fixture-shim'))() end
    """)
    descriptors = [read(main / "community/features" / (feature + ".json")) for feature in active]
    selected = {row["path"]: row["source"] for descriptor in descriptors for row in descriptor["files"]}
    combination = "+".join(sorted(active))
    for descriptor in descriptors:
        for row in descriptor.get("combinations", {}).get(combination, []):
            selected[row["path"]] = row["source"]
    if fallback:
        selected = {}
    checked = 0
    for target in targets:
        expected = selected.get(target, "community/pristine/" + target)
        if not (main / expected).is_file():
            continue  # A new Codex-only module has no pristine counterpart.
        actual = lua.globals().fixtureShim(text(target))
        assert actual == expected, (target, actual, expected)
        checked += 1
    assert checked > 0
    if "codex" in active and not fallback:
        # This small actual module has no native game or I/O calls.
        options = lua.execute(text(selected["social-options.lua"]))
        assert options.defaults.socialVVoiceEngine == "same"
        assert options.choices.socialVVoiceEngine[1] == "same"
        assert options.choices.socialVVoiceEngine[2] == "v-setting"
    return {"selectedTargets": checked, "compatibilityFallback": fallback, "actualProductLuaSourcesCompiled": lua.globals().fixtureCompiled,
            "productLuaBodiesStubbed": True, "selectorAndShimsExecuted": True, "sourceCompileEngine": "Lua 5.4"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-archive", type=Path, required=True)
    parser.add_argument("--node", default=shutil.which("node"))
    parser.add_argument("--fixture-root", type=Path, help="Optional writable location, including another drive, for disposable fixtures")
    args = parser.parse_args()
    packages = {row["feature"]: row for row in read(ROOT / "build/package-roots.json")}
    archive = zipfile.ZipFile(args.upstream_archive)
    names = set(archive.namelist())
    fixture = (args.fixture_root or ROOT / "build") / ("auto-fixture-" + str(time.time_ns())) / "別ドライブ 日本語 Game with spaces"
    fixture.mkdir(parents=True)
    def put(relative, data):
        file = fixture / relative
        assert file.resolve().is_relative_to(fixture.resolve())
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(data)
    for entry in archive.infolist():
        name = entry.filename
        if entry.is_dir() or "/runtime/" in name:
            continue
        if name.startswith(CODE + "/app/") or name in {CODE + "/code.json", CODE + "/install-code.mjs"} or name.startswith(CET + "/"):
            put(name, archive.read(entry))
    original_manifest = read(fixture / CODE / "code.json")
    original_installer = archive.read(CODE + "/install-code.mjs")
    put(RUNTIME + "/release.json", b'{"fixture":true}\n')
    # Dependency guards check paths/metadata only, never execute these fixtures.
    for path in (RUNTIME + "/node/node.exe", RUNTIME + "/python/python.exe", CODE + "/CyberpunkConvai.dll", CODE + "/CyberpunkConvaiNative.dll"):
        put(path, b'fixture-not-an-executable')
    sentinel = b'{"privateFixtureValue":"preserve","socialVReplies":"asked"}\n'
    put(RUNTIME + "/runtime/personal-fixture.json", sentinel)
    put(CET + "/runtime/settings.json", sentinel)
    fixture_state = fixture.parent / "Disposable player LocalAppData"
    bridge_state = fixture_state / "AiNpcCodexBridge"
    bridge_state.mkdir(parents=True)
    (bridge_state / "config.json").write_bytes(encoded({"host":"127.0.0.1","port":19876,"model":"codex-default"}))
    (bridge_state / "local-token.json").write_bytes(encoded({"schema":1,"token":"a" * 64}))
    player_data = fixture_state / "AiNpcCyberpunkMod/data"
    player_data.mkdir(parents=True)
    (player_data / "preserved-fixture.json").write_bytes(sentinel)
    probe_env = dict(os.environ, LOCALAPPDATA=str(fixture_state))
    members = {key: read(ROOT / "build" / (key + "-members.json")) for key in packages}
    owned = set().union(*(set(value) for value in members.values()))
    # Simulate a previous manual Apply, including a modified Code manifest and
    # a new untracked helper. Deploy must reset its original Code anchor itself.
    put(CODE + "/code.json", b'{"oldManagedApplyFixture":true}\n')
    put(CODE + "/app/bridge/context-ja.mjs", b'export const oldUnusedFixture = true;\n')
    targets = read(ROOT / "build/build-summary.json")["cetSelectorFiles"]
    outcomes = []
    source_mapping = read(ROOT / "source-overrides.json")
    tuning = {"rows": []}
    for variant, rows in source_mapping["files"].items():
        for row in rows:
            prefix = CODE + "/app/" if row["path"].startswith(CODE) else CET + "/"
            tuning["rows"].append({"variant": variant, "relative": ("app/" if prefix.startswith(CODE) else "mod/") + row["path"][len(prefix):], "sourceFile": row["sourceFile"]})
    for row in source_mapping.get("combinations", {}).get("codex+japanese", []):
        prefix = CODE + "/app/" if row["path"].startswith(CODE) else CET + "/"
        tuning["rows"].append({"variant": "combined", "relative": ("app/" if prefix.startswith(CODE) else "mod/") + row["path"][len(prefix):], "sourceFile": row["sourceFile"]})
    syntax_checked = set()
    node = args.node
    assert node
    sequence = [("Japanese alone", ["japanese"]), ("Codex alone", ["codex"]),
                ("Both", ["japanese", "codex"]), ("Disable Japanese", ["codex"]),
                ("Disable Codex", ["japanese"]), ("Both again", ["codex", "japanese"]),
                ("Disable both", [])]
    for label, active in sequence:
        # Model ordinary Vortex restoration/deployment of explicitly owned
        # files; the Runtime and personal state are deliberately kept in place.
        deployed = {}
        for feature in active:
            for member in members[feature]:
                data = (ROOT / packages[feature]["package"] / member).read_bytes()
                if member in deployed:
                    assert deployed[member] == data, "Shared deployed files differ: " + member
                deployed[member] = data
        for member in owned:
            if member in deployed:
                put(member, deployed[member])
            elif member in names:
                put(member, archive.read(member))
            else:
                file = fixture / member
                if file.is_file():
                    assert file.resolve().is_relative_to(fixture.resolve())
                    file.unlink()
        if "codex" in active:
            # Confirm the shipped auto-start module and backend helpers really
            # arrive at their installed paths; their own lifecycle tests use
            # fake CLI/server fixtures and are maintained separately.
            for row in read(ROOT / "codex_source/manifest.json")["files"]:
                if row["path"] in {"red4ext/plugins/AiNpcCodexBridge/README.ja.md", "red4ext/plugins/AiNpcCodexBridge/README.en.md"}:
                    assert "docs/codex/README" in (fixture / row["path"]).read_text(encoding="utf-8")
                    continue
                assert (fixture / row["path"]).read_bytes() == (ROOT / "codex_source/payload/game" / row["path"]).read_bytes(), row["path"]
        # Replace only service entry execution with a marker, and adapt only
        # this fixture's manifest/base identity accordingly. All real overlay
        # targets, transformations and source bytes remain the packaged ones.
        source_manifest = read(fixture / CODE / "code.json")
        assert source_manifest == original_manifest, "Deploy failed to restore the pristine Code baseline"
        stub = b"import {writeFileSync} from 'node:fs';\nwriteFileSync(new URL('../fixture-started.json', import.meta.url), JSON.stringify({started:true,argv:process.argv}));\n"
        put(CODE + "/app/launcher/start-service.mjs", stub)
        for row in source_manifest["files"]:
            if row["path"] == "launcher/start-service.mjs":
                row.update(size=len(stub), sha256=sha256(stub).hexdigest())
        manifest_bytes = encoded(source_manifest)
        put(CODE + "/code.json", manifest_bytes)
        for feature in active:
            file = fixture / "red4ext/plugins" / FOLDERS[feature] / "auto-feature.json"
            descriptor = read(file)
            descriptor["baseManifestSha256"] = sha256(manifest_bytes).hexdigest()
            file.write_bytes(encoded(descriptor))
        before = {file.relative_to(fixture / CODE).as_posix(): (file.stat().st_size, file.stat().st_mtime_ns)
                  for file in (fixture / CODE).rglob("*") if file.is_file()}
        marker = fixture / RUNTIME / "fixture-started.json"
        if marker.is_file():
            marker.unlink()
        result = subprocess.run([node, str(fixture / CODE / "install-code.mjs"), "--game-root", str(fixture), "--game-pid", "0", "--prepare-only"],
                                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
        if result.returncode:
            raise RuntimeError(label + "\n" + result.stdout + result.stderr)
        assert marker.is_file(), "The normal startup entry did not reach the service marker"
        after = {file.relative_to(fixture / CODE).as_posix(): (file.stat().st_size, file.stat().st_mtime_ns)
                 for file in (fixture / CODE).rglob("*") if file.is_file()}
        assert before == after, "Startup rewrote Vortex-owned Code files"
        runtime = fixture / RUNTIME
        assert (runtime / "bridge/social-controller.mjs").is_file() == ("codex" in active)
        assert (runtime / "bridge/context-ja.mjs").is_file() == ("japanese" in active)
        assert (runtime / "runtime/personal-fixture.json").read_bytes() == sentinel
        assert (fixture / CET / "runtime/settings.json").read_bytes() == sentinel
        assert (player_data / "preserved-fixture.json").read_bytes() == sentinel
        installed = read(runtime / "defaults/scripts-code.json")
        assert len(installed["files"]) >= len(original_manifest["files"])
        variant = "combined" if len(active) == 2 else active[0] if active else "none"
        selected_cet = {}
        cet_descriptors = [read(fixture / CET / "community/features" / (feature + ".json")) for feature in active]
        for descriptor in cet_descriptors:
            selected_cet.update({row["path"]: row["source"] for row in descriptor["files"]})
        for descriptor in cet_descriptors:
            selected_cet.update({row["path"]: row["source"] for row in descriptor.get("combinations", {}).get("+".join(sorted(active)), [])})
        exact_sources = 0
        for row in tuning["rows"]:
            if row["variant"] != variant:
                continue
            relative = row["relative"]
            actual = runtime / relative.removeprefix("app/") if relative.startswith("app/") else fixture / CET / selected_cet[relative.removeprefix("mod/")]
            assert actual.read_bytes() == (ROOT / row["sourceFile"]).read_bytes(), (variant, relative)
            exact_sources += 1
        probe = subprocess.run([node, str(ROOT / "tests/tuning-installed.mjs"), str(fixture), variant,
                                *(["--skip-syntax"] if variant in syntax_checked else [])],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, env=probe_env)
        if probe.returncode:
            raise RuntimeError(label + " tuning source probe failed\n" + probe.stderr)
        syntax_checked.add(variant)
        lua = lua_selection(fixture, active, targets) if active else {"lastShimRemoved": True}
        if not active:
            assert (fixture / CODE / "install-code.mjs").read_bytes() == original_installer
            assert not (fixture / CET / "community/selector.lua").exists()
            for target in targets:
                if CET + "/" + target in names:
                    assert (fixture / CET / target).read_bytes() == archive.read(CET + "/" + target)
        outcomes.append({"name": label, "active": active, "startupExit": 0, "serviceMarkerReached": True,
                         "manualApplyCalled": False, "codeTreeNotRewrittenAtStartup": True,
                         "personalStatePreserved": True, "runtimeCodeFiles": len(installed["files"]), "cet": lua,
                         "tuningExactSources": exact_sources, "tuningProbe": json.loads(probe.stdout)})
        print(json.dumps({"scenario": label, "passed": True, "manualApplyCalled": False}), flush=True)
    adversarial = []
    for old_feature in ["codex", "japanese"]:
        # A one-sided update must not silently let an old combination win.
        # Use the real packaged descriptors/payloads and both actual loaders.
        for feature in ["codex", "japanese"]:
            for member in members[feature]:
                put(member, (ROOT / packages[feature]["package"] / member).read_bytes())
        source_manifest = read(fixture / CODE / "code.json")
        put(CODE + "/app/launcher/start-service.mjs", stub)
        for row in source_manifest["files"]:
            if row["path"] == "launcher/start-service.mjs":
                row.update(size=len(stub), sha256=sha256(stub).hexdigest())
        manifest_bytes = encoded(source_manifest)
        put(CODE + "/code.json", manifest_bytes)
        for feature in ["codex", "japanese"]:
            descriptor_path = fixture / "red4ext/plugins" / FOLDERS[feature] / "auto-feature.json"
            descriptor = read(descriptor_path)
            descriptor["baseManifestSha256"] = sha256(manifest_bytes).hexdigest()
            if feature == old_feature:
                descriptor.pop("releaseFamily", None)
                descriptor.pop("supportedPairing", None)
                descriptor["release"] = "legacy-fixture"
            descriptor_path.write_bytes(encoded(descriptor))
            if feature == old_feature:
                cet_path = fixture / CET / "community/features" / (feature + ".json")
                cet_descriptor = read(cet_path)
                cet_descriptor.pop("releaseFamily", None)
                cet_descriptor.pop("supportedPairing", None)
                cet_path.write_bytes(encoded(cet_descriptor))
        marker.unlink(missing_ok=True)
        run = subprocess.run([node, str(fixture / CODE / "install-code.mjs"), "--game-root", str(fixture), "--game-pid", "0", "--prepare-only"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
        assert run.returncode == 0, run.stderr
        assert marker.is_file()
        assert not (runtime / "bridge/social-controller.mjs").exists()
        assert not (runtime / "bridge/context-ja.mjs").exists()
        probe = subprocess.run([node, str(ROOT / "tests/tuning-installed.mjs"), str(fixture), "none"],
            capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=60,env=probe_env)
        assert probe.returncode == 0, probe.stderr
        lua = lua_selection(fixture,["codex","japanese"],targets,fallback=True)
        assert (runtime / "runtime/personal-fixture.json").read_bytes() == sentinel
        assert (fixture / CET / "runtime/settings.json").read_bytes() == sentinel
        adversarial.append({"olderFeature":old_feature,"nodeFallback":"original046","cetFallback":"original046","oldCombinationNeverSelected":True,"cet":lua})
        print(json.dumps({"scenario":"Mixed release: old " + old_feature,"passed":True,"fallback":"original046"}),flush=True)
    package_state = {feature: {member: [(ROOT / row["package"] / member).stat().st_size, (ROOT / row["package"] / member).stat().st_mtime_ns]
                    for member in members[feature]} for feature, row in packages.items()}
    report = {"allPassed": True, "buildId": read(ROOT / "build/build-summary.json")["buildId"], "checkedPackageState": package_state,
              "scenarios": outcomes, "fixture": str(fixture),
              "mixedReleaseCases": adversarial,
              "unicodeAndSpacedGamePath": True, "fixtureDrive": fixture.drive,
              "actualStartupEntryExecuted": True, "actualOfficialCodeCopier": True,
              "serviceTargetStubbed": True, "oldManagedMigration": True,
              "archiveWideHashScan": False, "gameStarted": False, "liveGameWritten": False, "modelCalls": 0}
    (ROOT / "build/functional-report.json").write_bytes(encoded(report))
    print(json.dumps({"allPassed": True, "scenarios": len(outcomes), "manualApplyCalls": 0, "liveGameWritten": False}))


if __name__ == "__main__":
    main()
