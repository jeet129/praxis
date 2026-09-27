# Translation pipeline

The workflow that gets translations from translators into the catalog, referenced from the "Translation pipeline" section of SKILL.md.

```
1. Developer adds new key in en.json (default locale).
2. CI detects new key + extracts to translation tool (Lokalise, Crowdin, Transifex, Phrase, or git-based).
3. Translators receive notifications; provide translations.
4. Translation tool produces PR with updated locale files.
5. PR reviewed (lightweight; verifies format + context); merged.
6. CI deploys updated catalogs.
```

For solo / small projects: even a git-based workflow (PRs from a translation contractor) beats ad-hoc.

For larger projects: a managed translation platform with context-sharing (screenshots, glossary, style guide) produces higher quality.

## Translation context

Translators are blind without context. The catalog includes:

- **Key naming** — meaningful (`cart.items.count`, not `msg_42`).
- **Description per key** — short note about where it appears + tone.
- **Variable types** — what's `{count}`? An integer? Decimal?
- **Screenshots / preview** — for translation tools that support it.

Style guide per locale: tone (formal vs. informal), capitalization rules, currency placement, etc. Lives in `.project/procedural/i18n-style-guide.md`.
