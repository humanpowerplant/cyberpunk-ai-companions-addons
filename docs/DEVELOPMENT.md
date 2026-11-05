# Build and maintain

The repository is source-only. End users install the release ZIPs in Vortex; they do not need this toolchain. No local game state, official Full ZIP or authentication belongs in Git.

## Prerequisites

- Python 3.10+ for building; the targeted game's bundled Python is used by the installed integration.
- Node.js 24 recommended for source checks and the original copier fixture. The builder accepts `--node <executable>`.
- Development-only Lua wheels: `python -m pip install -r requirements-dev.txt`.
- The original author's **AI Companions 0.4.6 Full install for game 2.5**, downloaded separately as a ZIP. Do not commit or mirror it.

## One-command build

From the repository root:

```powershell
python build_auto.py --upstream-archive "<path-to-official-0.4.6-full.zip>"
```

The path is an example; supply your downloaded official file. This reads only required source entries, builds both package trees, runs loader/composition checks and finalizes the release ZIPs. It does not start a game, use a real Codex account, synthesize voice or install anything into the game.

The repository's `.gitattributes` disables automatic line-ending conversion. Preserve source bytes when checking out or exporting recipe inputs; do not remove that setting while keeping old content-address metadata.

Use `--build-only` only when developing package trees. It does not certify a release. Generated `build/`, `audit/` and `releases/` are not source inputs. The build must not depend on sibling workspaces or a developer-specific download inventory.

## Structure

- `common/`: shared startup composition, CET selection and local Codex transport helpers.
- `base_features/` and `overrides/`: explicit feature recipes with readable source files. These produce private content-addressed payloads for the existing runtime format.
- `codex_source/`: backend, process helpers, CET/Node add-on, model/UI metadata and backend fixtures.
- `docs/`: canonical user and developer Markdown. `write_docs.py` exports the reviewed Nexus text and versioned file descriptions; it never replaces READMEs with a preview template.
- `nexus/`: BBCode descriptions, upload metadata, disclosure and publishing guide.
- `media/`: original geometric title cards and a separate real-screenshot plan.
- `tests/`, `tools/`: fixtures and publication checks. Game files, login state and model calls are unnecessary for ordinary unit checks.

## Focused checks

```powershell
python write_docs.py --check
python -m unittest discover -s codex_source/tests -p "test_*.py"
python -m unittest discover -s tests -p test_publication_check.py
node --test tests/compose.test.mjs tests/codex-transport.test.mjs
node tools/run_node_tests.mjs
python tests/run_cet_lua.py
```

JavaScript tests under `codex_source/tests` and the remaining startup tests exercise mocked local processes and transports. On Windows the login helper tests execute PowerShell with the final CLI launch stubbed; they must not call the user's real login.

The fuller checks require the separately supplied official archive:

```powershell
python tests/auto_packages.py --upstream-archive "<path-to-official-0.4.6-full.zip>"
python tests/public-ux-integration.py --upstream-archive "<path-to-official-0.4.6-full.zip>"
python tests/portable_build.py --upstream-archive "<path-to-official-0.4.6-full.zip>"
```

The portability check copies only the publication allowlist to a new temporary location, then runs the same build. Use its `--destination` to test another writable drive. Results can record local paths in ignored `build/`; do not copy those raw logs into a public source archive.

## Publication checks

Update `.publication-files.json` through the repository's allowlist generator after adding a public source or document. Review the list; do not replace it with an unrestricted recursive ZIP operation.

```powershell
python tools/publication_check.py --root . --strict-links --max-text-bytes 4194304 --json
```

Pass each exact runtime ZIP with repeated `--zip` arguments before publication. Keep the text limit high enough to include the profile JSON. No warning about skipped text should be represented as a completed content scan. Fixture-only literals should be clearly marked; do not weaken secret detection to accommodate an opaque test token.

The GitHub workflow runs source/unit checks without an official archive or live authentication. Full-package and gameplay verification are separate. See [Testing](TESTING.md) for manual checks.

## Change boundaries

Keep feature IDs and saved-index semantics stable. Update both packages together when their shared loader or release family changes. Preserve original exports used by other upstream modules; syntax checking alone will not find a missing named export.

Any CLI change must retain environment isolation, read-only policy, bounded input/output, authenticated loopback transport, process ownership, deadlines and cancellation. Never make a test pass by silently relaxing guards. CLI native tool registration is not identical to tool execution permission; document the actual boundary.

Retain LICENSE and notices and a functional Convai option. Do not redistribute game recordings, extracted game dialogue corpora, model weights or personal settings. Public Japanese examples are editorial translations/style examples; exact-quotation exclusions are useful evidence, not a blanket originality or legal guarantee.

## 日本語

通常の利用者はビルド不要です。開発する場合だけPython・Node・requirements-devと、別途入手した公式0.4.6 Full ZIPを用意し、`--upstream-archive`で指定します。個人のインストール場所・Vortexの履歴・ゲーム設定・認証を必要とするビルドには戻さないでください。実ゲームの確認は自動fixtureと分け、元Modが更新された場合は新しい対応版として差分を見直します。
