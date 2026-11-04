import { useEffect, useMemo, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Camera, ScanLine, Trash2, Undo2, X } from 'lucide-react'
import { api, fileUrl } from '@/lib/api'
import type { StreamItem, StreamZone } from '@/lib/types'
import { Button, Modal, toast } from '@/components/ui'
import { cn } from '@/lib/utils'

const ZONE_COLORS = ['#56B4E9', '#E69F00', '#009E73', '#CC79A7', '#0072B2', '#D55E00', '#F0E442', '#7F7F7F']

const clamp01 = (n: number) => Math.min(1, Math.max(0, n))
const round4 = (n: number) => Math.round(n * 10000) / 10000
const pairs = (flat: number[]) => {
  const out: [number, number][] = []
  for (let i = 0; i + 1 < flat.length; i += 2) out.push([flat[i], flat[i + 1]])
  return out
}

/** Direction tick drawn in HTML so the line arrow is not stretched by the SVG's normalized viewBox. */
function LineArrow({ line, aspect, color }: { line: number[]; aspect: number; color: string }) {
  if (line.length !== 4) return null
  const [x1, y1, x2, y2] = line
  const t = 0.72
  const x = x1 + (x2 - x1) * t
  const y = y1 + (y2 - y1) * t
  const angle = (Math.atan2(y2 - y1, (x2 - x1) * aspect) * 180) / Math.PI
  return (
    <span aria-hidden="true" className="pointer-events-none absolute"
      style={{ left: `${x * 100}%`, top: `${y * 100}%`, transform: `translate(-50%, -50%) rotate(${angle}deg)` }}>
      <svg width="10" height="10" viewBox="0 0 10 10"><path d="M1 1 L9 5 L1 9 Z" fill={color} /></svg>
    </span>
  )
}

/**
 * Draw zones and threshold lines on a single paused MJPEG frame. The image element is closed as soon as
 * one frame has been copied into the canvas, so nothing keeps streaming while the dialog is open.
 */
