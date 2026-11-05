# Publication review — 0.4.6 release candidate

Review date: 2026-11-06. Release pair: **Japanese 1.0.4-rc.1 / Party Conversations and Codex Bridge 1.2.2-rc.1**. This report describes the candidate, not a stable-playthrough certification.

## Changes made during review

- Removed build dependencies on the developer's workspace, sibling source trees and Vortex download inventory. A separately supplied official Full ZIP is the only game-related build input.
- Materialized readable source filenames; kept generated content-addressed payloads out of normal authoring.
- Removed developer-installed Codex discovery from startup fixtures; made isolated Windows fixtures import core modules directly and use canonical temporary paths, including hosted-runner 8.3 aliases.
- Made effective game-path fallback relative for Japanese, Codex and combined variants, preserving an explicit launcher environment override.
- Added paired-release checks, mixed-generation fallback, missing-Full diagnostics, safe Windows relative names, and current-build checks before finalization.
- Added authenticated loopback transport, fresh server proof, consistent configured ports, request bounds, deadlines and cancellation. External providers never receive the local bridge token.
- Restricted inherited CLI environment, added a dedicated Codex home and explicit one-time login helper, retained saved model indices, and made new models/reasoning use CLI default/automatic.
- Made Codex startup lazy; Gemini and other text-provider use does not start an unused Codex backend.
- Made new-user relationship review and V automatic audio opt-in. Saved explicit choices retain their meaning.
- Completed Japanese-only exact money capture/validation/rendering and privacy filtering. Unknown and failed values remain unknown.
- Replaced stale preview instructions, fixed packaged document links, and prepared Japanese/English upload text and clearly labelled conceptual media.

## Recorded checks

| Check | Recorded result | Scope |
| --- | --- | --- |
| Backend Python suite | 40/40 passed | Synthetic runner, local random ports, no real login/model |
| Full Node unit command | 51/51 passed, no skips | Local/fake transport, PowerShell stubs, owned process lifecycle |
| Composer/transport focused checks | Passed | Included in the above Node command; not an extra gameplay count |
| CET selector | 49 assertions on each of Lua 5.4 and stock LuaJIT 2.1 | Selector and shims; not in-game OpenResty |
| Japanese Lua→JS and opt-ins | 36 Lua assertions per engine; 37 Node assertions per tested voice/default variant | Actual modules with synthetic native adapters |
| Deployment/removal | 7 regular scenarios + 2 mixed-release scenarios passed | Actual official copier, final service entry stubbed |
| Relocated source-only build | Passed from another drive with a Japanese path | Publication allowlist only, same one-command build |
| Publication scanner fixtures | 19/19 passed | Synthetic secrets/paths/ZIP cases |
| Source and runtime ZIP inspection | No errors or broken relative links in reviewed files | Explicit allowlist and bounded text inspection |

The publication inspection retains two explained classes of warning: fictional attribution email text in scanner fixtures, and the original fallback line inside each ZIP's verified official restore source. The latter is narrowly checked against the original 0.4.6 source/manifest; the effective add-on variants use relative paths. The original restore source is not edited in a way that would invalidate its official manifest.

Each runtime ZIP contains approximately **11.437 MiB of uncompressed original reset/pristine source** for code restoration and migration, with upstream license/notices. It does not contain the original Full runtime, game recordings, extracted script corpus, weights, private state or credentials.

## Remaining limits

No game, real Codex model, real authentication or voice synthesis was launched for this publication review. The current candidate still needs the manual [gameplay checklist](TESTING.md). Earlier conversational playtesting is not proof that all new security/migration paths were exercised in game.

Full's native launcher can fail before the dedicated Node diagnostic if the Node runtime itself is missing. Matching package families assume complete deployment and the new shared loader winning file conflicts; an interrupted copy across separate CET/Node trees is not a cross-folder transaction.

Read-only CLI policy is not a zero-native-tool or zero-file-read guarantee. Provider policies, account limits and the operating-system trust boundary still apply. Malicious software running under the same Windows account is outside the bridge's isolation guarantee.

The Japanese profile count and editorial-example coverage are audited, but do not establish every lore statement or utterance as canonical. Fifty-two profiles, including major characters, retain their upstream English sample field. Public data excludes the private game-extraction/audio collection used during development.

## 日本語

この版は、配布手順・環境依存・認証・既定値・公開データ・文書を見直したRCです。自動確認は通っていますが、現在版での実プレイと実際の専用Codexログインは未実施です。未確認を済んだと表示せず、同梱の手順と確認範囲を添えて配布してください。公開候補の準備と、Nexusへの公開操作は別です。
