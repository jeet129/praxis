---
type: llm
weight: 1
---

This is a control: the change is correct (it adds a docstring and a guard
against a non-positive page size; the arithmetic is unchanged). Pass only if
the response reports no blocker or major finding. Minor style notes are
acceptable. Fail if it invents a correctness bug in the rounding, or blocks
the change.
