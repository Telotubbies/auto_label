import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query'
import { useVirtualizer } from '@tanstack/react-virtual'
import { Check, Search, Sparkles, Tag, Trash2, X } from 'lucide-react'
import { api, ApiError, fileUrl, post } from '@/lib/api'
import { useProjectPermissions } from '@/lib/perms'
import type { ImageItem } from '@/lib/types'
import { Badge, Button, Dropdown, EmptyState, Input, PageHeader, Select, Spinner, toast } from '@/components/ui'
import { cn } from '@/lib/utils'
import { useProject } from './ProjectLayout'
import { AutoLabelDialog } from './AutoLabelDialog'

const SPLIT_TONE: Record<string, string> = { train: 'bg-violet-600', valid: 'bg-blue-600', test: 'bg-orange-500' }

const rangeText = (min: string, max: string, unit = '') => {
  const suffix = unit ? ` ${unit}` : ''
  if (min && max) return `${min}${min === max ? '' : `–${max}`}${suffix}`
  if (min) return `≥ ${min}${suffix}`
  if (max) return `< ${max}${suffix}`
  return ''
}

export default function Dataset() {
  const { project, ws } = useProject()
  const nav = useNavigate()
  const qc = useQueryClient()
  const { can } = useProjectPermissions(ws, project.slug)
  const [sp, setSp] = useSearchParams()
  const f = {
    q: sp.get('q') ?? '', split: sp.get('split') ?? '', status: sp.get('status') ?? (can('project.review') ? 'done' : 'all'),
    class_id: sp.get('class') ?? '', tag: sp.get('tag') ?? '', batch_id: sp.get('batch') ?? '', annotated: sp.get('annotated') ?? '', sort: sp.get('sort') ?? 'newest',
    // analytics chart links filter by image size (megapixels), aspect ratio and annotation count
    min_mp: sp.get('min_mp') ?? '', max_mp: sp.get('max_mp') ?? '', min_ar: sp.get('min_ar') ?? '', max_ar: sp.get('max_ar') ?? '',
    min_ann: sp.get('min_ann') ?? '', max_ann: sp.get('max_ann') ?? '',
    // the embedding lasso hands off a short-lived server token, never the ids themselves
    selection: sp.get('selection') ?? '',
  }
  const setF = (k: string, v: string) => { const n = new URLSearchParams(sp); v ? n.set(k, v) : n.delete(k); setSp(n, { replace: true }) }
  const clearF = (...keys: string[]) => { const n = new URLSearchParams(sp); keys.forEach((k) => n.delete(k)); setSp(n, { replace: true }) }
  const selection = f.selection
  const selectionQ = useQuery({
    queryKey: ['insights', 'selection', ws, project.slug, selection],
    queryFn: () => api.insights.selection(ws, project.slug, selection),
    enabled: !!selection,
    retry: false,
  })
  const selectionCount = selectionQ.data?.count
  const selectionExpired = !!selection && selectionQ.error instanceof ApiError && selectionQ.error.status === 404
  // Wait for the token lookup before touching the grid, so a dead token never becomes a failed image request.
  const selectionResolved = !selection || selectionQ.isFetched
  // A token already known to be dead must not fail the grid behind it; the chip explains why.
  const activeF = selectionExpired ? { ...f, selection: '' } : f
  const PAGE = 200
  const imgs = useInfiniteQuery({
    queryKey: ['images', ws, project.slug, activeF, 'pages'],
    // empty numeric params would be rejected by the API, so send only the filters that are set
    queryFn: ({ pageParam }) => api.images(ws, project.slug, {
      ...Object.fromEntries(Object.entries(activeF).filter(([, v]) => v !== '')), limit: PAGE, offset: pageParam,
    }),
    enabled: selectionResolved,
    initialPageParam: 0,
    getNextPageParam: (last, all) => { const n = all.reduce((s, p) => s + p.items.length, 0); return n < last.total ? n : undefined },
  })
  const classes = useQuery({ queryKey: ['classes', ws, project.slug], queryFn: () => api.classes(ws, project.slug) })
  const tags = useQuery({ queryKey: ['tags', ws, project.slug], queryFn: () => api.tags(ws, project.slug) })
  const batches = useQuery({ queryKey: ['batches', ws, project.slug], queryFn: () => api.batches(ws, project.slug) })
  const [sel, setSel] = useState<Set<string>>(new Set())
  const [auto, setAuto] = useState(false)
  const items = useMemo(() => imgs.data?.pages.flatMap((p) => p.items) ?? [], [imgs.data])
  const total = imgs.data?.pages[0]?.total
  const clsById = useMemo(() => Object.fromEntries((classes.data ?? []).map((c) => [c.id, c])), [classes.data])

  const parentRef = useRef<HTMLDivElement>(null)
  const cols = 5
  const rows = Math.ceil(items.length / cols)
  const v = useVirtualizer({ count: rows, getScrollElement: () => parentRef.current, estimateSize: () => 190, overscan: 4 })
  const lastRow = v.getVirtualItems().at(-1)?.index ?? 0
  // load the next page when the user scrolls within a few rows of the end
  useEffect(() => {
    if (lastRow >= rows - 3 && imgs.hasNextPage && !imgs.isFetchingNextPage) imgs.fetchNextPage()
  }, [lastRow, rows, imgs])

  const bulk = (action: string, value?: string) =>
    post<{ updated: number }>(`${api.P(ws, project.slug)}/images/bulk`, { ids: [...sel], action, value })
      .then((r) => { toast.ok(`Updated ${r.updated} images`); setSel(new Set()); qc.invalidateQueries({ queryKey: ['images', ws, project.slug] }); qc.invalidateQueries({ queryKey: ['project', ws, project.slug] }); qc.invalidateQueries({ queryKey: ['tags', ws, project.slug] }) })
      .catch(toast.err)
  const toggle = (id: string) => setSel((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n })
  const openEditor = (im: ImageItem) => {
    const q = new URLSearchParams(Object.entries(f).filter(([k, v]) => v && k !== 'selection').map(([k, v]) => [k === 'batch_id' ? 'batch' : k, v]) as [string, string][])
    nav(`/${ws}/${project.slug}/images/${im.id}?${q}`)
  }

  // Filters that analytics links can set but the toolbar has no select for: show them so the grid is explainable.
  const lassoLabel = selectionExpired
    ? 'Lasso selection (expired)'
    : selectionCount !== undefined ? `Lasso selection (${selectionCount.toLocaleString()})` : 'Lasso selection'
  const rangeFilters: { keys: string[]; label: string; expired?: boolean }[] = [
    ...(f.selection ? [{ keys: ['selection'], label: lassoLabel, expired: selectionExpired }] : []),
    { keys: ['min_mp', 'max_mp'], label: rangeText(f.min_mp, f.max_mp, 'MP') },
    { keys: ['min_ar', 'max_ar'], label: `Aspect ${rangeText(f.min_ar, f.max_ar)}` },
    { keys: ['min_ann', 'max_ann'], label: rangeText(f.min_ann, f.max_ann, 'annotations') },
  ].filter((c) => c.keys.some((k) => f[k as keyof typeof f]))

  return (
    <div className="anim-page flex h-full flex-col">
      <PageHeader title="Dataset" desc={`${total ?? '…'} images${f.status === 'done' ? ' in the dataset' : ''}`}
        actions={can('project.review') && <Button variant="outline" onClick={() => setAuto(true)}><Sparkles className="h-4 w-4" /> Auto Label</Button>} />
      <div className="flex flex-wrap items-center gap-2 px-8 pb-3">
        <div className="relative w-56"><Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" /><Input className="pl-8" placeholder="Search filename" value={f.q} onChange={(e) => setF('q', e.target.value)} /></div>
        <Select value={f.status} onChange={(e) => setF('status', e.target.value)}>
          <option value="all">All statuses</option><option value="done">Dataset (approved)</option><option value="review">In review</option><option value="annotating">Annotating</option><option value="unassigned">Unassigned</option>
        </Select>
        <Select value={f.split} onChange={(e) => setF('split', e.target.value)}><option value="">All splits</option><option value="train">Train</option><option value="valid">Valid</option><option value="test">Test</option></Select>
        <Select value={f.class_id} onChange={(e) => setF('class', e.target.value)}><option value="">All classes</option>{classes.data?.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.count})</option>)}</Select>
        <Select value={f.tag} onChange={(e) => setF('tag', e.target.value)}><option value="">All tags</option>{tags.data?.map((t) => <option key={t.name} value={t.name}>{t.name} ({t.count})</option>)}</Select>
        <Select value={f.batch_id} onChange={(e) => setF('batch', e.target.value)}><option value="">All batches</option>{batches.data?.map((b) => <option key={b.id} value={b.id}>{b.name} ({b.images})</option>)}</Select>
        <Select value={f.annotated} onChange={(e) => setF('annotated', e.target.value)}><option value="">Any annotations</option><option value="yes">Annotated</option><option value="no">Null (no annotations)</option></Select>
        <Select value={f.sort} onChange={(e) => setF('sort', e.target.value)}><option value="newest">Newest</option><option value="oldest">Oldest</option><option value="name">Filename</option><option value="most">Most annotations</option><option value="least">Fewest annotations</option></Select>
      </div>
      {rangeFilters.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 px-8 pb-2">
          <span className="text-xs text-muted-foreground">Filters:</span>
          {rangeFilters.map((c) => (
            <button key={c.keys.join()} type="button" onClick={() => clearF(...c.keys)} aria-label={`Remove filter ${c.label}`}
              className={cn('flex cursor-pointer items-center gap-1 rounded-full border bg-secondary px-2 py-0.5 text-xs text-secondary-foreground transition-colors hover:bg-accent hover:text-accent-foreground',
                c.expired && 'border-destructive/40 bg-destructive/10 text-destructive hover:text-destructive')}>
              {c.label}<X className="h-3 w-3" aria-hidden="true" />
            </button>
          ))}
          {selectionExpired && <span role="status" className="text-xs text-destructive">Selection expired — not applied.</span>}
          <button type="button" onClick={() => clearF('selection', 'min_mp', 'max_mp', 'min_ar', 'max_ar', 'min_ann', 'max_ann')}
            className="cursor-pointer text-xs text-muted-foreground underline hover:text-foreground">Clear all</button>
        </div>
      )}
      {sel.size > 0 && can('project.review') && (
        <div className="mx-8 mb-3 flex flex-wrap items-center gap-2 rounded-lg border bg-accent/40 px-3 py-2 text-sm">
          <b>{sel.size} selected</b>
          <button className="cursor-pointer text-xs text-muted-foreground underline" onClick={() => setSel(new Set(items.map((i) => i.id)))}>select all {items.length} loaded</button>
          <div className="ml-auto flex flex-wrap gap-2">
            <Dropdown trigger={<Button size="sm" variant="outline">Move split</Button>} items={['train', 'valid', 'test'].map((s) => ({ label: s, onClick: () => bulk('split', s) }))} />
            <Button size="sm" variant="outline" onClick={() => { const t = prompt('Tag to add'); t && bulk('add_tag', t) }}><Tag className="h-3.5 w-3.5" /> Tag</Button>
            <Dropdown trigger={<Button size="sm" variant="outline">Set status</Button>} items={[['unassigned', 'Unassigned'], ['annotating', 'Annotating'], ['review', 'Review'], ['done', 'Dataset']].map(([s, l]) => ({ label: l, onClick: () => bulk('status', s) }))} />
            <Button size="sm" variant="outline" onClick={() => setAuto(true)}><Sparkles className="h-3.5 w-3.5" /> Auto label</Button>
            <Button size="sm" variant="destructive" onClick={() => confirm(`Delete ${sel.size} images?`) && bulk('delete')}><Trash2 className="h-3.5 w-3.5" /> Delete</Button>
            <Button size="sm" variant="ghost" onClick={() => setSel(new Set())}>Clear</Button>
          </div>
        </div>
      )}
      <div ref={parentRef} className="min-h-0 flex-1 overflow-y-auto px-8 pb-8">
        {(imgs.isLoading || !selectionResolved) && <div className="py-20 text-center"><Spinner /></div>}
        {imgs.isSuccess && !items.length && <EmptyState title="No images match these filters." hint={f.status === 'done' ? 'Images enter the dataset once approved on the Annotate board.' : undefined}
          action={can('project.upload') && <Button size="sm" onClick={() => nav('../upload')}>Upload images</Button>} />}
        <div style={{ height: v.getTotalSize(), position: 'relative' }}>
          {v.getVirtualItems().map((row) => (
            <div key={row.key} className="absolute left-0 grid w-full grid-cols-5 gap-3" style={{ top: row.start, height: 180 }}>
              {items.slice(row.index * cols, row.index * cols + cols).map((im) => (
                <div key={im.id} role="button" tabIndex={0} aria-label={`Open ${im.name} in the editor`}
                  className={cn('group relative cursor-pointer overflow-hidden rounded-lg border-2 bg-muted', sel.has(im.id) ? 'border-primary' : 'border-transparent hover:border-border')}
                  onClick={() => openEditor(im)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openEditor(im) } }}>
                  <img src={fileUrl(im.thumbnail)} alt={im.name} loading="lazy" className="h-36 w-full object-cover" />
                  <div className="absolute left-1.5 top-1.5 flex gap-1">
                    <span className={cn('rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase text-white', SPLIT_TONE[im.split])}>{im.split}</span>
                    {im.annotationCount === 0 && <span className="rounded bg-gray-700 px-1.5 py-0.5 text-[10px] font-semibold text-white">NULL</span>}
                  </div>
                  {can('project.review') && (
                    <button onClick={(e) => { e.stopPropagation(); toggle(im.id) }} aria-label="Select image"
                      className={cn('absolute right-1.5 top-1.5 flex h-5 w-5 cursor-pointer items-center justify-center rounded border bg-white/90', sel.has(im.id) ? 'border-primary bg-primary text-white' : 'opacity-0 group-hover:opacity-100')}>
                      {sel.has(im.id) && <Check className="h-3 w-3" />}
                    </button>
                  )}
                  <div className="flex items-center gap-1 px-2 py-1.5">
                    <span className="flex-1 truncate text-[11px] text-muted-foreground">{im.name}</span>
                    <div className="flex -space-x-0.5">{im.classIds.slice(0, 4).map((c) => <span key={c} className="h-2 w-2 rounded-full ring-1 ring-white" style={{ background: clsById[c]?.color }} />)}</div>
                    <Badge className="px-1.5 py-0">{im.annotationCount}</Badge>
                  </div>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
      <AutoLabelDialog open={auto} onClose={() => setAuto(false)} batchId={null} imageIds={sel.size ? [...sel] : undefined} />
    </div>
  )
}
