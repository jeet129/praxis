# Locale-aware formatting & RTL support

Worked examples supporting the "Locale-aware formatting" and "RTL support" disciplines in SKILL.md.

## Locale-aware formatting

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

## RTL support

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
