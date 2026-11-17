/**
 * The Models tab (T-1012): one host's downloadable catalogue, filterable, one variant per row chosen
 * with a segmented control, and one sheet that states the gate and the disk before a job is queued.
 * The host picker lives in the hub header; this panel only consumes the chosen host.
 */
import { useCallback, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, ExternalLink, SlidersHorizontal } from 'lucide-react'
import { Glass } from '@/components/glass'
import { Button, Card, EmptyState, Modal, Select, Spinner } from '@/components/ui'
import { inferenceJobs, inferenceModels } from '@/lib/api/inference'
import type { InferenceHost, InferenceModel, InferenceModelVariant } from '@/lib/types'
import {
  BANDS, NO_FILTERS, defaultVariant, filterModels, gib, rowState, type ModelFilters,
} from './modelRows'
import InstallProgress from './InstallProgress'
import AssetsPanel from './AssetsPanel'
import ModelSheet from './ModelSheet'

const POLL_MS = 2000
const SKELETON = [0, 1, 2, 3, 4]

/** Five skeleton rows while the host list or its catalogue are still on the wire. */
const SkeletonRows = () => (
  <Card className="divide-y overflow-hidden" aria-busy="true" aria-label="Loading models">
    {SKELETON.map((i) => (
      <div key={i} className="flex items-center gap-3 p-4">
        <div className="h-4 flex-1 animate-pulse rounded bg-muted" />
        <div className="h-4 w-20 animate-pulse rounded bg-muted" />
        <div className="h-4 w-16 animate-pulse rounded bg-muted" />
      </div>
    ))}
  </Card>
)

/** The four selects and two toggles, in the sticky bar on a desk and in a sheet at 375 px. */
function FilterControls({ id, filters, onChange, families, quants, licences }: {
  id: string; filters: ModelFilters; onChange: (next: ModelFilters) => void
  families: string[]; quants: string[]; licences: string[]
}) {
  const set = (patch: Partial<ModelFilters>) => onChange({ ...filters, ...patch })
  return (
    <>
      <label className="block">
        <span className="mb-1 block text-xs text-muted-foreground">Family</span>
        <Select aria-label="Family" className="w-full md:w-40" value={filters.family}
          onChange={(e) => set({ family: e.target.value })}>
          <option value="all">All families</option>
          {families.map((family) => <option key={family} value={family}>{family}</option>)}
        </Select>
      </label>
      <label className="block">
        <span className="mb-1 block text-xs text-muted-foreground">Size</span>
        <Select aria-label="Size band" className="w-full md:w-36" value={filters.band}
          onChange={(e) => set({ band: e.target.value })}>
          <option value="all">Any size</option>
          {BANDS.map((band) => <option key={band.id} value={band.id}>{band.label}</option>)}
        </Select>
      </label>
      <label className="block">
        <span className="mb-1 block text-xs text-muted-foreground">Quantisation</span>
        <Select aria-label="Quantisation" className="w-full md:w-32" value={filters.quant}
          onChange={(e) => set({ quant: e.target.value })}>
          <option value="all">Any quant</option>
          {quants.map((quant) => <option key={quant} value={quant}>{quant}</option>)}
        </Select>
      </label>
      <label className="block">
        <span className="mb-1 block text-xs text-muted-foreground">Licence</span>
        <Select aria-label="Licence" className="w-full md:w-56" value={filters.licence}
          onChange={(e) => set({ licence: e.target.value })}>
          <option value="all">Any licence</option>
          {licences.map((name) => <option key={name} value={name}>{name}</option>)}
        </Select>
      </label>
      <div className="flex flex-wrap items-center gap-3 md:pb-2">
        <label className="flex items-center gap-2 text-sm">
          <input id={`${id}-fits`} type="checkbox" className="h-4 w-4 accent-primary" checked={filters.fits}
            onChange={(e) => set({ fits: e.target.checked })} />
          Fits this host
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input id={`${id}-installed`} type="checkbox" className="h-4 w-4 accent-primary"
            checked={filters.installed} onChange={(e) => set({ installed: e.target.checked })} />
          Installed
        </label>
      </div>
    </>
  )
}

