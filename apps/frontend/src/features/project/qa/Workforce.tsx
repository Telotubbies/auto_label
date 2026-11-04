import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, fileUrl } from '@/lib/api'
import { useProjectPermissions } from '@/lib/perms'
import { useApp } from '@/lib/store'
import type { LabelerStat } from '@/lib/types'
import { Card, EmptyState, Stat, fmtDate } from '@/components/ui'
import { cn } from '@/lib/utils'
import { ErrorNote, Loading, SectionTitle, pct, roleLabel } from './shared'

function Throughput({ days, window }: { days: { date: string; images: number; annotations: number }[]; window: number }) {
  const [view, setView] = useState<'chart' | 'table'>('chart')
  if (!days.length) {
    return <Card className="p-4"><p className="text-sm text-muted-foreground">No activity in the last {window} days.</p></Card>
  }
  return (
    <Card className="min-w-0 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold">Daily throughput</h3>
          <p className="mt-0.5 text-xs text-muted-foreground">Images labeled and annotations created, last {window} days.</p>
        </div>
        <div role="group" aria-label="Throughput view" className="flex shrink-0 rounded-md border p-0.5">
          {(['chart', 'table'] as const).map((v) => (
            <button key={v} type="button" aria-pressed={view === v} onClick={() => setView(v)}
              className={cn('cursor-pointer rounded px-2 py-1 text-xs transition-colors',
                view === v ? 'bg-accent font-medium text-foreground' : 'text-muted-foreground hover:text-foreground')}>
              {v === 'chart' ? 'Chart' : 'Table'}
            </button>
          ))}
        </div>
      </div>

      {view === 'table' ? (
        <figure className="mt-3 min-w-0 overflow-x-auto" role="region" aria-label="Daily throughput table" tabIndex={0}>
          <table className="w-full text-sm">
            <caption className="pb-2 text-left text-xs text-muted-foreground">Daily throughput — the same numbers as the chart.</caption>
            <thead>
              <tr className="border-b text-left text-xs text-muted-foreground">
                <th scope="col" className="py-1.5 font-medium">Date</th>
                <th scope="col" className="py-1.5 text-right font-medium">Images</th>
                <th scope="col" className="py-1.5 text-right font-medium">Annotations</th>
              </tr>
            </thead>
            <tbody>
              {days.map((d) => (
                <tr key={d.date} className="border-b last:border-0">
                  <td className="py-1.5 tabular-nums">{d.date}</td>
                  <td className="py-1.5 text-right tabular-nums">{d.images}</td>
                  <td className="py-1.5 text-right tabular-nums">{d.annotations}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </figure>
      ) : (
        <figure className="mt-3 min-w-0">
          <div className="h-64 min-w-0" aria-hidden="true">
            <ResponsiveContainer>
              <BarChart data={days} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }} tickLine={false} axisLine={false}
                  tickFormatter={(v: string) => v.slice(5)} minTickGap={16} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }} tickLine={false} axisLine={false} />
                <Tooltip cursor={{ fill: 'var(--muted)' }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="images" name="Images" fill="var(--primary)" radius={[3, 3, 0, 0]} isAnimationActive={false} />
                <Bar dataKey="annotations" name="Annotations" fill="var(--tertiary)" radius={[3, 3, 0, 0]} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <figcaption className="mt-2">
            <ul className="sr-only">
              {days.map((d) => <li key={d.date}>{d.date}: {d.images} images, {d.annotations} annotations</li>)}
            </ul>
            <p className="text-[11px] text-muted-foreground">Switch to Table for the exact figures.</p>
          </figcaption>
        </figure>
      )}
    </Card>
  )
}

