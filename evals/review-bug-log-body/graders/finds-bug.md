---
type: llm
weight: 1
---

Answer key: the change writes the raw request body, which contains card
holder name and card number, into the error log. That leaks payment card data
(PII / PCI scope) to log storage. Credit the response only if it reports this
leak as a blocker or major finding and recommends removing the body from the
log. Do not credit a response that only discusses performance of reading the
body twice.
