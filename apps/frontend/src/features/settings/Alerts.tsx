import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell, Mail, MessageCircle, Trash2 } from 'lucide-react'
import { del, get, patch, post } from '@/lib/api'
import type { AlertChannel, AlertDelivery, AlertKind } from '@/lib/types'
import { Badge, Button, Card, EmptyState, Field, Input, Select, Spinner, Switch, fmtAgo, toast } from '@/components/ui'
import { cn } from '@/lib/utils'

const KIND_LABEL: Record<AlertKind, string> = { line: 'LINE', slack: 'Slack', email: 'Email' }
const KIND_ICON: Record<AlertKind, typeof Bell> = { line: MessageCircle, slack: MessageCircle, email: Mail }

const STATUS_STYLE: Record<AlertDelivery['status'], string> = {
  ok: 'bg-success/15 text-success',
  failed: 'bg-destructive/15 text-destructive',
  skipped: 'bg-muted text-muted-foreground',
}

const emptyForm = {
  kind: 'line' as AlertKind, name: '',
  lineTo: '', lineToken: '',
  slackUrl: '',
  emails: '',
  throttle: '60',
  quiet: false, quietStart: '22:00', quietEnd: '07:00', quietTz: 'Asia/Bangkok',
}

function configLine(ch: AlertChannel): string {
  if (ch.kind === 'line') return `Target ${ch.config.to || '—'}`
  if (ch.kind === 'slack') return `Webhook ${ch.config.webhook_url || '—'}`
  return (ch.config.recipients ?? []).join(', ') || 'No recipients'
}

function ChannelCard({ ws, ch }: { ws: string; ch: AlertChannel }) {
  const qc = useQueryClient()
  const [busy, setBusy] = useState('')
  const Icon = KIND_ICON[ch.kind]
  const history = useQuery({
    queryKey: ['alert-deliveries', ws, ch.id],
    queryFn: () => get<AlertDelivery[]>(`/ws/${ws}/alerts/${ch.id}/deliveries`),
  })
  const refresh = () => qc.invalidateQueries({ queryKey: ['alerts', ws] })

  const test = async () => {
    setBusy('test')
    try {
      const d = await post<AlertDelivery>(`/ws/${ws}/alerts/${ch.id}/test`)
      if (d.status === 'ok') toast.ok('Test alert sent')
      else toast.err(`Test failed: ${d.reason || 'provider rejected it'}`)
      void qc.invalidateQueries({ queryKey: ['alert-deliveries', ws, ch.id] })
      refresh()
    } catch (e) {
      toast.err(e as Error)
    } finally {
      setBusy('')
    }
  }

  const toggle = async (active: boolean) => {
    try {
      await patch(`/ws/${ws}/alerts/${ch.id}`, { active })
      refresh()
    } catch (e) {
      toast.err(e as Error)
    }
  }

  const remove = async () => {
    if (!confirm(`Delete "${ch.name}"? This channel stops receiving alerts.`)) return
    try {
      await del(`/ws/${ws}/alerts/${ch.id}`)
      toast.ok('Alert channel deleted')
      refresh()
    } catch (e) {
      toast.err(e as Error)
    }
  }

  const quiet = ch.settings.quiet_hours
  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <span className="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary" aria-hidden>
            <Icon className="h-4 w-4" />
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-semibold">{ch.name}</h3>
              <Badge>{KIND_LABEL[ch.kind]}</Badge>
              {!ch.active && <Badge className="bg-muted text-muted-foreground">Paused</Badge>}
            </div>
            <p className="mt-0.5 break-all text-xs text-muted-foreground">{configLine(ch)}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Throttle {ch.settings.throttle_s ?? 60}s
              {quiet ? ` · Quiet ${quiet.start}–${quiet.end} (${quiet.tz})` : ' · Quiet hours off'}
              {ch.last_sent ? ` · Last sent ${fmtAgo(ch.last_sent)}` : ' · Not sent yet'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Switch checked={ch.active} onChange={toggle} label={`Enable ${ch.name}`} />
          <Button variant="outline" size="sm" onClick={test} disabled={busy === 'test'} aria-busy={busy === 'test'}>
            {busy === 'test' && <Spinner className="h-3.5 w-3.5" />}
            {busy === 'test' ? 'Sending…' : 'Send test'}
          </Button>
          <Button variant="ghost" size="icon" aria-label={`Delete ${ch.name}`} onClick={remove}>
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <details className="mt-3 border-t pt-3">
        <summary className="inline-flex min-h-6 cursor-pointer items-center rounded px-1 text-xs font-medium text-muted-foreground hover:text-foreground">
          Recent deliveries
        </summary>
        {history.isLoading ? (
          <p role="status" className="mt-2 flex items-center gap-2 text-xs text-muted-foreground"><Spinner /> Loading…</p>
        ) : history.isError ? (
          <p role="alert" className="mt-2 text-xs text-destructive">Could not load delivery history.</p>
        ) : !history.data?.length ? (
          <p className="mt-2 text-xs text-muted-foreground">No deliveries recorded yet.</p>
        ) : (
          <ul className="mt-2 space-y-1.5">
            {history.data.slice(0, 5).map((d) => (
              <li key={d.id} className="flex flex-wrap items-center gap-2 text-xs">
                <span className={cn('rounded px-1.5 py-0.5 font-medium', STATUS_STYLE[d.status])}>{d.status}</span>
                <span className="min-w-0 flex-1 truncate">{d.event.title || 'Stream alert'}{d.reason ? ` — ${d.reason}` : ''}</span>
                <time className="text-muted-foreground" dateTime={new Date(d.created * 1000).toISOString()}>{fmtAgo(d.created)}</time>
              </li>
            ))}
          </ul>
        )}
      </details>
    </Card>
  )
}

