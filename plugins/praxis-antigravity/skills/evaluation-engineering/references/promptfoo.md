# Reference — Promptfoo

Loaded by `evaluation-engineering` when Promptfoo is the chosen LLM evaluation framework.

## When to use

Promptfoo is the recommended OSS default for LLM evaluation when:
- You want YAML/JSON-driven test cases (easy to version-control).
- You need CI-friendly run mode (`promptfoo eval --output results.json`).
- Cross-provider comparison matters (OpenAI vs Anthropic vs local models).

Alternatives:
- **LangSmith**: tight LangChain integration; managed (`langsmith.md`).
- **Braintrust**: rich UX; managed (`braintrust.md`).
- **DeepEval**: pytest-style assertions for AI; OSS (`deepeval.md`).
- **Inspect AI**: research-grade; UK AISI (`inspect-ai.md`).

## Setup

```bash
# Global install or per-project npm install
npm install -g promptfoo

# Or via npx without install
npx promptfoo@latest init
```

Promptfoo initializes a `promptfooconfig.yaml`:

```yaml
description: "Customer support assistant evaluations"

prompts:
  - "You are a helpful support assistant.\n\nUser: {{question}}\nAssistant:"

providers:
  - openai:gpt-4o
  - anthropic:claude-sonnet-4-6
  - openai:gpt-4o-mini

tests:
  - vars:
      question: "How do I reset my password?"
    assert:
      - type: contains
        value: "Settings"
      - type: not-contains
        value: "I don't know"
      - type: llm-rubric
        value: "Mentions account settings or profile menu; tone is helpful and concise."
```

Run:
```bash
promptfoo eval
promptfoo view   # opens local UI to inspect results
```

## Concepts

| Concept | What |
|---|---|
| **Prompt** | Template with `{{variable}}` placeholders. |
| **Provider** | The LLM (OpenAI, Anthropic, local, custom). |
| **Test** | A case: vars to interpolate + asserts to apply. |
| **Assert** | A check on the output. Many types. |
| **Vars** | Variables interpolated into the prompt. |
| **Rubric** | LLM-as-judge evaluator (uses another LLM to score). |

## Assertion types

Promptfoo supports ~30 assertion types. The most useful:

### Deterministic checks
```yaml
assert:
  - type: contains
    value: "expected substring"
  - type: not-contains
    value: "forbidden phrase"
  - type: contains-all
    value: ["keyword1", "keyword2"]
  - type: starts-with
    value: "Hello"
  - type: regex
    value: '^\d{4}-\d{2}-\d{2}$'
  - type: equals
    value: "exact string"
  - type: is-json
    value: |
      {
        "type": "object",
        "properties": {
          "answer": {"type": "string"}
        },
        "required": ["answer"]
      }
```

### LLM-as-judge
```yaml
assert:
  - type: llm-rubric
    value: |
      Score 0-10:
      - Accuracy: facts are correct
      - Helpfulness: answers the question
      - Tone: professional and friendly
      Pass threshold: 7.
  - type: factuality
    value: "The answer should mention 2024 as the inflation peak year."
  - type: similar    # semantic similarity to expected
    value: "Reset password via Settings > Account"
    threshold: 0.7
```

### Per-output checks
```yaml
assert:
  - type: latency
    threshold: 2000  # ms
  - type: cost
    threshold: 0.01  # USD per call
  - type: contains-json
  - type: javascript
    value: "output.length > 50 && output.length < 500"
```

### Multi-criteria
```yaml
assert:
  - type: select-best   # picks best of several outputs by rubric
    value: "Most concise answer that's still complete"
```

## Loading from external files

```yaml
prompts:
  - file://prompts/support_v1.txt
  - file://prompts/support_v2.txt

providers:
  - openai:gpt-4o
  - anthropic:claude-sonnet-4-6

tests:
  - file://tests/customer_support_tests.yaml
```

