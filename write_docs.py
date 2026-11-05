"""Export reviewed static Nexus text and versioned file descriptions.

README Markdown is canonical, hand-reviewable source. This script never replaces
it with an old preview template. --check validates generated export freshness.
"""
from pathlib import Path
import argparse
import ast
import json

ROOT = Path(__file__).resolve().parent


def build_constants():
    tree = ast.parse((ROOT / "build_auto.py").read_text(encoding="utf-8-sig"))
    found = {}
    for row in tree.body:
        if isinstance(row, ast.Assign):
            for target in row.targets:
                if isinstance(target, ast.Name) and target.id in {"VERSIONS", "TITLES"}:
                    found[target.id] = ast.literal_eval(row.value)
    if set(found) != {"VERSIONS", "TITLES"}:
        raise ValueError("Build release constants must remain inspectable")
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    constants = build_constants()
    versions, titles = constants["VERSIONS"], constants["TITLES"]
    exports, metadata = {}, {}
    public_titles = {"japanese": "AI Companions 日本語会話・人物設定拡張", "codex": "AI Companions - Party Conversations and Codex Bridge"}
    summaries = {
        "japanese": "AI Companions 0.4.6の人物像・話し方・一人称とゲーム状況を日本語で調整する追加Mod。Vortexで導入。元ModのFull installが必要です。",
        "codex": "Companion-to-companion conversations, bounded optional replies by V, and an optional Codex CLI bridge. Also works with Gemini. Requires AI Companions 0.4.6 Full install.",
    }
    for feature in versions:
        for language in ("ja", "en"):
            source = ROOT / "nexus" / feature / f"description.{language}.bbcode.txt"
            exports[ROOT / "docs" / feature / f"NEXUS_DESCRIPTION.{language}.txt"] = source.read_text(encoding="utf-8")
        for language in ("ja", "en"):
            readme = (ROOT / "docs" / feature / f"README.{language}.md").read_text(encoding="utf-8")
            if versions[feature] not in readme or "0.4.6" not in readme:
                raise ValueError(f"README/version mismatch: {feature}/{language}")
        exports[ROOT / "docs" / feature / "CHANGES.txt"] = versions[feature] + " — AI Companions 0.4.6 / game 2.5\n\n" + (ROOT / "docs/CHANGELOG.md").read_text(encoding="utf-8")
        metadata[feature] = {
            "title": public_titles[feature], "version": versions[feature], "summary": summaries[feature],
            "categorySuggestion": "Translations" if feature == "japanese" else "Gameplay",
            "language": "Japanese" if feature == "japanese" else "English; Japanese guide included",
            "requiredMod": {"nexusModId": 35436, "version": "0.4.6 Full install for game 2.5", "url": "https://www.nexusmods.com/cyberpunk2077/mods/35436"},
            "tags": ["AI-Generated Content", "AI Media", "Dialogue", "Quality of Life"] + (["Japanese"] if feature == "japanese" else ["NPC Behaviours (AI)", "User Interface"]),
            "archive": titles[feature] + "-" + versions[feature] + "-Auto-Deploy-for-0.4.6.zip",
            "releaseType": "Release candidate; manual gameplay checklist remains separate",
            "descriptionFile": f"{feature}/description.{'ja' if feature == 'japanese' else 'en'}.bbcode.txt",
            "cover": f"../media/titlecards/{feature}-cover-1920x1080.png",
            "disclosure": "PERMISSIONS_AND_DISCLOSURE.ja.md",
        }
    exports[ROOT / "nexus/upload-metadata.json"] = json.dumps({"schema": 1, "game": "cyberpunk2077", "pages": metadata}, ensure_ascii=False, indent=2) + "\n"
    stale = []
    for file, text in exports.items():
        if args.check:
            if not file.is_file() or file.read_text(encoding="utf-8") != text:
                stale.append(file.relative_to(ROOT).as_posix())
        else:
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(text, encoding="utf-8")
    if stale:
        raise SystemExit("Run python write_docs.py to refresh: " + ", ".join(stale))
    print(json.dumps({"checked": args.check, "exports": len(exports), "versions": versions, "readmesOverwritten": False}))


if __name__ == "__main__":
    main()
