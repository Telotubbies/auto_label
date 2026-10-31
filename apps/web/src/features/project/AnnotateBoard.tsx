import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Bot, CheckCheck, Inbox, PencilLine, Send, Sparkles, UserPlus } from 'lucide-react'
import { api, post } from '@/lib/api'
import { useApp } from '@/lib/store'
import type { BoardCard, Status } from '@/lib/types'
import { Button, Card, Dropdown, EmptyState, Input, Modal, PageHeader, Progress, Select, StatusPill, fmtAgo, toast } from '@/components/ui'
import { AutoLabelDialog } from './AutoLabelDialog'
import { useProject } from './ProjectLayout'

const COLS: { id: Status; title: string; hint: string }[] = [
  { id: 'unassigned', title: 'Unassigned', hint: 'Uploaded, not yet assigned' },
  { id: 'annotating', title: 'Annotating', hint: 'Assigned to a labeler' },
  { id: 'review', title: 'Review', hint: 'Waiting for approval' },
  { id: 'done', title: 'Dataset', hint: 'Approved — used in versions' },
]

export default function AnnotateBoard() {
  const { project, ws } = useProject()
  const nav = useNavigate()
  const qc = useQueryClient()
  const can = useApp((s) => s.can)
  const me = useApp((s) => s.me)
  const board = useQuery({ queryKey: ['board', ws, project.slug], queryFn: () => api.board(ws, project.slug) })
  const jobs = useQuery({ queryKey: ['jobs', ws, project.slug, 'autolabel'], queryFn: () => api.jobs(ws, project.slug, 'autolabel'),
    refetchInterval: (q) => (q.state.data?.some((j) => ['queued', 'running'].includes(j.status)) ? 2000 : false) })
  const [auto, setAuto] = useState<{ batchId: string | null } | null>(null)
  const [assign, setAssign] = useState<BoardCard | null>(null)
  const [assignee, setAssignee] = useState('')
  const [filter, setFilter] = useState('')

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['board', ws, project.slug] }); qc.invalidateQueries({ queryKey: ['project', ws, project.slug] })
  }
  const move = (card: BoardCard, from: Status, to: Status, extra: Record<string, unknown> = {}) =>
    post<{ moved: number }>(`${api.P(ws, project.slug)}/board/move`, { batch_id: card.batchId, from_status: from, to_status: to, assignee_id: card.assigneeId ?? '', ...extra })
      .then((r) => { toast.ok(`Moved ${r.moved} images`); refresh() }).catch(toast.err)
  const open = (card: BoardCard, status: Status, review = false) => {
    const q = new URLSearchParams({ status, ...(card.batchId ? { batch: card.batchId } : {}), ...(card.assigneeId ? { assignee: card.assigneeId } : {}), ...(review ? { review: 'true', sort: 'review' } : {}) })
    api.images(ws, project.slug, { status, ...(card.batchId ? { batch_id: card.batchId } : {}), ...(review ? { sort: 'review' } : {}), limit: 1 }).then((r) => {
      if (r.items[0]) nav(`/${ws}/${project.slug}/images/${r.items[0].id}?${q}`)
      else toast.err('No images in this card')
    })
  }
  const running = (jobs.data ?? []).filter((j) => ['queued', 'running'].includes(j.status))

  return (
    <div className="anim-page">
      <PageHeader title="Annotate" desc="Move batches from upload to an approved dataset."
        actions={<>
          <Input className="w-56" placeholder="Filter batches" value={filter} onChange={(e) => setFilter(e.target.value)} />
          {can('reviewer') && <Button variant="outline" onClick={() => setAuto({ batchId: null })}><Sparkles className="h-4 w-4" /> Auto Label</Button>}
          {can('reviewer') && <Button onClick={() => nav('../upload')}>Upload More</Button>}
        </>} />
      {running.map((j) => (
        <div key={j.id} className="mx-8 mb-3 flex items-center gap-3 rounded-lg border bg-accent/30 px-4 py-2 text-sm">
          <Bot className="h-4 w-4 text-primary" /> Auto-labeling ({j.params.model_ref ?? (j.params.method === 'sam' ? 'SAM 3.1' : 'model')}) <StatusPill status={j.status} />
          <Progress className="w-48" value={j.progress} /> <span className="text-xs text-muted-foreground">{Math.round(j.progress)}%</span>
        </div>
      ))}
      {(jobs.data ?? []).filter((j) => j.status === 'failed').slice(0, 1).map((j) => (
        <div key={j.id} className="mx-8 mb-3 rounded-lg border border-destructive/40 bg-red-50 px-4 py-2 text-sm text-red-900">Last auto-label failed: {j.error}</div>
      ))}
      <div className="grid gap-4 px-8 pb-10 lg:grid-cols-4">
        {COLS.map((col) => {
          const cards = (board.data?.columns[col.id] ?? []).filter((c) => !filter || c.batchName.toLowerCase().includes(filter.toLowerCase()))
          const n = cards.reduce((s, c) => s + c.images, 0)
          return (
            <div key={col.id} className="flex min-h-64 flex-col rounded-xl bg-muted/60 p-3">
              <div className="mb-3 flex items-baseline justify-between px-1">
                <div><div className="text-sm font-semibold">{col.title}</div><div className="text-[11px] text-muted-foreground">{col.hint}</div></div>
                <span className="text-xs font-semibold text-muted-foreground">{n}</span>
              </div>
              <div className="flex-1 space-y-2">
                {cards.map((c) => (
                  <Card key={`${c.batchId}-${c.assigneeId}`} className="p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="truncate text-sm font-semibold">{c.batchName}</div>
                        <div className="text-[11px] text-muted-foreground">{c.created ? fmtAgo(c.created) : ''}{c.assignee ? ` · ${c.assignee}` : ''}</div>
                      </div>
                      {col.id === 'unassigned' && can('reviewer') && (
                        <Dropdown align="right" trigger={<button className="cursor-pointer px-1 text-muted-foreground">⋮</button>} items={[
                          { label: 'Auto Label batch', onClick: () => setAuto({ batchId: c.batchId }) },
                          { label: 'Add straight to Dataset', onClick: () => move(c, 'unassigned', 'done', { only_annotated: true }) },
                        ]} />
                      )}
                    </div>
                    <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                      <Progress value={(c.annotated / c.images) * 100} /> <span className="whitespace-nowrap">{c.annotated}/{c.images}</span>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {col.id === 'unassigned' && can('reviewer') && <Button size="sm" onClick={() => { setAssign(c); setAssignee(me?.id ?? '') }}><UserPlus className="h-3.5 w-3.5" /> Assign</Button>}
                      {col.id === 'unassigned' && <Button size="sm" variant="outline" onClick={() => open(c, 'unassigned')}><PencilLine className="h-3.5 w-3.5" /> Label</Button>}
                      {col.id === 'annotating' && <Button size="sm" variant="outline" onClick={() => open(c, 'annotating')}><PencilLine className="h-3.5 w-3.5" /> Annotate</Button>}
                      {col.id === 'annotating' && c.annotated > 0 && <Button size="sm" onClick={() => move(c, 'annotating', 'review', { only_annotated: true })}><Send className="h-3.5 w-3.5" /> Submit</Button>}
                      {col.id === 'review' && can('reviewer') && <Button size="sm" variant="outline" onClick={() => open(c, 'review', true)}>Review</Button>}
                      {col.id === 'review' && can('reviewer') && <Button size="sm" className="bg-green-600 hover:bg-green-700" onClick={() => move(c, 'review', 'done')}><CheckCheck className="h-3.5 w-3.5" /> Approve all</Button>}
                      {col.id === 'review' && can('reviewer') && <Button size="sm" variant="ghost" onClick={() => move(c, 'review', 'annotating')}>Reject all</Button>}
                      {col.id === 'done' && <Button size="sm" variant="outline" onClick={() => nav(`../browse?batch=${c.batchId ?? ''}`)}>View</Button>}
                    </div>
                  </Card>
                ))}
                {board.isSuccess && !cards.length && <EmptyState icon={<Inbox className="h-6 w-6 text-muted-foreground/50" />} title="Empty" />}
              </div>
            </div>
          )
        })}
      </div>
      <Modal open={!!assign} onClose={() => setAssign(null)} title="Assign images">
        <p className="mb-3 text-sm text-muted-foreground">{assign?.images} images from “{assign?.batchName}” move to Annotating.</p>
        <Select className="w-full" value={assignee} onChange={(e) => setAssignee(e.target.value)}>
          {(board.data?.members ?? []).map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
        </Select>
        <div className="mt-4 flex justify-end gap-2"><Button variant="ghost" onClick={() => setAssign(null)}>Cancel</Button>
          <Button disabled={!assignee} onClick={() => { move(assign!, 'unassigned', 'annotating', { set_assignee: assignee }); setAssign(null) }}>Assign</Button></div>
      </Modal>
      <AutoLabelDialog open={!!auto} onClose={() => setAuto(null)} batchId={auto?.batchId ?? null} />
    </div>
  )
}
