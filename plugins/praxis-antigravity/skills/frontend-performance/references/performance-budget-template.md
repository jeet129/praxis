# Performance budget template

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
