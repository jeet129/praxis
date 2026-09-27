# Git Workflow Checklist

A reference loaded by `engineering-standards` when git practice is in scope. Not a standalone SKILL — git practice is universal enough that it lives with the broader standards.

## The principle

**Git is the safety net.** Commits are save points. Branches are sandboxes. History is documentation. With AI-generated code arriving at high speed, the discipline of small commits + clean history + reversible operations is what makes velocity safe.

## Branching strategy

### Trunk-based (recommended default)

```
main ──●──●──●──●──●──●──●──●──●──  (always deployable)
        ╲      ╱  ╲    ╱
         ●──●─╱    ●──╱   ← short-lived feature branches (1-3 days)
```

- `main` always deployable.
- Feature branches live 1-3 days max.
- Long-lived branches accumulate merge risk; avoid.
- DORA research consistently associates trunk-based development with high-performing engineering teams.

### Other models (if the project mandates them)

- **GitHub Flow** — close to trunk-based; works fine.
- **Gitflow** — adds `develop` + release branches. The commit discipline (atomic, small, descriptive) matters more than the branching topology. Adapt the principles.
- **Long-lived feature branches** — high cost. If unavoidable, rebase from main daily.

## Atomic commits

Each commit:

- **One logical change.** If the commit message has "and" in the middle, it's two commits.
- **Compiles and passes tests.** Don't push commits that break the build mid-history.
- **Reversible.** A single revert undoes one logical thing.
- **Self-contained.** Includes the code, the test, the docs change for that one thing.

### Sizing — the ~100-line rule

| Commit size | Behavior |
|---|---|
| < 50 lines | ideal — fast review, easy revert |
| 50-150 lines | normal |
| 150-300 lines | OK if cohesive; flag for sequencing |
| 300+ lines | **decompose.** Too big to review well; revert risk too high |

Big commits hide bugs in the noise. Reviewer attention drops sharply past ~200 lines.

### Decomposition tactics

- Refactor before adding behavior — separate commit.
- Add the test first — separate commit.
- One module / file family per commit.
- "Move this, then change it" — two commits (the move is mechanical; the change is real).

## Commit messages

### Format

```
<type>(<scope>): <one-line summary; imperative mood; ~70 chars>

<body — wrap at 72; explains WHY, not WHAT>

<footer — Refs: ISSUE-123 / Co-authored-by: ... / Reviewed-by: ...>
```

Types (conventional commits):

- `feat:` user-visible feature
- `fix:` bug fix
- `refactor:` code change with no behavior change
- `test:` adding / fixing tests
- `docs:` documentation
- `chore:` build / tooling / non-code change
- `perf:` performance work
- `revert:` undo

### Quality bar

A good message answers two questions:

1. **What is this change?** (the subject)
2. **Why did we make it?** (the body)

Never "fix bug" or "update". Always say which bug, what behavior it caused, what triggered it.

### Examples

```
fix(orders): prevent double-charge on retry of pending payments

The payment retry path re-issued a charge if the previous attempt's
network call timed out before the gateway responded. Now we check
the gateway's idempotency key before issuing the retry.

Reproducer: spec/orders/retry_double_charge_spec.rb (new)
Refs: INC-4421
```

```
refactor(api): extract pagination helper

No behavior change. Extracted because three endpoints had grown
near-identical pagination logic; the extracted helper is unit-tested.
The next PR adds cursor-based pagination behind this seam.
```

## Pull requests

### Sizing

Same ~100-line rule applies to PRs. PRs grow because:

- The slice was sized wrong (re-decompose; per `project-phasing`).
- Mechanical changes bundled with substantive ones (split).
- "While I was in there" expansion (forbidden; see scope discipline below).

### Description

Required content:

- **What:** one paragraph.
- **Why:** the user-facing or system-facing reason.
- **How:** the approach in 3-5 bullets.
- **Tests:** how this is verified.
- **Risks:** what could break + the mitigation.
- **Sources:** for any framework / library decisions (per `source-grounded-coding`).

### Self-review before opening

- Read your own diff. The first reviewer is you.
- Look for: commented-out code, debug prints, test fixtures, files added by accident, secrets, large generated files.
- Check the commit history reads cleanly (`git log -p main..HEAD`).

## Scope discipline

In-flight discipline:

- **Touch only what the task requires.** No "cleanups" of orthogonal code.
- **No drive-by refactors.** Open a separate PR or a `tech-debt-management` entry.
- **Don't rename across files mid-PR.** Renames are mechanical; bundling them with behavior changes makes both harder to review.
- **Don't delete code you don't understand.** It's there for a reason (Chesterton's Fence).

The Boy Scout rule applies WITHIN the touched files only, and only for tiny improvements (a typo in a doc comment; a clearer variable name). Anything bigger goes in the debt register.

## Rebase, merge, fast-forward

| Strategy | When |
|---|---|
| **Rebase + fast-forward merge** | Default for clean history. Feature branch rebased on main; merged with `--ff-only`. |
| **Squash merge** | If the feature branch has noisy intermediate commits; collapse to one. |
| **Merge commit** | Rare; only when preserving the integration moment matters (e.g., a long release branch). |

Decide per-project; don't mix without rationale.

## Conflict resolution

- Resolve conflicts in the feature branch (rebase main → fix → re-push).
- Don't resolve conflicts in the merge commit (the diff becomes uninspectable).
- After a non-trivial conflict, **re-run tests** before opening the PR.
- For semantic conflicts (no textual conflict but the logic interacts), explicitly verify the integrated behavior.

## Reverts

A revert is a first-class operation:

```bash
git revert <SHA>          # creates a new commit that undoes <SHA>
```

- Reverts are atomic — revert one logical change at a time.
- The revert commit message says WHY: "Reverts <SHA>: incident INC-NNN; the change caused X."
- After revert, decide forward path: re-do correctly OR document as wont-fix.

Never `git reset` shared history. The repo's history is owned by everyone who pulled it.

## The safety habits

1. **Commit often.** Save-points are free; lost work isn't.
2. **Push the branch.** Local-only branches lose to laptop fires.
3. **Run tests before push.** CI is for catching what you missed; not what you should have caught.
4. **`git status` before every commit.** No untracked-file surprises.
5. **`git diff --staged` before every commit.** Confirms what you're actually committing.
6. **`git log -p main..HEAD` before every PR.** Reviews your own history.

## Anti-patterns

- Long-lived feature branches that accumulate weeks of changes.
- Commits with "and" or "various" or "wip" in the message.
- Force-pushes to shared branches.
- 1000-line PRs.
- Squashing meaningful intermediate commits into a single "the feature" commit (the history loses the decomposition).
- "Resolved conflicts" without explanation.
- Mixing mechanical (renames, formatting) with logical (behavior) changes in the same commit.
- Secrets committed to history (even briefly — rotate the secret regardless).
- PR descriptions that say "see commits."
- Reverts without saying WHY.

## When this reference loads

`engineering-standards` loads this when:

- Implementing any change touching git workflow.
- Reviewing a PR's commit history.
- Setting up a new repository's standards.
- Resolving a non-trivial merge or rebase situation.
- Investigating a revert decision.
