---
max_turns: 6
runs: 3
tags: [review, known-bug]
allowed_tools: [Read, Skill]
---

Review this change before it merges. List each problem with a severity
(blocker, major, minor, or pre-existing) and a fix. Say "no findings" if
there are none.

```diff
--- a/api/handlers/payments.py
+++ b/api/handlers/payments.py
@@ async def create_payment(request):
     try:
         return await service.create(await request.json())
     except PaymentError as exc:
-        log.error("payment failed", extra={"request_id": request.id, "code": exc.code})
+        log.error("payment failed", extra={"request_id": request.id, "code": exc.code,
+                                           "body": await request.json()})
         raise
```

The request body of this endpoint contains the card holder's name and card
number.