export default function Alerts() {
  const { ws = '' } = useParams()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['alerts', ws], queryFn: () => get<AlertChannel[]>(`/ws/${ws}/alerts`) })
  const [f, setF] = useState(emptyForm)
  const [saving, setSaving] = useState(false)
  const set = <K extends keyof typeof emptyForm>(key: K, value: (typeof emptyForm)[K]) => setF((x) => ({ ...x, [key]: value }))

  const create = async () => {
    const config = f.kind === 'line'
      ? { to: f.lineTo.trim(), channel_token: f.lineToken }
      : f.kind === 'slack'
        ? { webhook_url: f.slackUrl.trim() }
        : { recipients: f.emails.split(',').map((x) => x.trim()).filter(Boolean) }
    const settings = {
      throttle_s: Number(f.throttle),
      quiet_hours: f.quiet ? { start: f.quietStart, end: f.quietEnd, tz: f.quietTz.trim() } : null,
    }
    setSaving(true)
    try {
      await post(`/ws/${ws}/alerts`, { kind: f.kind, name: f.name.trim(), config, settings })
      setF(emptyForm)
      toast.ok('Alert channel created')
      qc.invalidateQueries({ queryKey: ['alerts', ws] })
    } catch (e) {
      toast.err(e as Error)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-4">
      <Card className="p-5">
        <h2 className="font-semibold">Add an alert channel</h2>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Stream rule events can go to LINE, Slack or email with a snapshot link. LINE uses the
          Messaging API (LINE Notify was retired on 31 March 2025).
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <Field label="Channel">
            <Select value={f.kind} onChange={(e) => set('kind', e.target.value as AlertKind)}>
              {(Object.keys(KIND_LABEL) as AlertKind[]).map((k) => <option key={k} value={k}>{KIND_LABEL[k]}</option>)}
            </Select>
          </Field>
          <Field label="Name" hint="Shown in this list and in the audit log.">
            <Input value={f.name} maxLength={120} placeholder="Factory on-call" onChange={(e) => set('name', e.target.value)} />
          </Field>

          {f.kind === 'line' ? (
            <>
              <Field label="Target ID" hint="User, group or room ID that receives the push message.">
                <Input value={f.lineTo} placeholder="U4af4980629…" onChange={(e) => set('lineTo', e.target.value)} autoComplete="off" />
              </Field>
              <Field label="Channel access token" hint="Stored encrypted; never shown again.">
                <Input type="password" value={f.lineToken} onChange={(e) => set('lineToken', e.target.value)} autoComplete="new-password" />
              </Field>
            </>
          ) : f.kind === 'slack' ? (
            <Field label="Incoming webhook URL" hint="https://hooks.slack.com/services/… — stored encrypted.">
              <Input type="password" value={f.slackUrl} onChange={(e) => set('slackUrl', e.target.value)} autoComplete="new-password" />
            </Field>
          ) : (
            <Field label="Recipients" hint="Comma-separated, up to 20 addresses.">
              <Input type="email" multiple value={f.emails} placeholder="ops@example.com, on-call@example.com" onChange={(e) => set('emails', e.target.value)} />
            </Field>
          )}

          <Field label="Minimum seconds between alerts" hint="0 disables throttling; default 60 seconds.">
            <Input type="number" min={0} max={86400} value={f.throttle} onChange={(e) => set('throttle', e.target.value)} />
          </Field>
          <div className="flex items-end pb-1">
            <div className="flex items-center justify-between gap-4">
              <div>
                <div className="text-sm font-medium">Quiet hours</div>
                <div className="text-xs text-muted-foreground">Hold alerts during this window.</div>
              </div>
              <Switch checked={f.quiet} onChange={(v) => set('quiet', v)} label="Quiet hours" />
            </div>
          </div>
          {f.quiet && (
            <>
              <Field label="Quiet from"><Input type="time" value={f.quietStart} onChange={(e) => set('quietStart', e.target.value)} /></Field>
              <Field label="Quiet until"><Input type="time" value={f.quietEnd} onChange={(e) => set('quietEnd', e.target.value)} /></Field>
              <Field label="Time zone" hint="IANA name, e.g. Asia/Bangkok.">
                <Input value={f.quietTz} onChange={(e) => set('quietTz', e.target.value)} />
              </Field>
            </>
          )}
        </div>
        <div className="mt-4">
          <Button onClick={create} disabled={saving || !f.name.trim()} aria-busy={saving}>
            {saving ? <Spinner className="h-3.5 w-3.5" /> : <Bell className="h-4 w-4" />}
            {saving ? 'Creating…' : 'Create channel'}
          </Button>
        </div>
      </Card>

      {q.isLoading ? (
        <Card className="flex items-center gap-2 p-5 text-sm text-muted-foreground" role="status"><Spinner /> Loading alert channels…</Card>
      ) : q.isError ? (
        <Card className="p-5">
          <EmptyState title="Couldn't load alert channels." hint={q.error instanceof Error ? q.error.message : undefined}
            action={<Button variant="outline" size="sm" onClick={() => void q.refetch()}>Try again</Button>} />
        </Card>
      ) : !q.data?.length ? (
        <Card><EmptyState icon={<Bell className="h-8 w-8 text-muted-foreground" aria-hidden />} title="No alert channels yet."
          hint="Add LINE, Slack or email above to route stream events to your team." /></Card>
      ) : (
        <div className="space-y-3">
          {q.data.map((ch) => <ChannelCard key={ch.id} ws={ws} ch={ch} />)}
        </div>
      )}
    </div>
  )
}
