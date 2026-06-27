---
name: i18n-l10n
description: Internationalization and localization done right. Locale-aware formatting (numbers, dates, currencies), ICU MessageFormat for variable + plural-aware strings, RTL layout support, locale-routing strategy, translation pipelines, fallback handling, locale switching UX. Build it in early — retrofitting is painful and bug-prone. Frontend Developer applies during implementation; UX Designer establishes the i18n requirements at design time. Use whenever new user-facing strings are introduced, when adding a new locale, when designing locale-switching UX, or when investigating locale-specific rendering bugs.
---

# i18n & L10n


<!-- praxis:metadata:begin -->
```yaml
capability: quality-and-security
domain: frontend
state: active
dependencies:
  - stack-web-frontend
  - design-system
  - frontend-architecture
triggers:
  - "implementing user-facing strings in any component"
  - "adding support for a new locale"
  - "designing locale-switching UX"
  - "investigating locale-specific layout / rendering bugs"
  - "establishing i18n architecture for a new project"
outputs:
  - i18n architecture decision (locale routing, message catalog format, fallback chain)
  - message catalogs per locale (translation files)
  - locale-routing plan (URL strategy + auto-detection)
  - translation pipeline (translator workflow, sync, review)
  - RTL support design (CSS + component-level)
  - locale-aware formatting plan (Intl APIs)
consumers:
  - frontend-developer (primary; applies during implementation)
  - ux-designer (consumes for design decisions; consulted on RTL)
  - product-manager (consumes for content / market strategy)
  - tech-writer (consumes for documentation localization)
references: []
```
<!-- praxis:metadata:end -->

Internationalization (i18n) = building the app so it *can* support multiple locales. Localization (l10n) = the actual translations and locale-specific content. Build i18n from day one even if only one locale ships initially; retrofitting i18n into an established codebase is a multi-quarter project that touches every component.

The principle: **no user-facing string is ever hardcoded; every locale-affected value (date, number, currency, plural) is formatted via the locale-aware API.**

## When this skill fires

- A user-facing string is being added — through the i18n library, not as a literal.
- A new locale is being added — establish translation, layout, and routing.
- Locale-switching UX is being designed.
- Locale-specific bugs are reported (RTL layout broken; date in wrong format; plural rules wrong).
- A new project is being set up — establish i18n architecture before features land.

## The architecture decisions

### 1. Library choice

| Library | When |
|---|---|
| **next-intl** | Next.js projects. Modern, App Router-friendly, ICU MessageFormat. |
| **react-intl (FormatJS)** | React projects broadly; mature; ICU MessageFormat. |
| **i18next** | Vue / Angular / general; broad ecosystem; flexible. |
| **vue-i18n** | Vue / Nuxt projects. Composition API support. |
| **Angular's @angular/localize** | Angular projects. Built-in. |

Default for new React projects: **next-intl** (Next.js) or **react-intl** (other React). For Vue: **vue-i18n**. For Angular: **@angular/localize**.

### 2. Message catalog format

The translator-facing format. The shared standard: **ICU MessageFormat**.

```json
{
  "orderItems.count": "{count, plural, =0 {No items} one {1 item} other {# items}}",
  "orderTotal.label": "Total: {amount, number, ::currency/USD}",
  "lastUpdated": "Last updated: {date, date, ::yyyyMMdd}"
}
```

ICU MessageFormat handles:
- **Plurals** correctly per locale (English has 2 forms; Polish has 3; Arabic has 6).
- **Genders** in languages where they affect translation.
- **Selects** for arbitrary branching.
- **Date / number / currency formatting** within the message.

JSON catalogs per locale: `en.json`, `de.json`, `ja.json`. One file per locale; one key per message.

### 3. Locale routing

How the URL encodes locale:

| Strategy | Example | Pro | Con |
|---|---|---|---|
| **Path-based** | `/de/products` | SEO-clear; sharable per locale. | URL bookkeeping. |
| **Subdomain-based** | `de.example.com/products` | Cleaner; separate SEO surface. | DNS / SSL setup per locale. |
| **Query parameter** | `/products?locale=de` | Simple. | Worst for SEO; not preferred. |
| **No URL** | (locale stored in cookie / accept-language) | Simple. | Not shareable per locale. |

Default: **path-based** for SEO-relevant content. **Subdomain** for very large multi-locale sites. **No URL** acceptable for authenticated app-like surfaces with user-stored preference.

### 4. Locale auto-detection

The first-visit detection chain:

```
1. URL explicit (path or subdomain) → highest priority
2. User preference (logged in user's saved locale)
3. Cookie from prior visit
4. Accept-Language header (browser preference)
5. Geo-IP guess (lowest priority; for first visit only)
6. Default locale (fallback)
```

Always allow override. The UI's locale switcher should be visible and stable.

### 5. Fallback chain

When a message is missing in the requested locale:

```
1. Try the exact locale (de-AT).
2. Fall back to the language (de).
3. Fall back to the default (en).
4. Last resort: show the message key (signals missing translation in dev).
```

Missing translations are tracked; in production they shouldn't show the key (use the default locale). In dev, show the key to surface the gap.

## The disciplines

### No hardcoded strings

Every string the user sees goes through the i18n library:

```tsx
// Bad
<button>Save</button>

// Good
<button>{t('save')}</button>

// Bad
<p>You have 5 items in your cart.</p>

// Good — uses ICU plural
<p>{t('cart.items', { count: 5 })}</p>
```

Static strings in error responses, validation messages, tooltips, alt text — *all* go through i18n.

CI / lint rules can enforce: a linter rule that flags string literals in JSX (ESLint `react/jsx-no-literals`); manual review for what slipped through.

### Plural-aware (always)

Every count-related message uses ICU plural, never string concatenation:

```tsx
// Bad
<p>{count} item{count !== 1 ? 's' : ''}</p>

// Good
<p>{t('items.count', { count })}</p>
// where the message is: "{count, plural, =0 {No items} one {1 item} other {# items}}"
```

Plural rules vary wildly across languages. The `{count !== 1 ? 's' : ''}` pattern is English-only thinking; it produces nonsense translations.

### Locale-aware formatting

Numbers, dates, currencies, times — through the locale-aware API:

```tsx
// Bad
<p>Total: ${amount.toFixed(2)}</p>

// Good
<p>{t('total', { amount })}</p>
// where the message: "Total: {amount, number, ::currency/USD}"

// Or directly:
<p>Total: {new Intl.NumberFormat(locale, { style: 'currency', currency: 'USD' }).format(amount)}</p>
```

Use the platform's `Intl` API (built into modern browsers and Node) for date/number/currency formatting. The library wraps this.

### RTL support

For Arabic, Hebrew, Persian, Urdu, etc. (right-to-left layout):

```html
<html dir="rtl" lang="ar">
```

CSS implications:
- **Logical properties**: `margin-inline-start` instead of `margin-left`; `padding-inline-end` instead of `padding-right`. Auto-flips in RTL.
- **Logical units**: `inset-inline-start` instead of `left`.
- **Icons that imply direction** (arrows): may need flipping in RTL; the design system documents which.
- **Test in RTL** during design and development; don't bolt on later.

Modern CSS supports logical properties broadly; use them by default even in LTR-only projects (future-proof).

### Locale-switching UX

The user-visible control:

- **Prominent** — visible in header / footer; not buried in settings.
- **Self-described** — show each locale in its own language ("Deutsch", not "German").
- **Persistent** — saves the user's choice (cookie or user profile).
- **Available to anonymous users** — not gated behind login.

## Translation pipeline

The workflow that gets translations from translators into the catalog:

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

### Translation context

Translators are blind without context. The catalog includes:

