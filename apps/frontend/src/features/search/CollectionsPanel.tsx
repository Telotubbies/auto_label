import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, ChevronLeft, ChevronRight, Pencil, RotateCw, Trash2, X } from 'lucide-react'
import { api, fileUrl } from '@/lib/api'
import type { CollectionItem, CollectionSummary } from '@/lib/types'
import { Button, Card, EmptyState, Field, Input, Modal, Spinner, fmtDate, toast } from '@/components/ui'
import { cn } from '@/lib/utils'
import { toggleId } from './searchState'

const PAGE = 24

/** A collection thumbnail doubles as the checkbox target, so the whole tile is at least 100 px. */
function CollectionTile({ item, selected, onToggle }: {
  item: CollectionItem; selected: boolean; onToggle: (id: string) => void
}) {
  return (
    <label className={cn('group relative cursor-pointer overflow-hidden rounded-md bg-muted',
      selected && 'ring-1 ring-primary')}>
      <img src={fileUrl(item.thumbnail)} alt={item.name} loading="lazy" className="aspect-square w-full object-cover" />
      <input type="checkbox" className="absolute left-1 top-1 h-4 w-4 accent-primary" checked={selected}
        onChange={() => onToggle(item.id)} aria-label={`Select ${item.name}`} />
      <span className="block truncate px-1 py-0.5 text-[10px]" title={item.name}>{item.name}</span>
    </label>
  )
}

