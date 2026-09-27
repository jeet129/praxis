# ML Serving / Deployment — Latency Budget Worked Example

Per the NFR register, the model's prediction is one component of a larger user-facing operation. Worked budget:

```
Total user-perceived latency: 200ms
 - Network round-trip: 30ms
 - Auth, routing, business logic: 40ms
 - Feature retrieval: 50ms
 - Model inference: 50ms ← model's budget
 - Response serialization: 20ms
 - Headroom: 10ms
```
