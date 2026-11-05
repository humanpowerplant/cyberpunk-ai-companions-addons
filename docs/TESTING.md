# Release verification

Automated results belong to the exact source and package version that produced them. Record the release pair and the commands used. No binary/archive-wide SHA scan is required; the runtime's source-content addresses are part of its existing recipe format.

## Automated scope

- Parse/compile changed Python, JavaScript and Lua, and import affected modules to catch missing exports.
- Run backend protocol and CLI-argument fixtures with a fake runner; do not require real credentials or spend model quota in CI.
- Check standalone Japanese, standalone Party/Codex, both, reversed overlay order, removing either and removing both.
- Check matching and mixed release families, missing Full install, spaces/Japanese characters, and a relocated source tree without the developer's sibling folders.
- Exercise the original startup copier with a service-entry marker. Retain personal state sentinel files.
- Verify new-user defaults and explicit saved values, money unknown/zero/privacy controls, bounded/cancelled V replies, and the current voice route.
- Check source/ZIP publication allowlists, forbidden data, relative paths, documentation links and notices.

These are code and fixture checks. A marker at the service entry does not mean the real service, game or audio ran.

## Manual gameplay before a stable release

- [ ] Clean installation: original 0.4.6 Full install + dependencies + one add-on. No compilation/startup errors; manager opens.
- [ ] Japanese-only: choose Japanese voice language; Japanese profile and game-state text reach a normal NPC conversation.
- [ ] Party/Codex-only: an existing non-Codex provider still works without a Codex login.
- [ ] Two invited companions: group chat and automatic chatter address each other, without unlimited continuations.
- [ ] V asked-only, then contextual: an eligible V caption appears, and optional V audio uses V's own voice. Manual player input takes priority.
- [ ] Save/load, fast travel, vehicle entry/exit, an event and the return to normal manager interaction.
- [ ] Disable each add-on separately, then both: correct remaining/original behavior and retained user data.
- [ ] Dedicated Codex login, first completion, model/default changes, a quota or cancellation error, then normal recovery.
- [ ] Exit the game: owned bridge/CLI/voice/browser processes finish. Manually started unrelated tools remain unaffected.
- [ ] Capture the screenshots in the media plan with credentials and personal data hidden.

## 公開候補の扱い

RCは、確認範囲を明示して配布するための公開候補です。未実施の実プレイ・他PC・サービス契約の確認を済んだと表記しないでください。画面写真や動画も実際の機能を撮り、作例・図とは区別します。自動検証の最終結果は、その公開版のreview資料で確認してください。