Tests file:
```yaml
# tests/customer_support_tests.yaml
- description: "Password reset basic flow"
  vars:
    question: "How do I reset my password?"
  assert:
    - type: contains
      value: "Settings"

- description: "Refund request handling"
  vars:
    question: "I want a refund"
  assert:
    - type: llm-rubric
      value: "Acknowledges the request empathetically + provides next steps."
```

This makes the test set diff-able + reviewable in code review.

## Custom assertion via JavaScript

```yaml
tests:
  - vars:
      question: "How tall is the Eiffel Tower?"
    assert:
      - type: javascript
        value: |
          // output is the LLM's response
          const numbers = output.match(/\d+/g);
          if (!numbers) return { pass: false, reason: "No number in answer" };
          const hasReasonable = numbers.some(n => parseInt(n) > 300 && parseInt(n) < 400);
          return { 
            pass: hasReasonable, 
            reason: hasReasonable ? "Found reasonable height" : "Height claim incorrect" 
          };
```

## Per-slice evaluation (per `evaluation-engineering` SKILL)

Tag tests with cohort metadata; aggregate by slice:

```yaml
tests:
  - description: "Easy question, English"
    vars:
      question: "What is your return policy?"
      metadata:
        difficulty: "easy"
        language: "en"
  - description: "Hard question, French"
    vars:
      question: "Quelle est votre politique de remboursement pour les produits achetés en promotion?"
      metadata:
        difficulty: "hard"
        language: "fr"
```

Promptfoo reports per-tag pass rates. Per-slice regression is what you watch for.

## CI integration (per `cicd-pipeline`)

```yaml
# .github/workflows/llm-eval.yml
name: LLM Evaluation
on:
  pull_request:
    paths:
      - 'prompts/**'
      - 'src/llm/**'

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: npm install -g promptfoo
      - name: Run eval
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          promptfoo eval --output results.json
      - name: Check against baseline
        run: |
          # Compare pass rate to baseline; fail if regression > threshold
          node scripts/check_regression.js results.json baseline.json -0.02
      - name: Upload results
        uses: actions/upload-artifact@v4
        with:
          name: eval-results
          path: results.json
```

A regression script (per `evaluation-engineering`):

```javascript
// scripts/check_regression.js
const current = require(process.argv[2]);
const baseline = require(process.argv[3]);
const threshold = parseFloat(process.argv[4]);

const currentPass = current.results.stats.successes / current.results.stats.successes + current.results.stats.failures;
const baselinePass = baseline.results.stats.successes / (baseline.results.stats.successes + baseline.results.stats.failures);

const delta = currentPass - baselinePass;

if (delta < threshold) {
    console.error(`Regression: ${(delta * 100).toFixed(2)}pp below baseline (threshold ${threshold * 100}pp)`);
    process.exit(1);
}
console.log(`Pass rate: ${(currentPass * 100).toFixed(1)}% (baseline ${(baselinePass * 100).toFixed(1)}%)`);
```

## Comparing across providers

The killer feature — same tests run against multiple providers; UI shows side-by-side:

```yaml
providers:
  - openai:gpt-4o
  - openai:gpt-4o-mini
  - anthropic:claude-sonnet-4-6
  - anthropic:claude-haiku-4-5
  - id: vllm-llama-3-70b
    config:
      apiBaseUrl: "http://vllm:8000/v1"
      model: "meta-llama/Llama-3-70B-Instruct"

# Same tests; promptfoo runs each test against each provider
```

Useful for:
- Choosing the right model tier per use case (per `llm-cost-optimization`).
- Validating routing decisions (cheap model handles easy queries adequately).
- Detecting regressions when a provider releases a new version.

## Provider configuration

```yaml
providers:
  - id: openai:gpt-4o
    config:
      temperature: 0.1
      max_tokens: 500
      system: |
        You are a customer support assistant.
        Tone: helpful and concise.
        If you don't know, say so.
  
  - id: anthropic:claude-sonnet-4-6
    config:
      temperature: 0.1
      max_tokens: 500
      system: |
        You are a customer support assistant.
  
  - id: ollama:chat:llama3
    config:
      apiBaseUrl: "http://ollama:11434"
```

