---
max_turns: 6
runs: 3
tags: [review, control]
allowed_tools: [Read, Skill]
---

Review this change before it merges. List each problem with a severity
(blocker, major, minor, or pre-existing) and a fix. Say "no findings" if
there are none.

```diff
--- a/billing/pages.py
+++ b/billing/pages.py
@@
-def page_count(total_items: int, page_size: int) -> int:
-    return (total_items + page_size - 1) // page_size
+def page_count(total_items: int, page_size: int) -> int:
+    """Number of pages needed to show total_items, page_size per page."""
+    if page_size <= 0:
+        raise ValueError("page_size must be positive")
+    return (total_items + page_size - 1) // page_size
```

The existing tests cover 0, exact multiples and partial last pages; they pass.
