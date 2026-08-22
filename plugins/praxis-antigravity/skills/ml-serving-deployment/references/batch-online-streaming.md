# ML Serving / Deployment — Batch vs Online vs Streaming Inference

The inference *pattern* choice comes before the tool choice (SageMaker vs KServe vs Triton) — it's set by latency requirement, cost tolerance, and data freshness need, not by team preference. Get this decision wrong and the tool choice doesn't save you.

## The three patterns

| | Batch | Online (real-time) | Streaming |
|---|---|---|---|
| **Trigger** | Scheduled job, or on-demand bulk run | Individual request, synchronous | Continuous event stream (Kafka/Kinesis/Pub-Sub) |
| **Latency** | Minutes to hours acceptable | Milliseconds to low-seconds (SLA-bound) | Seconds (near-real-time, per-event or micro-batch) |
| **Throughput unit** | Whole dataset / large partition | Single request or small batch | Continuous, unbounded |
| **Cost profile** | Cheapest per-prediction (amortized over huge batches, spot/preemptible compute) | Most expensive per-prediction (always-warm capacity, low-latency infra) | Medium — sized for sustained stream rate, not peak |
| **Freshness of result** | Stale by definition (as of last run) | Fresh as of request | Fresh as of event arrival |
| **Typical infra** | Spark / Airflow / Dagster batch job, `data-pipeline` skill | KServe / SageMaker endpoint / Triton, `ml-serving-deployment` | Kafka Streams / Flink / Spark Structured Streaming + KServe/Triton call |

## Decision matrix

Ask these questions in order — the first one that produces a hard constraint decides the pattern.

1. **Does a human or system need this prediction to respond to a specific request right now?**
   Yes → **online**. (User clicks "recommend," fraud-check on a live transaction, chatbot response.)
   No → continue.

2. **Does the prediction need to reflect an event within seconds of it happening, even though nothing is "waiting" for it synchronously?**
   Yes → **streaming**. (Real-time fraud scoring feeding a downstream alerting pipeline; live personalization signal updates.)
   No → continue.

3. **Can the prediction be computed ahead of need and looked up later, or does it apply to a whole dataset at once?**
   Yes → **batch**. (Nightly churn-risk scores for every customer, monthly credit-model recalibration, bulk document classification.)

## Latency / cost / freshness tradeoffs in practice

- **Batch is 10-100x cheaper per prediction** than online serving because it amortizes fixed costs (model load, warm-up) across huge volumes and can run on spot/preemptible infrastructure with no SLA. Default to batch whenever the freshness requirement allows it — it's the cheapest correct answer, not a fallback.
- **Online is the only choice when a human or a synchronous system call is blocked waiting on the result.** The cost premium (always-warm capacity per `ml-serving-deployment/references/kserve.md`'s `minReplicas: 1+` guidance) buys latency; there's no way around paying for it if the SLA demands sub-second response.
- **Streaming sits in the middle** — no single request is waiting, but staleness beyond seconds-to-low-minutes breaks the use case (fraud scoring against a transaction that already cleared is useless). Streaming infra costs less than online (no per-request warm capacity spike) but more than batch (continuous processing, not amortized over huge batches).

## Hybrid patterns (common in practice)

- **Batch-then-serve (precompute + lookup)** — the most common "fake online" pattern: batch-score all entities nightly, write results to a low-latency key-value store (Redis, DynamoDB), serve reads from that store with millisecond latency. Use when predictions don't depend on request-time context (recommendation candidates, churn scores) — gives online-latency UX at batch-inference cost. This *is* what most "real-time recommendation" systems actually do.
- **Streaming feature computation + online inference** — a streaming job (Kafka Streams/Flink) continuously updates features in the online feature store (`ml-feature-engineering/references/feast.md`'s online store), while the actual model call remains synchronous online inference at request time. Freshness comes from the feature pipeline, not from re-architecting the inference call itself.
- **Micro-batch as a streaming substitute** — when true per-event streaming infra isn't justified, a batch job on a very short schedule (every 1-5 minutes) approximates streaming freshness at much lower operational complexity. Valid when the freshness requirement is "a few minutes," not "seconds."

## Choosing per case — worked examples

| Case | Pattern | Why |
|---|---|---|
| Nightly customer churn scoring for a marketing campaign | Batch | No synchronous waiter; freshness of "as of last night" is acceptable; huge volume favors amortized cost. |
| Credit card fraud check blocking a transaction | Online | A synchronous system call is blocked on the response; sub-100ms SLA. |
| Product recommendations on a homepage | Batch-then-serve hybrid | Precompute candidates nightly/hourly into a KV store; serve via cache lookup — avoids paying online-inference cost for read-heavy, context-independent predictions. |
| Real-time bidding in ad auctions | Online | Hard millisecond SLA, per-request context (auction details) that can't be precomputed. |
| Anomaly detection on IoT sensor stream | Streaming | No single request waits, but minutes-old anomaly detection is too late to act on. |
| Monthly loan-portfolio risk recalibration | Batch | Large dataset, no freshness requirement tighter than the reporting cycle. |
| Live chat assistant response generation | Online | User is synchronously waiting for the response. |

## Common violations to flag in review

- An online endpoint (`minReplicas: 1+`, always-warm) serving predictions that are actually looked up nightly-batch-computed values with no per-request context — should be a batch-then-serve KV lookup, not a model inference call on the hot path.
- A batch job re-implemented as a loop of synchronous online-inference calls (thousands of individual HTTP requests to a model endpoint) instead of a genuine batch-inference job — wildly more expensive and slower than a real batch run.
- Streaming infra (Kafka Streams/Flink) stood up for a use case whose actual freshness requirement is "once an hour" — micro-batch would be simpler and cheaper.
- No documented freshness requirement at all — the pattern choice was made by habit/team-familiarity rather than an explicit NFR from `nfr-definition`.
- Online serving cost not weighed against `cost-finops` guidance before defaulting to always-on infrastructure for a low-traffic model.
