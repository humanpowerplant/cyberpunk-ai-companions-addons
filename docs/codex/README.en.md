# AI Companions — Party Conversations and Codex Bridge

**1.2.2-rc.1 / AI Companions 0.4.6 / Cyberpunk 2077 2.5 / Windows**

Companions can talk to one another about shared experiences, retain directed memories of each other, and optionally hear a short reply from V. An optional local bridge lets Codex CLI provide the generated text. **The conversation features also work with Gemini and other supported text providers; using Codex is a separate choice.**

## Install with Vortex

1. Install the [original mod's 0.4.6 Full install for game 2.5](https://www.nexusmods.com/cyberpunk2077/mods/35436) and its requirements.
2. Close the game and its conversation service. Install this ZIP in Vortex, enable it after the original mod, and Deploy.
3. Disable older copies of this add-on and the old standalone **CodexBridge-Settings** add-on. Its menu is included here.
4. Start the game normally. No `apply.cmd` step is needed. Open Companion Manager, then **Conversations** for the new conversation options.

If using the Japanese add-on too, use **Japanese 1.0.4-rc.1 / this add-on 1.2.2-rc.1**. Conflict order: original mod → Party/Codex add-on → Japanese add-on. Do not combine old and new release generations.

## Start with conversation features

Keep your working text provider selected. Invite two companions using the original mod, then travel with them. Chatter uses the original mod's availability and scheduling, so it will not occur at an exact clock rate. For a short trial, optionally choose **Conversations → Companions speak up → Often (30/hour)**; the original new-user Normal setting can be quiet for several minutes. Restore your preferred frequency afterwards.

| Option | What it changes | New-user default |
| --- | --- | --- |
| Companion memory | Remembers delivered conversation and observed/shared events locally | On |
| Relationship updates | Uses an additional AI review to update directed relationships | Off |
| V automatic replies | Off, asked-only or contextual participation | Off |
| Automatic V voice | Adds speech to an eligible V response | Off |
| Automatic V voice engine | Same as companions, or V's separate manual engine | Same as companions |
| V personality / first person / detail | The voice and priorities used for generated V replies | Player-selectable |
| High-frequency chatter and scene chatter | More opportunities to speak; may increase interruptions and requests | Opt in; existing choices are retained |

For a first trial, enable **asked-only** V replies, keep one reply per round, and leave relationship review off. Later, contextual replies can allow V to participate when the planner considers a reply useful. V does not answer every remark. The reply cap, cooldown and round lifetime prevent an endless automatic conversation.

V's automatic voice uses V's own reference, even when it shares the companions' voice engine. Subtitles are displayed before waiting for generated audio; if a usable voice route is unavailable, the line can remain as subtitles. Manual typed/microphone V-voice settings stay separate. Japanese V speech also requires a compatible engine and Japanese reference from the original mod.

**Edit V personality** opens a local browser editor. Choose a V1–V4 memory slot manually when changing playthrough. These slots are not automatically linked to game save names. See [Privacy](../PRIVACY.md) for retained data and additional model requests.

## Optional: use Codex for replies

**Codex CLI is a cloud client. It is not a local LLM and this add-on does not make usage unlimited or free.** Access and limits depend on your account. The CLI, login and subscriptions are not bundled. Follow the [official installation and authentication instructions](https://developers.openai.com/codex/cli/).

The release uses a dedicated Codex home for new installations, keeping general coding instructions separate from NPC dialogue. In your game folder, open **`red4ext/plugins/AiNpcCodexBridge/Login.cmd`** yourself once and complete the official Codex login with your own eligible ChatGPT account. It uses the bridge's dedicated per-user home. This bridge rejects API-key authentication and does not inherit an environment API key for billing. Normal game startup never completes authentication on your behalf. An existing installation can retain a shared home for compatibility; check its status warning and use the login helper's migration prompt before switching it.

In the original mod's **AI provider → Custom** settings, use:

| Setting | Default local bridge value |
| --- | --- |
| Endpoint | `http://127.0.0.1:17865/v1` |
| Model | `codex-default` |
| API key field | No manual key is required for the bundled integration; it uses a local connection token |

The bridge is started for the local integration. Do not expose the port to a LAN or the internet. If you change the port in bridge configuration, use that port in the Custom endpoint too.

Open **Content packs → Codex Bridge** for model and reasoning settings. Start with the **CLI default** model and **automatic** reasoning choices. Older preset models are retained for saved-setting compatibility and may not exist or be available to your account. Custom model IDs are an advanced configuration option; use identifiers your CLI account actually supports. Unsupported models or efforts report an error rather than silently choosing a different model.

Codex is run in a dedicated work area with a read-only sandbox. Shell, external integrations and instruction loading are restricted by the bridge. This is a containment policy, not a claim that every native Codex tool is removed: the CLI can register tools whose actions are rejected by its sandbox. The original service's content policies still apply.

## Update and remove

Close the game before changing files. Disable the previous add-on version, enable the new version and Deploy. Keep the pair in sync if using Japanese support. Personal settings, character edits, memories and authentication are not replaced by packaged defaults.

To remove, disable this add-on and Deploy, then start normally. If the Japanese add-on remains, its features remain. With both disabled, the original startup copier restores the original code selection. User data is retained; removal is not a privacy-data wipe.

## Scope and limitations

This release candidate targets Vortex on Windows, game 2.5 and base mod 0.4.6. Other base versions, game 2.31, MO2 and Proton are not verified. Automated fixtures exercise source loading, composition, removal and request boundaries. They are not a substitute for real gameplay, voice-quality or cross-PC tests. See [Compatibility](../COMPATIBILITY.md) and [Troubleshooting](../TROUBLESHOOTING.md).

Original mod by Alystria AI. Convai remains available. The upstream use license and third-party notices apply. No model weights, game recordings, runtime binary, personal credentials or dialogue history is included. Generative AI was used for code, text and documentation.
