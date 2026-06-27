---
name: frontend-performance
description: Frontend perf discipline. Core Web Vitals (LCP / INP / CLS) target setting, bundle-size budgets per route, code splitting, image and font optimization, prefetch/preload strategy, Lighthouse CI as release gate, RUM-based regression detection. Frontend Developer applies during implementation; Platform/SRE wires Lighthouse CI; performance regressions fail the merge gate.
---

# Frontend Performance


<!-- praxis:description:full -->
## Full description

Frontend perf discipline. Core Web Vitals (LCP / INP / CLS) target setting, bundle-size budgets per route, code splitting, image and font optimization, prefetch/preload strategy, Lighthouse CI as release gate, RUM-based regression detection. Frontend Developer applies during implementation; Platform/SRE wires Lighthouse CI; performance regressions fail the merge gate. Use whenever new FE features are being implemented, when Lighthouse score degrades, when investigating user-reported slowness, or when establishing the perf-budget per route.

<!-- praxis:description:end -->


<!-- praxis:metadata:begin -->
```yaml
capability: quality-and-security
domain: frontend
state: active
dependencies:
 - nfr-definition
 - stack-web-frontend
 - design-system
 - observability
triggers:
 - "implementing a new frontend feature"
 - "Lighthouse score degrades on a PR"
 - "investigating user-reported slowness"
 - "establishing performance budget per route"
 - "designing image / font / asset loading strategy"
outputs:
 - performance budget per route (LCP / INP / CLS / bundle-size thresholds)
 - Lighthouse CI configuration + thresholds
 - RUM (Real User Monitoring) dashboard spec
 - optimization backlog (per regression / per opportunity)
 - bundle-size analysis (per route, with anomaly alerts)
consumers:
 - frontend-developer (primary; applies during implementation)
 - ux-designer (consumes budgets for design choices)
 - platform-sre (wires Lighthouse CI + RUM)
 - cicd-pipeline (enforces budgets as merge gate)
references: []
```
<!-- praxis:metadata:end -->

The discipline that keeps the user-facing app fast as features land. Backend performance (`performance-testing`) defends server-side targets; this skill defends *user-perceived* performance. A page that renders in 500ms server-side but takes 8 seconds to become interactive on a mid-range phone has a frontend problem, not a backend problem.

The principle: **measure what users experience; budget what affects experience; gate regressions before merge.**

## When this skill fires

- A new frontend feature is being implemented — verify the perf budget per affected route.
- Lighthouse CI fails a PR — investigate the regression.
- Users report slowness — RUM data isolates the affected route + device class.
- New routes are being added — establish the perf budget.
- Asset loading strategy needs design (images, fonts, third-party scripts).

## Core Web Vitals

The three Google-defined metrics that capture user-perceived performance:

| Metric | What it measures | "Good" threshold |
|---|---|---|
| **LCP** (Largest Contentful Paint) | When the largest visible content rendered. | < 2.5s |
| **INP** (Interaction to Next Paint) | Latency of user interactions (replaces FID). | < 200ms |
| **CLS** (Cumulative Layout Shift) | Visual stability during load. | < 0.1 |

These map directly to user experience:

- LCP slow → page feels slow to load.
- INP slow → page feels unresponsive.
- CLS high → page jumps around as it loads (annoying; mis-clicks).

Each project's NFR register specifies targets per route — typically "Good" for landing and primary user-journey routes; "Needs improvement" can be acceptable for admin / low-traffic routes.

## The performance budget

Per route, the budget specifies:

```yaml
# routes: /products/:id
budget:
 lcp_p75_ms: 2500 # 75th percentile field data
 inp_p75_ms: 200
 cls_p75: 0.1

 javascript_kb_compressed: 200 # bundled + compressed
 css_kb_compressed: 30
 images_kb_total: 500
 fonts_kb_total: 100
 total_kb_compressed: 850

 lighthouse_performance_min: 90
 lighthouse_accessibility_min: 95
 lighthouse_best_practices_min: 95
 lighthouse_seo_min: 90
```

Budgets are tracked per route, not just app-wide. The home page's budget differs from the admin dashboard's.

## Bundle-size discipline

JavaScript is the dominant performance cost. Strategies:

### Code splitting

