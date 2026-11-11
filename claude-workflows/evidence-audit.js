export const meta = {
  name: 'evidence-audit',
  description: 'Re-run the verify command of every task marked done in the Praxis slice ledgers and report which ones really pass',
  phases: [{ title: 'Collect' }, { title: 'Re-verify' }, { title: 'Report' }],
}

// args: a slice id ("S9") to audit one slice, or nothing to audit every open ledger.
const only = typeof args === 'string' ? args : (args && args.slice) || ''

const TASKS = {
  type: 'object',
  required: ['tasks'],
  properties: {
    tasks: {
      type: 'array',
      items: {
        type: 'object',
        required: ['slice', 'id', 'verify'],
        properties: { slice: { type: 'string' }, id: { type: 'string' }, verify: { type: 'string' } },
      },
    },
  },
}
const RESULT = {
  type: 'object',
  required: ['ran', 'passed', 'detail'],
  properties: {
    ran: { type: 'boolean' },
    passed: { type: 'boolean' },
    exit_code: { type: 'integer' },
    detail: { type: 'string' },
  },
}

phase('Collect')
const found = await agent(
  'Read the Praxis task ledgers at .project/working/slice-*-tasks.yaml' +
    (only ? ` (only slice ${only})` : '') +
    '. List every task whose status is done and whose verify field is a command (skip verify: null). ' +
    'Copy each verify command exactly as written. Do not edit any file.',
  { schema: TASKS, label: 'done tasks' },
)
const tasks = (found && found.tasks) || []
if (tasks.length === 0) {
  return { summary: 'No done tasks with a verify command were found.', passed: [], failed: [], not_run: [] }
}
log(`${tasks.length} done tasks to re-verify`)

phase('Re-verify')
const results = await pipeline(tasks, t =>
  agent(
    `Run this verification command from the repository root exactly as written, then report its exit code:\n${t.verify}\n` +
      `It belongs to task ${t.id} of slice ${t.slice}. Do not fix anything, do not edit source files or the ledger, ` +
      'and do not retry with a changed command. Set ran to false if the command could not be started at all. ' +
      'passed is true only when the exit code is 0. In detail, give the last lines of output that explain the result.',
    { schema: RESULT, label: t.id },
  ),
)

phase('Report')
const passed = []
const failed = []
const notRun = []
tasks.forEach((t, i) => {
  const r = results[i]
  if (!r || !r.ran) notRun.push({ ...t, detail: r ? r.detail : 'agent did not finish' })
  else if (r.passed) passed.push(t.id)
  else failed.push({ ...t, exit_code: r.exit_code, detail: r.detail })
})
return {
  summary:
    `${passed.length} of ${tasks.length} done tasks still pass their verify command; ` +
    `${failed.length} fail and should be reopened; ${notRun.length} could not be run.`,
  passed,
  failed,
  not_run: notRun,
}
