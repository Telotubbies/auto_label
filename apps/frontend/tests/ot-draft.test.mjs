// OT output form rules (Task 40): the endpoint each protocol sends, the validation applied
// before a request leaves the browser, and the one-line endpoint summary in the list.
//   node --test tests/ot-draft.test.mjs   (from apps/frontend)
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  draftEndpoint, draftInput, emptyDraft, endpointSummary, intField,
} from '../src/features/project/otDraft.ts'

const draft = (over = {}) => ({ ...emptyDraft(), ...over })

test('modbus sends host, port, unit id, register and address', () => {
  const endpoint = draftEndpoint(draft({ protocol: 'modbus', host: '192.168.1.10', port: '502', unit_id: '1', register: 'holding', address: '7' }))
  assert.deepEqual(endpoint, { host: '192.168.1.10', port: 502, unit_id: 1, register: 'holding', address: 7 })
})

test('mqtt sends host, port and topic', () => {
  const endpoint = draftEndpoint(draft({ protocol: 'mqtt', host: 'broker.example.com', port: '1883', topic: 'line1/reject' }))
  assert.deepEqual(endpoint, { host: 'broker.example.com', port: 1883, topic: 'line1/reject' })
})

test('opcua sends the endpoint url and node id, and refuses a non-opc.tcp url', () => {
  const endpoint = draftEndpoint(draft({ protocol: 'opcua', endpoint_url: 'opc.tcp://plc:4840', node_id: 'ns=2;s=Reject' }))
  assert.deepEqual(endpoint, { endpoint_url: 'opc.tcp://plc:4840', node_id: 'ns=2;s=Reject' })
  assert.throws(() => draftEndpoint(draft({ protocol: 'opcua', endpoint_url: 'http://plc:4840', node_id: 'x' })), /opc\.tcp:\/\//)
})

test('gpio sends the line and its polarity', () => {
  const endpoint = draftEndpoint(draft({ protocol: 'gpio', line: '4', active_high: false }))
  assert.deepEqual(endpoint, { line: 4, active_high: false })
})

test('intField rejects a non-integer and an out-of-range value', () => {
  assert.throws(() => intField('1.5', 'Port', 1, 65535), /Port must be an integer between 1 and 65535/)
  assert.throws(() => intField('70000', 'Port', 1, 65535), /Port must be an integer between 1 and 65535/)
  assert.throws(() => intField('abc', 'Port', 1, 65535), /Port must be an integer between 1 and 65535/)
  assert.equal(intField('502', 'Port', 1, 65535), 502)
})

test('the input carries the checked kinds and a split, trimmed class list', () => {
  const input = draftInput(draft({ name: ' Gate ', host: '10.0.0.1', kinds: ['zone', 'line'], classes: ' scratch, dent ,, ' }))
  assert.equal(input.name, 'Gate')
  assert.deepEqual(input.event_filter, { kinds: ['zone', 'line'], classes: ['scratch', 'dent'] })
  assert.equal(input.latency_budget_ms, 250)
  assert.equal(input.pulse_ms, 100)
})

test('the input rejects a pulse or budget outside the API range', () => {
  assert.throws(() => draftInput(draft({ name: 'Gate', host: '10.0.0.1', latency: '5' })), /Latency budget/)
  assert.throws(() => draftInput(draft({ name: 'Gate', host: '10.0.0.1', pulse: '9000' })), /Pulse/)
})

test('endpointSummary renders one line for every protocol', () => {
  const base = { id: 'o', workspace_id: 'w', project_id: 'p', name: 'n', event_filter: { kinds: [], classes: [] },
    latency_budget_ms: 250, pulse_ms: 100, enabled: true, last_status: 'never', last_latency_ms: null,
    last_error: '', created: 0, updated: 0 }
  const lines = [
    ['modbus', { host: '10.0.0.1', port: 502, unit_id: 1, register: 'coil', address: 10 }, ['10.0.0.1:502', 'coil 10', 'unit 1']],
    ['mqtt', { host: '10.0.0.2', port: 1883, topic: 'line1/reject' }, ['line1/reject @ 10.0.0.2:1883']],
    ['opcua', { endpoint_url: 'opc.tcp://plc:4840', node_id: 'ns=2;s=Reject' }, ['ns=2;s=Reject', 'opc.tcp://plc:4840']],
    ['gpio', { line: 4, active_high: false }, ['line 4', 'active low']],
  ]
  for (const [protocol, endpoint, parts] of lines) {
    const text = endpointSummary({ ...base, protocol, endpoint })
    assert.ok(!text.includes('\n'), `${protocol} summary must stay on one line`)
    for (const part of parts) assert.ok(text.includes(part), `${protocol} summary should include ${part}: ${text}`)
  }
})
