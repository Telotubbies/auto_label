import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { LoaderCircle } from 'lucide-react'
import { api, download, fileUrl } from '@/lib/api'
import { emptyOcr, convertOcr, maskPii, ocrText, resizeCells } from '@/lib/ocr'
import type { Annotation, LabelClass, OcrData, OcrKind } from '@/lib/types'
import { Badge, Button, Input, Select, Tabs, toast } from '@/components/ui'
import { cn } from '@/lib/utils'

const KIND_LABEL: Record<OcrKind, string> = { text: 'Text', keyvalue: 'Key-value', table: 'Table' }
const KIND_CHIP: Record<OcrKind, string> = { text: 'Text', keyvalue: 'Field', table: 'Table' }
const KINDS: OcrKind[] = ['text', 'keyvalue', 'table']

type DatasetFormat = 'markdown' | 'json' | 'paddleocr'
type ImageFormat = 'markdown' | 'json'

const asInt = (raw: string, fallback: number) => {
  const n = Number.parseInt(raw, 10)
  return Number.isFinite(n) ? n : fallback
}

function KindPicker({ action, onPick }: { action: string; onPick: (kind: OcrKind) => void }) {
  return (
    <div className="grid grid-cols-3 gap-1.5 pt-1.5">
      {KINDS.map((kind) => (
        <Button key={kind} size="sm" variant="outline" aria-label={`${action} ${KIND_LABEL[kind]}`}
          className="h-7 min-h-6 px-1 text-[11px]" onClick={() => onPick(kind)}>
          {KIND_LABEL[kind]}
        </Button>
      ))}
    </div>
  )
}

/**
 * Text/key-value/table fields for the selected annotation. Edits live in the panel's draft
 * and commit on blur, so typing is one undo step and one save — not one per keystroke.
 */
function OcrFields({ ocr, fields, onChange, onCommit, onCommitNow }: {
  ocr: OcrData
  fields: string[]
  onChange: (ocr: OcrData) => void
  onCommit: () => void
  onCommitNow: (ocr: OcrData) => void
}) {
  if (ocr.kind === 'text') {
    return (
      <label className="block min-w-0">
        <span className="mb-1 block text-[11px] text-muted-foreground">Text</span>
        <Input aria-label="Text" className="h-8" maxLength={2000} value={ocr.text ?? ''}
          onChange={(e) => onChange({ kind: 'text', text: e.target.value })} onBlur={onCommit} />
      </label>
    )
  }
  if (ocr.kind === 'keyvalue') {
    const value = ocr.value ?? ''
    const key = ocr.key ?? ''
    return (
      <div className="space-y-1.5">
        <label className="block min-w-0">
          <span className="mb-1 block text-[11px] text-muted-foreground">Key</span>
          <Input aria-label="Key" className="h-8" maxLength={200} value={key}
            onChange={(e) => onChange({ kind: 'keyvalue', key: e.target.value, value })} onBlur={onCommit} />
        </label>
        {fields.length > 0 && (
          <label className="block min-w-0">
            <span className="mb-1 block text-[11px] text-muted-foreground">Template field</span>
            <Select aria-label="Template field" className="h-8 w-full text-xs" value=""
              onChange={(e) => { if (e.target.value) onCommitNow({ kind: 'keyvalue', key: e.target.value, value }) }}>
              <option value="">Pick a field…</option>
              {fields.map((f) => <option key={f} value={f}>{f}</option>)}
            </Select>
          </label>
        )}
        <label className="block min-w-0">
          <span className="mb-1 block text-[11px] text-muted-foreground">Value</span>
          <Input aria-label="Value" className="h-8" maxLength={2000} value={value}
            onChange={(e) => onChange({ kind: 'keyvalue', key, value: e.target.value })} onBlur={onCommit} />
        </label>
      </div>
    )
  }
  return <TableFields ocr={ocr} onChange={onChange} onCommit={onCommit} />
}

