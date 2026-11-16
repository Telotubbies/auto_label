import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { History, Plus, RadioTower, Trash2, Zap } from 'lucide-react'
import { api } from '@/lib/api'
import { useFlag } from '@/lib/flags'
import type { OtOutput, OtProtocol } from '@/lib/types'
import { Badge, Button, Card, EmptyState, Field, Input, Modal, Select, Spinner, Switch, toast, fmtAgo, fmtDate } from '@/components/ui'
import { draftInput, emptyDraft, endpointSummary } from './otDraft'
import type { Draft } from './otDraft'

const PROTOCOLS: { id: OtProtocol; label: string }[] = [
  { id: 'modbus', label: 'Modbus TCP' }, { id: 'opcua', label: 'OPC-UA' },
  { id: 'mqtt', label: 'MQTT' }, { id: 'gpio', label: 'GPIO' },
]
const KINDS = ['count', 'zone', 'line', 'dwell', 'vlm']
const STATUS_TONE: Record<string, string> = {
  ok: 'bg-success/15 text-success', late: 'bg-warning/15 text-warning', failed: 'bg-destructive/15 text-destructive',
  never: 'bg-secondary text-secondary-foreground',
}
const OtStatus = ({ status }: { status: string }) => <Badge className={STATUS_TONE[status] ?? STATUS_TONE.never}>{status}</Badge>

const Num = ({ label, value, set, min, max }: { label: string; value: string; set: (v: string) => void; min: number; max: number }) => (
  <Field label={label}><Input type="number" inputMode="numeric" min={min} max={max} value={value} onChange={(e) => set(e.target.value)} /></Field>
)
const Text = ({ label, value, set, placeholder }: { label: string; value: string; set: (v: string) => void; placeholder?: string }) => (
  <Field label={label}><Input required value={value} onChange={(e) => set(e.target.value)} placeholder={placeholder} /></Field>
)

function OutputForm({ ws, project, onClose }: { ws: string; project: string; onClose: () => void }) {
  const qc = useQueryClient()
  const [d, setD] = useState<Draft>(emptyDraft)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setD((prev) => ({ ...prev, [key]: value }))
  const choose = (protocol: OtProtocol) => setD({ ...d, protocol, port: protocol === 'modbus' ? '502' : protocol === 'mqtt' ? '1883' : '' })

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    let body
    try {
      body = draftInput(d)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Check the values above'
      setError(msg); toast.err(msg); return
    }
    setBusy(true)
    try {
      await api.createOtOutput(ws, project, body)
      await qc.invalidateQueries({ queryKey: ['ot-outputs', ws, project] })
      toast.ok(`Output "${body.name}" added`); onClose()
    } catch (err) { toast.err(err as Error) } finally { setBusy(false) }
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded-lg border bg-muted/30 p-4" aria-label="Add OT output">
      <div className="grid gap-3 sm:grid-cols-2">
        <Text label="Name" value={d.name} set={(v) => set('name', v)} />
        <Field label="Protocol">
          <Select className="w-full" value={d.protocol} onChange={(e) => choose(e.target.value as OtProtocol)}>
            {PROTOCOLS.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
          </Select>
        </Field>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {d.protocol === 'modbus' && <>
          <Text label="Host" value={d.host} set={(v) => set('host', v)} placeholder="192.168.1.10" />
          <Num label="Port" value={d.port} set={(v) => set('port', v)} min={1} max={65535} />
          <Num label="Unit ID" value={d.unit_id} set={(v) => set('unit_id', v)} min={1} max={247} />
          <Field label="Register">
            <Select className="w-full" value={d.register} onChange={(e) => set('register', e.target.value as 'coil' | 'holding')}>
              <option value="coil">Coil</option><option value="holding">Holding register</option>
            </Select>
          </Field>
          <Num label="Address" value={d.address} set={(v) => set('address', v)} min={0} max={65535} />
        </>}
        {d.protocol === 'mqtt' && <>
          <Text label="Host" value={d.host} set={(v) => set('host', v)} placeholder="broker.example.com" />
          <Num label="Port" value={d.port} set={(v) => set('port', v)} min={1} max={65535} />
          <Text label="Topic" value={d.topic} set={(v) => set('topic', v)} placeholder="line/reject" />
        </>}
        {d.protocol === 'opcua' && <>
          <Text label="Endpoint URL" value={d.endpoint_url} set={(v) => set('endpoint_url', v)} placeholder="opc.tcp://plc:4840" />
          <Text label="Node ID" value={d.node_id} set={(v) => set('node_id', v)} placeholder="ns=2;s=Reject" />
        </>}
        {d.protocol === 'gpio' && <>
          <Num label="Line" value={d.line} set={(v) => set('line', v)} min={0} max={1023} />
          <label className="flex items-end gap-2 pb-2 text-sm">
            <input type="checkbox" className="accent-primary" checked={d.active_high} onChange={(e) => set('active_high', e.target.checked)} />
            Active high
          </label>
        </>}
      </div>
      <fieldset className="m-0 border-0 p-0">
        <legend className="mb-1.5 text-sm font-medium">Event filter</legend>
        <div className="flex flex-wrap gap-x-4 gap-y-1.5">
          {KINDS.map((k) => <label key={k} className="flex items-center gap-1.5 text-sm capitalize"><input type="checkbox" className="accent-primary" checked={d.kinds.includes(k)} onChange={(e) => set('kinds', e.target.checked ? [...d.kinds, k] : d.kinds.filter((x) => x !== k))} />{k}</label>)}
        </div>
        <div className="mt-2">
          <Field label="Class filter" hint="Comma-separated class names. Empty matches any class.">
            <Input value={d.classes} onChange={(e) => set('classes', e.target.value)} placeholder="scratch, dent" />
          </Field>
        </div>
      </fieldset>
      <div className="grid gap-3 sm:grid-cols-3">
        <Num label="Latency budget (ms)" value={d.latency} set={(v) => set('latency', v)} min={10} max={10000} />
        <Num label="Pulse (ms)" value={d.pulse} set={(v) => set('pulse', v)} min={10} max={5000} />
        <div className="flex items-end gap-2 pb-2 text-sm">
          <Switch label="Output enabled" checked={d.enabled} onChange={(v) => set('enabled', v)} />
          <span>{d.enabled ? 'Enabled' : 'Disabled'}</span>
        </div>
      </div>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      <div className="flex flex-wrap justify-end gap-2">
        <Button type="button" variant="outline" size="sm" onClick={onClose} disabled={busy}>Cancel</Button>
        <Button type="submit" size="sm" disabled={busy}>{busy ? 'Adding…' : 'Add output'}</Button>
      </div>
    </form>
  )
}

