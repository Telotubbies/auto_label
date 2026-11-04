import { useEffect, useState, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, FolderPlus, Info, RotateCw, Search } from 'lucide-react'
import { api, fileUrl } from '@/lib/api'
import type { SearchResultItem } from '@/lib/types'
import {
  Badge, Button, Card, EmptyState, Field, Input, Modal, PageHeader, Select, Spinner, toast,
} from '@/components/ui'
import { cn } from '@/lib/utils'
import { useProjectPermissions } from '@/lib/perms'
import { useProject } from '../project/ProjectLayout'
import CollectionsPanel from './CollectionsPanel'
import { buildCollectionQuery, buildSearchQuery, collectionTargets, selectAll, toggleId, type SearchFilters } from './searchState'

const percent = (score: number | null) => (score === null ? null : `${Math.round(score * 100)}%`)

/** One inline explanation above the grid: a degraded search, or why nothing ranked. */
function Notice({ children, tone = 'info' }: { children: ReactNode; tone?: 'info' | 'warning' }) {
  const Icon = tone === 'warning' ? AlertTriangle : Info
  return (
    <div role="status" className={cn('mx-8 mb-3 flex items-start gap-2 rounded-lg border px-3 py-2 text-sm',
      tone === 'warning' ? 'border-warning/40 bg-warning/10' : 'bg-accent/40')}>
      <Icon className={cn('mt-0.5 h-4 w-4 shrink-0', tone === 'warning' ? 'text-warning' : 'text-muted-foreground')} aria-hidden />
      <div className="min-w-0">{children}</div>
    </div>
  )
}

function ResultCard({ item, selected, semantic, selectable, onToggle }: {
  item: SearchResultItem; selected: boolean; semantic: boolean; selectable: boolean; onToggle: (id: string) => void
}) {
  const score = percent(item.score)
  return (
    <Card className={cn('group overflow-hidden', selected && 'border-primary ring-1 ring-primary')}>
      <div className="relative">
        <img src={fileUrl(item.thumbnail)} alt={item.name} loading="lazy" className="aspect-[4/3] w-full object-cover" />
        {selectable && (
          <label className="absolute left-1.5 top-1.5 flex h-7 w-7 cursor-pointer items-center justify-center rounded-md bg-card/90 shadow-sm">
            <input type="checkbox" className="h-4 w-4 accent-primary" checked={selected}
              onChange={() => onToggle(item.id)} aria-label={`Select ${item.name}`} />
          </label>
        )}
        {semantic && score && <Badge className="absolute right-1.5 top-1.5 bg-primary text-primary-foreground">{score}</Badge>}
      </div>
      <div className="space-y-1.5 p-2">
        <div className="truncate text-xs font-medium" title={item.name}>{item.name}</div>
        <div className="flex flex-wrap gap-1">
          <Badge className="uppercase">{item.split}</Badge>
          {item.class_name && <Badge className="bg-accent text-accent-foreground">{item.class_name}</Badge>}
          {item.tags.slice(0, 3).map((t) => <Badge key={t}>{t}</Badge>)}
          {item.tags.length > 3 && <Badge>+{item.tags.length - 3}</Badge>}
        </div>
      </div>
    </Card>
  )
}

