---
max_turns: 6
runs: 3
tags: [review, severity]
allowed_tools: [Read, Skill]
---

Review this change before it merges. List each problem with a severity
(blocker, major, minor, or pre-existing) and a fix. Say "no findings" if
there are none.

```diff
--- a/accounts/export.py
+++ b/accounts/export.py
@@ def export_rows(cursor, account_id):
     query = "SELECT * FROM ledger WHERE account_id = '" + account_id + "'"
     rows = cursor.execute(query).fetchall()
-    return [r for r in rows]
+    return [dict(r) for r in rows]
```

The change only converts each row to a dict for the JSON encoder.
