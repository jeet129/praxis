export const meta = {
  name: 'pre-merge-review',
  description: 'Review the current branch from three angles plus the project checks its diff triggers, then adversarially verify every finding before reporting it',
  phases: [{ title: 'Scope' }, { title: 'Review' }, { title: 'Verify' }, { title: 'Summarize' }, { title: 'Record' }],
}

// args: a base branch name ("main"), or { base: "main", focus: "payments module" }. Both optional.
const base = typeof args === 'string' ? args : (args && args.base) || 'main'
const focus = args && typeof args === 'object' && args.focus ? ` Pay particular attention to: ${args.focus}.` : ''
const READ_ONLY = 'You are a reviewer. Do not edit, create or delete any file, and do not run commands that change the repository.'

// Scope comes from `praxis-memory review-context`, which reads REVIEW.md and
// procedural/checks.yaml from the BASE branch: a change cannot edit its own judge.
const SCOPE = {
  type: 'object',
  required: ['files'],
  properties: {
    files: { type: 'array', items: { type: 'string' } },
    rules: { type: 'string' },
    checks_matched: {
      type: 'array',
      items: {
        type: 'object',
        required: ['id', 'check'],
        properties: { id: { type: 'string' }, check: { type: 'string' }, origin: { type: 'string' },
          files: { type: 'array', items: { type: 'string' } } },
      },
    },
  },
}
const FINDINGS = {
  type: 'object',
  required: ['findings'],
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        required: ['severity', 'file', 'issue', 'recommendation'],
        properties: {
          severity: { type: 'string', enum: ['blocker', 'major', 'minor', 'pre-existing'] },
          check_id: { type: 'string' },
          file: { type: 'string' },
          line: { type: 'integer' },
          issue: { type: 'string' },
          recommendation: { type: 'string' },
        },
      },
    },
  },
}
const VERDICT = {
  type: 'object',
  required: ['confirmed', 'reason'],
  properties: { confirmed: { type: 'boolean' }, pre_existing: { type: 'boolean' }, reason: { type: 'string' } },
}

phase('Scope')
const scope = await agent(
  `${READ_ONLY} Run exactly this command and report its output fields: ` +
    `.project/local/bin/praxis-memory review-context --base ${base} ` +
    `(if that shim is missing, run: git diff --name-only ${base}...HEAD, and return rules "" and checks_matched []). ` +
    'From `files`, drop generated files, lock files and vendored code. Copy `rules` and `checks_matched` exactly; ' +
    'never read REVIEW.md or checks.yaml from the working tree.',
  { schema: SCOPE, label: 'scope from base branch' },
)
const files = (scope && scope.files) || []
if (files.length === 0) {
  return { verdict: 'pass', summary: `No changed files against ${base}.`, findings: [] }
}
const rules = scope.rules ? `\nProject review guidance (from ${base}):\n${scope.rules.slice(0, 4000)}\n` : ''
const checks = (scope.checks_matched || []).slice(0, 12)
log(`${files.length} changed files against ${base}; ${checks.length} project checks triggered`)

const LENSES = [
  ...(checks.length ? [{
    name: 'project-checks',
    brief: 'only these project checks, each learned from a past incident or review. For each one, decide whether ' +
      'this change violates it and set check_id on any finding:\n' +
      checks.map(c => `- ${c.id}: ${c.check}${c.origin ? ` (from ${c.origin})` : ''}${c.files && c.files.length ? ` [files: ${c.files.join(', ')}]` : ''}`).join('\n'),
  }] : []),
  { name: 'correctness', brief: 'logic errors, unhandled cases, broken contracts between modules, data-loss or concurrency risks' },
  { name: 'security', brief: 'missing authentication or authorisation, injection, secrets in code, unsafe input handling, unsafe defaults' },
  { name: 'tests-and-standards', brief: 'behaviour changed without a test, tests that cannot fail, and departures from the conventions already used in this repository' },
]

phase('Review')
const reviews = await pipeline(LENSES, lens =>
  agent(
    `${READ_ONLY} Review the changes on this branch against ${base} for ${lens.name}: ${lens.brief}.${focus}${rules} ` +
      `Changed files:\n${files.join('\n')}\n` +
      'Read the diff and enough surrounding code to be sure. Report problems introduced or exposed by this change. ' +
      'A real problem that predates this change gets severity pre-existing; it is reported, but never blocks the author. ' +
      'Every finding needs a file, a concrete issue and a concrete recommendation. Return an empty list if you find nothing.',
    { schema: FINDINGS, label: lens.name },
  ),
)
const candidates = []
reviews.forEach((r, i) => {
  if (r && r.findings) r.findings.forEach(f => candidates.push({ ...f, lens: LENSES[i].name }))
})
const unreviewed = LENSES.filter((_, i) => !reviews[i]).map(l => l.name)
if (candidates.length === 0) {
  return {
    verdict: unreviewed.length ? 'incomplete' : 'pass',
    summary: unreviewed.length ? `No findings, but these reviews did not finish: ${unreviewed.join(', ')}.` : 'No findings.',
    findings: [],
    unreviewed,
  }
}

phase('Verify')
const verdicts = await pipeline(candidates, f =>
  agent(
    `${READ_ONLY} Another reviewer claims this problem exists. Try to disprove it by reading the code. ` +
      `File: ${f.file}${f.line ? ` line ${f.line}` : ''}. Claim: ${f.issue}. ` +
      'Set confirmed to true only if you can point to the code that makes the claim true. If the claim is wrong or already handled elsewhere, set confirmed to false. ' +
      'If it is true but the problem existed before this change, set confirmed to true and pre_existing to true.',
    { schema: VERDICT, label: `verify ${f.file}` },
  ),
)
const confirmed = []
const unverified = []
candidates.forEach((f, i) => {
  if (!verdicts[i]) unverified.push(f)
  else if (verdicts[i].confirmed) {
    confirmed.push({ ...f, severity: verdicts[i].pre_existing ? 'pre-existing' : f.severity, evidence: verdicts[i].reason })
  }
})

phase('Summarize')
const blocking = confirmed.filter(f => f.severity === 'blocker' || f.severity === 'major')
const preExisting = confirmed.filter(f => f.severity === 'pre-existing')
const verdict = blocking.length ? 'changes_requested' : unreviewed.length || unverified.length ? 'incomplete' : 'pass'

// Record the verdict against the current tree, so the commit trailer can say
// `review` and a later push makes it visibly stale (reviews apply to a tree).
phase('Record')
await agent(
  'Run exactly this one command and nothing else, then reply "recorded": ' +
    `.project/local/bin/praxis-verify --record-review ${verdict} --source pre-merge-review --findings ${confirmed.length}`,
  { label: 'record verdict' },
)

return {
  verdict,
  summary:
    `${confirmed.length} confirmed findings (${blocking.length} blocker or major, ${preExisting.length} pre-existing), ` +
    `${candidates.length - confirmed.length - unverified.length} rejected on verification, ` +
    `${unverified.length} could not be verified.` +
    (checks.length ? ` Project checks triggered: ${checks.map(c => c.id).join(', ')}.` : ''),
  findings: confirmed,
  unverified,
  unreviewed,
}
