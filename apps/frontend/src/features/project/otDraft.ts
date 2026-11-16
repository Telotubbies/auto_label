// Pure draft rules for the OT output form. Kept free of React so the Node test runner can
// exercise the endpoint mapping without mounting the page; the page only renders the draft.
import type { OtOutput, OtOutputInput, OtProtocol } from '../../lib/types'

export type Draft = {
  name: string; protocol: OtProtocol; host: string; port: string; unit_id: string; register: 'coil' | 'holding'; address: string
  topic: string; endpoint_url: string; node_id: string; line: string; active_high: boolean
  kinds: string[]; classes: string; latency: string; pulse: string; enabled: boolean
}

export const emptyDraft = (): Draft => ({
  name: '', protocol: 'modbus', host: '', port: '502', unit_id: '1', register: 'coil', address: '0', topic: '',
  endpoint_url: 'opc.tcp://', node_id: '', line: '0', active_high: true, kinds: [], classes: '', latency: '250',
  pulse: '100', enabled: true,
})

export const required = (value: string, label: string) => {
  const text = value.trim(); if (!text) throw new Error(`${label} is required`)
  return text
}

/** Parse an integer field and reject anything the API would call invalid. */
export const intField = (value: string, label: string, min: number, max: number) => {
  const n = Number(value)
  if (!Number.isInteger(n) || n < min || n > max) throw new Error(`${label} must be an integer between ${min} and ${max}`)
  return n
}

/** The protocol-specific endpoint object the API accepts. */
export function draftEndpoint(d: Draft): Record<string, string | number | boolean> {
  if (d.protocol === 'modbus') return {
    host: required(d.host, 'Host'), port: intField(d.port, 'Port', 1, 65535), unit_id: intField(d.unit_id, 'Unit ID', 1, 247),
    register: d.register, address: intField(d.address, 'Address', 0, 65535),
  }
  if (d.protocol === 'mqtt') return { host: required(d.host, 'Host'), port: intField(d.port, 'Port', 1, 65535), topic: required(d.topic, 'Topic') }
  if (d.protocol === 'opcua') {
    const url = required(d.endpoint_url, 'Endpoint URL')
    if (!url.startsWith('opc.tcp://')) throw new Error('Endpoint URL must start with opc.tcp://')
    return { endpoint_url: url, node_id: required(d.node_id, 'Node ID') }
  }
  return { line: intField(d.line, 'Line', 0, 1023), active_high: d.active_high }
}

/** Create payload for a draft; throws on the first value the API would reject. */
export const draftInput = (d: Draft): OtOutputInput => ({
  name: required(d.name, 'Name'), protocol: d.protocol, endpoint: draftEndpoint(d),
  event_filter: { kinds: d.kinds, classes: d.classes.split(',').map((x) => x.trim()).filter(Boolean) },
  latency_budget_ms: intField(d.latency, 'Latency budget', 10, 10_000),
  pulse_ms: intField(d.pulse, 'Pulse', 10, 5_000), enabled: d.enabled,
})

const str = (v: unknown) => (v == null ? '' : String(v))

/** One-line endpoint preview, kept close to what an integrator would type. */
export function endpointSummary(o: OtOutput): string {
  const e = o.endpoint
  if (o.protocol === 'modbus') return `${str(e.host)}:${str(e.port)} · ${str(e.register)} ${str(e.address)} (unit ${str(e.unit_id)})`
  if (o.protocol === 'mqtt') return `${str(e.topic)} @ ${str(e.host)}:${str(e.port)}`
  if (o.protocol === 'opcua') return `${str(e.node_id)} · ${str(e.endpoint_url)}`
  return `line ${str(e.line)} · active ${e.active_high === false ? 'low' : 'high'}`
}
