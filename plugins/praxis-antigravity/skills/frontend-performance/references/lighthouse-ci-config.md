# Lighthouse CI budget configuration

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
