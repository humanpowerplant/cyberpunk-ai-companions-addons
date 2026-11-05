# Contributing

Keep changes specific to Cyberpunk 2077 and compatible with AI Companions 0.4.6. Retain the upstream license, copyright notices and a working Convai option. Do not present this project as an official OpenAI or original-author release.

Before changing a feature, read [Development](docs/DEVELOPMENT.md), the relevant source module, and its tests. Shared loaders must behave identically in both add-ons. Check standalone, combined, upgrade and removal behavior whenever a recipe, selector or shared module changes.

Do not commit credentials, local state, conversation history, voice recordings, game archives, extracted game scripts, generated model caches or private crash dumps. Use synthetic test data. Describe a bug with versions, settings and a short reproduction, rather than a complete save or conversation history.

Japanese speech rules should distinguish a character's first-person form, register, relationships and knowledge limits. Do not assign a pronoun from gender alone. Describe uncertain behavior as uncertain. Public examples should be original editorial examples; game quotations and local extraction output belong outside the distribution.

Preserve existing player settings. Defaults for new users may change, but an explicit saved value must keep its meaning. New cloud requests, data retention or automatic speech require clear options and documentation.

Tests using fixtures are useful evidence, but do not label them as gameplay or cross-PC verification. Record untested paths plainly. Never weaken CLI isolation, token checks, origin restrictions, bounds or cancellation to make a test pass.