export default function ZoneEditor({ open, onClose, ws, project, stream, onSaved, initialMode = 'zones', onLine }: {
  open: boolean
  onClose: () => void
  ws: string
  project: string
  stream: StreamItem
  onSaved?: (zones: StreamZone[]) => void
  initialMode?: 'zones' | 'line'
  /** Present only when the parent is capturing a line for a rule; enables line mode. */
  onLine?: (line: number[]) => void
}) {
  const qc = useQueryClient()
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const allowLine = !!onLine
  const startMode = allowLine && initialMode === 'line' ? 'line' : 'zones'

  const [mode, setMode] = useState<'zones' | 'line'>(startMode)
  const [zones, setZones] = useState<StreamZone[]>(stream.zones ?? [])
  const [draft, setDraft] = useState<number[]>([])
  const [lineDraft, setLineDraft] = useState<number[]>([])
  const [drawnLine, setDrawnLine] = useState<number[] | null>(null)
  const [hover, setHover] = useState<[number, number] | null>(null)
  const [aspect, setAspect] = useState(16 / 9)
  const [loaded, setLoaded] = useState(false)
  const [saving, setSaving] = useState(false)
  const [frameNonce, setFrameNonce] = useState(0)

  const lines = useMemo(
    () => stream.rules.flatMap((rule) => (rule.kind === 'line' && rule.line.length === 4 ? [rule] : [])),
    [stream.rules],
  )

  // Reset the working copy whenever the dialog opens.
  useEffect(() => {
    if (!open) return
    setZones(stream.zones ?? [])
    setDraft([])
    setLineDraft([])
    setDrawnLine(null)
    setHover(null)
    setMode(startMode)
    // startMode is derived from initialMode/onLine and changes only when the caller changes intent.
  }, [open, stream.id, startMode])

  // Fetch exactly one JPEG from /frame into the canvas — the MJPEG connection is never held open here.
  useEffect(() => {
    if (!open) return
    setLoaded(false)
    if (!stream.frame || stream.status === 'stopped' || stream.status === 'error') return

    let cancelled = false
    let objectUrl = ''
    let img: HTMLImageElement | null = null
    const ctrl = new AbortController()
    const timer = window.setTimeout(() => ctrl.abort(), 8000)
    const fail = () => { if (!cancelled) setLoaded(false) }

    fetch(fileUrl(stream.frame), { signal: ctrl.signal })
      .then((r) => (r.ok ? r.blob() : Promise.reject(new Error(String(r.status)))))
      .then((blob) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        const image = new window.Image()
        img = image
        image.onload = () => {
          if (cancelled) return
          const canvas = canvasRef.current
          if (canvas) {
            canvas.width = image.naturalWidth || 1280
            canvas.height = image.naturalHeight || 720
            canvas.getContext('2d')?.drawImage(image, 0, 0)
            setAspect((image.naturalWidth || 16) / (image.naturalHeight || 9))
          }
          setLoaded(true)
        }
        image.onerror = fail
        image.src = objectUrl
      })
      .catch(fail)

    return () => {
      cancelled = true
      window.clearTimeout(timer)
      ctrl.abort()
      if (img) { img.onload = null; img.onerror = null }
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
    // Not watching stream.frame: its signature changes every poll and one frame is enough.
    // frameNonce is the explicit "Capture frame" refresh.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, stream.id, stream.status, frameNonce])

  const nextZoneId = () => {
    const used = new Set(zones.map((z) => z.id))
    let n = zones.length + 1
    while (used.has(`zone-${n}`)) n++
    return `zone-${n}`
  }

  const finishPolygon = () => {
    if (draft.length < 6) return
    setZones((z) => [...z, { id: nextZoneId(), points: draft.map(round4) }])
    setDraft([])
  }

  // Capture phase so Esc cancels the shape before Modal's own Esc handler closes the dialog.
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return
      if (e.key === 'Escape') {
        if (!draft.length && !lineDraft.length) return
        e.preventDefault(); e.stopImmediatePropagation()
        setDraft([]); setLineDraft([])
      } else if (e.key === 'Enter') {
        if (draft.length < 6) return
        // Let Enter activate the focused control instead of closing the polygon twice.
        if (t && (t.tagName === 'BUTTON' || t.tagName === 'A' || t.tagName === 'SELECT')) return
        e.preventDefault(); e.stopImmediatePropagation()
        finishPolygon()
      } else if (e.key === 'Backspace') {
        if (!draft.length && !lineDraft.length) return
        e.preventDefault(); e.stopImmediatePropagation()
        setDraft((d) => d.slice(0, -2))
        setLineDraft((l) => l.slice(0, -2))
      }
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [open, draft, lineDraft, zones])

  const pointOf = (e: React.MouseEvent<HTMLDivElement>): [number, number] => {
    const r = e.currentTarget.getBoundingClientRect()
    return [clamp01((e.clientX - r.left) / r.width), clamp01((e.clientY - r.top) / r.height)]
  }

  const draw = (e: React.MouseEvent<HTMLDivElement>) => {
    if (mode === 'zones' && e.detail > 1) return // second click of a double-click; onDoubleClick closes the shape
    const [x, y] = pointOf(e)
    if (mode === 'line') {
      if (!lineDraft.length) { setLineDraft([x, y]); return }
      if (Math.hypot(x - lineDraft[0], y - lineDraft[1]) < 0.005) return
      const line = [lineDraft[0], lineDraft[1], x, y].map(round4)
      setLineDraft([])
      setDrawnLine(line)
      onLine?.(line)
      return
    }
    setDraft((d) => [...d, x, y])
  }

  const track = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!draft.length && !lineDraft.length) return
    setHover(pointOf(e))
  }

  const switchMode = (next: 'zones' | 'line') => {
    setMode(next)
    setDraft([])
    setLineDraft([])
    setHover(null)
  }

  const save = async () => {
    setSaving(true)
    try {
      const updated = await api.updateStream(ws, project, stream.id, { zones })
      qc.setQueryData(['stream', ws, project, stream.id], updated)
      qc.invalidateQueries({ queryKey: ['streams', ws, project] })
      toast.ok(`Saved ${zones.length} zone${zones.length === 1 ? '' : 's'}`)
      onSaved?.(zones)
      onClose()
    } catch (e) { toast.err(e as Error) } finally { setSaving(false) }
  }

  const busyShape = draft.length > 0 || lineDraft.length > 0

  return (
    <Modal open={open} onClose={onClose} wide title="Zones & lines">
      <div className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="text-sm text-muted-foreground">
              {mode === 'zones'
                ? 'Click the frame to add polygon points. Double-click or press Enter to close a polygon.'
                : 'Click twice to draw a line. Existing line rules are dashed.'}
            </p>
            <p id="zone-editor-hint" className="mt-1 text-xs text-muted-foreground">
              Esc cancels the shape · Backspace or Undo removes the last point · geometry is normalised 0–1
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
            <Button size="sm" variant="outline" onClick={() => setFrameNonce((n) => n + 1)}
              disabled={stream.status === 'stopped' || stream.status === 'error'}
              title={stream.status === 'stopped' || stream.status === 'error' ? 'Start the stream to capture a frame' : 'Capture the current frame'}>
              <Camera className="h-3.5 w-3.5" /> Capture frame
            </Button>
            {allowLine && (
              <div role="group" aria-label="Drawing mode" className="flex gap-0.5 rounded-md border p-0.5">
                <button type="button" aria-pressed={mode === 'zones'} onClick={() => switchMode('zones')}
                  className={cn('rounded px-2.5 py-1 text-xs font-medium', mode === 'zones' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-accent')}>
                  Zones
                </button>
                <button type="button" aria-pressed={mode === 'line'} onClick={() => switchMode('line')}
                  className={cn('rounded px-2.5 py-1 text-xs font-medium', mode === 'line' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-accent')}>
                  Line
                </button>
              </div>
            )}
          </div>
        </div>

        <div
          role="application"
          aria-label="Zone editor"
          aria-describedby="zone-editor-hint"
          className={cn('relative w-full overflow-hidden rounded-lg border border-border bg-black', mode === 'line' ? 'cursor-cell' : 'cursor-crosshair')}
          style={{ aspectRatio: String(aspect) }}
          onClick={draw}
          onDoubleClick={() => { if (mode === 'zones') finishPolygon() }}
          onMouseMove={track}
          onMouseLeave={() => setHover(null)}
        >
          <canvas ref={canvasRef} role="img" aria-label="Paused camera frame for drawing zones and lines"
            aria-describedby="zone-editor-hint" className="absolute inset-0 h-full w-full" />

          {!loaded && (
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-1 px-6 text-center"
              style={{
                backgroundImage:
                  'linear-gradient(to right, rgb(255 255 255 / .07) 1px, transparent 1px), linear-gradient(to bottom, rgb(255 255 255 / .07) 1px, transparent 1px)',
                backgroundSize: '32px 32px',
              }}>
              <ScanLine className="h-6 w-6 text-white/50" />
              <p className="text-sm font-medium text-white/80">No frame available</p>
              <p className="max-w-sm text-xs text-white/50">
                {stream.status === 'stopped' || stream.status === 'error'
                  ? 'The stream is stopped, but you can still draw zones on this grid. Start it to see a frame next time.'
                  : 'The frame did not arrive. You can still draw zones on this grid.'}
              </p>
            </div>
          )}

          <svg viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden="true"
            className="pointer-events-none absolute inset-0 h-full w-full">
            {zones.map((zone, i) => (
              <polygon key={zone.id} points={pairs(zone.points).map(([x, y]) => `${x},${y}`).join(' ')}
                fill={`${ZONE_COLORS[i % ZONE_COLORS.length]}33`} stroke={ZONE_COLORS[i % ZONE_COLORS.length]}
                strokeWidth={2} vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
            ))}

            {lines.map((rule, i) => (
              <g key={`line-${i}`}>
                <line x1={rule.line[0]} y1={rule.line[1]} x2={rule.line[2]} y2={rule.line[3]}
                  stroke="#FDE047" strokeWidth={2} strokeDasharray="6 4" vectorEffect="non-scaling-stroke" />
              </g>
            ))}

            {drawnLine && (
              <line x1={drawnLine[0]} y1={drawnLine[1]} x2={drawnLine[2]} y2={drawnLine[3]}
                stroke="#34D399" strokeWidth={2} vectorEffect="non-scaling-stroke" />
            )}

            {draft.length >= 4 && (
              <polyline points={pairs(draft).map(([x, y]) => `${x},${y}`).join(' ')}
                fill="none" stroke="#FFFFFF" strokeWidth={2} strokeDasharray="5 3" vectorEffect="non-scaling-stroke" />
            )}
            {draft.length >= 2 && hover && (
              <line x1={draft[draft.length - 2]} y1={draft[draft.length - 1]} x2={hover[0]} y2={hover[1]}
                stroke="#FFFFFF" strokeWidth={1} strokeDasharray="3 3" vectorEffect="non-scaling-stroke" opacity={0.7} />
            )}
            {lineDraft.length === 2 && hover && (
              <line x1={lineDraft[0]} y1={lineDraft[1]} x2={hover[0]} y2={hover[1]}
                stroke="#34D399" strokeWidth={1} strokeDasharray="3 3" vectorEffect="non-scaling-stroke" opacity={0.7} />
            )}
          </svg>

          {zones.map((zone, i) => {
            const pts = pairs(zone.points)
            if (!pts.length) return null
            const cx = pts.reduce((s, p) => s + p[0], 0) / pts.length
            const cy = pts.reduce((s, p) => s + p[1], 0) / pts.length
            return (
              <span key={zone.id} className="pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 rounded bg-black/70 px-1 py-0.5 text-[10px] font-medium text-white"
                style={{ left: `${cx * 100}%`, top: `${cy * 100}%` }}>
                Zone {i + 1}
              </span>
            )
          })}
          {lines.map((rule, i) => (
            <LineArrow key={`line-arrow-${i}`} line={rule.line} aspect={aspect} color="#FDE047" />
          ))}
          {lines.map((rule, i) => (
            <span key={`line-label-${i}`} className="pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 rounded bg-black/70 px-1 py-0.5 text-[10px] font-medium text-white"
              style={{ left: `${((rule.line[0] + rule.line[2]) / 2) * 100}%`, top: `${((rule.line[1] + rule.line[3]) / 2) * 100}%` }}>
              {rule.class} · {rule.direction}
            </span>
          ))}
          {drawnLine && (
            <>
              <LineArrow line={drawnLine} aspect={aspect} color="#34D399" />
              <span className="pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 rounded bg-black/70 px-1 py-0.5 text-[10px] font-medium text-emerald-300"
                style={{ left: `${((drawnLine[0] + drawnLine[2]) / 2) * 100}%`, top: `${((drawnLine[1] + drawnLine[3]) / 2) * 100}%` }}>
                new line
              </span>
            </>
          )}

          {pairs(draft).map(([x, y], i) => (
            <span key={`draft-${i}`} aria-hidden="true"
              className="pointer-events-none absolute h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-black bg-white"
              style={{ left: `${x * 100}%`, top: `${y * 100}%` }} />
          ))}
          {lineDraft.length === 2 && (
            <span aria-hidden="true" className="pointer-events-none absolute h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-black bg-emerald-300"
              style={{ left: `${lineDraft[0] * 100}%`, top: `${lineDraft[1] * 100}%` }} />
          )}

          {loaded && <span className="pointer-events-none absolute right-2 top-2 rounded bg-black/60 px-1.5 py-0.5 text-[10px] text-white/70">Paused frame</span>}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {mode === 'zones' ? (
            <>
              <Button variant="outline" size="sm" disabled={!draft.length} onClick={() => setDraft((d) => d.slice(0, -2))}>
                <Undo2 className="h-3.5 w-3.5" /> Undo
              </Button>
              <Button variant="outline" size="sm" disabled={draft.length < 6} onClick={finishPolygon}>
                <ScanLine className="h-3.5 w-3.5" /> Finish polygon
              </Button>
              <Button variant="ghost" size="sm" disabled={!draft.length} onClick={() => setDraft([])}>
                <X className="h-3.5 w-3.5" /> Cancel shape
              </Button>
              <span className="text-xs text-muted-foreground" aria-live="polite">
                {draft.length ? `${draft.length / 2} point${draft.length === 2 ? '' : 's'} placed` : 'No shape in progress'}
              </span>
            </>
          ) : (
            <>
              <Button variant="ghost" size="sm" disabled={!lineDraft.length} onClick={() => setLineDraft([])}>
                <X className="h-3.5 w-3.5" /> Cancel line
              </Button>
              <span className="text-xs text-muted-foreground" aria-live="polite">
                {drawnLine ? 'Line captured. Close this dialog to keep it with the rule.' : lineDraft.length ? 'Click the end point' : 'Click the start point'}
              </span>
            </>
          )}
        </div>

        <div>
          <h3 className="mb-1.5 text-sm font-semibold">Zones</h3>
          {!zones.length ? (
            <p className="rounded-md border border-dashed px-3 py-4 text-sm text-muted-foreground">
              No zones yet. Switch to Zones and click on the frame to start a polygon.
            </p>
          ) : (
            <ul className="space-y-1.5">
              {zones.map((zone, i) => {
                const usedBy = stream.rules.filter((r) => (r.kind === 'zone' || r.kind === 'dwell') && r.zone_id === zone.id).length
                return (
                  <li key={zone.id} className="flex min-w-0 items-center gap-2 rounded-md border px-2.5 py-2 text-sm">
                    <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: ZONE_COLORS[i % ZONE_COLORS.length] }} aria-hidden />
                    <span className="font-medium">Zone {i + 1}</span>
                    <span className="min-w-0 truncate text-xs text-muted-foreground">
                      {zone.id} · {zone.points.length / 2} points
                      {usedBy ? ` · used by ${usedBy} rule${usedBy === 1 ? '' : 's'}` : ''}
                    </span>
                    <Button variant="ghost" size="icon" className="ml-auto h-7 w-7 shrink-0 text-muted-foreground hover:text-destructive"
                      aria-label={`Delete zone ${i + 1}`} disabled={usedBy > 0}
                      title={usedBy ? `Used by ${usedBy} rule${usedBy === 1 ? '' : 's'} — remove the rule first.` : undefined}
                      onClick={() => setZones((z) => z.filter((x) => x.id !== zone.id))}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </li>
                )
              })}
            </ul>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-end gap-2">
          {busyShape && <span className="mr-auto text-xs text-muted-foreground">Finish or cancel the current shape before saving.</span>}
          <Button variant="ghost" onClick={onClose}>Close</Button>
          <Button disabled={saving || busyShape} onClick={save}>{saving ? 'Saving…' : 'Save zones'}</Button>
        </div>
      </div>
    </Modal>
  )
}
