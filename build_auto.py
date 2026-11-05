"""Build Vortex-native overlays without changing any installed game files.

The official startup copier composes Runtime code. Vortex owns only the common
startup hook, CET selectors/private sources, feature recipes, and pristine Code
reset sources needed to migrate a previous managed Apply installation.
"""
from pathlib import Path
from hashlib import sha256
import json
import shutil
import subprocess
import sys
import zipfile
import argparse
import uuid

ROOT = Path(__file__).resolve().parent
CODE = "red4ext/plugins/AiNpcCyberpunkCode"
CET = "bin/x64/plugins/cyber_engine_tweaks/mods/AiNpcCyberpunkMod"
AUTO = "red4ext/plugins/AiNpcCommunityAuto"
FOLDERS = {"japanese": "AiNpcJapaneseOptimization", "codex": "AiNpcCodexBridge"}
VERSIONS = {"japanese": "1.0.4-rc.1", "codex": "1.2.2-rc.1"}
RELEASE_FAMILY = "companion-addons-046-rc1"
TITLES = {"japanese": "AI-Companions-Japanese-Dialogue-Character-Pack", "codex": "AI-Companions-Party-Conversations-Codex-Bridge"}
DOCS = ["README.ja.md", "README.en.md", "CHANGES.txt", "NEXUS_DESCRIPTION.ja.txt", "NEXUS_DESCRIPTION.en.txt"]
COMMON_DOCS = ["PRIVACY.md", "COMPATIBILITY.md", "TROUBLESHOOTING.md", "TESTING.md", "CHANGELOG.md"]


def read(file):
    return json.loads(file.read_text(encoding="utf-8-sig"))


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def safe(relative):
    if not isinstance(relative, str) or relative.startswith("/") or "\\" in relative or ":" in relative or any(part in {"", ".", ".."} for part in relative.split("/")):
        raise ValueError("Unsafe package relative path")
    return relative