Per route (default in modern frameworks):

```typescript
// Next.js / Remix / Vue Router / Angular: file-based routing produces per-route chunks
// Manually:
const HeavyChart = lazy( => import('./HeavyChart'));
```

Per feature (where features within a route are conditional):

```typescript
const ProDashboard = lazy( => import('./ProDashboard'));
// Loaded only when user is Pro tier
```

Bundle analysis in CI: `next-bundle-analyzer`, `webpack-bundle-analyzer`, `rollup-plugin-visualizer`. Per-route bundle sizes tracked over time.

### Tree-shaking

Every import is per-symbol, not per-module:

```typescript
// Good
import { useState } from 'react';

// Bad — pulls in the whole library
import * as React from 'react';
```

ESM modules, sideEffects: false in package.json, proper dependency exports.

### Third-party scripts

Each third-party script is a regression target. The discipline:

- **Audit** — what does each script add? Analytics, monitoring, marketing pixels, A/B testing.
- **Defer / async** — most third-party scripts should be `defer` or `async`. Synchronous loading blocks rendering.
- **Self-host where possible** — fonts, analytics scripts via your own CDN reduce DNS lookups.
- **Set budgets** — total third-party weight per page; reject additions beyond.

Common offenders: tag managers (load 10+ scripts), chat widgets, A/B testing tools, marketing pixels. Each one degrades the user experience.

## Image optimization

Images are often the largest single asset:

- **Modern formats**: WebP, AVIF when supported. Fall back to JPEG/PNG.
- **Right-sized**: serve different sizes per viewport (`srcset`, `<picture>`).
- **Lazy load below-the-fold**: native `loading="lazy"` or IntersectionObserver-based libraries.
- **Use framework-native components**: Next.js `<Image>`, Nuxt `<NuxtImg>`, Angular `NgOptimizedImage` handle most of the above automatically.
- **CDN with image optimization**: Cloudflare Images, Cloudinary, AWS Image Optimization.

LCP frequently traces to a hero image. Optimize the LCP image aggressively (priority hint, preloaded, optimal format, right size).

## Font optimization

Web fonts are common LCP / CLS offenders:

- **Preload critical fonts** with `<link rel="preload" as="font">`.
- **font-display: swap** — show fallback while loading; reduces blocking.
- **Subset fonts** — include only the glyphs actually used.
- **Variable fonts** when using multiple weights/styles.
- **Self-host** rather than Google Fonts (eliminates DNS lookup + privacy benefit).

CLS from font loading is common: the fallback font's metrics differ from the web font, so layout shifts when the web font loads. Use `size-adjust` or font-matching to minimize.

## Rendering strategy impact

Per `frontend-architecture`, the rendering strategy affects perf:

- **SSR / RSC** — fast LCP (server delivers rendered HTML); requires server resources.
- **SSG** — fastest LCP (static HTML); requires build-time data.
- **ISR** — middle ground; periodic re-generation.
- **CSR** — slowest LCP (browser must download JS, then render); cheapest on server.

For most user-facing pages, SSR or SSG. CSR for app-like surfaces where data is highly dynamic.

## Lighthouse CI

Per PR, Lighthouse runs against built artifacts (often via Storybook or ephemeral preview deployments) and verifies budgets:

```yaml
# lighthouse-budget.json (per route)
{
 "path": "/products",
 "timings": [
 { "metric": "interactive", "budget": 3000 },
 { "metric": "first-contentful-paint", "budget": 1500 }
 ],
 "resourceSizes": [
 { "resourceType": "script", "budget": 200 },
 { "resourceType": "total", "budget": 850 }
 ]
}
```

CI fails the PR on budget breaches. Per-route budgets prevent the "but only this route got slower" pattern.

## RUM (Real User Monitoring)

Lighthouse measures synthetic; RUM measures real users on real devices on real networks.

Tools:
- **web-vitals** (Google) — lightweight script; emit Web Vitals to your endpoint.
- **Sentry Performance**, **Datadog RUM**, **New Relic Browser**, **Cloudflare Analytics** — managed.
- **Self-hosted**: collect via `navigator.sendBeacon` to a custom endpoint.