export default function ModelsTab({ ws, host, hostsLoading, hostsError, onRetryHosts }: {
  ws: string
  host: InferenceHost | null
  hostsLoading: boolean
  hostsError: boolean
  onRetryHosts: () => void
}) {
  const hostId = host?.id ?? ''
  const qc = useQueryClient()
  const models = useQuery({
    queryKey: ['inference-models', ws, hostId],
    enabled: !!hostId,
    retry: false,
    queryFn: () => inferenceModels(ws, hostId),
  })
  // The same key InstallProgress reads: one poll feeds the row's percent and the job card.
  const jobs = useQuery({
    queryKey: ['inference-jobs', ws],
    enabled: !!ws,
    retry: false,
    queryFn: () => inferenceJobs(ws),
    refetchInterval: (query) => ((query.state.data ?? []).length ? POLL_MS : false),
  })
  const [filters, setFilters] = useState<ModelFilters>(NO_FILTERS)
  const [picked, setPicked] = useState<Record<string, string>>({})
  const [sheet, setSheet] = useState<{ row: InferenceModel; variant: InferenceModelVariant } | null>(null)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [queued, setQueued] = useState<{ row: string; variant: string; job: string } | null>(null)
  const [seenHost, setSeenHost] = useState(hostId)

  // A different host has a different disk and GPU: a job queued on the old one is not this one's state.
  if (seenHost !== hostId) {
    setSeenHost(hostId)
    setQueued(null)
  }

  const settled = useCallback(() => {
    setQueued(null)
    void qc.invalidateQueries({ queryKey: ['inference-models', ws, hostId] })
    void qc.invalidateQueries({ queryKey: ['inference-hosts', ws] })
  }, [qc, ws, hostId])

  const all = models.data?.models ?? []
  const rows = filterModels(all, filters)
  const families = [...new Set(all.map((row) => row.family))]
  const quants = [...new Set(all.flatMap((row) => row.variants.map((variant) => variant.quant)))]
  const licences = [...new Set(all.map((row) => row.licence.name))]
  const narrowed = filters.family !== 'all' || filters.band !== 'all' || filters.quant !== 'all'
    || filters.licence !== 'all' || filters.fits || filters.installed
  const live = jobs.data ?? []

  const variantOf = (row: InferenceModel) =>
    row.variants.find((variant) => variant.id === picked[row.id]) ?? defaultVariant(row)

  // A queued row knows its job id before the poll lists it, so it reads `Queued` at once.
  const jobOf = (rowId: string) => queued?.row === rowId
    ? live.find((job) => job.id === queued.job) ?? { status: 'queued' as const, progress: 0 }
    : null

  const onQueued = (jobId: string, rowId: string, variantId: string) => {
    setQueued({ row: rowId, variant: variantId, job: jobId })
    setPicked((current) => ({ ...current, [rowId]: variantId }))
    void qc.invalidateQueries({ queryKey: ['inference-jobs', ws] })
  }

  const progress = <InstallProgress ws={ws} onSettled={settled} />

  if (hostsLoading) return <div className="space-y-3">{progress}<SkeletonRows /></div>

  if (hostsError) {
    return (
      <div className="space-y-3">
        {progress}
        <Card className="p-6">
          <p className="text-sm text-destructive">Models did not load for this host.</p>
          <Button variant="outline" size="sm" className="mt-2" onClick={onRetryHosts}>Retry</Button>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {progress}
      <AssetsPanel ws={ws} host={host} />
      {!host ? (
        <Card className="p-6">
          <EmptyState title="Pick a host to see what fits."
            hint="A worker reports its disk, GPU and installed models when it claims a job." />
        </Card>
      ) : (
        <>
          <Glass className="sticky top-0 z-20 rounded-xl p-3">
            <div className="hidden flex-wrap items-end gap-3 md:flex">
              <FilterControls id="filters-bar" filters={filters} onChange={setFilters}
                families={families} quants={quants} licences={licences} />
              <Button variant="ghost" size="sm" className="md:ml-auto md:mb-1" disabled={!narrowed}
                onClick={() => setFilters(NO_FILTERS)}>Clear filters</Button>
            </div>
            <div className="flex items-center justify-between gap-2 md:hidden">
              <p className="text-sm">{rows.length} of {all.length} models · {host.host}</p>
              <Button variant="outline" size="sm" onClick={() => setFiltersOpen(true)}>
                <SlidersHorizontal className="h-4 w-4" aria-hidden /> Filters
              </Button>
            </div>
          </Glass>

          {models.isLoading ? <SkeletonRows /> : models.isError ? (
            <Card className="p-6">
              <p className="text-sm text-destructive">Models did not load for this host.</p>
              <Button variant="outline" size="sm" className="mt-2" onClick={() => void models.refetch()}>Retry</Button>
            </Card>
          ) : !rows.length ? (
            <Card className="p-6">
              <EmptyState title={narrowed ? 'No model matches these filters.' : 'No model has a verified pin yet.'}
                action={narrowed
                  ? <Button variant="outline" size="sm" onClick={() => setFilters(NO_FILTERS)}>Clear filters</Button>
                  : undefined} />
            </Card>
          ) : (
            <Card className="overflow-hidden">
              <div className="overflow-x-auto" role="region" aria-label="Models" tabIndex={0}>
                <table className="w-full min-w-[56rem] text-sm">
                  <caption className="sr-only">Models, their variants and what fits {host.host}</caption>
                  <thead className="bg-muted/60 text-left text-xs text-muted-foreground">
                    <tr>
                      <th scope="col" className="sticky left-0 z-10 w-56 bg-muted/60 px-3 py-2 font-medium">Model</th>
                      <th scope="col" className="whitespace-nowrap px-3 py-2 font-medium">Params</th>
                      <th scope="col" className="px-3 py-2 font-medium">Variant</th>
                      <th scope="col" className="whitespace-nowrap px-3 py-2 font-medium">Download</th>
                      <th scope="col" className="px-3 py-2 font-medium">Licence</th>
                      <th scope="col" className="px-3 py-2 font-medium">Gate</th>
                      <th scope="col" className="px-3 py-2 font-medium">Engine</th>
                      <th scope="col" className="whitespace-nowrap px-3 py-2 font-medium">Est. VRAM</th>
                      <th scope="col" className="px-3 py-2 font-medium">State</th>
                      <th scope="col" className="px-2 py-2"><span className="sr-only">Actions</span></th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => {
                      const variant = variantOf(row)
                      const state = rowState(row, jobOf(row.id))
                      return (
                        <tr key={row.id} className="border-t align-top">
                          <td className="sticky left-0 z-10 bg-card px-3 py-2.5">
                            <span className="block font-medium">{row.name}</span>
                            <span className="block text-xs text-muted-foreground">{row.family}</span>
                            {row.fits === false && (
                              <span className="mt-1 inline-flex rounded-full bg-warning/15 px-2 py-0.5 text-xs font-medium text-warning">
                                Does not fit this host
                              </span>
                            )}
                          </td>
                          <td className="whitespace-nowrap px-3 py-2.5 tabular-nums">{row.params_b} B</td>
                          <td className="px-3 py-2.5">
                            <div role="group" aria-label={`Variant for ${row.name}`} className="flex flex-wrap gap-1">
                              {row.variants.map((item) => (
                                <button key={item.id} type="button" aria-pressed={item.id === variant.id}
                                  onClick={() => setPicked((current) => ({ ...current, [row.id]: item.id }))}
                                  className={item.id === variant.id
                                    ? 'rounded-full bg-primary px-2 py-0.5 text-xs font-medium text-primary-foreground'
                                    : 'rounded-full bg-secondary px-2 py-0.5 text-xs hover:bg-accent'}>
                                  {item.quant}
                                </button>
                              ))}
                            </div>
                          </td>
                          <td className="whitespace-nowrap px-3 py-2.5 tabular-nums">{gib(variant.bytes)}</td>
                          <td className="px-3 py-2.5">
                            <a href={row.licence.url} target="_blank" rel="noreferrer noopener"
                              title={row.licence.name} className="inline-flex max-w-44 items-center gap-1 text-xs hover:underline">
                              <span className="truncate">{row.licence.name}</span>
                              <ExternalLink className="h-3 w-3 shrink-0" aria-hidden />
                            </a>
                            {row.licence.non_commercial && (
                              <span className="mt-1 block text-xs font-medium text-warning">Non-commercial licence</span>
                            )}
                          </td>
                          <td className="px-3 py-2.5">
                            {row.licence.gated
                              ? <span className="rounded-full bg-warning/15 px-2 py-0.5 text-xs font-medium text-warning">Gated</span>
                              : <span className="text-xs text-muted-foreground">—</span>}
                          </td>
                          <td className="whitespace-nowrap px-3 py-2.5 text-muted-foreground">{variant.engine}</td>
                          <td className="whitespace-nowrap px-3 py-2.5 tabular-nums">
                            {variant.vram_gb === null ? 'unknown' : `${variant.vram_gb.toFixed(1)} GB`}
                          </td>
                          <td className="whitespace-nowrap px-3 py-2.5">
                            {state.state === 'downloading' || state.state === 'queued' ? (
                              <span className="inline-flex items-center gap-1.5 text-muted-foreground">
                                <Spinner className="h-3 w-3" /> {state.label}
                              </span>
                            ) : state.state === 'installed' ? (
                              <span className="inline-flex items-center gap-1.5">
                                <Check className="h-3 w-3 text-success" aria-hidden /> {state.label}
                              </span>
                            ) : <span className="text-muted-foreground">{state.label}</span>}
                          </td>
                          <td className="px-2 py-2.5 text-right">
                            {state.actions.map((action) => action.kind === 'download' ? (
                              <Button key={action.kind} size="sm" variant="outline"
                                onClick={() => setSheet({ row, variant })}>{action.label}</Button>
                            ) : (
                              <a key={action.kind} href="#host-assets" className="text-xs hover:underline">
                                {action.label}
                              </a>
                            ))}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </>
      )}

      {filtersOpen && (
        <Modal open onClose={() => setFiltersOpen(false)} title="Filters">
          <div className="flex h-[calc(100dvh-9rem)] flex-col gap-3 sm:h-auto sm:min-h-0">
            <FilterControls id="filters-sheet" filters={filters} onChange={setFilters}
              families={families} quants={quants} licences={licences} />
            <div className="mt-auto flex justify-between gap-2 pt-4">
              <Button variant="ghost" disabled={!narrowed} onClick={() => setFilters(NO_FILTERS)}>Clear filters</Button>
              <Button onClick={() => setFiltersOpen(false)}>Done</Button>
            </div>
          </div>
        </Modal>
      )}
      {sheet && host && (
        <ModelSheet ws={ws} host={host} row={sheet.row} variant={sheet.variant} open
          onClose={() => setSheet(null)} onQueued={onQueued} />
      )}
    </div>
  )
}