- **Key naming** — meaningful (`cart.items.count`, not `msg_42`).
- **Description per key** — short note about where it appears + tone.
- **Variable types** — what's `{count}`? An integer? Decimal?
- **Screenshots / preview** — for translation tools that support it.

Style guide per locale: tone (formal vs. informal), capitalization rules, currency placement, etc. Lives in `.project/procedural/i18n-style-guide.md`.

## Outputs

| Output | Location |
|---|---|
| i18n architecture decision + ADR | `.project/decision/` |
| Default locale message catalog | `src/locales/en.json` (or framework convention) |
| Per-locale catalogs | `src/locales/{locale}.json` |
| Locale routing config | framework-specific (e.g., `next.config.js` `i18n` block) |
| RTL CSS conventions | in `design-system` |
| Translation pipeline doc | `.project/procedural/i18n-pipeline.md` |
| Style guide | `.project/procedural/i18n-style-guide.md` |

## Mode handling (G/B)

**Greenfield.** Build with i18n from day one. Even if only English ships, every string is i18n-routed; ICU MessageFormat used for plurals.

**Brownfield.** Audit existing strings. Common findings: hardcoded strings everywhere; plural bugs (`{n} item${n > 1 ? 's' : ''}`); dates / currencies in fixed format. Migrating is multi-quarter; prioritize new code first; old code via opportunistic slice work.

## What this skill does not do

- Choose the supported locales (product / business decision).
- Translate the strings (translators do; this skill provides the pipeline).
- Design locale-specific imagery / illustrations (UX Designer + content team).
- Locale-specific compliance (data residency, content restrictions) — that's `compliance-privacy`.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "English-only is fine; we'll i18n later." | Retrofit cost is 5-20x build-in cost. If you're shipping anywhere beyond a tight market, i18n from day one. |
| "We'll just translate the strings." | i18n is strings + plurals + dates + numbers + currencies + names + addresses + RTL + length-tolerance + locale-specific layouts. |
| "Translators handle plurals." | Plurals have CLDR rules. Use a library that supports them; don't roll your own. |
| "Server-side i18n is the only model." | Client-side i18n exists. The right place to translate depends on caching, latency, and SEO needs. |
| "RTL is easy with CSS direction: rtl;" | RTL means flipping icons, layouts, gestures, and copy logic. Not a one-liner. |
| "Translation memory is finance's tool." | TM saves cost + improves consistency. Engineering benefits directly. |
| "We support en-US, en-GB is the same." | Date formats, currency, spelling, idioms differ. Locales are not interchangeable. |

## Verification

You are done when:

- [ ] Strings externalized in resource files; no hardcoded user-facing strings.
- [ ] ICU MessageFormat (or equivalent) supports plurals + gender + select.
- [ ] Date / number / currency formatted per locale (Intl APIs).
- [ ] RTL layout tested for RTL locales (Arabic, Hebrew).
- [ ] Length tolerance in UI components (German is ~30% longer than English).
- [ ] Locale switcher works without page reload (or is intentionally page-reload).
- [ ] Fallback chain for missing translations documented.
- [ ] Translation workflow + memory documented.
- [ ] Locale-aware tests in CI (at least one non-en locale exercised).

Evidence to check:
- Locale switch produces correct strings + format + layout for a sample.
- A new locale can be added by translators without engineering changes.

## Anti-patterns

- Hardcoded strings ("just for now").
- String concatenation for plurals (`item${n > 1 ? 's' : ''}`).
- Date / number / currency formatting hardcoded.
- `dir="ltr"` assumed (breaks RTL).
- Locale stored in localStorage only (lost across devices).
- Locale switcher hidden in settings.
- Translation files in code reviews without translation tool (translators can't access).
- Adding a new locale "just" by translating the JSON (ignores RTL, locale-specific formats, plural rules).
- Plurals: `{n} item${n > 1 ? 's' : ''}` — English-only thinking.
- "We'll add i18n in v2" — costs 5x more than building it in.