function OutputRow({ ws, project, output, canEdit, onHistory }: {
  ws: string; project: string; output: OtOutput; canEdit: boolean; onHistory: () => void
}) {
  const qc = useQueryClient()
  const [busy, setBusy] = useState(false)
  const refresh = () => qc.invalidateQueries({ queryKey: ['ot-outputs', ws, project] })
  const toggle = async (enabled: boolean) => {
    setBusy(true); try { await api.updateOtOutput(ws, project, output.id, { enabled }); await refresh() }
    catch (err) { toast.err(err as Error) } finally { setBusy(false) }
  }
  const test = async () => {
    setBusy(true)
    try {
      const r = await api.testOtOutput(ws, project, output.id)
      if (r.status === 'failed') toast.err(`Failed: ${r.detail}`)
      else if (r.status === 'late') toast.err(`Too late — not actuated (${r.latency_ms ?? 0} ms)`)
      else toast.ok(`Signal sent in ${r.latency_ms ?? 0} ms`)
      await refresh()
    } catch (err) { toast.err(err as Error) } finally { setBusy(false) }
  }
  const remove = async () => {
    if (!confirm(`Delete "${output.name}" and its delivery history?`)) return
    setBusy(true); try { await api.deleteOtOutput(ws, project, output.id); await refresh(); toast.ok('Output deleted') }
    catch (err) { toast.err(err as Error) } finally { setBusy(false) }
  }

  const filter = output.event_filter
  return (
    <li className="flex flex-wrap items-start justify-between gap-3 p-4">
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">{output.name}</span>
          <Badge>{PROTOCOLS.find((p) => p.id === output.protocol)?.label ?? output.protocol}</Badge>
          <OtStatus status={output.last_status} />
          {!output.enabled && <Badge className="bg-muted text-muted-foreground">Disabled</Badge>}
        </div>
        <p className="break-all font-mono text-xs text-muted-foreground">{endpointSummary(output)}</p>
        <p className="text-xs text-muted-foreground">
          Budget {output.latency_budget_ms} ms · pulse {output.pulse_ms} ms · {filter.kinds.length ? filter.kinds.join(', ') : 'any event'}
          {filter.classes.length ? ` · classes: ${filter.classes.join(', ')}` : ''}
        </p>
        {output.last_latency_ms != null && <p className="text-xs text-muted-foreground">Last latency {output.last_latency_ms} ms</p>}
        {output.last_error && <p className="text-xs text-destructive">{output.last_error}</p>}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {canEdit && <Switch label={`Enable ${output.name}`} checked={output.enabled} onChange={(v) => void toggle(v)} />}
        {canEdit && <Button variant="outline" size="sm" onClick={test} disabled={busy || !output.enabled}
          title={output.enabled ? 'Send one reject pulse' : 'Enable the output first'}><Zap className="h-3.5 w-3.5" aria-hidden />Test signal</Button>}
        <Button variant="outline" size="sm" onClick={onHistory}><History className="h-3.5 w-3.5" aria-hidden />History</Button>
        {canEdit && <Button variant="ghost" size="sm" className="text-destructive" onClick={remove} disabled={busy} aria-label={`Delete ${output.name}`}><Trash2 className="h-3.5 w-3.5" aria-hidden />Delete</Button>}
      </div>
    </li>
  )
}

