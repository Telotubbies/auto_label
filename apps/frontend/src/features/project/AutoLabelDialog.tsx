import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bot, Eye, LoaderCircle, Sparkles, TriangleAlert } from 'lucide-react'
import { api, fileUrl, post } from '@/lib/api'
import type { AutoLabelInput, Job, RegistryItem } from '@/lib/types'
import { Badge, Button, Field, Input, Modal, Select, toast } from '@/components/ui'
import { cn } from '@/lib/utils'
import { useProject } from './ProjectLayout'

/** Capabilities an auto-label model must have at least one of. */
const AUTOLABEL_CAPS = ['detect', 'segment', 'open-vocab']
const SAM_REF = 'sam3:sam3.1'
const SAMPLE_SIZES = [3, 4, 5] as const

const canAutoLabel = (m: RegistryItem) => m.capabilities.some((c) => AUTOLABEL_CAPS.includes(c))

/** Short, actionable next step for a failed call. */
function errorHint(message: string): string {
  if (/detection or segmentation/i.test(message)) return 'Pick another project, or use a detection/segmentation model.'
  if (/class/i.test(message)) return 'Add classes to the project first, then reopen this dialog.'
  if (/SAM/i.test(message)) return 'SAM 3.1 must be available on the worker for VLM boxes.'
  if (/vLLM|vlm/i.test(message)) return 'Check that the vLLM server is running, then try again.'
  if (/model|registry|adapter/i.test(message)) return 'Pick another model, or check that its adapter is installed.'
  return ''
}

