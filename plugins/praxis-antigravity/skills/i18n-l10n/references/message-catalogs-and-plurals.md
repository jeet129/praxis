# Message catalogs & plurals

Worked examples supporting the "Message catalog format" and "No hardcoded strings / Plural-aware" disciplines in SKILL.md.

## ICU MessageFormat catalog example

```json
{
  "orderItems.count": "{count, plural, =0 {No items} one {1 item} other {# items}}",
  "orderTotal.label": "Total: {amount, number, ::currency/USD}",
  "lastUpdated": "Last updated: {date, date, ::yyyyMMdd}"
}
```

## No hardcoded strings

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

## Plural-aware (always)

Every count-related message uses ICU plural, never string concatenation:

```tsx
// Bad
<p>{count} item{count !== 1 ? 's' : ''}</p>

// Good
<p>{t('items.count', { count })}</p>
// where the message is: "{count, plural, =0 {No items} one {1 item} other {# items}}"
```

Plural rules vary wildly across languages. The `{count !== 1 ? 's' : ''}` pattern is English-only thinking; it produces nonsense translations.