Per-route RUM dashboards in `observability` . Regression detection: 75th percentile of LCP / INP / CLS over the last 7 days, alerted on degradation.

## Per-route monitoring strategy

For each significant route:

```markdown
# Route: /products/:id

## Budget
- LCP target: 2.5s (75th percentile, mobile)
- INP target: 200ms
- CLS target: 0.1
- JS budget: 200KB compressed
- Total page weight: 850KB

## Lighthouse CI
- Lighthouse Performance score ≥ 90
- Budget enforced per PR

## RUM tracking
- LCP / INP / CLS reported via web-vitals
- Dashboard in [observability tool]
- Alert if 7-day p75 exceeds budget

## Optimization tactics applied
- LCP image: hero.webp, optimized, priority hint, preloaded
- Font: Inter subset, self-hosted, font-display: swap
- JS: route-split; ProDashboard lazy-loaded per tier
- Third-party: 1 analytics script (deferred), 0 others
```

## Outputs

| Output | Location |
|---|---|
| Performance budget (per route) | `lighthouse-budget.json` in repo + `.project/procedural/fe-perf-budgets.md` |
| Lighthouse CI configuration | `.lighthouserc.json` + CI step |
| RUM dashboard | provisioned in observability stack |
| Optimization backlog | `.project/working/fe-perf-backlog.md` |
| Bundle-size trend | CI artifact + showback dashboard |

## Mode handling (G/B)

**Greenfield.** Build with budgets from day one; Lighthouse CI on first PR; RUM live by initial release.

**Brownfield.** Measure first (RUM data is more reliable than synthetic for legacy apps). Common findings: monolithic bundles; hero image unoptimized; layout shifts everywhere. Prioritize LCP first (largest user-experience impact), then INP, then CLS.

## What this skill does not do

- Backend perf testing — that's `performance-testing`.
- Accessibility audit — that's `accessibility`.
- General observability — that's `observability` (this skill consumes for RUM dashboards).
- Visual design — that's `design-system` + `wireframing-prototyping`.

## Common rationalizations

| The agent's thought | Counter |
|---|---|
| "Modern devices are fast; perf doesn't matter." | They aren't fast in the slowest hands of your users. Median device is slower than your dev laptop. |
| "Lighthouse score is the goal." | Lighthouse is a simulator. Real-user measurements (RUM) are the truth. Both matter; weight RUM higher. |
| "Core Web Vitals are nice-to-have." | They're SEO + UX signals. Treat as binding targets. |
| "Bundle size is just a vibe." | Bundle directly drives LCP and TBT. Track and budget. |
| "Lazy-load everything." | Lazy-loading critical assets harms perceived perf. Critical-path images load eagerly; below-fold lazy. |
| "Cache headers are infrastructure's problem." | They're product perf levers. Set them per asset class. |
| "Third-party scripts are necessary." | They're the largest perf regression source. Audit + budget + defer / sandbox. |

## Verification

You are done when:

- [ ] Core Web Vitals targets met per device class (mobile + desktop).
- [ ] LCP < 2.5s, INP < 200ms, CLS < 0.1 (or project-specific tighter targets).
- [ ] Bundle budgets defined + enforced in CI.
- [ ] RUM (Real User Monitoring) instrumented; field data tracked.
- [ ] Lighthouse CI runs on PR (regression alarm).
- [ ] Third-party script inventory + budget; new third-party requires review.
- [ ] Image optimization pipeline (responsive sizes, modern formats, lazy below-fold).
- [ ] Cache headers set per asset class (immutable for fingerprinted; revalidate for HTML).
- [ ] Critical CSS path inlined; non-critical deferred.

Evidence to check:
- 75th percentile field data passes Core Web Vitals.
- Bundle regression caught by CI before merge.

## Anti-patterns

- Performance addressed only when users complain.
- Lighthouse run manually rather than in CI.
- Budgets app-wide (hides per-route regressions).
- "Performance is the framework's job" (it isn't; choices matter).
- Third-party scripts added without budget review.
- Images served at full resolution to mobile devices.
- Web fonts not preloaded; blocking render.
- Layout shifts from font loading not addressed.
- RUM data collected but no dashboard / no alerting.
- Synthetic Lighthouse score 95 but real users at p75 4s LCP (no RUM = no truth).