## Datasets

For large eval sets, use external CSV/JSON:

```yaml
tests:
  - file://datasets/customer_support_v3.csv
```

```csv
question,expected_answer,difficulty,language
"How do I reset my password?","Via Settings > Account > Reset","easy","en"
"What is your refund policy?","Per terms of service Section 4","easy","en"
...
```

Each row becomes a test case; columns become vars.

## Golden datasets discipline (per `evaluation-engineering`)

- Start with ~20-50 hand-curated examples covering happy paths.
- Add examples from real production logs (sanitized).
- Add adversarial / hard examples from red-team exercises.
- Version the dataset (e.g., `customer_support_v3.csv`); track changes.
- Owner accountable for currency.

## LLM-judge calibration

Per `evaluation-engineering` — LLM-as-judge is powerful but biased. Calibrate:

1. Sample 50-100 examples.
2. Have humans label them (pass/fail OR scored).
3. Run the LLM judge on the same examples.
4. Compute agreement.
5. Tune the judge prompt until human agreement > target (typically 80%).

```yaml
assert:
  - type: llm-rubric
    provider: openai:gpt-4o  # use a strong model AS judge
    value: |
      Evaluate this customer support response on:
      1. Accuracy: Are claims correct?
      2. Helpfulness: Does it answer the question?
      3. Tone: Professional + friendly?
      
      Score each 1-5. Pass = all >= 4.
      
      Output JSON: {"accuracy": int, "helpfulness": int, "tone": int, "pass": bool, "reason": str}
```

## Gotchas

- **API costs add up** — eval suites with 100+ tests x 5 providers run quickly. Budget.
- **Non-deterministic outputs** — even with `temperature: 0` some models vary. Use seed if supported; otherwise tolerate via `similar` / `llm-rubric` rather than exact match.
- **`llm-rubric` cost** — every test that uses it makes another LLM call. Costly at scale; sample.
- **Cache results** — promptfoo caches by default; clear with `--no-cache` when testing prompt changes.
- **Test set sacred** — the test set is the eval truth. Treat it like production code; review changes in PR.

## Common rationalizations

| Thought | Counter |
|---|---|
| "Vibe testing is fine for now." | Vibe testing scales like manual QA. Build the eval suite from day one. |
| "5 test cases is enough to start." | For statistical signal, start at 20-50. 5 doesn't distinguish improvement from noise. |
| "LLM-judge is unreliable." | Calibrated against human labels, it's reliable enough. Run calibration; track human agreement. |
| "We'll add eval after launch." | After launch you're flying blind. Eval is the navigation, not the post-mortem. |
| "We can just look at outputs in the UI." | Manual review doesn't scale. Aggregate metrics + targeted dives. |

## Verification (per `evaluation-engineering` SKILL)

- [ ] Golden dataset versioned in repo (`tests/datasets/` or external).
- [ ] At least 20 test cases per use case (happy + edge + adversarial).
- [ ] Programmatic checks where deterministic (regex, contains, JSON schema).
- [ ] LLM-judge calibrated against human labels (≥ 80% agreement on sample).
- [ ] Per-slice metrics tracked (difficulty, language, cohort).
- [ ] Regression eval in CI; threshold blocks PR merge.
- [ ] Baseline committed; updates reviewed as PRs.
- [ ] Hallucination / groundedness checks for grounded generation tasks.

## Official sources

- Promptfoo: https://www.promptfoo.dev
- GitHub: https://github.com/promptfoo/promptfoo
- Assertion types: https://www.promptfoo.dev/docs/configuration/expected-outputs/
- Provider list: https://www.promptfoo.dev/docs/providers/
- CI examples: https://www.promptfoo.dev/docs/getting-started#ci-integration