/** Rows/columns keep their values while resized; the grid scrolls, the panel never does. */
function TableFields({ ocr, onChange, onCommit }: {
  ocr: OcrData
  onChange: (ocr: OcrData) => void
  onCommit: () => void
}) {
  const rows = ocr.rows ?? ocr.cells?.length ?? 1
  const cols = ocr.cols ?? ocr.cells?.[0]?.length ?? 1
  const resize = (nextRows: number, nextCols: number) =>
    onChange({ kind: 'table', rows: nextRows, cols: nextCols, cells: resizeCells(ocr.cells, nextRows, nextCols) })
  const setCell = (r: number, c: number, value: string) => {
    const cells = resizeCells(ocr.cells, rows, cols)
    cells[r][c] = value
    onChange({ kind: 'table', rows, cols, cells })
  }
  return (
    <div className="min-w-0">
      <div className="grid grid-cols-2 gap-1.5">
        <label className="block min-w-0">
          <span className="mb-1 block text-[11px] text-muted-foreground">Rows</span>
          <Input type="number" inputMode="numeric" min={1} max={50} aria-label="Rows"
            className="h-7 px-1.5 text-xs tabular-nums" value={rows} onBlur={onCommit}
            onChange={(e) => resize(Math.min(50, Math.max(1, asInt(e.target.value, rows))), cols)} />
        </label>
        <label className="block min-w-0">
          <span className="mb-1 block text-[11px] text-muted-foreground">Columns</span>
          <Input type="number" inputMode="numeric" min={1} max={20} aria-label="Columns"
            className="h-7 px-1.5 text-xs tabular-nums" value={cols} onBlur={onCommit}
            onChange={(e) => resize(rows, Math.min(20, Math.max(1, asInt(e.target.value, cols))))} />
        </label>
      </div>
      <div className="mt-1.5 overflow-x-auto pb-0.5">
        <div role="group" aria-label="Table cells" className="grid min-w-full gap-1"
          style={{ gridTemplateColumns: `repeat(${cols}, minmax(4.5rem, 1fr))` }}>
          {Array.from({ length: rows }, (_, r) => Array.from({ length: cols }, (_, c) => (
            <Input key={`${r}-${c}`} aria-label={`Cell row ${r + 1} column ${c + 1}`} maxLength={500}
              className="h-7 min-w-0 px-1.5 text-xs" value={ocr.cells?.[r]?.[c] ?? ''}
              onChange={(e) => setCell(r, c, e.target.value)} onBlur={onCommit} />
          ))).flat()}
        </div>
      </div>
    </div>
  )
}

function OcrEditor({ ocr, fields, onChange, onCommit, onCommitNow }: {
  ocr: OcrData
  fields: string[]
  onChange: (ocr: OcrData) => void
  onCommit: () => void
  onCommitNow: (ocr: OcrData) => void
}) {
  return (
    <div className="min-w-0">
      <Tabs tabs={KINDS.map((kind) => ({ id: kind, label: KIND_LABEL[kind] }))}
        active={ocr.kind} onChange={(id) => onCommitNow(convertOcr(ocr, id as OcrKind))} />
      <div className="pt-2">
        <OcrFields ocr={ocr} fields={fields} onChange={onChange} onCommit={onCommit} onCommitNow={onCommitNow} />
      </div>
    </div>
  )
}