function LabelerTable({ rows }: { rows: LabelerStat[] }) {
  return (
    <Card className="min-w-0 overflow-hidden">
      <div className="overflow-x-auto" role="region" aria-label="Labeler quality table" tabIndex={0}>
        <table className="w-full min-w-[760px] text-sm">
          <caption className="sr-only">Per-labeler throughput and quality</caption>
          <thead>
            <tr className="border-b bg-muted/50 text-left text-xs text-muted-foreground">
              <th scope="col" className="px-3 py-2 font-medium">Labeler</th>
              <th scope="col" className="px-3 py-2 font-medium">Role</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Images</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Annotations</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Per day</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">AI acceptance</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Honeypot accuracy</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Rejection rate</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.user_id} className="border-b last:border-0">
                <th scope="row" className="px-3 py-2 text-left font-medium">{r.name}</th>
                <td className="px-3 py-2 text-muted-foreground">{roleLabel(r.role)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{r.images}</td>
                <td className="px-3 py-2 text-right tabular-nums">{r.annotations}</td>
                <td className="px-3 py-2 text-right tabular-nums">{r.per_day.toFixed(1)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{pct(r.ai_acceptance)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{pct(r.honeypot_accuracy)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{pct(r.rejection_rate)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

function MyTasks({ ws, slug }: { ws: string; slug: string }) {
  const q = useQuery({ queryKey: ['labeling-tasks', ws, slug], queryFn: () => api.labelingTasks(ws, slug) })
  if (q.isLoading) return <Loading />
  if (q.isError) return <ErrorNote error={q.error} />
  const tasks = q.data?.tasks ?? []
  return (
    <section aria-labelledby="my-tasks-heading" className="space-y-2">
      <SectionTitle id="my-tasks-heading" title="My tasks"
        desc="Images a reviewer sent to you for consensus labeling. Autosave stays private; Submit consensus draft in the editor sends your labels." />
      {!tasks.length ? (
        <Card className="p-4">
          <EmptyState title="No consensus tasks waiting." hint="When a reviewer starts a consensus job that includes you, the images appear here." />
        </Card>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {tasks.map((t) => (
            <li key={`${t.job_id}-${t.image_id}`}>
              <Card className="flex gap-3 p-3">
                <img src={fileUrl(t.thumbnail)} alt="" loading="lazy"
                  className="h-16 w-24 shrink-0 rounded-md border bg-muted object-cover" />
                <div className="min-w-0 flex-1">
                  <Link to={`/${ws}/${slug}/images/${t.image_id}?status=annotating`}
                    className="block truncate text-sm font-medium hover:underline">{t.name}</Link>
                  <p className="mt-0.5 text-xs text-muted-foreground">Assigned {fmtDate(t.created)}</p>
                  <Link to={`/${ws}/${slug}/images/${t.image_id}?status=annotating`}
                    className="mt-1.5 inline-flex min-h-6 items-center text-xs font-medium text-primary hover:underline">
                    Open editor
                  </Link>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export default function Workforce({ ws, slug }: { ws: string; slug: string }) {
  const me = useApp((s) => s.me)
  const { can } = useProjectPermissions(ws, slug)
  const canReview = can('project.review')
  const q = useQuery({ queryKey: ['labeling-dashboard', ws, slug], queryFn: () => api.labelingDashboard(ws, slug) })
  if (q.isLoading) return <Loading />
  if (q.isError) return <ErrorNote error={q.error} />
  const d = q.data!
  // Annotators get their own row only; reviewers see the whole team.
  const rows = canReview ? d.labelers : d.labelers.filter((l) => l.user_id === me?.id)

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Stat label="Images labeled" value={d.totals.images} sub={`last ${d.window_days} days`} />
        <Stat label="Annotations" value={d.totals.annotations} sub={`last ${d.window_days} days`} />
        <Stat label="AI acceptance" value={pct(d.totals.ai_acceptance)} sub="accepted without edits" />
        <Stat label="Honeypot accuracy" value={pct(d.totals.honeypot_accuracy)} sub="on ground-truth images" />
        <Stat label="Consensus pending" value={d.totals.consensus_pending} sub="drafts not submitted" />
        <Stat label="Review queue" value={d.totals.review_queue} sub="images to review" />
      </div>

      <Throughput days={d.daily} window={d.window_days} />

      <section aria-labelledby="labelers-heading" className="space-y-2">
        <SectionTitle id="labelers-heading" title="Labelers"
          desc={canReview ? 'Throughput and quality across everyone who labeled in this window.' : 'Your throughput and quality in this window.'} />
        {rows.length ? <LabelerTable rows={rows} /> : (
          <Card className="p-4"><EmptyState title="No labeling activity yet." hint="Numbers appear once images are labeled or reviewed." /></Card>
        )}
      </section>

      <MyTasks ws={ws} slug={slug} />
    </div>
  )
}