export default function SearchPage() {
  const { project, ws } = useProject()
  const qc = useQueryClient()
  // Collections are reviewer-only on the API; labelers keep search (assigned images only).
  const perms = useProjectPermissions(ws, project.slug)
  const canReview = perms.ready && perms.can('project.review')
  const [sp, setSp] = useSearchParams()
  const filters: SearchFilters = {
    q: sp.get('q') ?? '', class_id: sp.get('class_id') ?? '', tag: sp.get('tag') ?? '',
    split: sp.get('split') ?? '', status: sp.get('status') ?? '', annotated: sp.get('annotated') ?? '',
  }
  const [text, setText] = useState(filters.q)
  const [sel, setSel] = useState<Set<string>>(new Set())
  const [saveOpen, setSaveOpen] = useState(false)
  const [name, setName] = useState('')
  // Browser back/forward and filter clicks both land here; typing in the box must not be overwritten.
  useEffect(() => { setText(filters.q) }, [filters.q])
  useEffect(() => { setSel(new Set()) }, [sp])

  const params = buildSearchQuery(filters)
  const search = useQuery({
    queryKey: ['search', ws, project.slug, params],
    queryFn: () => api.search(ws, project.slug, params),
    placeholderData: (prev) => prev,
    retry: 1,
  })
  const data = search.data
  const items = data?.items ?? []
  const targets = collectionTargets(sel, items)

  const setF = (key: string, value: string) => {
    const next = new URLSearchParams(sp)
    if (value) next.set(key, value)
    else next.delete(key)
    setSp(next, { replace: true })
  }
  const submit = () => setF('q', text.trim())
  const clearFilters = () => { setSp(new URLSearchParams(), { replace: true }); setText('') }
  const toggle = (id: string) => setSel((s) => toggleId(s, id))

  const save = useMutation({
    mutationFn: () => api.createCollection(ws, project.slug, {
      name: name.trim(),
      image_ids: targets.length ? targets : undefined,
      query: buildCollectionQuery(filters.q, filters) || undefined,
    }),
    onSuccess: (c) => {
      toast.ok(`Saved “${c.name}” with ${c.count} image${c.count === 1 ? '' : 's'}`)
      setSaveOpen(false); setName('')
      qc.invalidateQueries({ queryKey: ['collections', ws, project.slug] })
    },
    onError: (e) => toast.err(e as Error),
  })

  const mode = data?.mode
  const hint = mode === 'semantic' ? 'sorted by visual similarity' : mode === 'filter' ? 'filters only' : 'browse'
  const filtered = Object.keys(params).length > 0

  return (
    <div className="anim-page flex h-full flex-col">
      <PageHeader title="Search" desc="Find images by what they show — semantic ranking once the project is indexed." />
      <div className="flex flex-wrap items-center gap-2 px-8 pb-3">
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" aria-hidden />
          <Input className="pl-8" aria-label="Search images" placeholder="e.g. workers without helmets"
            value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && submit()} />
        </div>
        <Select aria-label="Filter by class" value={filters.class_id} onChange={(e) => setF('class_id', e.target.value)}>
          <option value="">All classes</option>
          {data?.facets.classes.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.count})</option>)}
        </Select>
        <Select aria-label="Filter by split" value={filters.split} onChange={(e) => setF('split', e.target.value)}>
          <option value="">All splits</option><option value="train">Train</option><option value="valid">Valid</option><option value="test">Test</option>
        </Select>
        <Select aria-label="Filter by tag" value={filters.tag} onChange={(e) => setF('tag', e.target.value)}>
          <option value="">All tags</option>
          {data?.facets.tags.map((t) => <option key={t} value={t}>{t}</option>)}
        </Select>
        <Select aria-label="Filter by annotation state" value={filters.annotated} onChange={(e) => setF('annotated', e.target.value)}>
          <option value="">Any annotations</option><option value="yes">Annotated</option><option value="no">No annotations</option>
        </Select>
        <Select aria-label="Filter by status" value={filters.status} onChange={(e) => setF('status', e.target.value)}>
          <option value="">All statuses</option><option value="unassigned">Unassigned</option><option value="annotating">Annotating</option>
          <option value="review">Review</option><option value="done">Dataset</option>
        </Select>
        <Button variant="outline" onClick={submit}>Search</Button>
      </div>

      {mode === 'filter' && (
        <Notice tone="warning">
          <b>Semantic search is unavailable.</b> {data?.reason || 'Showing matches from the filters only.'}
        </Notice>
      )}

      <div className="flex flex-wrap items-center gap-2 px-8 pb-3 text-sm">
        <span className="font-medium" aria-live="polite">
          {data?.total ?? 0} results{canReview && sel.size ? ` · ${sel.size} selected` : ''}
        </span>
        <span className="text-muted-foreground">· {hint}</span>
        {data && <span className="text-xs text-muted-foreground">({data.indexed} indexed{data.missing ? `, ${data.missing} not indexed` : ''})</span>}
        <div className="ml-auto flex flex-wrap items-center gap-1.5">
          {canReview && (
            <>
              <Button variant="ghost" size="sm" onClick={() => setSel(selectAll(items.map((i) => i.id), true))} disabled={!items.length}>Select all</Button>
              <Button variant="ghost" size="sm" onClick={() => setSel(selectAll(items.map((i) => i.id), false))} disabled={!sel.size}>Clear selection</Button>
              <Button size="sm" onClick={() => setSaveOpen(true)} disabled={!items.length && !filtered}>
                <FolderPlus className="h-3.5 w-3.5" /> Save as collection
              </Button>
            </>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-4 px-8 pb-8 xl:flex-row xl:items-start">
        <section aria-label="Search results" className="min-w-0 flex-1">
          {search.isLoading ? (
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4" aria-label="Loading results">
              {Array.from({ length: 8 }).map((_, i) => <div key={i} className="h-52 animate-pulse rounded-lg bg-muted" />)}
            </div>
          ) : search.isError ? (
            <Card className="p-8 text-center">
              <p className="text-sm text-destructive">{(search.error as Error).message}</p>
              <Button size="sm" className="mt-3" onClick={() => search.refetch()}><RotateCw className="h-3.5 w-3.5" /> Retry</Button>
            </Card>
          ) : !items.length ? (
            <EmptyState title={filtered ? 'No images match this search.' : 'No images to show yet.'}
              hint={filtered ? 'Try a broader description or remove a filter.' : 'Upload images to the project, or ask a reviewer to assign images to you.'}
              action={filtered ? <Button size="sm" variant="outline" onClick={clearFilters}>Clear filters</Button> : undefined} />
          ) : (
            <>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
                {items.map((item) => (
                  <ResultCard key={item.id} item={item} selected={sel.has(item.id)} semantic={mode === 'semantic'}
                    selectable={canReview} onToggle={toggle} />
                ))}
              </div>
              {search.isFetching && (
                <p className="mt-2 flex items-center gap-2 text-xs text-muted-foreground"><Spinner className="h-3 w-3" /> Updating results…</p>
              )}
            </>
          )}
        </section>
        {canReview && (
          <aside className="w-full shrink-0 xl:sticky xl:top-4 xl:w-80">
            <CollectionsPanel ws={ws} slug={project.slug} />
          </aside>
        )}
      </div>

      {canReview && (
        <Modal open={saveOpen} onClose={() => setSaveOpen(false)} title="Save as collection">
          <Field label="Name" hint={`Saves ${targets.length} image${targets.length === 1 ? '' : 's'}${sel.size ? ' (selected)' : ' (all results)'} plus the query text.`}>
            <Input autoFocus placeholder="e.g. Workers missing helmets" value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && name.trim() && !save.isPending && save.mutate()} />
          </Field>
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setSaveOpen(false)}>Cancel</Button>
            <Button disabled={!name.trim() || save.isPending} onClick={() => save.mutate()}>Save</Button>
          </div>
        </Modal>
      )}
    </div>
  )
}
