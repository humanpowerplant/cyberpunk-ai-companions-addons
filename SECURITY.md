# Security and privacy reports

For a suspected exposure of credentials or an unsafe process/action boundary, **do not put real keys, tokens, full conversations, saves or personal paths in a public issue**. A minimal synthetic reproduction and affected versions are usually enough.

Use the repository host's private security-reporting facility if it is enabled. If it is unavailable, start with a public issue containing only a high-level description and ask for a private reporting channel; withhold exploit details and personal data.

The Codex bridge is intended for loopback use by the current player's account. Do not expose its port through port forwarding, a proxy or a LAN bind. The bridge does not provide remote account isolation or make arbitrary software running under your own Windows account trustworthy.

The project does not need administrator access, a Defender exclusion, disabled antivirus, a system execution-policy change or a Windows scheduled task. Do not use instructions claiming that these are required by this add-on.

Provider-side safeguards, account terms, quota limits and retention policies still apply. See [Privacy](docs/PRIVACY.md) for the local and remote data flow.
