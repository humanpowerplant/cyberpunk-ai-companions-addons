"""Describe only reviewed game-root source files. Never read user data or credentials."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GAME = ROOT / "payload/game"
BACKEND = "red4ext/plugins/AiNpcCodexBridge/"
ADDON = "bin/x64/plugins/cyber_engine_tweaks/mods/AiNpcCodexBridge/"
FILES = [BACKEND + name for name in (
    "bridge.py", "bridge-common.ps1", "check.ps1", "config.example.json", "model_catalog.json",
    "start.ps1", "status.ps1", "stop.ps1", "login.ps1", "Start.cmd", "Stop.cmd", "Login.cmd", "README.ja.md", "README.en.md",
)] + [ADDON + name for name in ("init.lua", "bridge.mjs", "auto-start.mjs", "codex-connection.mjs", "convai-addon.json", "settings-map.json", "ui-catalog.json", "ui-localization.lua")]


def main():
    actual = {path.relative_to(GAME).as_posix() for path in GAME.rglob("*") if path.is_file()}
    if actual != set(FILES):
        raise RuntimeError("Payload membership differs from the explicit reviewed whitelist")
    entries = []
    for name in FILES:
        path = GAME / name
        if path.is_symlink():
            raise RuntimeError("Payload must contain regular source files")
        data = path.read_bytes()
        workspace = next((parent for parent in ROOT.parents if (parent / ".git").exists()
                          or (parent / "distribution/companion_addons").is_dir()), None)
        sensitive_roots = [Path.home()] + ([workspace] if workspace else [])
        for directory in sensitive_roots:
            variants = (str(directory).replace("\\", "/"), str(directory).replace("/", "\\"))
            if any(marker.encode("utf-8").lower() in data.lower() for marker in variants):
                raise RuntimeError("Payload contains a development-machine path")
        entries.append({"path": name, "bytes": len(data), "sha256": sha256(data).hexdigest()})
    manifest = {
        "schema": 1, "id": "codex-bridge", "version": "1.2.2-rc.1", "backendVersion": "1.2.0-rc.1", "addonVersion": "1.2.2-rc.1", "baseMod": "AI Companions 0.4.6",
        "addonApi": "1.1", "payloadRoot": "payload/game", "files": entries,
        "settingsNamespace": "addons.codex-bridge", "defaultModel": "codex-default", "defaultEffort": "auto",
        "modelIndexDefault": 11, "effortIndexDefault": 7,
        "stateDirectory": "%LOCALAPPDATA%/AiNpcCodexBridge", "port": 17865,
        "requiresPython": "AI Companions bundled app/python/python.exe or system Python 3.10+",
        "requiresCodex": "Native Codex CLI with --ephemeral, --ignore-user-config, --ignore-rules and tool-feature controls",
        "requiresUserLogin": "User signs in once with official CLI in the dedicated codex-home; no auth is copied",
        "osAutostartRegistered": False, "credentialsIncluded": False, "liveFilesModified": False,
        "gameplayVerified": False,
        "interfaceLanguages": ["en", "zh-cn", "zh-tw", "es", "pt-br", "fr", "de", "it", "pl", "cs", "hu", "tr", "ru", "uk", "ja", "ko", "ar"],
        "rootInstallerOwnedFiles": ["auto-feature.json"],
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"id": manifest["id"], "version": manifest["version"], "files": len(entries),
                      "bytes": sum(entry["bytes"] for entry in entries), "liveWrites": False}))


if __name__ == "__main__":
    main()
