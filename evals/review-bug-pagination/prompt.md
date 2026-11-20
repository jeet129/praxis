---
max_turns: 6
runs: 3
tags: [review, known-bug]
allowed_tools: [Read, Skill]
---

Review this change as a code reviewer before it merges. List each problem with
a severity (blocker, major, minor, or pre-existing) and a fix. Say "no
findings" if there are none.

```diff
--- a/billing/pages.py
+++ b/billing/pages.py
@@ def page_count(total_items: int, page_size: int) -> int:
-    return (total_items + page_size - 1) // page_size
+    # simpler and faster
+    return total_items // page_size
```

`page_count` decides how many invoice pages the statement job renders.
