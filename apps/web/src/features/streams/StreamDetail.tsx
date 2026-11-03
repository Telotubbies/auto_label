import { Fragment, useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, ImageOff, Play, Plus, ScanLine, Send, Square, Trash2, TriangleAlert, VideoOff } from 'lucide-react'
import { api, fileUrl } from '@/lib/api'
import { useProjectPermissions } from '@/lib/perms'
import { classColor, dateLocale } from '@/lib/theme'
import type { StreamCountOp, StreamEvent, StreamEventPage, StreamEventRule, StreamItem, StreamPrediction, StreamRule, StreamRuleKind, StreamZone } from '@/lib/types'
import { Badge, Button, Card, EmptyState, Field, Input, Modal, PageHeader, Select, Spinner, Switch, Tabs, fmtAgo, toast } from '@/components/ui'
import { Glass } from '@/components/glass'
import { cn } from '@/lib/utils'
import { StreamStatusChip, displaySource, isStreamLive } from './Streams'
import ZoneEditor from './ZoneEditor'

// ---------- shared formatting -------------------------------------------------
const fmtInt = (n: number) => (Number.isFinite(n) ? n.toLocaleString() : '—')
const fmtCoord = (n: number) => (Math.round(n * 100) / 100).toFixed(2)
const fmtLine = (line: number[]) => line.map(fmtCoord).join(', ')
const fmtTime = (t: number) =>
  new Date(t * 1000).toLocaleString(dateLocale(), { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' })

const zoneName = (zones: StreamZone[], id: string) => {
  const i = zones.findIndex((z) => z.id === id)
  return i >= 0 ? `Zone ${i + 1}` : id
}

const ruleClassName = (rule: StreamRule) => (rule.kind === 'vlm' ? 'VLM' : rule.class)

/** Events carry the rule that fired (copy), so history survives later rule edits. */
const eventRuleName = (rule?: StreamEventRule) => rule?.label ?? 'Removed rule'

/** Short human label used by the current rules and their filter. */
function ruleName(rule: StreamRule | undefined, zones: StreamZone[]): string {
  if (!rule) return 'Removed rule'
  switch (rule.kind) {
    case 'count': return `${rule.class} ${rule.op} ${rule.k}${rule.for_s ? ` for ${rule.for_s}s` : ''}`
    case 'zone': return `${rule.class} enters ${zoneName(zones, rule.zone_id)}`
    case 'line': return `${rule.class} crosses line (${rule.direction})`
    case 'dwell': return `${rule.class} stays over ${rule.seconds}s in ${zoneName(zones, rule.zone_id)}`
    case 'vlm': return `VLM: ${rule.question}`
  }
}

/** Everything that is not the class, so a rule row can show every param it stores. */
function ruleDetail(rule: StreamRule, zones: StreamZone[]): string {
  switch (rule.kind) {
    case 'count': return `count · ${rule.op} ${rule.k} · stable ${rule.for_s ?? 0}s`
    case 'zone': return `zone · ${zoneName(zones, rule.zone_id)} (${rule.zone_id})`
    case 'line': return `line · ${fmtLine(rule.line)} · direction ${rule.direction}`
    case 'dwell': return `dwell · ${zoneName(zones, rule.zone_id)} (${rule.zone_id}) · ${rule.seconds}s`
    case 'vlm': return `vlm · every ${rule.every_s}s`
  }
}

const topClasses = (preds: StreamPrediction[]) => {
  const best = new Map<string, { conf: number; id: number }>()
  for (const p of preds) {
    const cur = best.get(p.class)
    if (!cur || p.confidence > cur.conf) best.set(p.class, { conf: p.confidence, id: p.class_id ?? 0 })
  }
  return [...best.entries()].sort((a, b) => b[1].conf - a[1].conf)
}

// ---------- live panel --------------------------------------------------------
function LivePanel({ stream, admin, busy, onStart }: { stream: StreamItem; admin: boolean; busy: boolean; onStart: () => void }) {
  const live = isStreamLive(stream.status)
  const nextSrc = fileUrl(stream.mjpeg)
  const [src, setSrc] = useState('')
  const [failed, setFailed] = useState(false)
  const [ready, setReady] = useState(false)
  const [nonce, setNonce] = useState(0)

  // Keep the open MJPEG connection across polls: only swap the URL when the stream restarts or the token
  // is refreshed after an error.
  useEffect(() => {
    if (!live || !nextSrc) { setSrc(''); return }
    setSrc((prev) => (prev && prev.split('?')[0] === nextSrc.split('?')[0] ? prev : nextSrc))
  }, [live, nextSrc])

  useEffect(() => { setFailed(false); setReady(false) }, [stream.id])
  // A fresh URL is a fresh connection attempt; clearing `failed` lets the retry mount the <img>.
  // An empty URL means the stream stopped: hide the old frame until new bytes arrive.
  useEffect(() => { if (src) setFailed(false); else setReady(false) }, [src])

  const showImage = live && !failed && !!src
  const showFrame = showImage && ready
  const fps = Number.isFinite(stream.fps) ? stream.fps.toFixed(1) : '0.0'
  const stoppedLike = stream.status === 'stopped' || stream.status === 'error'
  const retry = () => {
    setFailed(false)
    setNonce((n) => n + 1)
    setSrc(nextSrc ? `${nextSrc}${nextSrc.includes('?') ? '&' : '?'}retry=${nonce + 1}` : '')
  }

  return (
    <section aria-label="Live stream">
      <Card className="overflow-hidden">
        <div className="relative w-full bg-black" style={{ aspectRatio: '16 / 9' }}>
          {showImage && (
            <img src={src} alt={`Live view of ${stream.name}`}
              className="absolute inset-0 h-full w-full object-contain"
              onLoad={() => { setReady(true); setFailed(false) }}
              onError={() => { setFailed(true); setSrc('') }} />
          )}

          {!showFrame && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 px-6 text-center">
              <VideoOff className="h-7 w-7 text-white/40" aria-hidden />
              <p className="text-sm font-medium text-white">
                {stream.status === 'stopped' ? 'Stream is stopped'
                  : stream.status === 'error' ? 'Stream failed'
                    : failed ? 'Frame unavailable'
                      : stream.status === 'connecting' ? 'Connecting…'
                        : stream.status === 'reconnecting' ? 'Reconnecting…'
                          : 'Waiting for frames…'}
              </p>
              <p className="max-w-sm text-xs text-white/60 [overflow-wrap:anywhere]">
                {stoppedLike
                  ? (stream.lastError || 'Start the stream to open the camera feed.')
                  : failed
                    ? 'The live image could not load. It retries on the next refresh.'
                    : 'The camera is open; the first frame can take a few seconds.'}
              </p>
              <div className="mt-1 flex flex-wrap items-center justify-center gap-2">
                {failed && live && <Button size="sm" variant="outline" onClick={retry}>Retry</Button>}
                {admin && !live && stream.status !== 'connecting' && (
                  <Button size="sm" disabled={busy} onClick={onStart}>{busy ? <Spinner /> : <><Play className="h-3.5 w-3.5" /> Start stream</>}</Button>
                )}
              </div>
            </div>
          )}

          {/* Overlay chrome is the one glass surface on this solid, near-black viewport. */}
          <div className="pointer-events-none absolute inset-0">
            <Glass strength="overlay" className="absolute left-2 top-2 flex max-w-[52%] flex-wrap items-center gap-1.5 rounded-lg px-2 py-1.5 text-[11px] text-popover-foreground">
              <StreamStatusChip status={stream.status} />
              <span className="shrink-0 tabular-nums text-popover-foreground/80">{fps} fps</span>
            </Glass>
            <Glass strength="overlay" className="absolute right-2 top-2 hidden max-w-[44%] items-center rounded-lg px-2 py-1.5 text-[11px] text-popover-foreground sm:flex" title={stream.modelRef}>
              <span className="truncate font-mono">{stream.modelRef}</span>
            </Glass>
            <Glass strength="overlay" className="absolute bottom-2 left-2 flex max-w-[calc(100%-1rem)] flex-wrap items-center gap-x-3 gap-y-0.5 rounded-lg px-2 py-1.5 text-[11px] text-popover-foreground">
              <span><b className="font-semibold tabular-nums">{fmtInt(stream.events)}</b> <span className="text-popover-foreground/70">events</span></span>
              <span><b className="font-semibold tabular-nums">{stream.zones.length}</b> <span className="text-popover-foreground/70">zones</span></span>
              <span><b className="font-semibold tabular-nums">{stream.sampleFps}</b> <span className="text-popover-foreground/70">fps sample</span></span>
            </Glass>
          </div>
        </div>
      </Card>
    </section>
  )
}

// ---------- side summary ------------------------------------------------------
function SummaryPanel({ stream }: { stream: StreamItem }) {
  const rows: [string, ReactNode][] = [
    ['Model', <span className="block truncate font-mono text-xs" title={stream.modelRef}>{stream.modelRef}</span>],
    ['Capture fps', <span className="tabular-nums">{stream.fps.toFixed(1)}</span>],
    ['Sample fps', <span className="tabular-nums">{stream.sampleFps}</span>],
    ['Frames read', <span className="tabular-nums">{fmtInt(stream.frames)}</span>],
    ['Detections', <span className="tabular-nums">{fmtInt(stream.detections)}</span>],
    ['Events', <span className="tabular-nums">{fmtInt(stream.events)}</span>],
    ['Zones', <span className="tabular-nums">{stream.zones.length}</span>],
    ['Rules', <span className="tabular-nums">{stream.rules.length}</span>],
  ]
  return (
    <Card className="p-4" role="region" aria-label="Stream summary">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">Stream</h2>
        <StreamStatusChip status={stream.status} />
      </div>
      {stream.lastError && (
        <p className={cn('mt-2 rounded-md px-2.5 py-2 text-xs [overflow-wrap:anywhere]',
          stream.status === 'error' ? 'bg-destructive/10 text-destructive' : 'bg-warning/10 text-warning')}>
          {stream.lastError}
        </p>
      )}
      <dl className="mt-3 grid grid-cols-[auto_minmax(0,1fr)] items-baseline gap-x-4 gap-y-1.5">
        {rows.map(([label, value]) => (
          <Fragment key={label}>
            <dt className="text-xs text-muted-foreground">{label}</dt>
            <dd className="min-w-0 text-right text-sm">{value}</dd>
          </Fragment>
        ))}
      </dl>
      <div className="mt-3 border-t pt-3">
        <h3 className="text-xs font-semibold text-muted-foreground">Rules</h3>
        {!stream.rules.length ? (
          <p className="mt-1 text-xs text-muted-foreground">No rules yet.</p>
        ) : (
          <ul className="mt-1.5 max-h-56 space-y-1 overflow-y-auto pr-1">
            {stream.rules.map((rule, i) => (
              <li key={i} className="flex min-w-0 items-start gap-1.5 text-xs">
                <Badge className="mt-px shrink-0 px-1.5 py-0 text-[10px]">{rule.kind}</Badge>
                <span className="min-w-0 flex-1 [overflow-wrap:anywhere]">{ruleName(rule, stream.zones)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  )
}

// ---------- read-only rules (non-admins) -------------------------------------
function ReadOnlyRules({ stream }: { stream: StreamItem }) {
  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">Zones & rules</h2>
        <Badge>Read only</Badge>
      </div>
      <p className="mt-0.5 text-xs text-muted-foreground">Only project admins can change zones and rules. You can still review events.</p>
      <h3 className="mt-3 text-xs font-semibold text-muted-foreground">Zones</h3>
      {!stream.zones.length ? (
        <p className="mt-1 text-sm text-muted-foreground">No zones.</p>
      ) : (
        <ul className="mt-1 space-y-1 text-sm">
          {stream.zones.map((zone, i) => (
            <li key={zone.id} className="flex items-center gap-2">
              <span className="h-2 w-2 shrink-0 rounded-sm bg-primary" aria-hidden />
              <span>Zone {i + 1}</span>
              <span className="text-xs tabular-nums text-muted-foreground">{zone.points.length / 2} points</span>
            </li>
          ))}
        </ul>
      )}
      <h3 className="mt-3 text-xs font-semibold text-muted-foreground">Rules</h3>
      {!stream.rules.length ? (
        <p className="mt-1 text-sm text-muted-foreground">No rules.</p>
      ) : (
        <ul className="mt-1 space-y-1.5">
          {stream.rules.map((rule, i) => (
            <li key={i} className="flex min-w-0 items-start gap-2 text-sm">
              <Badge className="mt-0.5 shrink-0">{rule.kind}</Badge>
              <span className="min-w-0 [overflow-wrap:anywhere]">{ruleName(rule, stream.zones)}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

// ---------- rules -------------------------------------------------------------
function RulesSection({ stream, ws, project }: { stream: StreamItem; ws: string; project: string }) {
  const qc = useQueryClient()
  const classes = useQuery({ queryKey: ['classes', ws, project], queryFn: () => api.classes(ws, project) })
  const [kind, setKind] = useState<StreamRuleKind>('count')
  const [cls, setCls] = useState('')
  const [op, setOp] = useState<StreamCountOp>('>=')
  const [k, setK] = useState(1)
  const [forS, setForS] = useState(0)
  const [zoneId, setZoneId] = useState('')
  const [seconds, setSeconds] = useState(5)
  const [direction, setDirection] = useState<'in' | 'out' | 'both'>('both')
  const [question, setQuestion] = useState('')
  const [everyS, setEveryS] = useState(30)
  const [pendingLine, setPendingLine] = useState<number[] | null>(null)
  const [editor, setEditor] = useState<null | 'zones' | 'line'>(null)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!stream.zones.some((z) => z.id === zoneId)) setZoneId(stream.zones[0]?.id ?? '')
  }, [stream.zones, zoneId])

  const writeRules = async (rules: StreamRule[], ok: string) => {
    setSaving(true)
    try {
      const updated = await api.updateStream(ws, project, stream.id, { rules })
      qc.setQueryData(['stream', ws, project, stream.id], updated)
      qc.invalidateQueries({ queryKey: ['streams', ws, project] })
      toast.ok(ok)
      return true
    } catch (e) { toast.err(e as Error); return false } finally { setSaving(false) }
  }

  const remove = (index: number) => {
    void writeRules(stream.rules.filter((_, i) => i !== index), 'Rule removed')
  }

  const add = async () => {
    setError('')
    const name = cls.trim()
    if (kind !== 'vlm' && !name) { setError('Choose or type a class.'); return }

    let rule: StreamRule
    if (kind === 'count') {
      if (!Number.isInteger(k) || k <= 0) { setError('The threshold must be a whole number greater than 0.'); return }
      if (!Number.isFinite(forS) || forS < 0) { setError('Hold time must be 0 seconds or more.'); return }
      rule = { kind: 'count', class: name, op, k, for_s: forS }
    } else if (kind === 'zone') {
      if (!stream.zones.some((z) => z.id === zoneId)) { setError('Draw and select a zone first.'); return }
      rule = { kind: 'zone', class: name, zone_id: zoneId }
    } else if (kind === 'dwell') {
      if (!stream.zones.some((z) => z.id === zoneId)) { setError('Draw and select a zone first.'); return }
      if (!Number.isFinite(seconds) || seconds <= 0) { setError('Dwell time must be greater than 0.'); return }
      rule = { kind: 'dwell', class: name, zone_id: zoneId, seconds }
    } else if (kind === 'line') {
      if (!pendingLine || pendingLine.length !== 4) { setError('Draw the threshold line first.'); return }
      rule = { kind: 'line', class: name, line: pendingLine, direction }
    } else {
      if (!question.trim()) { setError('Enter the question for the vision model.'); return }
      if (!Number.isFinite(everyS) || everyS <= 0) { setError('The VLM interval must be greater than 0 seconds.'); return }
      rule = { kind: 'vlm', question: question.trim(), every_s: everyS }
    }

    if (await writeRules([...stream.rules, rule], 'Rule added')) {
      setPendingLine(null)
      setQuestion('')
      setError('')
    }
  }

  const zoneOptions = stream.zones.map((z, i) => <option key={z.id} value={z.id}>Zone {i + 1}</option>)

  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold">Rules</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">Counts, zones, lines, dwell time and VLM questions. Saving restarts a running stream; past events keep the rule that fired.</p>
        </div>
        <Badge className="tabular-nums">{stream.rules.length} rule{stream.rules.length === 1 ? '' : 's'}</Badge>
      </div>

      <ul className="mt-3 space-y-1.5">
        {!stream.rules.length && (
          <li className="rounded-md border border-dashed px-3 py-4 text-sm text-muted-foreground">
            No rules yet. Add one below to start capturing events.
          </li>
        )}
        {stream.rules.map((rule, i) => (
          <li key={i} className="flex min-w-0 flex-wrap items-center gap-2 rounded-md border px-2.5 py-2 text-sm">
            <span className="rounded bg-secondary px-1.5 py-0.5 text-[10px] font-semibold tabular-nums text-secondary-foreground">#{i + 1}</span>
            <span className="font-medium">{ruleClassName(rule)}</span>
            <Badge>{rule.kind}</Badge>
            <span className="min-w-0 flex-1 text-xs text-muted-foreground [overflow-wrap:anywhere]">{ruleDetail(rule, stream.zones)}</span>
            <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0 text-muted-foreground hover:text-destructive"
              aria-label={`Remove rule ${i + 1}`} disabled={saving} onClick={() => remove(i)}>
              <Trash2 className="h-4 w-4" />
            </Button>
          </li>
        ))}
      </ul>

      <div className="mt-4 rounded-lg border p-3">
        <h3 className="text-sm font-semibold">Add a rule</h3>
        <div className="mt-2 grid gap-3 sm:grid-cols-2">
          <Field label="Kind">
            <Select className="w-full" value={kind} onChange={(e) => setKind(e.target.value as StreamRuleKind)}>
              <option value="count">Count</option>
              <option value="zone">Zone entry</option>
              <option value="line">Line crossing</option>
              <option value="dwell">Dwell time</option>
              <option value="vlm">VLM question</option>
            </Select>
          </Field>
          {kind !== 'vlm' && (
            <Field label="Class" hint="Must match the model's class name.">
              <Input list="stream-rule-classes" placeholder="person" value={cls} onChange={(e) => setCls(e.target.value)} spellCheck={false} />
            </Field>
          )}

          {kind === 'vlm' && (
            <>
              <Field label="Question" hint="A yes/no question about the sampled frame. Only a “yes” answer creates an event.">
                <Input placeholder="Is anyone not wearing a helmet?" value={question} onChange={(e) => setQuestion(e.target.value)} />
              </Field>
              <Field label="Every (seconds)" hint="How often the question runs. VLM calls are not charged.">
                <Input type="number" min={1} step={1} value={everyS} onChange={(e) => setEveryS(Number(e.target.value))} inputMode="decimal" />
              </Field>
            </>
          )}

          {kind === 'count' && (
            <>
              <Field label="Operator">
                <Select className="w-full" value={op} onChange={(e) => setOp(e.target.value as StreamCountOp)}>
                  <option value=">=">≥ at least</option>
                  <option value=">">&gt; more than</option>
                  <option value="<=">≤ at most</option>
                  <option value="<">&lt; fewer than</option>
                  <option value="==">= exactly</option>
                </Select>
              </Field>
              <Field label="Threshold (k)">
                <Input type="number" min={1} step={1} value={k} onChange={(e) => setK(Number(e.target.value))} inputMode="numeric" />
              </Field>
              <Field label="Stable for (seconds)" hint="0 fires as soon as the count matches.">
                <Input type="number" min={0} step={0.5} value={forS} onChange={(e) => setForS(Number(e.target.value))} inputMode="decimal" />
              </Field>
            </>
          )}

          {(kind === 'zone' || kind === 'dwell') && (
            <div>
              <span className="mb-1.5 block text-sm font-medium">Zone</span>
              <div className="flex flex-wrap items-center gap-2">
                <Select aria-label="Zone" className="min-w-0 flex-1" value={zoneId} onChange={(e) => setZoneId(e.target.value)} disabled={!stream.zones.length}>
                  {!stream.zones.length && <option value="">No zones</option>}
                  {zoneOptions}
                </Select>
                <Button type="button" variant="ghost" size="sm" onClick={() => setEditor('zones')}><ScanLine className="h-3.5 w-3.5" /> Draw zones</Button>
              </div>
              {!stream.zones.length && <span className="mt-1 block text-xs text-muted-foreground">No zones yet — draw one first.</span>}
            </div>
          )}

          {kind === 'dwell' && (
            <Field label="Dwell (seconds)">
              <Input type="number" min={0.5} step={0.5} value={seconds} onChange={(e) => setSeconds(Number(e.target.value))} inputMode="decimal" />
            </Field>
          )}

          {kind === 'line' && (
            <>
              <Field label="Direction">
                <Select className="w-full" value={direction} onChange={(e) => setDirection(e.target.value as 'in' | 'out' | 'both')}>
                  <option value="both">Both directions</option>
                  <option value="in">In</option>
                  <option value="out">Out</option>
                </Select>
              </Field>
              <div>
                <span className="mb-1.5 block text-sm font-medium">Line</span>
                <div className="flex flex-wrap items-center gap-2">
                  <Button type="button" variant="outline" size="sm" onClick={() => setEditor('line')}>
                    <ScanLine className="h-3.5 w-3.5" /> {pendingLine ? 'Redraw line' : 'Draw line'}
                  </Button>
                  {pendingLine
                    ? <span className="font-mono text-[11px] text-muted-foreground">{fmtLine(pendingLine)}</span>
                    : <span className="text-xs text-muted-foreground">Draw on a paused frame.</span>}
                </div>
              </div>
            </>
          )}
        </div>

        <datalist id="stream-rule-classes">
          {(classes.data ?? []).map((c) => <option key={c.id} value={c.name} />)}
        </datalist>

        {error && <p className="mt-2 text-xs text-destructive" role="alert">{error}</p>}

        <div className="mt-3 flex justify-end">
          <Button disabled={saving} onClick={add}>{saving ? <><Spinner /> Saving…</> : <><Plus className="h-4 w-4" /> Add rule</>}</Button>
        </div>
      </div>

      <ZoneEditor open={!!editor} onClose={() => setEditor(null)} ws={ws} project={project} stream={stream}
        initialMode={editor ?? 'zones'} onLine={editor === 'line' ? (line) => { setPendingLine(line); setEditor(null) } : undefined} />
    </Card>
  )
}

// ---------- events ------------------------------------------------------------
function EventsTimeline({ stream, ws, project, active }: { stream: StreamItem; ws: string; project: string; active: boolean }) {
  const qc = useQueryClient()
  const { can } = useProjectPermissions(ws, project)
  // Reviewing footage follows the effective project role, not the workspace rank (I12).
  const canReview = can('project.review')
  const [rule, setRule] = useState('')
  const [cls, setCls] = useState('')
  const [reviewed, setReviewed] = useState('')
  const [preview, setPreview] = useState<StreamEvent | null>(null)

  const q = useQuery({
    queryKey: ['stream-events', ws, project, stream.id, rule, cls, reviewed],
    queryFn: () => api.streamEvents(ws, project, stream.id, {
      rule: rule === '' ? undefined : Number(rule),
      class: cls || undefined,
      reviewed: reviewed === '' ? undefined : (reviewed as 'yes' | 'no'),
      limit: 100,
    }),
    placeholderData: keepPreviousData,
    enabled: active,
    refetchInterval: active ? 3000 : false,
  })
  const events = q.data?.items ?? []
  const matching = q.data?.total ?? events.length
  const filtered = rule !== '' || cls !== '' || reviewed !== ''

  const classes = useQuery({ queryKey: ['classes', ws, project], queryFn: () => api.classes(ws, project) })
  const classNames = useMemo(() => {
    const set = new Set<string>((classes.data ?? []).map((c) => c.name))
    for (const e of events) for (const p of e.predictions ?? []) set.add(p.class)
    return [...set].sort((a, b) => a.localeCompare(b))
  }, [classes.data, events])

  const review = useMutation({
    mutationFn: (v: { id: string; reviewed: boolean }) => api.patchStreamEvent(ws, project, stream.id, v.id, v.reviewed),
    onSuccess: (event) => {
      qc.setQueryData<StreamEventPage>(
        ['stream-events', ws, project, stream.id, rule, cls, reviewed],
        (old) => (old ? { ...old, items: old.items.map((x) => (x.id === event.id ? event : x)) } : old),
      )
      qc.invalidateQueries({ queryKey: ['stream-events', ws, project, stream.id] })
    },
    onError: (e) => toast.err(e as Error),
  })

  const send = useMutation({
    mutationFn: (id: string) => api.eventToDataset(ws, project, stream.id, id),
    onSuccess: (r) => {
      toast.ok(r.uploaded > 0
        ? `Added ${r.uploaded} image${r.uploaded === 1 ? '' : 's'} to the dataset`
        : 'Nothing new — this event is already in the dataset')
      qc.invalidateQueries({ queryKey: ['images', ws, project] })
      qc.invalidateQueries({ queryKey: ['stream-events', ws, project, stream.id] })
      qc.invalidateQueries({ queryKey: ['stream', ws, project, stream.id] })
      qc.invalidateQueries({ queryKey: ['streams', ws, project] })
    },
    onError: (e) => toast.err(e as Error),
  })

  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">Events</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {filtered ? `${fmtInt(matching)} matching · ${fmtInt(stream.events)} captured` : `${fmtInt(stream.events)} captured`} · newest first · refreshed every 3 s
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex min-w-0 items-center gap-1.5 text-xs">
            <span className="text-muted-foreground">Rule</span>
            <Select className="h-8 max-w-[9.5rem] text-xs" value={rule} onChange={(e) => setRule(e.target.value)}>
              <option value="">All</option>
              {stream.rules.map((r, i) => (
                <option key={i} value={i}>#{i + 1} {r.kind} · {ruleClassName(r)}</option>
              ))}
            </Select>
          </label>
          <label className="flex min-w-0 items-center gap-1.5 text-xs">
            <span className="text-muted-foreground">Class</span>
            <Select className="h-8 max-w-[8.5rem] text-xs" value={cls} onChange={(e) => setCls(e.target.value)}>
              <option value="">All</option>
              {classNames.map((name) => <option key={name} value={name}>{name}</option>)}
            </Select>
          </label>
          <label className="flex min-w-0 items-center gap-1.5 text-xs">
            <span className="text-muted-foreground">Reviewed</span>
            <Select className="h-8 max-w-[8rem] text-xs" value={reviewed} onChange={(e) => setReviewed(e.target.value)}>
              <option value="">All</option>
              <option value="yes">Reviewed</option>
              <option value="no">Unreviewed</option>
            </Select>
          </label>
        </div>
      </div>

      {q.isLoading ? (
        <div className="flex justify-center py-12"><Spinner /></div>
      ) : q.isError ? (
        <div className="py-8">
          <EmptyState icon={<TriangleAlert className="h-6 w-6 text-destructive" />} title="Could not load events"
            hint={(q.error as Error)?.message} action={<Button size="sm" onClick={() => q.refetch()}>Try again</Button>} />
        </div>
      ) : !events.length ? (
        <div className="py-8">
          <EmptyState icon={<ImageOff className="h-6 w-6 text-muted-foreground/60" />}
            title={filtered ? 'No events match these filters' : 'No events yet'}
            hint={filtered ? 'Clear a filter to see more.' : 'Start the stream. Events appear here as soon as a rule fires.'}
            action={filtered
              ? <Button size="sm" variant="outline" onClick={() => { setRule(''); setCls(''); setReviewed('') }}>Clear filters</Button>
              : undefined} />
        </div>
      ) : (
        <ul className="mt-3 divide-y">
          {events.map((event) => {
            const rule_ = event.rule
            const chips = topClasses(event.predictions ?? [])
            const sending = send.isPending && send.variables === event.id
            const reviewing = review.isPending && review.variables?.id === event.id
            return (
              <li key={event.id} className="flex flex-wrap gap-3 py-3 first:pt-1 last:pb-1">
                <button type="button" onClick={() => setPreview(event)}
                  aria-label={`Open preview for ${eventRuleName(rule_)}`}
                  className="h-14 w-24 shrink-0 overflow-hidden rounded-md border bg-muted hover:ring-2 hover:ring-ring sm:h-[72px] sm:w-32">
                  {event.snapshot
                    ? <img src={fileUrl(event.snapshot)} alt="" loading="lazy" className="h-full w-full object-cover" />
                    : <span className="grid h-full w-full place-items-center text-muted-foreground"><ImageOff className="h-4 w-4" aria-hidden /></span>}
                </button>

                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <span className="rounded bg-secondary px-1.5 py-0.5 text-[10px] font-semibold tabular-nums text-secondary-foreground">#{rule_.index + 1}</span>
                    <Badge className="px-1.5 py-0 text-[10px]">{rule_.kind}</Badge>
                    <span className="min-w-0 text-sm font-medium">{eventRuleName(rule_)}</span>
                    <time className="text-[11px] text-muted-foreground" dateTime={new Date(event.ts * 1000).toISOString()}>{fmtTime(event.ts)}</time>
                    <span className="text-[11px] text-muted-foreground">· {fmtAgo(event.ts)}</span>
                  </div>
                  <p className="mt-0.5 text-sm text-muted-foreground [overflow-wrap:anywhere]">{event.summary}</p>
                  {!!chips.length && (
                    <ul className="mt-1.5 flex flex-wrap gap-1" aria-label="Detected classes">
                      {chips.slice(0, 5).map(([name, v]) => (
                        <li key={name} className="inline-flex items-center gap-1 rounded-full bg-secondary px-2 py-0.5 text-[11px] text-secondary-foreground">
                          <span className="h-1.5 w-1.5 rounded-full" style={{ background: classColor(v.id) }} aria-hidden />
                          {name} <span className="tabular-nums text-muted-foreground">{Math.round(v.conf * 100)}%</span>
                        </li>
                      ))}
                      {chips.length > 5 && <li className="px-1 text-[11px] text-muted-foreground">+{chips.length - 5}</li>}
                    </ul>
                  )}
                </div>

                <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto sm:flex-col sm:items-end">
                  {canReview ? (
                    <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                      <span>Reviewed</span>
                      <Switch checked={event.reviewed} label={`Reviewed — event at ${fmtTime(event.ts)}`}
                        onChange={(v) => review.mutate({ id: event.id, reviewed: v })} />
                      {reviewing && <Spinner className="h-3 w-3" />}
                    </div>
                  ) : (
                    <Badge className={event.reviewed ? 'bg-success/15 text-success' : ''}>{event.reviewed ? 'Reviewed' : 'Unreviewed'}</Badge>
                  )}
                  {canReview && (
                    <Button variant="outline" size="sm" disabled={sending} onClick={() => send.mutate(event.id)}>
                      {sending ? <><Spinner /> Sending…</> : <><Send className="h-3.5 w-3.5" /> Send to dataset</>}
                    </Button>
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      )}
      <EventPreview event={preview} onClose={() => setPreview(null)} />
    </Card>
  )
}

// ---------- event preview -----------------------------------------------------
function EventPreview({ event, onClose }: { event: StreamEvent | null; onClose: () => void }) {
  const label = eventRuleName(event?.rule)
  return (
    <Modal open={!!event} onClose={onClose} wide title={event ? label : 'Event'}>
      {event && (
        <div className="space-y-4">
          <div className="overflow-hidden rounded-lg border bg-black">
            {event.snapshot
              ? <img src={fileUrl(event.snapshot)} alt={`Snapshot for ${label}`} className="mx-auto max-h-[60vh] w-full object-contain" />
              : <div className="grid aspect-video place-items-center gap-2 text-sm text-white/60"><ImageOff className="h-6 w-6" aria-hidden /> No snapshot for this event</div>}
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <Badge className="tabular-nums">#{event.rule.index + 1}</Badge>
            <Badge>{event.rule.kind}</Badge>
            <time dateTime={new Date(event.ts * 1000).toISOString()}>{fmtTime(event.ts)}</time>
            <span className="min-w-0 text-foreground [overflow-wrap:anywhere]">{event.summary}</span>
            <Badge className={event.reviewed ? 'bg-success/15 text-success' : ''}>{event.reviewed ? 'Reviewed' : 'Unreviewed'}</Badge>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[320px] text-sm">
              <thead>
                <tr className="border-b text-left text-xs text-muted-foreground">
                  <th scope="col" className="py-1.5 pr-3 font-medium">Class</th>
                  <th scope="col" className="py-1.5 pr-3 font-medium">Track</th>
                  <th scope="col" className="py-1.5 pr-3 text-right font-medium" title="Confidence">Conf.</th>
                  <th scope="col" className="py-1.5 text-right font-medium" title="Normalized box: x, y, width, height">Box</th>
                </tr>
              </thead>
              <tbody>
                {!event.predictions.length && (
                  <tr><td colSpan={4} className="py-4 text-center text-xs text-muted-foreground">No predictions stored for this event.</td></tr>
                )}
                {event.predictions.map((p, i) => (
                  <tr key={i} className="border-b last:border-0">
                    <td className="py-1.5 pr-3">
                      <span className="inline-flex items-center gap-1.5">
                        <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: classColor(p.class_id ?? 0) }} aria-hidden />
                        {p.class}
                      </span>
                    </td>
                    <td className="py-1.5 pr-3 tabular-nums text-muted-foreground">{p.track_id ?? '—'}</td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">{Math.round(p.confidence * 100)}%</td>
                    <td className="py-1.5 text-right font-mono text-[11px] tabular-nums text-muted-foreground">
                      {p.x.toFixed(2)}, {p.y.toFixed(2)}, {p.width.toFixed(2)}, {p.height.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Modal>
  )
}

// ---------- page --------------------------------------------------------------
export default function StreamDetail() {
  const { ws = '', project = '', sid = '' } = useParams()
  const nav = useNavigate()
  const qc = useQueryClient()
  const { isManager } = useProjectPermissions(ws, project)
  // Start/stop/edit/delete are need("admin") on the server: a project manager, not a workspace rank.
  const admin = isManager
  const [zoneOpen, setZoneOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [tab, setTab] = useState('events')

  const q = useQuery({
    queryKey: ['stream', ws, project, sid],
    queryFn: () => api.stream(ws, project, sid),
    enabled: !!ws && !!project && !!sid,
    refetchInterval: 3000,
  })
  const stream = q.data

  if (q.isLoading) return <div className="flex h-full items-center justify-center"><Spinner /></div>
  if (!stream) {
    return (
      <EmptyState title="Stream not found" hint={(q.error as Error)?.message}
        action={<Button size="sm" onClick={() => nav(`/${ws}/${project}/streams`)}>Back to streams</Button>} />
    )
  }

  const act = async (action: 'start' | 'stop') => {
    setBusy(true)
    try {
      const updated = action === 'start' ? await api.startStream(ws, project, stream.id) : await api.stopStream(ws, project, stream.id)
      qc.setQueryData(['stream', ws, project, stream.id], updated)
      qc.invalidateQueries({ queryKey: ['streams', ws, project] })
      toast.ok(action === 'start' ? 'Stream started' : 'Stream stopped')
    } catch (e) { toast.err(e as Error) } finally { setBusy(false) }
  }

  const remove = async () => {
    if (!confirm(`Delete “${stream.name}”? Its captured events are removed too.`)) return
    setBusy(true)
    try {
      await api.deleteStream(ws, project, stream.id)
      qc.invalidateQueries({ queryKey: ['streams', ws, project] })
      toast.ok(`Deleted ${stream.name}`)
      nav(`/${ws}/${project}/streams`)
    } catch (e) { toast.err(e as Error); setBusy(false) }
  }

  const live = isStreamLive(stream.status)

  return (
    <div className="anim-page">
      <PageHeader
        title={
          <span className="flex min-w-0 flex-wrap items-center gap-2">
            <span className="max-w-[70vw] truncate sm:max-w-[42ch]">{stream.name}</span>
            <StreamStatusChip status={stream.status} />
          </span>
        }
        desc={<span className="[overflow-wrap:anywhere]"><span className="font-mono">{stream.modelRef}</span> · {displaySource(stream.source)}</span>}
        actions={
          <div className="flex flex-wrap items-center justify-end gap-2">
            <Link to={`/${ws}/${project}/streams`}>
              <Button variant="ghost" size="sm"><ChevronLeft className="h-3.5 w-3.5" aria-hidden /> Streams</Button>
            </Link>
            {admin && (
              <>
                <Button variant="outline" size="sm" disabled={busy} onClick={() => act(live ? 'stop' : 'start')}>
                  {busy ? <Spinner /> : live ? <><Square className="h-3.5 w-3.5" /> Stop</> : <><Play className="h-3.5 w-3.5" /> Start</>}
                </Button>
                <Button variant="outline" size="sm" onClick={() => setZoneOpen(true)}><ScanLine className="h-4 w-4" /> Edit zones</Button>
                <Button variant="ghost" size="icon" aria-label="Delete stream" disabled={busy} onClick={remove}><Trash2 className="h-4 w-4" /></Button>
              </>
            )}
          </div>
        }
      />

      <div className="space-y-4 px-4 pb-10 sm:px-8">
        <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
          <LivePanel stream={stream} admin={admin} busy={busy} onStart={() => act('start')} />
          <SummaryPanel stream={stream} />
        </div>

        <Tabs tabs={[{ id: 'events', label: 'Events' }, { id: 'rules', label: 'Zones & rules' }]} active={tab} onChange={setTab} />
        <div className={tab === 'events' ? '' : 'hidden'}>
          <EventsTimeline stream={stream} ws={ws} project={project} active={tab === 'events'} />
        </div>
        <div className={tab === 'rules' ? '' : 'hidden'}>
          {admin ? <RulesSection stream={stream} ws={ws} project={project} /> : <ReadOnlyRules stream={stream} />}
        </div>
      </div>

      <ZoneEditor open={zoneOpen} onClose={() => setZoneOpen(false)} ws={ws} project={project} stream={stream}
        onSaved={(zones) => qc.setQueryData<StreamItem>(['stream', ws, project, stream.id], (old) => (old ? { ...old, zones } : old))} />
    </div>
  )
}