function HistoryModal({ ws, project, output, onClose }: {
  ws: string; project: string; output: OtOutput | null; onClose: () => void
}) {
  const q = useQuery({
    queryKey: ['ot-deliveries', output?.id], queryFn: () => api.otDeliveries(ws, project, output!.id), enabled: !!output,
  })
  return (
    <Modal open={!!output} onClose={onClose} wide title={output ? `${output.name} · delivery history` : 'Delivery history'}>
      {q.isLoading ? <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground"><Spinner /> Loading deliveries…</p> : q.isError ? (
        <div className="flex flex-wrap items-center gap-2"><p role="alert" className="text-sm text-destructive">Could not load delivery history.</p><Button variant="outline" size="sm" onClick={() => void q.refetch()}>Try again</Button></div>
      ) : !q.data?.length ? (
        <EmptyState title="No deliveries yet." hint="Send a test signal or wait for a rule to fire." />
      ) : (
        <div className="overflow-x-auto" role="region" aria-label="Delivery history" tabIndex={0}>
          <table className="w-full min-w-[36rem] text-sm">
            <caption className="sr-only">Recent deliveries for {output?.name}</caption>
            <thead className="bg-muted/60 text-left text-xs text-muted-foreground">
              <tr>
                {['Time', 'Status', 'Latency', 'Stream / kind', 'Detail'].map((h) => <th key={h} scope="col" className="px-3 py-2 font-medium">{h}</th>)}
              </tr>
            </thead>
            <tbody className="divide-y">
              {q.data.map((d) => (
                <tr key={d.id} className="align-top">
                  <td className="px-3 py-2"><div>{fmtDate(d.created)}</div><div className="text-xs text-muted-foreground">{fmtAgo(d.created)}</div></td>
                  <td className="px-3 py-2"><OtStatus status={d.status} /></td>
                  <td className="px-3 py-2">{d.latency_ms == null ? '—' : `${d.latency_ms} ms`}</td>
                  <td className="px-3 py-2">
                    <div className="font-mono text-xs">{d.rule_kind} · {d.stream_id}</div>
                    {(d.event.summary || d.event.class) && (
                      <div className="text-xs text-muted-foreground">{d.event.class ?? ''}{d.event.class && d.event.summary ? ' · ' : ''}{d.event.summary ?? ''}</div>
                    )}
                  </td>
                  <td className="px-3 py-2 text-xs text-muted-foreground">{d.detail || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Modal>
  )
}

export default function OtOutputs({ ws, project, canEdit }: { ws: string; project: string; canEdit: boolean }) {
  const enabled = useFlag('task_40')
  const q = useQuery({ queryKey: ['ot-outputs', ws, project], queryFn: () => api.otOutputs(ws, project), enabled })
  const [adding, setAdding] = useState(false)
  const [history, setHistory] = useState<OtOutput | null>(null)
  if (!enabled) return null

  return (
    <>
      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b p-5">
          <div className="max-w-prose">
            <h2 className="flex items-center gap-2 font-semibold"><RadioTower className="h-4 w-4 text-primary" aria-hidden />PLC / OT output</h2>
            <p className="mt-0.5 text-sm text-muted-foreground">
              A rule firing pulses a reject output; the signal is released (fail-safe) after the pulse. Events later than the latency budget are reported and do not actuate.
            </p>
          </div>
          {canEdit && !adding && <Button size="sm" onClick={() => setAdding(true)}><Plus className="h-3.5 w-3.5" aria-hidden />Add output</Button>}
        </div>
        <div className="space-y-4 p-5">
          {adding && <OutputForm ws={ws} project={project} onClose={() => setAdding(false)} />}
          {q.isLoading ? <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground"><Spinner /> Loading OT outputs…</p> : q.isError ? (
            <div className="flex flex-wrap items-center gap-2"><p role="alert" className="text-sm text-destructive">Could not load OT outputs.</p><Button variant="outline" size="sm" onClick={() => void q.refetch()}>Try again</Button></div>
          ) : !q.data?.length ? (
            <EmptyState title="No OT outputs configured." hint="Add a Modbus, OPC-UA, MQTT or GPIO endpoint to pulse a reject signal when a rule fires." />
          ) : (
            <ul className="divide-y rounded-lg border">
              {q.data.map((o) => <OutputRow key={o.id} ws={ws} project={project} output={o} canEdit={canEdit} onHistory={() => setHistory(o)} />)}
            </ul>
          )}
          {!canEdit && q.isSuccess && <p className="text-xs text-muted-foreground">Read only — a project manager or workspace admin can change OT outputs.</p>}
        </div>
      </Card>
      <HistoryModal ws={ws} project={project} output={history} onClose={() => setHistory(null)} />
    </>
  )
}
