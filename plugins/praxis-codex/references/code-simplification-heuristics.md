# Code Simplification Heuristics

A reference loaded by `code-review` (and consumable directly by any implementation agent) when simplification is in scope. Not a standalone SKILL — simplification is an aspect of review, not a separate phase.

## The principle

**Cleverness is expensive.** Simpler code is easier to read, easier to test, easier to change, easier to debug. The agent's natural tendency is to over-engineer; the discipline is to actively resist it.

The bar: **would a staff engineer look at this and say "why didn't you just..."?** If yes, simplify.

## Chesterton's Fence

> "Don't ever take a fence down until you know the reason it was put up." — G. K. Chesterton

Before removing or refactoring code:

1. Find out why it's there.
2. Find out who put it there.
3. Find out what it was protecting against.
4. **THEN** decide whether to remove it.

Common Chesterton's Fence failures:

- Removing "unused" code that turns out to handle a rare error path.
- Simplifying a "weird" conditional that handles a specific data shape from a specific legacy consumer.
- Inlining a function that turns out to have a meaningful name for a non-obvious reason.
- Replacing a manual loop with a stream / map that subtly changes ordering or laziness.

**Rule:** if you can't explain why the original was there, you don't yet know enough to remove it.

## The Rule of 500

When a file approaches 500 lines, consider whether it's doing too many things. Not a hard cutoff — context matters — but a useful flag.

| Lines | Treatment |
|---|---|
| < 200 | comfortable |
| 200-500 | acceptable for cohesive responsibilities |
| 500-800 | review the responsibilities; consider splitting |
| 800+ | usually means multiple things bundled — split |

Same applies to functions:

| Lines per function | Treatment |
|---|---|
| < 30 | typical |
| 30-50 | acceptable for substantive work |
| 50+ | extract or restructure unless tightly cohesive |

These aren't laws. Cohesion matters more than line count. But the numbers are useful flags.

## Six simplification levers

### 1. Fewer parameters

```diff
- def process(user, request, config, logger, cache, db, feature_flags, timeout):
+ def process(user, request, ctx):
+     # ctx carries config, logger, cache, db, feature_flags, timeout
```

Long parameter lists are a smell. If 7 parameters move together, they belong in an object. If 7 parameters DON'T move together, the function is doing too much.

### 2. Earlier returns / guard clauses

```diff
- if user is not None:
-     if user.active:
-         if user.has_permission(...):
-             return do_thing()
-         else:
-             return Error("no permission")
-     else:
-         return Error("inactive")
- else:
-     return Error("no user")

+ if user is None:
+     return Error("no user")
+ if not user.active:
+     return Error("inactive")
+ if not user.has_permission(...):
+     return Error("no permission")
+ return do_thing()
```

Guard clauses flatten code. The happy path stays clear.

### 3. Names that explain themselves

```diff
- def f(d, x):
-     return d[x] if x in d else None

+ def lookup_user(by_id, user_id):
+     return by_id.get(user_id)
```

A good name removes the need for a comment. A good name explains intent that the types can't.

### 4. Eliminate dead abstractions

A class with one method, instantiated once, is just a function with extra steps.

```diff
- class OrderProcessor:
-     def __init__(self, order):
-         self.order = order
-     def process(self):
-         return ...
- OrderProcessor(order).process()

+ def process_order(order):
+     return ...
```

Abstractions that don't earn their complexity are removed.

### 5. Push state to the leaves

State at the top of a call tree contaminates everything below it. Push state down (or out) where it's actually used.

```diff
- # bad: cache lives at module level; every function reads/writes
- _cache = {}
- def f1(x): _cache[x] = ...; return _cache[x]
- def f2(): return _cache

+ # better: cache is a parameter where it's needed; no global mutable state
+ def f1(x, cache): cache[x] = ...; return cache[x]
+ def f2(cache): return cache
```

Functions without hidden state are easier to test and parallelize.

### 6. Remove premature flexibility

```diff
- # plugin system for the one thing we have
- class StrategyRegistry:
-     def __init__(self): self.strategies = {}
-     def register(self, name, strat): self.strategies[name] = strat
-     def get(self, name): return self.strategies[name]
- registry = StrategyRegistry()
- registry.register("v1", StrategyV1())
- # only ever called as: registry.get("v1").execute()

+ # what we actually have
+ result = StrategyV1().execute()
```

YAGNI. Flexibility added "in case we need it" almost always rots.

## Behavior-preserving simplification

Before simplifying, write a test that captures the current behavior. Then simplify. Then re-run the test.

If the test still passes: simplification is safe.
If the test fails: you've discovered the original wasn't as simple as it looked. Investigate (per Chesterton's Fence).

## The simplification cycle

For each candidate simplification:

1. **Identify** the candidate (a smell, a heuristic violation, a "why didn't you just..." moment).
2. **Understand** what it does today (Chesterton).
3. **Test** the current behavior.
4. **Simplify** behavior-preservingly.
5. **Re-test.** Same tests must pass.
6. **Re-read** the diff. Is it actually simpler? Or just differently complex?

If step 6 fails, revert. Not all simplification attempts work.

## When simplification is wrong

Don't simplify:

- **Code in a hot path** without measurement (perceived simplicity can hide performance differences).
- **Code under active feature work** (simplify in a separate PR before or after; never during).
- **Defensive code** for known production failure modes (Chesterton applies).
- **Domain-driven code** where the apparent complexity reflects actual domain complexity.
- **Generated code.**

## When this reference loads

`code-review` loads this when:

- Reviewing a PR for clarity dimension.
- Investigating a "this works but I can't read it" complaint.
- Code Reviewer is flagging complexity as a finding.

Implementation agents load it directly when:

- Self-reviewing before opening a PR.
- Following the "would a staff engineer ask why I didn't just..." instinct.
- The slice's code is in or near the Rule-of-500 thresholds.

## Anti-patterns

- "Refactoring" that's actually re-shuffling (no measurable simplicity gain).
- Behavior change disguised as simplification.
- Removing defensive code because "we don't need it" without verifying.
- Adding abstractions to "make it more flexible" — the same impulse as over-engineering.
- Simplification PRs bundled with feature changes (review becomes impossible).
- Aggressive simplification mid-incident (incident first; refactor later).
- Removing Chesterton fences without finding out why they were built.
- One-letter variable names that "are simpler" (they aren't; they're harder to read).
- Over-applying YAGNI to genuine extension points the team has agreed on.