def root_file(relative):
    """Source mappings are portable repository-relative paths, never personal paths."""
    path = ROOT / safe(relative)
    if path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("Source mapping escapes this repository")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-archive", type=Path, required=True, help="Official AI Companions 0.4.6 Full ZIP (read only)")
    parser.add_argument("--node", default=shutil.which("node"), help="Node.js 20+ executable; defaults to PATH")
    parser.add_argument("--build-only", action="store_true", help="Developer mode: create package trees without tests or ZIPs")
    args = parser.parse_args()
    if not args.node:
        parser.error("Node.js 20+ is required; install it or pass --node PATH")
    archive_path = args.upstream_archive.resolve(strict=True)
    build_id = uuid.uuid4().hex
    (ROOT / "build").mkdir(exist_ok=True)
    (ROOT / "build/functional-report.json").write_bytes(encoded({"allPassed": False, "reason": "New build requires current functional checks"}))
    # Local backend fixtures can leave import bytecode. It is not distribution
    # source; remove only generated .pyc files in verified in-fork cache folders.
    payload = (ROOT / "codex_source/payload/game").resolve()
    for cache in payload.rglob("__pycache__"):
        if cache.is_symlink() or not cache.resolve().is_relative_to(payload):
            raise ValueError("Unexpected source cache path")
        for child in cache.iterdir():
            if not child.is_file() or child.is_symlink() or child.suffix != ".pyc":
                raise ValueError("Unexpected generated-cache content")
            child.unlink()
        cache.rmdir()
    # This only refreshes the explicit source index, never credentials or config.
    subprocess.run([sys.executable, "-B", str(ROOT / "codex_source/build_manifest.py")], check=True)
    descriptors, addons = {}, {}
    for feature in FOLDERS:
        addons[feature] = ROOT / "base_features" / feature
        descriptors[feature] = read(addons[feature] / "auto-feature.json")
    # Open only required source entries. No archive-wide or binary hash scan.
    archive = zipfile.ZipFile(archive_path)
    names = set(archive.namelist())
    required_full = [CODE + "/CyberpunkConvai.dll", CODE + "/CyberpunkConvaiNative.dll",
                     "red4ext/plugins/AiNpcCyberpunkMod/app/node/node.exe",
                     "red4ext/plugins/AiNpcCyberpunkMod/app/python/python.exe"]
    missing = [name for name in required_full if name not in names or archive.getinfo(name).file_size == 0]
    if missing:
        raise ValueError("Use the official 0.4.6 Full ZIP, not a Scripts/update package. Missing: " + ", ".join(missing))
    original_manifest = json.loads(archive.read(CODE + "/code.json"))
    if original_manifest.get("release") != "0.4.6" or original_manifest.get("package") != "scripts-code" or original_manifest.get("game") != "2.5":
        raise ValueError("The upstream archive must be the official 0.4.6 Full release for game 2.5")
    base_manifest_sha = sha256(archive.read(CODE + "/code.json")).hexdigest()
    if any(descriptor.get("baseManifestSha256") != base_manifest_sha for descriptor in descriptors.values()):
        raise ValueError("This source release targets a different 0.4.6 Code manifest. Use the documented official Full release; do not bypass the baseline guard.")
    # Keep the released preview recipes immutable. New fixes become additional
    # in-memory rows and small source payloads in this distribution fork.
    original_code_rows = {row["path"]: row for row in original_manifest["files"]}
    # Readable source recipes become content-addressed runtime recipes here.
    # Only small selected source bytes are hashed, as required by the installer.
    rendered = ROOT / "build/profile-render"
    rendered.mkdir(exist_ok=True)
    source_payloads = {}
    def materialize_row(owner, row):
        row = dict(row)
        data = root_file("base_features/" + owner + "/" + safe(row["source"])).read_bytes()
        digest = sha256(data).hexdigest()
        source = "payload/" + digest + Path(row["source"]).suffix
        source_payloads[owner, source] = data
        output = data
        if row.get("transform") == "profile-overlay":
            target = row["path"]
            if target not in names:
                raise ValueError("Profile overlay has no original roster: " + target)
            base_file, overlay_file, output_file = [rendered / (owner + "-" + key + ".json") for key in ("base", "overlay", "output")]
            base_file.write_bytes(archive.read(target))
            overlay_file.write_bytes(data)
            subprocess.run([args.node, str(ROOT / "tools/render_profile.mjs"), str(base_file), str(overlay_file), str(output_file)], check=True)
            output = output_file.read_bytes()
        row.update(source=source, sha256=digest, outputSha256=sha256(output).hexdigest())
        return row
    for owner, descriptor in descriptors.items():
        descriptor["files"] = [materialize_row(owner, row) for row in descriptor["files"]]
        descriptor["combinations"] = {key: [materialize_row(owner, row) for row in rows] for key, rows in descriptor.get("combinations", {}).items()}
    overrides_file = ROOT / "source-overrides.json"
    if not overrides_file.is_file():
        raise ValueError("The reviewed preview.3 source mapping is required")
    overrides = read(overrides_file)
    if overrides.get("schema") != 1:
        raise ValueError("Unsupported source-override mapping")
    base_rows = {row["path"]: row for descriptor in descriptors.values()
                 for row in descriptor["files"]}
    source_overrides = {}
    def override_row(owner, item):
        target = safe(item["path"])
        if not ((target.startswith(CET + "/") and target.endswith(".lua"))
                or (target.startswith(CODE + "/app/bridge/") and target.endswith(".mjs"))):
            raise ValueError("Tuning sources must be CET Lua or Node bridge modules")
        source_file = root_file(item["sourceFile"])
        data = source_file.read_bytes()
        # Existing content-addressed recipe fields require the source digest;
        # this creates metadata for new small sources, not an extra scan/check.
        digest = sha256(data).hexdigest()
        source = "payload/" + digest + Path(target).suffix
        source_overrides[owner, source] = data
        base = base_rows.get(target, {}).get("baseSha256")
        if target not in base_rows and target in names:
            if target.startswith(CODE + "/app/"):
                base = original_code_rows[target[len(CODE + "/app/"):]]["sha256"]
            else:
                base = sha256(archive.read(target)).hexdigest()
        return {"path": target, "source": source, "sha256": digest, "outputSha256": digest, "baseSha256": base}
    for owner, items in overrides.get("files", {}).items():
        if owner not in descriptors:
            raise ValueError("Unknown source-override feature")
        for item in items:
            row = override_row(owner, item)
            descriptors[owner]["files"] = [old for old in descriptors[owner]["files"] if old["path"] != row["path"]] + [row]
    for combination, items in overrides.get("combinations", {}).items():
        if combination != "codex+japanese":
            raise ValueError("Unsupported tuning combination")
        for item in items:
            owner = item.get("owner", "codex")
            if owner not in descriptors:
                raise ValueError("Unknown combination owner")
            row = override_row(owner, item)
            previous = descriptors[owner].setdefault("combinations", {}).get(combination, [])
            descriptors[owner]["combinations"][combination] = [old for old in previous if old["path"] != row["path"]] + [row]
    def payload_bytes(owner, row):
        source = safe(row["source"])
        if (owner, source) in source_overrides:
            return source_overrides[owner, source]
        return source_payloads[owner, source]
    code_resets = {CODE + "/code.json"}
    cet_targets = set()
    for descriptor in descriptors.values():
        for row in descriptor["files"] + [row for rows in descriptor.get("combinations", {}).values() for row in rows]:
            target = safe(row["path"])
            if target.startswith(CODE + "/app/") and target in names:
                code_resets.add(target)
            elif target.startswith(CET + "/"):
                cet_targets.add(target[len(CET) + 1:])
    shared = {
        CODE + "/install-code.mjs": (ROOT / "common/install-code.mjs").read_bytes(),
        AUTO + "/community-compose.mjs": (ROOT / "common/community-compose.mjs").read_bytes(),
        CET + "/community/selector.lua": (ROOT / "common/cet-auto.lua").read_bytes(),
    }
    for target in sorted(code_resets):
        shared[target] = archive.read(target)
    for target in sorted(cet_targets):
        # The exact same selector shim is supplied by either add-on. Selection
        # happens once at game startup; no running-session switching is attempted.
        shared[CET + "/" + target] = ("return dofile('community/selector.lua').load(" + json.dumps(target) + ")\n").encode("utf-8")
        if CET + "/" + target in names:
            shared[CET + "/community/pristine/" + target] = archive.read(CET + "/" + target)
    results = []
    for feature, folder in FOLDERS.items():
        package = ROOT / "build/packages" / feature
        members = {}
        member_aliases = {}
        def put(relative, data):
            safe(relative)
            alias = relative.lower()
            if alias in member_aliases and member_aliases[alias] != relative:
                raise ValueError("Windows path alias in package: " + relative)
            member_aliases[alias] = relative
            if relative in members and members[relative] != data:
                raise ValueError("Conflicting generated member: " + relative)
            file = package / relative
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(data)
            members[relative] = data
        for target, data in shared.items():
            put(target, data)
        descriptor = descriptors[feature]
        auto_descriptor = {"schema": 1, "id": feature, "release": VERSIONS[feature],
                           "releaseFamily": RELEASE_FAMILY, "supportedPairing": VERSIONS,
                           "upstreamRelease": "0.4.6", "baseManifestSha256": descriptor["baseManifestSha256"],
                           "files": descriptor["files"], "combinations": descriptor.get("combinations", {})}
        backend = "red4ext/plugins/" + folder
        put(backend + "/auto-feature.json", encoded(auto_descriptor))
        rows = descriptor["files"] + [row for rows in descriptor.get("combinations", {}).values() for row in rows]
        for row in rows:
            source = safe(row["source"])
            put(backend + "/" + source, payload_bytes(feature, row))
        def cet_row(row):
            relative = row["path"][len(CET) + 1:]
            source = "community/payload/" + Path(row["source"]).name
            put(CET + "/" + source, payload_bytes(feature, row))
            return {"path": relative, "source": source}
        cet_descriptor = {"schema": 1, "id": feature, "upstreamRelease": "0.4.6",
                          "release": VERSIONS[feature], "releaseFamily": RELEASE_FAMILY, "supportedPairing": VERSIONS,
                          "files": [cet_row(row) for row in descriptor["files"] if row["path"].startswith(CET + "/")],
                          "combinations": {}}
        for key, values in descriptor.get("combinations", {}).items():
            selected = [cet_row(row) for row in values if row["path"].startswith(CET + "/")]
            if selected:
                cet_descriptor["combinations"][key] = selected
        put(CET + "/community/features/" + feature + ".json", encoded(cet_descriptor))
        if feature == "codex":
            for row in read(ROOT / "codex_source/manifest.json")["files"]:
                relative = safe(row["path"])
                # Release-level canonical guides replace the backend source
                # handoff READMEs at these two documented export destinations.
                if relative in {backend + "/README.ja.md", backend + "/README.en.md"}:
                    continue
                put(relative, (ROOT / "codex_source/payload/game" / relative).read_bytes())
        for name in DOCS:
            source = (ROOT / "docs" / feature / name).read_bytes()
            if name.startswith("README."):
                target = "docs/" + feature + "/" + name
                wrapper = ("# AI Companions community add-on\n\n" + ("使い方と必要条件: " if name == "README.ja.md" else "Installation and requirements: ")
                           + "[" + name + "](" + target + ")\n\n[Privacy / プライバシー](docs/PRIVACY.md)\n")
                put(backend + "/" + name, wrapper.encode("utf-8"))
            else:
                put(backend + "/" + name, source)
        for name in COMMON_DOCS:
            put(backend + "/docs/" + name, (ROOT / "docs" / name).read_bytes())
        for file in sorted((ROOT / "docs" / feature).iterdir()):
            if file.is_file() and file.suffix.lower() in {".md", ".txt"}:
                put(backend + "/docs/" + feature + "/" + file.name, file.read_bytes())
        if feature == "codex":
            put(backend + "/SOCIAL_PREVIEW.ja.md", (ROOT / "docs/codex/SOCIAL_PREVIEW.ja.md").read_bytes())
        for name in ("LICENSE.txt", "THIRD-PARTY-NOTICES.txt"):
            put(backend + "/" + name, archive.read(CODE + "/" + name))
        forbidden_suffixes = {".exe", ".dll", ".pyd", ".wav", ".wem", ".ogg", ".gguf", ".sqlite", ".db"}
        private_markers = {str(path).replace("\\", "/").lower().encode("utf-8") for path in (ROOT, ROOT.parent, Path.home())}
        for member, data in members.items():
            if Path(member).suffix.lower() in forbidden_suffixes or any(part in {"__pycache__", ".git", "originals", "runtime"} for part in member.split("/")):
                raise ValueError("Unexpected asset/private state in package: " + member)
            if any(marker in data.replace(b"\\", b"/").lower() for marker in private_markers):
                raise ValueError("Development path in public package: " + member)
        (ROOT / "build" / (feature + "-members.json")).write_bytes(encoded(sorted(members)))
        results.append({"feature": feature, "version": VERSIONS[feature], "package": package.relative_to(ROOT).as_posix(),
                        "members": len(members), "archive": TITLES[feature] + "-" + VERSIONS[feature] + "-Auto-Deploy-for-0.4.6.zip"})
    (ROOT / "build/package-roots.json").write_bytes(encoded(results))
    (ROOT / "build/build-summary.json").write_bytes(encoded({"buildId": build_id, "upstreamRelease": "0.4.6", "versions": VERSIONS,
        "releaseFamily": RELEASE_FAMILY, "upstreamArchive": str(archive_path), "node": str(args.node),
        "sharedFiles": sorted(shared), "codeResetFiles": len(code_resets), "cetSelectorFiles": sorted(cet_targets),
        "redistributedOriginalSourceBytesPerPackage": sum(len(shared[path]) for path in code_resets)
            + sum(len(data) for path, data in shared.items() if path.startswith(CET + "/community/pristine/")),
        "sourceOverrides": {key: [item["path"] for item in value] for key, value in overrides.get("files", {}).items()},
        "baseArchiveReadOnly": True, "archiveHashScan": False, "liveGameWritten": False, "packages": results}))
    print(json.dumps({"built": True, "packages": results, "sharedFiles": len(shared), "gameWritten": False}))
    if not args.build_only:
        subprocess.run([args.node, "--test", str(ROOT / "tests/compose.test.mjs"), str(ROOT / "tests/codex-transport.test.mjs")], check=True)
        subprocess.run([sys.executable, "-X", "utf8", "-B", str(ROOT / "tests/run_cet_lua.py")], check=True)
        subprocess.run([sys.executable, "-X", "utf8", "-B", str(ROOT / "tests/test_finalize.py")], check=True)
        subprocess.run([sys.executable, "-X", "utf8", "-B", str(ROOT / "tests/auto_packages.py"), "--upstream-archive", str(archive_path), "--node", str(args.node)], check=True)
        subprocess.run([sys.executable, "-X", "utf8", "-B", str(ROOT / "finalize_auto.py")], check=True)


if __name__ == "__main__":
    main()
