export const meta = {
  name: 'pre-merge-review',
  description: 'Review the current branch from three angles, then adversarially verify every finding before reporting it',
  phases: [{ title: 'Scope' }, { title: 'Review' }, { title: 'Verify' }, { title: 'Summarize' }],
}

// args: a base branch name ("main"), or { base: "main", focus: "payments module" }. Both optional.
const base = typeof args === 'string' ? args : (args && args.base) || 'main'
const focus = args && typeof args === 'object' && args.focus ? ` Pay particular attention to: ${args.focus}.` : ''
const READ_ONLY = 'You are a reviewer. Do not edit, create or delete any file, and do not run commands that change the repository.'

const FILES = {
  type: 'object',
  required: ['files'],
  properties: { files: { type: 'array', items: { type: 'string' } } },
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
          severity: { type: 'string', enum: ['blocker', 'major', 'minor'] },
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
  properties: { confirmed: { type: 'boolean' }, reason: { type: 'string' } },
}

phase('Scope')
const scope = await agent(
  `${READ_ONLY} List the files changed on the current branch compared with ${base} ` +
    `(use: git diff --name-only ${base}...HEAD). Exclude generated files, lock files and vendored code.`,
  { schema: FILES, label: 'changed files' },
)
const files = (scope && scope.files) || []
if (files.length === 0) {
  return { verdict: 'pass', summary: `No changed files against ${base}.`, findings: [] }
}
log(`${files.length} changed files against ${base}`)

const LENSES = [
  { name: 'correctness', brief: 'logic errors, unhandled cases, broken contracts between modules, data-loss or concurrency risks' },
  { name: 'security', brief: 'missing authentication or authorisation, injection, secrets in code, unsafe input handling, unsafe defaults' },
  { name: 'tests-and-standards', brief: 'behaviour changed without a test, tests that cannot fail, and departures from the conventions already used in this repository' },
]

phase('Review')
const reviews = await pipeline(LENSES, lens =>
  agent(
    `${READ_ONLY} Review the changes on this branch against ${base} for ${lens.name}: ${lens.brief}.${focus} ` +
      `Changed files:\n${files.join('\n')}\n` +
      'Read the diff and enough surrounding code to be sure. Report only problems introduced or exposed by this change. ' +
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
const checks = await pipeline(candidates, f =>
  agent(
    `${READ_ONLY} Another reviewer claims this problem exists. Try to disprove it by reading the code. ` +
      `File: ${f.file}${f.line ? ` line ${f.line}` : ''}. Claim: ${f.issue}. ` +
      'Set confirmed to true only if you can point to the code that makes the claim true. If the claim is wrong, already handled elsewhere, or not caused by this change, set confirmed to false.',
    { schema: VERDICT, label: `verify ${f.file}` },
  ),
)
const confirmed = []
const unverified = []
candidates.forEach((f, i) => {
  if (!checks[i]) unverified.push(f)
  else if (checks[i].confirmed) confirmed.push({ ...f, evidence: checks[i].reason })
})

phase('Summarize')
const blocking = confirmed.filter(f => f.severity === 'blocker' || f.severity === 'major')
return {
  verdict: blocking.length ? 'changes_requested' : unreviewed.length || unverified.length ? 'incomplete' : 'pass',
  summary:
    `${confirmed.length} confirmed findings (${blocking.length} blocker or major), ` +
    `${candidates.length - confirmed.length - unverified.length} rejected on verification, ` +
    `${unverified.length} could not be verified.`,
  findings: confirmed,
  unverified,
  unreviewed,
}