export function OcrPanel({
  ws,
  project,
  imageId,
  anns,
  sel,
  selId,
  classes,
  mask,
  locked,
  onMaskChange,
  onSelect,
  onUpdate,
  onAdd,
}: {
  ws: string
  project: string
  imageId: string
  anns: Annotation[]
  sel: Annotation | null
  selId: string | null
  classes: LabelClass[]
  mask: boolean
  locked: boolean
  onMaskChange: (mask: boolean) => void
  onSelect: (id: string) => void
  onUpdate: (id: string, ocr: OcrData) => void
  onAdd: (kind: OcrKind) => void
}) {
  const qc = useQueryClient()
  const [pick, setPick] = useState('')
  const [tplBusy, setTplBusy] = useState(false)
  const [busy, setBusy] = useState('')
  const [draft, setDraft] = useState<OcrData | null>(null)
  const draftRef = useRef<OcrData | null>(null)
  draftRef.current = draft
  const templatesQ = useQuery({
    queryKey: ['ocr-templates', ws, project],
    queryFn: () => api.ocrTemplates(ws, project),
  })
  const templates = templatesQ.data?.templates ?? []
  const current = templatesQ.data?.current ?? null
  const active = templates.find((t) => t.id === current) ?? null
  const ocrAnns = anns.filter((a) => !!a.ocr)
  const selected = sel && sel.shape.kind === 'bbox' ? sel : null
  const selectedOcr = selected?.ocr ?? null
  const classOf = (id: string) => classes.find((c) => c.id === id) ?? null

  useEffect(() => { setPick(current ?? '') }, [current])
  // The saved payload is the source of truth: a selection change, undo or redo drops the draft.
  useEffect(() => { setDraft(null) }, [selected?.id, selectedOcr])

  const commitDraft = () => {
    if (selected && draftRef.current) onUpdate(selected.id, draftRef.current)
  }
  const commitNow = (ocr: OcrData) => {
    setDraft(ocr)
    if (selected) onUpdate(selected.id, ocr)
  }

  const applyTemplate = async () => {
    if (!pick) return
    setTplBusy(true)
    try {
      await api.ocrTemplate(ws, project, pick)
      await Promise.all([
        qc.invalidateQueries({ queryKey: ['ocr-templates', ws, project] }),
        qc.invalidateQueries({ queryKey: ['classes', ws, project] }),
      ])
      toast.ok(`Template applied: ${templates.find((t) => t.id === pick)?.name ?? pick}`)
    } catch (e) {
      toast.err(e as Error)
    } finally {
      setTplBusy(false)
    }
  }

  const exportDataset = async (format: DatasetFormat) => {
    setBusy(format)
    try {
      const r = await api.ocrExport(ws, project, { format, mask_pii: mask })
      window.location.assign(fileUrl(r.url))
    } catch (e) {
      toast.err(e as Error)
    } finally {
      setBusy('')
    }
  }

  const exportImage = async (format: ImageFormat) => {
    setBusy(`image-${format}`)
    try {
      await download(`/images/${imageId}/ocr/export?format=${format}&mask_pii=${mask}`,
        `ocr.${format === 'markdown' ? 'md' : 'json'}`)
    } catch (e) {
      toast.err(e as Error)
    } finally {
      setBusy('')
    }
  }

  return (
    <aside aria-label="OCR text" className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center gap-2 px-4 pt-4">
        <h2 className="text-sm font-semibold">OCR text</h2>
        <Badge>{ocrAnns.length}</Badge>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-4 pb-4">
        <section className="mt-3 border-t pt-3" aria-labelledby="ocr-template">
          <h3 id="ocr-template" className="pb-1.5 text-[11px] font-semibold">Document template</h3>
          <div className="flex min-w-0 gap-1.5">
            <Select aria-label="Document template" className="h-8 min-w-0 flex-1 text-xs" value={pick}
              disabled={templatesQ.isLoading} onChange={(e) => setPick(e.target.value)}>
              <option value="">No template</option>
              {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </Select>
            <Button size="sm" aria-label="Apply document template" className="h-8 shrink-0 px-2 text-xs"
              disabled={!pick || tplBusy} onClick={applyTemplate}>
              {tplBusy ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : 'Apply'}
            </Button>
          </div>
          {templatesQ.isError ? (
            <p role="alert" className="pt-1.5 text-[11px] text-destructive">Templates are unavailable right now.</p>
          ) : active ? (
            <div className="pt-1.5">
              <p className="text-[11px] font-medium">Active: {active.name}</p>
              <p className="line-clamp-2 text-[11px] leading-relaxed text-muted-foreground">{active.fields.join(' · ')}</p>
            </div>
          ) : (
            <p className="pt-1.5 text-[11px] leading-relaxed text-muted-foreground">
              No template — key and value stay free text.
            </p>
          )}
        </section>

        <section className="mt-3 border-t pt-3">
          <label className="flex cursor-pointer items-start gap-2">
            <input type="checkbox" className="mt-0.5 h-3.5 w-3.5 shrink-0 accent-primary"
              checked={mask} onChange={(e) => onMaskChange(e.target.checked)} />
            <span className="min-w-0">
              <span className="block text-xs font-medium">Mask personal data</span>
              <span className="block text-[11px] leading-relaxed text-muted-foreground">
                Values are masked in the panel, on the canvas and in exports.
              </span>
            </span>
          </label>
        </section>

        <section className="mt-3 border-t pt-3" aria-labelledby="ocr-selected">
          <h3 id="ocr-selected" className="pb-1.5 text-[11px] font-semibold">Selected annotation</h3>
          {selected ? (
            selected.ocr ? (
              <>
                <p className="pb-1.5 text-[11px] text-muted-foreground">{classOf(selected.classId)?.name ?? 'OCR'}</p>
                {locked ? (
                  <p className="text-[11px] leading-relaxed text-muted-foreground">
                    This annotation is locked — unlock it in Objects to edit its text.
                  </p>
                ) : (
                  <OcrEditor ocr={draft ?? selected.ocr} fields={active?.fields ?? []}
                    onChange={setDraft} onCommit={commitDraft} onCommitNow={commitNow} />
                )}
                {mask && (
                  <p className="pt-2 text-[11px] leading-relaxed text-muted-foreground">
                    <span className="font-medium">Masked preview:</span>{' '}
                    {maskPii(ocrText({ ...selected, ocr: draft ?? selected.ocr })) || '—'}
                  </p>
                )}
              </>
            ) : (
              <>
                <p className="text-[11px] text-muted-foreground">Mark this box as</p>
                <KindPicker action="Mark as" onPick={(kind) => onUpdate(selected.id, emptyOcr(kind))} />
              </>
            )
          ) : (
            <>
              <p className="text-[11px] leading-relaxed text-muted-foreground">
                Select a box on the canvas or in the list, or add one here.
              </p>
              <p className="pt-1.5 text-[11px] text-muted-foreground">Add a centred box as</p>
              <KindPicker action="Add" onPick={onAdd} />
            </>
          )}
        </section>

        <section className="mt-3 border-t pt-3" aria-labelledby="ocr-list">
          <h3 id="ocr-list" className="pb-1.5 text-[11px] font-semibold">
            Annotations <span className="font-normal text-muted-foreground">({ocrAnns.length})</span>
          </h3>
          {ocrAnns.length === 0 ? (
            <p className="text-[11px] leading-relaxed text-muted-foreground">
              No OCR text yet. Draw a box with the OCR tool, or add one above.
            </p>
          ) : (
            <ul className="space-y-0.5">
              {ocrAnns.map((a) => {
                const ocr = a.ocr!
                const c = classOf(a.classId)
                const preview = mask ? maskPii(ocrText(a)) : ocrText(a)
                return (
                  <li key={a.id} className="min-w-0">
                    <button type="button" aria-pressed={a.id === selId} onClick={() => onSelect(a.id)}
                      className={cn('flex w-full min-w-0 cursor-pointer items-start gap-2 rounded px-2 py-1.5 text-left',
                        a.id === selId ? 'bg-accent text-accent-foreground' : 'hover:bg-muted')}>
                      <span aria-hidden className="mt-1 h-2 w-2 shrink-0 rounded-full"
                        style={{ background: c?.color ?? 'currentColor' }} />
                      <span className="min-w-0 flex-1">
                        <span className="flex min-w-0 items-center gap-1.5">
                          <Badge className="shrink-0 px-1 py-0 text-[10px]">{KIND_CHIP[ocr.kind]}</Badge>
                          <span className="min-w-0 truncate text-[10px] text-muted-foreground">{c?.name ?? ''}</span>
                        </span>
                        <span className="mt-0.5 line-clamp-2 break-words text-xs">{preview || 'Empty'}</span>
                      </span>
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </section>

        <section className="mt-3 border-t pt-3" aria-labelledby="ocr-export">
          <h3 id="ocr-export" className="pb-1.5 text-[11px] font-semibold">Export</h3>
          <div role="group" aria-label="Export OCR dataset" className="grid grid-cols-3 gap-1.5">
            <Button size="sm" variant="outline" className="h-7 min-h-6 px-1 text-[10px]"
              aria-label="Export OCR dataset as Markdown" disabled={!ocrAnns.length || !!busy}
              onClick={() => exportDataset('markdown')}>
              {busy === 'markdown' ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : 'Markdown'}
            </Button>
            <Button size="sm" variant="outline" className="h-7 min-h-6 px-1 text-[10px]"
              aria-label="Export OCR dataset as JSON" disabled={!ocrAnns.length || !!busy}
              onClick={() => exportDataset('json')}>
              {busy === 'json' ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : 'JSON'}
            </Button>
            <Button size="sm" variant="outline" className="h-7 min-h-6 px-1 text-[10px]"
              aria-label="Export OCR dataset for PaddleOCR" disabled={!ocrAnns.length || !!busy}
              onClick={() => exportDataset('paddleocr')}>
              {busy === 'paddleocr' ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : 'PaddleOCR'}
            </Button>
          </div>
          <div role="group" aria-label="Export this image" className="flex flex-col gap-1.5 pt-1.5">
            <Button size="sm" variant="outline" className="h-7 min-h-6 justify-start px-2 text-[11px]"
              disabled={!ocrAnns.length || !!busy} onClick={() => exportImage('markdown')}>
              {busy === 'image-markdown' ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : null}
              This image: Markdown
            </Button>
            <Button size="sm" variant="outline" className="h-7 min-h-6 justify-start px-2 text-[11px]"
              disabled={!ocrAnns.length || !!busy} onClick={() => exportImage('json')}>
              {busy === 'image-json' ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : null}
              This image: JSON
            </Button>
          </div>
          <p className="pt-1.5 text-[10px] leading-relaxed text-muted-foreground">
            {ocrAnns.length
              ? mask ? 'Personal data is masked on export.' : 'Masking is off — personal data is included.'
              : 'Add OCR text to enable export.'}
          </p>
        </section>
      </div>
    </aside>
  )
}
