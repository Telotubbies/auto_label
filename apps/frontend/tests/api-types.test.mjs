// The frontend API types are generated from apps/backend/openapi.json, so a schema change that
// skips regeneration fails here and in `npm run build`.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { render } from '../scripts/gen-api-types.mjs'

const spec = JSON.parse(readFileSync(new URL('../../backend/openapi.json', import.meta.url), 'utf8'))
const committed = readFileSync(new URL('../src/lib/api-types.gen.ts', import.meta.url), 'utf8')

test('the committed api types match the OpenAPI document', () => {
  assert.equal(committed, render(spec), 'run `npm run gen:api-types` — the generated types are stale')
})

test('a changed schema changes the generated text', () => {
  const drifted = structuredClone(spec)
  drifted.components.schemas.ProjectIn.properties.new_field = { type: 'string', title: 'New Field' }
  assert.notEqual(render(drifted), committed)
})

test('required, nullable, array, map and numeric properties keep their shape', () => {
  const ts = render({
    components: {
      schemas: {
        ThingIn: {
          type: 'object',
          required: ['name'],
          properties: {
            name: { type: 'string' },
            note: { anyOf: [{ type: 'string' }, { type: 'null' }] },
            tags: { type: 'array', items: { type: 'string' } },
            config: { type: 'object', additionalProperties: true },
            count: { type: 'integer' },
          },
        },
      },
    },
  })
  assert.match(ts, /export interface ThingIn \{/)
  assert.match(ts, /\n {2}name: string\n/)
  assert.match(ts, /\n {2}note\?: string \| null\n/)
  assert.match(ts, /\n {2}tags\?: string\[\]\n/)
  assert.match(ts, /\n {2}config\?: Record<string, unknown>\n/)
  assert.match(ts, /\n {2}count\?: number\n/)
})
