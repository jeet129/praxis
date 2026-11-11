#!/usr/bin/env node
// validate-claude-workflows.js — offline check of claude-workflows/*.js against the
// documented script contract (code.claude.com/docs/en/workflows):
//   - `export const meta` is the first statement, a literal with name + description
//   - phases listed in meta match the phase() titles used
//   - no import(), Date.now(), Math.random(), new Date()
//   - the body is valid JavaScript and runs to completion against mock
//     agent()/pipeline()/parallel()/phase()/log() with several mock outcomes
// This proves the script is well formed; it does not prove agents behave.
const fs = require('fs')
const path = require('path')
const dir = path.join(process.argv[2] || path.join(__dirname, '..'), 'claude-workflows')
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
let failed = 0
const fail = (f, m) => { failed++; console.log(`ERROR ${f}: ${m}`) }

function sample(schema, mode) {
  if (!schema) return 'text'
  if (schema.enum) return schema.enum[0]
  switch (schema.type) {
    case 'object': {
      const o = {}
      for (const [k, v] of Object.entries(schema.properties || {})) o[k] = sample(v, mode)
      return o
    }
    case 'array': return mode === 'empty' ? [] : [sample(schema.items, mode), sample(schema.items, mode)]
    case 'boolean': return mode !== 'negative'
    case 'integer': case 'number': return mode === 'negative' ? 1 : 0
    default: return 'x'
  }
}

async function run(file, body, meta, mode, args) {
  const phases = []
  let agents = 0
  const agent = async (prompt, opts = {}) => {
    if (typeof prompt !== 'string' || !prompt.trim()) throw new Error('agent() needs a non-empty prompt string')
    for (const k of Object.keys(opts)) if (!['schema', 'label', 'stallMs'].includes(k)) throw new Error(`agent() option "${k}" is not in the documented set`)
    agents++
    if (mode === 'null') return null
    return sample(opts.schema, mode)
  }
  const pipeline = async (items, fn) => {
    if (!Array.isArray(items)) throw new Error('pipeline() needs an array')
    if (items.length > 4096) throw new Error('pipeline() over 4,096 items')
    return Promise.all(items.map(i => fn(i)))
  }
  const parallel = async tasks => Promise.all(tasks.map(t => (typeof t === 'function' ? t() : t)))
  const out = await new AsyncFunction('agent', 'pipeline', 'parallel', 'phase', 'log', 'args', body)(
    agent, pipeline, parallel, t => phases.push(t), () => {}, args)
  if (out === undefined) throw new Error(`returned nothing (mode ${mode})`)
  JSON.stringify(out)
  const declared = (meta.phases || []).map(p => p.title)
  for (const p of phases) if (declared.length && !declared.includes(p)) throw new Error(`phase("${p}") is not listed in meta.phases`)
  return agents
}

;(async () => {
  if (!fs.existsSync(dir)) { console.log('claude-workflows/ missing'); process.exit(1) }
  const files = fs.readdirSync(dir).filter(f => f.endsWith('.js')).sort()
  const names = new Set()
  for (const f of files) {
    const src = fs.readFileSync(path.join(dir, f), 'utf8')
    if (/[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(src) || /\r(?!\n)/.test(src)) fail(f, 'contains a control character')
    const m = src.match(/^export const meta = (\{[\s\S]*?\n\})\n/)
    if (!m) { fail(f, '`export const meta = {...}` must be the first statement'); continue }
    let meta
    try { meta = new Function(`return (${m[1]})`)() } catch (e) { fail(f, `meta is not a plain literal: ${e.message}`); continue }
    if (!meta.name || !meta.description) fail(f, 'meta needs name and description')
    if (meta.name !== f.replace(/\.js$/, '')) fail(f, `meta.name "${meta.name}" should match the file name`)
    if (names.has(meta.name)) fail(f, 'duplicate meta.name'); names.add(meta.name)
    const body = src.slice(m[0].length)
    for (const [re, what] of [[/\bimport\s*\(/, 'import()'], [/^\s*import\s/m, 'import'], [/\brequire\s*\(/, 'require()'],
      [/Date\.now\s*\(/, 'Date.now()'], [/Math\.random\s*\(/, 'Math.random()'], [/new Date\s*\(\s*\)/, 'new Date()']]) {
      if (re.test(body)) fail(f, `${what} is not allowed in a workflow script`)
    }
    try {
      let most = 0
      for (const mode of ['positive', 'negative', 'empty', 'null']) {
        for (const args of [undefined, 'main', { base: 'main', slice: 'S1', focus: 'x' }]) {
          most = Math.max(most, await run(f, body, meta, mode, args))
        }
      }
      console.log(`ok    ${f}  (/praxis:${meta.name}, up to ${most} agents in the mock run)`)
    } catch (e) { fail(f, e.message) }
  }
  console.log(`${files.length} workflow scripts, ${failed} errors`)
  process.exit(failed ? 1 : 0)
})()
