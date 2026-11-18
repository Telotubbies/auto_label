import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useVirtualizer } from '@tanstack/react-virtual'
import { Check, ChevronLeft, ChevronRight, Database, LayoutGrid, List, Search, SlidersHorizontal, Sparkles, Tag, Trash2, X } from 'lucide-react'
import { api, ApiError, fileUrl, post } from '@/lib/api'
import { editorPath, projectPath } from '@/lib/routes'
import { useProjectPermissions } from '@/lib/perms'
import type { ImageItem } from '@/lib/types'
import { Badge, Button, Dropdown, EmptyState, Input, Select, Spinner, toast } from '@/components/ui'
import { cn } from '@/lib/utils'
import { splitColor } from '@/lib/theme'
import { useProject } from './ProjectLayout'
import { AutoLabelDialog } from './AutoLabelDialog'
import { autolabelParam } from './autolabelLabel'
import { colsForWidth, pageWindow, rowHeightForWidth } from './datasetGrid'
import { countLine } from './datasetCopy'

// Stable across renders, so React does not resubscribe the width listener on every re-render.
const subscribeResize = (onChange: () => void) => {
  window.addEventListener('resize', onChange)
  return () => window.removeEventListener('resize', onChange)
}

const STATUS_LABEL: Record<string, string> = { unassigned: 'Unassigned', annotating: 'Annotating', review: 'Review', done: 'Dataset' }

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
    // ingest-time quality flags from the health check's click-through
    quality: sp.get('quality') ?? '',
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
  const [perPage, setPerPage] = useState(100)
  const [page, setPage] = useState(1)
  const filterKey = JSON.stringify(activeF)
  // A new filter or page size starts again from page one.
  useEffect(() => { setPage(1) }, [filterKey, perPage])
  const imgs = useQuery({
    queryKey: ['images', ws, project.slug, activeF, perPage, page],
    // empty numeric params would be rejected by the API, so send only the filters that are set
    queryFn: () => api.images(ws, project.slug, {
      ...Object.fromEntries(Object.entries(activeF).filter(([, v]) => v !== '')), limit: perPage, offset: (page - 1) * perPage,
    }),
    enabled: selectionResolved,
    placeholderData: (prev) => prev,
  })
  const classes = useQuery({ queryKey: ['classes', ws, project.slug], queryFn: () => api.classes(ws, project.slug) })
  const tags = useQuery({ queryKey: ['tags', ws, project.slug], queryFn: () => api.tags(ws, project.slug) })
  const batches = useQuery({ queryKey: ['batches', ws, project.slug], queryFn: () => api.batches(ws, project.slug) })
  const [sel, setSel] = useState<Set<string>>(new Set())
  const [showFilters, setShowFilters] = useState(false)
  const [showAnn, setShowAnn] = useState(true)
  const [view, setView] = useState<'grid' | 'list'>('grid')
  const [help, setHelp] = useState(false)
  const [auto, setAuto] = useState(false)
  const [autoRef, setAutoRef] = useState<string | null>(null)
  // a link from the Inference Hub opens the dialog once, then leaves a clean URL behind
  useEffect(() => {
    const ref = autolabelParam(sp)
    if (!ref) return
    setAutoRef(ref); setAuto(true)
    const n = new URLSearchParams(sp); n.delete('autolabel'); setSp(n, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- read the link once on mount
  }, [])
  const items = useMemo(() => imgs.data?.items ?? [], [imgs.data])
  const total = imgs.data?.total
  const pages = Math.max(1, Math.ceil((total ?? 0) / perPage))
  // A filter that hides every image is not an empty project; the two states must not say the same thing.
  const filtered = project.images > (total ?? 0)
  const clsById = useMemo(() => Object.fromEntries((classes.data ?? []).map((c) => [c.id, c])), [classes.data])

  const parentRef = useRef<HTMLDivElement>(null)
  // The virtualiser slices `cols` items per row, so the slice follows the same breakpoints the row's
  // classes use. One resize listener is enough; the width itself is all the helpers need.
  const width = useSyncExternalStore(subscribeResize, () => window.innerWidth, () => 1440)
  const cols = colsForWidth(width)
  const rowH = rowHeightForWidth(width)
  const rows = Math.ceil(items.length / cols)
  const v = useVirtualizer({ count: view === 'grid' ? rows : 0, getScrollElement: () => parentRef.current, estimateSize: () => rowH, overscan: 4 })

  const bulk = (action: string, value?: string) =>
    post<{ updated: number }>(`${api.P(ws, project.slug)}/images/bulk`, { ids: [...sel], action, value })
      .then((r) => { toast.ok(`Updated ${r.updated} images`); setSel(new Set()); qc.invalidateQueries({ queryKey: ['images', ws, project.slug] }); qc.invalidateQueries({ queryKey: ['project', ws, project.slug] }); qc.invalidateQueries({ queryKey: ['tags', ws, project.slug] }) })
      .catch(toast.err)
  const toggle = (id: string) => setSel((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n })
  const openEditor = (im: ImageItem) => {
    const q = new URLSearchParams(Object.entries(f).filter(([k, v]) => v && k !== 'selection').map(([k, v]) => [k === 'batch_id' ? 'batch' : k, v]) as [string, string][])
    nav(editorPath(ws, project.slug, im.id, `?${q}`))
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
      <div className="mx-8 mb-3 mt-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-secondary text-secondary-foreground"><Database className="h-5 w-5" aria-hidden /></span>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Dataset</h1>
            <p className="text-sm text-muted-foreground">
              {total === undefined ? '…' : countLine(total, project.images)}{' · '}
              <button type="button" aria-expanded={help} onClick={() => setHelp(!help)} className="cursor-pointer underline hover:text-foreground">How to search</button>
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {can('project.review') && <Button variant="outline" onClick={() => setAuto(true)}><Sparkles className="h-4 w-4" /> Auto Label</Button>}
          {can('project.train') && <Button onClick={() => nav(projectPath(ws, project.slug, 'train'))}>Train model</Button>}
        </div>
      </div>
      {help && <p className="mx-8 mb-3 rounded-lg border bg-muted/50 px-3 py-2 text-sm text-muted-foreground">Type part of a filename to search. Use Add filter to narrow by status, split, class, tag, batch, annotations or quality; filters combine.</p>}
      <div className="flex flex-wrap items-center gap-2 px-8 pb-3">
        <div className="relative w-56"><Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" /><Input className="pl-8" placeholder="Search filename" value={f.q} onChange={(e) => setF('q', e.target.value)} /></div>
        <Button variant="outline" aria-expanded={showFilters} onClick={() => setShowFilters(!showFilters)}><SlidersHorizontal className="h-4 w-4" /> Add filter</Button>
        <Select aria-label="Sort" value={f.sort} onChange={(e) => setF('sort', e.target.value)}><option value="newest">Newest</option><option value="oldest">Oldest</option><option value="name">Filename</option><option value="most">Most annotations</option><option value="least">Fewest annotations</option></Select>
        <label className="ml-auto flex cursor-pointer items-center gap-2 text-sm"><input type="checkbox" checked={showAnn} onChange={(e) => setShowAnn(e.target.checked)} /> Show annotations</label>
        <div role="group" aria-label="View" className="flex overflow-hidden rounded-md border">
          {([['grid', LayoutGrid, 'Grid view'], ['list', List, 'List view']] as const).map(([id, Icon, label]) => (
            <button key={id} type="button" aria-label={label} aria-pressed={view === id} onClick={() => setView(id)}
              className={cn('grid h-9 w-9 cursor-pointer place-items-center', view === id ? 'bg-accent text-accent-foreground' : 'hover:bg-muted')}><Icon className="h-4 w-4" /></button>
          ))}
        </div>
      </div>
      {showFilters && (
        <div className="flex flex-wrap items-center gap-2 px-8 pb-3">
          <Select value={f.status} onChange={(e) => setF('status', e.target.value)}>
            <option value="all">All statuses</option><option value="done">Dataset (approved)</option><option value="review">In review</option><option value="annotating">Annotating</option><option value="unassigned">Unassigned</option>
          </Select>
          <Select value={f.split} onChange={(e) => setF('split', e.target.value)}><option value="">All splits</option><option value="train">Train</option><option value="valid">Valid</option><option value="test">Test</option></Select>
          <Select value={f.class_id} onChange={(e) => setF('class', e.target.value)}><option value="">All classes</option>{classes.data?.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.count})</option>)}</Select>
          <Select value={f.tag} onChange={(e) => setF('tag', e.target.value)}><option value="">All tags</option>{tags.data?.map((t) => <option key={t.name} value={t.name}>{t.name} ({t.count})</option>)}</Select>
          <Select value={f.batch_id} onChange={(e) => setF('batch', e.target.value)}><option value="">All batches</option>{batches.data?.map((b) => <option key={b.id} value={b.id}>{b.name} ({b.images})</option>)}</Select>
          <Select value={f.annotated} onChange={(e) => setF('annotated', e.target.value)}><option value="">Any annotations</option><option value="yes">Annotated</option><option value="no">Null (no annotations)</option></Select>
          <Select value={f.quality} onChange={(e) => setF('quality', e.target.value)}><option value="">Any quality</option><option value="blurry">Blurry</option><option value="dark">Too dark</option><option value="ok">Good quality</option><option value="unknown">Not scored</option></Select>
        </div>
      )}
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
      <div ref={parentRef} className="min-h-0 flex-1 overflow-y-auto px-4 pb-8 sm:px-8">
        {(imgs.isLoading || !selectionResolved) && <div className="py-20 text-center"><Spinner /></div>}
        {imgs.isError && <p role="alert" className="py-6 text-sm text-destructive">Could not load images.{' '}
          <button type="button" className="cursor-pointer underline" onClick={() => imgs.refetch()}>Try again</button></p>}
        {imgs.isSuccess && !items.length && <EmptyState title={filtered ? 'No images match these filters.' : 'No images yet'} hint={f.status === 'done' ? 'Images enter the dataset once approved on the Annotate board.' : undefined}
          action={can('project.upload') && <Button size="sm" onClick={() => nav(projectPath(ws, project.slug, 'upload'))}>Upload images</Button>} />}
        {view === 'list' && (
          <ul className="divide-y rounded-lg border">
            {items.map((im) => (
              <li key={im.id}>
                <button type="button" onClick={() => openEditor(im)} className="flex w-full cursor-pointer items-center gap-3 px-3 py-2 text-left text-sm hover:bg-muted/60">
                  <img src={fileUrl(im.thumbnail)} alt="" loading="lazy" className="h-10 w-14 rounded object-cover" />
                  <span className="min-w-0 flex-1 truncate">{im.name}</span>
                  <span className={cn('rounded px-1.5 py-0.5 text-xs font-semibold uppercase', splitColor(im.split))}>{im.split}</span>
                  <span className="w-24 text-xs text-muted-foreground">{STATUS_LABEL[im.status] ?? im.status}</span>
                  {showAnn && <Badge className="px-1.5 py-0">{im.annotationCount}</Badge>}
                </button>
              </li>
            ))}
          </ul>
        )}
        <div style={{ height: v.getTotalSize(), position: 'relative' }}>
          {v.getVirtualItems().map((row) => (
            <div key={row.key} className="absolute left-0 grid w-full grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5" style={{ top: row.start, height: rowH }}>
              {items.slice(row.index * cols, row.index * cols + cols).map((im) => (
                <div key={im.id} role="button" tabIndex={0} aria-label={`Open ${im.name} in the editor`}
                  className={cn('group relative cursor-pointer overflow-hidden rounded-lg border-2 bg-muted', sel.has(im.id) ? 'border-primary' : 'border-transparent hover:border-border')}
                  onClick={() => openEditor(im)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openEditor(im) } }}>
                  <img src={fileUrl(im.thumbnail)} alt={im.name} loading="lazy" className="w-full object-cover" style={{ height: rowH - 36 }} />
                  <div className="absolute left-1.5 top-1.5 flex gap-1">
                    <span className={cn('rounded px-1.5 py-0.5 text-xs font-semibold uppercase', splitColor(im.split))}>{im.split}</span>
                    {im.annotationCount === 0 && <span className="rounded bg-gray-700 px-1.5 py-0.5 text-[10px] font-semibold text-white">NULL</span>}
                  </div>
                  {can('project.review') && (
                    <button onClick={(e) => { e.stopPropagation(); toggle(im.id) }} aria-label="Select image"
                      className={cn('absolute right-1.5 top-1.5 flex h-5 w-5 cursor-pointer items-center justify-center rounded border bg-white/90', sel.has(im.id) ? 'border-primary bg-primary text-white' : 'opacity-0 group-hover:opacity-100')}>
                      {sel.has(im.id) && <Check className="h-3 w-3" />}
                    </button>
                  )}
                  <span className="absolute bottom-9 left-1.5 rounded bg-scrim/70 px-1.5 py-0.5 text-xs font-semibold text-white">{STATUS_LABEL[im.status] ?? im.status}</span>
                  <div className="flex items-center gap-1 px-2 py-1.5">
                    <span className="flex-1 truncate text-[11px] text-muted-foreground">{im.name}</span>
                    {showAnn && <>
                      <div className="flex -space-x-0.5">{im.classIds.slice(0, 4).map((c) => <span key={c} className="h-2 w-2 rounded-full ring-1 ring-white" style={{ background: clsById[c]?.color }} />)}</div>
                      <Badge className="px-1.5 py-0">{im.annotationCount}</Badge>
                    </>}
                  </div>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-3 border-t px-8 py-2 text-sm">
        <label className="flex items-center gap-2 text-muted-foreground">Per page
          <Select value={perPage} onChange={(e) => setPerPage(Number(e.target.value))}>{[25, 50, 100, 200].map((n) => <option key={n} value={n}>{n}</option>)}</Select>
        </label>
        <span className="ml-auto tabular-nums text-muted-foreground">
          {total ? `${(page - 1) * perPage + 1}-${Math.min(page * perPage, total)} of ${total.toLocaleString()}` : '0 of 0'}
        </span>
        <nav aria-label="Pages" className="flex items-center gap-1">
          <button type="button" aria-label="Previous page" disabled={page <= 1} onClick={() => setPage(page - 1)} className="grid h-8 w-8 cursor-pointer place-items-center rounded-md hover:bg-muted disabled:opacity-40"><ChevronLeft className="h-4 w-4" /></button>
          {pageWindow(page, pages).map((n, i) => n === '…'
            ? <span key={`gap${i}`} className="px-1 text-muted-foreground">…</span>
            : <button key={n} type="button" aria-current={n === page ? 'page' : undefined} onClick={() => setPage(n)}
              className={cn('h-8 min-w-8 cursor-pointer rounded-md px-2 tabular-nums', n === page ? 'bg-primary text-primary-foreground' : 'hover:bg-muted')}>{n}</button>)}
          <button type="button" aria-label="Next page" disabled={page >= pages} onClick={() => setPage(page + 1)} className="grid h-8 w-8 cursor-pointer place-items-center rounded-md hover:bg-muted disabled:opacity-40"><ChevronRight className="h-4 w-4" /></button>
        </nav>
      </div>
      <AutoLabelDialog open={auto} onClose={() => { setAuto(false); setAutoRef(null) }} batchId={null} imageIds={sel.size ? [...sel] : undefined} initialRef={autoRef} />
    </div>
  )
}
