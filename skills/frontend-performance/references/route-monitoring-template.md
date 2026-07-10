# Per-route monitoring strategy template

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