export function AutoLabelDialog({ open, onClose, batchId, imageIds }: {
  open: boolean; onClose: () => void; batchId: string | null
  /** Limit the run to a hand-picked selection; empty means the whole batch/project. */
  imageIds?: string[]
}) {
  const { project, ws } = useProject()
  const qc = useQueryClient()
  const registryQ = useQuery({ queryKey: ['registry', ws], queryFn: () => api.registry(ws), enabled: open })
  const classesQ = useQuery({ queryKey: ['classes', ws, project.slug], queryFn: () => api.classes(ws, project.slug), enabled: open })

  const items = useMemo(
    () => (registryQ.data ?? []).filter((m) => canAutoLabel(m)
      && !(project.type === 'classification' && (m.family === 'sam3' || m.family === 'vlm'))),
    [registryQ.data, project.type],
  )
  const groups = useMemo(() => ({
    trained: items.filter((m) => m.kind === 'trained'),
    zoo: items.filter((m) => m.kind === 'zoo'),
    vlm: items.filter((m) => m.kind === 'vlm'),
  }), [items])

  const [modelRef, setModelRef] = useState('')
  // null = untouched, so every class stays selected without an effect once the list loads
  const [classIds, setClassIds] = useState<string[] | null>(null)
  const [prompt, setPrompt] = useState('')
  const [vlmVerify, setVlmVerify] = useState(false)
  const [confidence, setConfidence] = useState(40)
  const [onlyUnannotated, setOnlyUnannotated] = useState(true)
  const [sample, setSample] = useState(4)

  // opening the dialog or switching project starts from a clean slate (class ids are project-scoped)
  useEffect(() => {
    if (!open) return
    setModelRef(''); setClassIds(null); setPrompt(''); setVlmVerify(false)
    setConfidence(40); setOnlyUnannotated(true); setSample(4)
    previewMutation.reset(); runMutation.reset()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reset only on open/project transitions
  }, [open, project.slug])

  const classes = classesQ.data ?? []
  const available = items.filter((m) => m.available)
  const defaultRef = (available.find((m) => m.kind === 'trained') ?? available.find((m) => m.kind === 'zoo') ?? available[0])?.ref ?? ''
  const selectedRef = modelRef || defaultRef
  const selected = items.find((m) => m.ref === selectedRef) ?? null
  const isVlm = selectedRef.startsWith('vlm:')
  const sam = (registryQ.data ?? []).find((m) => m.ref === SAM_REF)
  const samMissing = isVlm && (!sam || !sam.available)

  const pickedClassIds = classIds ?? classes.map((c) => c.id)
  const validClassIds = pickedClassIds.filter((id) => classes.some((c) => c.id === id))
  const firstClass = classes.find((c) => c.id === validClassIds[0]) ?? null
  const allSelected = classes.length > 0 && validClassIds.length === classes.length

  const previewMutation = useMutation({
    mutationFn: (body: AutoLabelInput & { sample?: number }) => api.autolabelPreview(ws, project.slug, body),
  })
  const runMutation = useMutation({
    mutationFn: (body: AutoLabelInput) => post<Job>(`${api.P(ws, project.slug)}/autolabel`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['jobs', ws, project.slug] })
      toast.ok('Auto-label job queued — results land in Review')
      previewMutation.reset()
      onClose()
    },
  })

  const touch = () => {
    if (!previewMutation.isPending) previewMutation.reset()
    if (!runMutation.isPending) runMutation.reset()
  }
  const close = () => { previewMutation.reset(); runMutation.reset(); onClose() }
  const toggleClass = (id: string) => {
    setClassIds(pickedClassIds.includes(id) ? pickedClassIds.filter((x) => x !== id) : [...pickedClassIds, id])
    touch()
  }

  const blocked =
    registryQ.isLoading ? 'Loading models…'
      : registryQ.isError ? 'Models could not be loaded.'
        : !selected ? 'No model is available for auto-labeling.'
          : !selected.available ? (selected.reason || 'This model is not available on the worker.')
            : samMissing ? 'VLM boxes need SAM 3.1.'
              : classesQ.isLoading ? 'Loading classes…'
                : !classes.length ? 'Add classes first. SAM uses class names as text prompts.'
                  : !validClassIds.length ? 'Select at least one class.'
                    : ''
  const runBlocked = !!blocked || runMutation.isPending || previewMutation.isPending
  const previewBlocked = !!blocked || previewMutation.isPending
  const runHint = blocked || (previewMutation.isPending ? 'Waiting for the preview to finish.' : '')

  const input: AutoLabelInput = {
    model_ref: selectedRef || undefined,
    prompt: prompt.trim() || null,
    vlm_verify: vlmVerify,
    batch_id: batchId ?? null,
    image_ids: imageIds ?? [],
    class_ids: validClassIds,
    confidence: confidence / 100,
    only_unannotated: onlyUnannotated,
    send_to_review: true,
  }

  const error = runMutation.error ?? previewMutation.error
  // a response that finished for older settings must not be shown as if it matched the current ones
  const previewKey = JSON.stringify({ ...input, sample })
  const preview = previewMutation.isSuccess && JSON.stringify(previewMutation.variables) === previewKey
    ? previewMutation.data : undefined
  const previewTotal = preview ? preview.images.reduce((n, im) => n + im.annotations.length, 0) : 0
  const countRows = Object.entries(preview?.counts ?? {}).filter(([, n]) => n > 0)

  return (
    <Modal open={open} onClose={close} title={<span className="flex items-center gap-2"><Sparkles className="h-5 w-5 text-primary" /> Auto label images</span>}>
      <div className="space-y-3.5">
        {registryQ.isError && (
          <div role="alert" className="rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive">
            <p>Models could not be loaded. {(registryQ.error as Error).message}</p>
            <button onClick={() => registryQ.refetch()} className="mt-1 cursor-pointer text-xs font-medium underline underline-offset-2">Try again</button>
          </div>
        )}

        {items.length === 0 ? (
          <p className="rounded-lg border border-dashed px-3 py-2.5 text-xs text-muted-foreground">
            No model reports detection, segmentation or open-vocabulary support yet.
          </p>
        ) : (
          <>
            <Field label="Model">
              <Select className="w-full" value={selectedRef} onChange={(e) => { setModelRef(e.target.value); touch() }}>
                {!selected && <option value="" disabled>No available model</option>}
                {groups.trained.length > 0 && (
                  <optgroup label="Your models">
                    {groups.trained.map((m) => (
                      <option key={m.ref} value={m.ref} disabled={!m.available}>{m.name}{m.available ? '' : ' — unavailable'}</option>
                    ))}
                  </optgroup>
                )}
                {groups.zoo.length > 0 && (
                  <optgroup label="Model zoo">
                    {groups.zoo.map((m) => (
                      <option key={m.ref} value={m.ref} disabled={!m.available}>{m.name}{m.available ? '' : ' — unavailable'}</option>
                    ))}
                  </optgroup>
                )}
                {groups.vlm.length > 0 && (
                  <optgroup label="Vision-language">
                    {groups.vlm.map((m) => (
                      <option key={m.ref} value={m.ref} disabled={!m.available}>{m.name}{m.available ? '' : ' — unavailable'}</option>
                    ))}
                  </optgroup>
                )}
              </Select>
            </Field>
            {selected && (
              <div className="-mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted-foreground">
                <span>License: {selected.license}</span>
                {selected.capabilities.map((c) => <Badge key={c} className="px-1.5 py-px text-[10px] font-normal">{c}</Badge>)}
                {!selected.available && <span className="text-destructive">{selected.reason}</span>}
              </div>
            )}
            {!selected && (
              <p className="-mt-2 text-xs text-muted-foreground">No model is available on this worker right now.</p>
            )}
            {samMissing && (
              <div role="alert" className="flex gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
                <p>
                  VLM boxes are never saved without SAM 3.1, and it is not available
                  {sam?.reason ? ` (${sam.reason})` : ''}. Preview and Run are disabled until SAM 3.1 is available.
                </p>
              </div>
            )}
          </>
        )}

        <div>
          <div className="mb-1.5 flex items-baseline justify-between">
            <span className="text-sm font-medium">Class prompts</span>
            {classes.length > 1 && (
              <button type="button" onClick={() => { setClassIds(allSelected ? [] : classes.map((c) => c.id)); touch() }}
                className="cursor-pointer text-[11px] text-muted-foreground underline underline-offset-2 hover:text-foreground">
                {allSelected ? 'Clear all' : 'Select all'}
              </button>
            )}
          </div>
          {classesQ.isError ? (
            <p role="alert" className="rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2 text-xs text-destructive">
              Classes could not be loaded. {(classesQ.error as Error).message}{' '}
              <button onClick={() => classesQ.refetch()} className="cursor-pointer font-medium underline underline-offset-2">Try again</button>
            </p>
          ) : !classesQ.isLoading && !classes.length ? (
            <p className="rounded-lg border border-dashed px-3 py-2.5 text-xs text-muted-foreground">
              Add classes first. SAM 3.1 uses class names as text prompts.
            </p>
          ) : (
            <div role="group" aria-label="Class prompts" className="max-h-32 space-y-0.5 overflow-y-auto rounded-lg border p-1.5">
              {classes.map((c) => (
                <label key={c.id} className="flex cursor-pointer items-center gap-2 rounded px-1.5 py-1 text-sm hover:bg-muted">
                  <input type="checkbox" className="accent-primary" checked={pickedClassIds.includes(c.id)} onChange={() => toggleClass(c.id)} />
                  <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: c.color }} aria-hidden />
                  <span className="flex-1 truncate">{c.name}</span>
                  <span className="text-[10px] text-muted-foreground">{c.count}</span>
                </label>
              ))}
              {classesQ.isLoading && <p className="px-1.5 py-1 text-xs text-muted-foreground">Loading classes…</p>}
            </div>
          )}
        </div>

        <Field
          label="Describe what to label"
          hint={prompt.trim() && firstClass
            ? <>Parsed into short noun phrases for SAM 3.1. Results attach to <b>{firstClass.name}</b>.</>
            : 'Optional. Parsed into short noun phrases for SAM 3.1.'}
        >
          <Input placeholder="Workers without helmets near the forklift" value={prompt}
            onChange={(e) => { setPrompt(e.target.value); touch() }} />
        </Field>

        <label className="flex cursor-pointer items-start gap-2 text-sm">
          <input type="checkbox" className="mt-0.5 accent-primary" checked={vlmVerify} onChange={(e) => { setVlmVerify(e.target.checked); touch() }} />
          <span>VLM verify each box<span className="block text-xs text-muted-foreground">One vLLM call per box. Drops boxes the VLM cannot confirm.</span></span>
        </label>

        {isVlm ? (
          <p className="rounded-lg bg-muted px-3 py-2 text-xs text-muted-foreground">
            VLM boxes use a fixed 0.50 score and are always refined with SAM 3.1, so the confidence threshold does not apply.
          </p>
        ) : (
          <Field label={`Confidence ${confidence}%`} hint="Boxes below this score are dropped.">
            <input type="range" min={5} max={95} value={confidence} onChange={(e) => { setConfidence(+e.target.value); touch() }}
              className="w-full accent-primary" aria-label="Confidence threshold" />
          </Field>
        )}

        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" className="accent-primary" checked={onlyUnannotated} onChange={(e) => { setOnlyUnannotated(e.target.checked); touch() }} />
          Only images without annotations
        </label>

        {error && (
          <div role="alert" className="flex gap-2 rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive">
            <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p>{error.message}</p>
              {errorHint(error.message) && <p className="pt-1 text-xs">{errorHint(error.message)}</p>}
            </div>
          </div>
        )}

        {preview && (
          <div className="rounded-lg border p-2.5">
            <div className="mb-2 flex items-baseline justify-between">
              <span className="text-xs font-medium">Preview · {preview.images.length} images</span>
              <span className="text-[11px] text-muted-foreground">{previewTotal} annotations</span>
            </div>
            {previewTotal === 0 ? (
              <p className="rounded-md bg-muted px-3 py-3 text-center text-xs text-muted-foreground">
                No annotations found. Try a lower confidence, another class, or a clearer prompt.
              </p>
            ) : (
              <>
                <div className="grid gap-1.5" style={{ gridTemplateColumns: `repeat(${Math.min(5, preview.images.length)}, minmax(0, 1fr))` }}>
                  {preview.images.map((im) => (
                    <figure key={im.id} className="relative overflow-hidden rounded-md border bg-muted">
                      <img src={fileUrl(im.url)} alt="" loading="lazy" className="aspect-[4/3] w-full object-cover" />
                      <figcaption className="absolute bottom-1 right-1 rounded bg-black/70 px-1 py-px text-[10px] font-medium text-white">
                        {im.annotations.length}
                      </figcaption>
                    </figure>
                  ))}
                </div>
                <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
                  {countRows.map(([name, n]) => (
                    <span key={name} className="flex items-center gap-1">
                      <span className="h-2 w-2 rounded-full" style={{ background: classes.find((c) => c.name === name)?.color ?? '#999' }} aria-hidden />
                      {name} <span className="font-medium text-foreground">{n}</span>
                    </span>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        <div className="border-t pt-3">
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-muted-foreground">Sample</span>
            <div role="group" aria-label="Preview sample size" className="flex overflow-hidden rounded-md border text-xs">
              {SAMPLE_SIZES.map((n) => (
                <button key={n} type="button" aria-pressed={sample === n} aria-label={`Preview ${n} images`}
                  onClick={() => { setSample(n); touch() }}
                  className={cn('h-7 w-7 cursor-pointer border-r last:border-r-0 transition-colors', sample === n ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-accent')}>
                  {n}
                </button>
              ))}
            </div>
            <Button size="sm" variant="outline" disabled={previewBlocked} title={blocked || undefined}
              onClick={() => previewMutation.mutate({ ...input, sample })}>
              {previewMutation.isPending ? <><LoaderCircle className="h-3.5 w-3.5 animate-spin" /> Previewing…</> : <><Eye className="h-3.5 w-3.5" /> Preview</>}
            </Button>
            <span className="ml-auto text-[11px] text-muted-foreground">Optional before a run</span>
          </div>
          <div className="mt-2 flex items-center justify-end gap-2">
            {runHint && !runMutation.isPending && <p className="mr-auto min-w-0 text-[11px] leading-tight text-muted-foreground">{runHint}</p>}
            <Button variant="ghost" size="sm" onClick={close}>Cancel</Button>
            <Button size="sm" disabled={runBlocked} title={runHint || undefined} onClick={() => runMutation.mutate(input)}>
              {runMutation.isPending ? <><LoaderCircle className="h-3.5 w-3.5 animate-spin" /> Queueing…</> : <><Bot className="h-3.5 w-3.5" /> Run</>}
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  )
}
