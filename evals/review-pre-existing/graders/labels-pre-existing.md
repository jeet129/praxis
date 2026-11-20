---
type: llm
weight: 1
---

Answer key: the SQL built by string concatenation (SQL injection through
account_id) is real but was already there; this change did not introduce it.
Pass only if the response mentions the injection AND labels it pre-existing
(or clearly says it predates the change and should not block this change),
and does not block the change because of it. Fail if it ignores the injection
entirely or treats it as a blocker caused by this change.
