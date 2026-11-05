# Changes

## Japanese 1.0.4-rc.1 / Party Conversations and Codex Bridge 1.2.2-rc.1

Publication review of the previous 0.4.6 previews. Internal feature IDs and user-data locations remain compatible.

- Make the source build independent of the developer's workspace, sibling projects and Vortex download inventory. Accept an explicit official Full ZIP and use readable source paths.
- Add matching release-family checks and clearer missing-Full-install diagnostics. Mixed generations do not silently choose an older combined recipe when the new shared loader is active.
- Harden the local Codex transport with per-user authentication, server verification and bounded requests. Use configured ports consistently, and start the backend only when needed by Codex or an explicit settings action.
- Give new installations a dedicated Codex home and an explicit one-time login helper. Preserve an existing shared-home configuration with a warning instead of copying authentication or silently changing it.
- Offer the CLI default model and automatic reasoning for new settings; retain legacy indices for saved settings and document account-dependent model availability.
- Make relationship reviews and automatic V audio opt-in for missing/new settings while retaining saved choices.
- Complete the Japanese-only exact-money path across Lua capture, validation, Japanese rendering and Dynamic info controls. Unknown values stay unknown; an actual zero is valid.
- Replace stale preview instructions with Japanese/English installation, update, removal, privacy, troubleshooting and source-build documents.
- Add publication receipts, public-source checks, upload materials and original title-card assets. No game recordings, extracted script corpus or personal state is added.

## Features retained from preview.3

- Companion-to-companion shared experience and directed relationship memory; optional bounded participation by V.
- V personality, first-person/detail settings, reply-length controls, early subtitles and a status HUD.
- Higher eligible companion/Johnny chatter options, with scene-interruption options and bounded continuations.
- Event-recovery handling for a stale world-suspension state, and V start-condition handling for the ordinary gameplay scene flag.
- Same-as-companions automatic V voice routing, using V's own reference and retaining captions when the route is unavailable.
- Character-led responses that allow disagreement, conditions, refusal and ordinary social reactions without inventing completed game actions.
- Japanese profiles and editorial examples, names, speech rules and context processing.

These changes are not claims of universal crash fixes, exact chatter frequency, guaranteed canonical dialogue, voice likeness or a performance improvement.