/** Saved result sets: open, page through, rename, delete and remove images from the set. */
export default function CollectionsPanel({ ws, slug }: { ws: string; slug: string }) {
  const qc = useQueryClient()
  const [openId, setOpenId] = useState<string | null>(null)
  const [offset, setOffset] = useState(0)
  const [sel, setSel] = useState<Set<string>>(new Set())
  const [renaming, setRenaming] = useState<CollectionSummary | null>(null)
  const [renameName, setRenameName] = useState('')

  const list = useQuery({ queryKey: ['collections', ws, slug], queryFn: () => api.collections(ws, slug), retry: 1 })
  const detail = useQuery({
    queryKey: ['collection', ws, slug, openId, offset],
    queryFn: () => api.collection(ws, slug, openId!, PAGE, offset),
    enabled: !!openId,
    retry: 1,
  })
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['collections', ws, slug] })
    qc.invalidateQueries({ queryKey: ['collection', ws, slug] })
  }

  const open = (id: string) => { setOpenId(id); setOffset(0); setSel(new Set()) }
  const startRename = (c: CollectionSummary) => { setRenaming(c); setRenameName(c.name) }
  const toggle = (id: string) => setSel((s) => toggleId(s, id))

  const rename = useMutation({
    mutationFn: () => api.renameCollection(ws, slug, renaming!.id, renameName.trim()),
    onSuccess: () => { toast.ok('Collection renamed'); setRenaming(null); refresh() },
    onError: (e) => toast.err(e as Error),
  })
  const remove = useMutation({
    mutationFn: (c: CollectionSummary) => api.deleteCollection(ws, slug, c.id),
    onSuccess: (_r, c) => {
      toast.ok(`Deleted “${c.name}”`)
      if (openId === c.id) setOpenId(null)
      refresh()
    },
    onError: (e) => toast.err(e as Error),
  })
  const removeItems = useMutation({
    mutationFn: (ids: string[]) => api.removeCollectionItems(ws, slug, openId!, ids),
    onSuccess: (r) => {
      toast.ok(`Collection now has ${r.count} image${r.count === 1 ? '' : 's'}`)
      setSel(new Set()); refresh()
    },
    onError: (e) => toast.err(e as Error),
  })

  const collections = list.data?.collections ?? []
  const items = detail.data?.items ?? []
  const total = detail.data?.total ?? 0
  const nameOf = detail.data?.name ?? collections.find((c) => c.id === openId)?.name ?? 'Collection'

  return (
    <>
      <Card className="p-3">
        <div className="mb-2 flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold">Collections</h2>
          {!!collections.length && <span className="text-xs text-muted-foreground">{collections.length}</span>}
        </div>
        {openId ? (
          <div className="space-y-2">
            <div className="flex items-start gap-1">
              <Button variant="ghost" size="icon" className="h-7 w-7" aria-label="Back to collections"
                onClick={() => { setOpenId(null); setSel(new Set()) }}><ArrowLeft className="h-3.5 w-3.5" /></Button>
              <div className="min-w-0 flex-1">
                <h3 className="truncate text-sm font-semibold" title={nameOf}>{nameOf}</h3>
                <p className="truncate text-[11px] text-muted-foreground" title={detail.data?.query}>
                  {total} images{detail.data?.query ? ` · ${detail.data.query}` : ''}
                </p>
              </div>
              {detail.data && (
                <>
                  <Button variant="ghost" size="icon" className="h-7 w-7" aria-label={`Rename ${nameOf}`}
                    onClick={() => startRename(detail.data)}><Pencil className="h-3.5 w-3.5" /></Button>
                  <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive" aria-label={`Delete ${nameOf}`}
                    onClick={() => window.confirm(`Delete “${nameOf}”? Images stay in the dataset.`) && remove.mutate(detail.data)}>
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </>
              )}
            </div>
            {detail.isLoading ? (
              <div className="space-y-2"><Spinner /><span className="sr-only">Loading collection</span></div>
            ) : detail.isError ? (
              <div className="py-3 text-center text-xs text-muted-foreground">
                <p className="text-destructive">{(detail.error as Error).message}</p>
                <Button size="sm" variant="outline" className="mt-2" onClick={() => detail.refetch()}><RotateCw className="h-3.5 w-3.5" /> Retry</Button>
              </div>
            ) : !items.length ? (
              <EmptyState title="This collection is empty." hint="Add images from a search, or remove fewer items next time." />
            ) : (
              <div className="grid grid-cols-2 gap-2">
                {items.map((item) => <CollectionTile key={item.id} item={item} selected={sel.has(item.id)} onToggle={toggle} />)}
              </div>
            )}
            <div className="flex items-center justify-between gap-2">
              <Button variant="outline" size="sm" aria-label="Previous page" disabled={offset === 0 || detail.isFetching}
                onClick={() => setOffset((o) => Math.max(0, o - PAGE))}><ChevronLeft className="h-3.5 w-3.5" /> Prev</Button>
              <span className="text-[11px] text-muted-foreground">{offset + 1}–{offset + items.length} of {total}</span>
              <Button variant="outline" size="sm" aria-label="Next page" disabled={offset + items.length >= total || detail.isFetching}
                onClick={() => setOffset((o) => o + PAGE)}>Next <ChevronRight className="h-3.5 w-3.5" /></Button>
            </div>
            {sel.size > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 rounded-md border bg-accent/40 p-2">
                <span className="w-full text-xs"><b>{sel.size}</b> selected</span>
                <Button size="sm" variant="outline" disabled={removeItems.isPending}
                  onClick={() => removeItems.mutate([...sel])}><X className="h-3.5 w-3.5" /> Remove from collection</Button>
                <Button size="sm" variant="ghost" onClick={() => setSel(new Set())}>Clear</Button>
              </div>
            )}
          </div>
        ) : list.isLoading ? (
          <div className="flex justify-center py-4"><Spinner /></div>
        ) : list.isError ? (
          <div className="py-3 text-center text-xs">
            <p className="text-destructive">{(list.error as Error).message}</p>
            <Button size="sm" variant="outline" className="mt-2" onClick={() => list.refetch()}><RotateCw className="h-3.5 w-3.5" /> Retry</Button>
          </div>
        ) : !collections.length ? (
          <p className="py-4 text-center text-xs text-muted-foreground">No collections yet. Save a search to build one.</p>
        ) : (
          <ul className="divide-y">
            {collections.map((c) => (
              <li key={c.id} className="flex items-center gap-0.5 py-1">
                <button type="button" onClick={() => open(c.id)}
                  className="min-w-0 flex-1 cursor-pointer rounded px-1 py-1 text-left hover:bg-accent/60">
                  <span className="block truncate text-sm" title={c.name}>{c.name}</span>
                  <span className="block text-[11px] text-muted-foreground">{c.count} images · {fmtDate(c.updated)}</span>
                  {c.query && <span className="block truncate text-[11px] text-muted-foreground" title={c.query}>{c.query}</span>}
                </button>
                <Button variant="ghost" size="icon" className="h-7 w-7" aria-label={`Rename ${c.name}`} onClick={() => startRename(c)}>
                  <Pencil className="h-3.5 w-3.5" />
                </Button>
                <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive" aria-label={`Delete ${c.name}`}
                  onClick={() => { if (window.confirm(`Delete “${c.name}”? Images stay in the dataset.`)) remove.mutate(c) }}>
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Modal open={!!renaming} onClose={() => setRenaming(null)} title="Rename collection">
        <Field label="Name">
          <Input autoFocus value={renameName} onChange={(e) => setRenameName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && renameName.trim() && !rename.isPending && rename.mutate()} />
        </Field>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setRenaming(null)}>Cancel</Button>
          <Button disabled={!renameName.trim() || rename.isPending} onClick={() => rename.mutate()}>Save</Button>
        </div>
      </Modal>
    </>
  )
}
