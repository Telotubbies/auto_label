import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Circle, Group, Image as KImage, Layer, Line, Rect, Stage, Transformer } from 'react-konva'
import {
  ArrowDown, ArrowLeft, ArrowRight, ArrowUp, Ban, Bot, Check, ChevronLeft,
  ChevronRight, Eye, EyeOff, FileCode, Hand, History, Info, Keyboard,
  LoaderCircle, Lock, MessageSquare, Plus, Redo2, RotateCw, Send, SlidersHorizontal,
  Sparkles, SquareDashed, Spline, Tag, TriangleAlert, Undo2, Unlock, Waypoints,
  X, type LucideIcon,
} from 'lucide-react'
import { ApiError, api, fileUrl, get, patch, post, put } from '@/lib/api'
import { useApp } from '@/lib/store'
import type { Annotation, LabelClass, Shape, Skeleton } from '@/lib/types'
import { Badge, Button, Input, Select, StatusPill, Tabs, toast } from '@/components/ui'
import { Glass } from '@/components/glass'
import { cn } from '@/lib/utils'
import { AttributesPanel, CommentsPanel, HistoryPanel, RawDataPanel, SourceChip, type EditorComment, type LogEntry } from './Panels'
import { ShortcutModal } from './ShortcutModal'
import { classListQuery, classResultText, hotkeyClass, visibleClasses } from './classFilter'
import {
  keyLabel, loadShortcuts, resolveShortcut,
  type ShortcutId, type ShortcutMap,
} from './shortcuts'

const W = 1000                      // canvas width in stage units; height follows the image aspect
const SMART = '#7c3aed'             // canvas stroke only — CSS tokens cannot resolve inside Konva
const EPS_MIN = 0.0005              // matches segment.EPS_MIN / EPS_MAX in the API
const EPS_MAX = 0.02
const EPS_DEFAULT = 0.004
const SIMPLIFY_DEBOUNCE_MS = 220
const clamp01 = (v: number) => Math.min(1, Math.max(0, v))
// Canvas tool hints stay inside the stage at 375 px and wrap instead of squeezing into a column.
const HINT = 'pointer-events-none absolute left-1/2 top-3 max-w-[calc(100%-1rem)] -translate-x-1/2 rounded-full border bg-card px-3 py-1.5 text-center text-xs shadow'
const uid = () => 'a' + Math.random().toString(36).slice(2, 12)
const isAi = (a: Annotation) => !!a.source && a.source !== 'human'

/** Even-odd point-in-polygon test on a normalized flat [x0,y0,x1,y1,…] ring. */
function inPoly(x: number, y: number, pts: number[]) {
  let inside = false
  for (let i = 0, j = pts.length - 2; i < pts.length; j = i, i += 2) {
    const xi = pts[i], yi = pts[i + 1], xj = pts[j], yj = pts[j + 1]
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside
  }
  return inside
}

const fmtNum = (v: number) => String(Math.round(v * 100) / 100)
/** Locale-tolerant decimal parse; returns null instead of NaN so bad input is ignored. */
const parseNum = (text: string) => {
  const n = Number(text.trim().replace(',', '.'))
  return Number.isFinite(n) ? n : null
}
const wrapAngle = (a: number) => ((a + Math.PI) % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI) - Math.PI
/** Pixel-space corners, matching `imaging.obb_corners` in the API (clockwise at angle 0). */
function obbCorners(s: { cx: number; cy: number; w: number; h: number; angle: number }, H: number) {
  const cx = s.cx * W, cy = s.cy * H, hw = (s.w * W) / 2, hh = (s.h * H) / 2
  const c = Math.cos(s.angle), sn = Math.sin(s.angle)
  return [[-hw, -hh], [hw, -hh], [hw, hh], [-hw, hh]].flatMap(([dx, dy]) => [cx + dx * c - dy * sn, cy + dx * sn + dy * c])
}

interface ClassSuggestion {
  classId: string | null
  name: string | null
  candidates: { classId: string; name: string }[]
  checked: number
}

/** Numeric field that keeps the raw text while typing and commits clamped values on blur/Enter. */
function NumberField({ label, value, onCommit, min, max, step = 0.1 }: {
  label: string
  value: number
  onCommit: (v: number) => void
  min?: number
  max?: number
  step?: number
}) {
  const id = useId()
  const [text, setText] = useState(fmtNum(value))
  useEffect(() => setText(fmtNum(value)), [value])
  const commit = () => {
    const n = parseNum(text)
    if (n === null) { setText(fmtNum(value)); return }
    const bounded = Math.min(max ?? Infinity, Math.max(min ?? -Infinity, n))
    setText(fmtNum(bounded))
    onCommit(bounded)
  }
  return (
    <label htmlFor={id} className="flex min-w-0 flex-col gap-0.5 text-[10px] text-muted-foreground">
      <span className="truncate">{label}</span>
      <input id={id} type="text" inputMode="decimal" step={step} value={text}
        onChange={(e) => setText(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') { e.currentTarget.blur() }
          if (e.key === 'Escape') { setText(fmtNum(value)); e.currentTarget.blur() }
        }}
        className="h-7 w-full rounded-md border border-input bg-card px-1.5 text-xs tabular-nums text-foreground outline-none focus:border-ring" />
    </label>
  )
}

/** Geometry editor for one annotation: boxes, rotated boxes and keypoints. */
function GeometryPanel({ shape, skeleton, activeJoint, onActiveJoint, onShape }: {
  shape: Shape
  skeleton: Skeleton | null
  activeJoint: number
  onActiveJoint: (i: number) => void
  onShape: (shape: Shape) => void
}) {
  if (shape.kind === 'bbox') {
    const s = shape
    return (
      <section aria-label="Bounding box geometry" className="mt-2 rounded-lg border bg-card p-2">
        <h3 className="pb-1.5 text-[11px] font-semibold">Geometry (%)</h3>
        <div className="grid grid-cols-2 gap-1.5">
          <NumberField label="X" value={s.x * 100} min={0} max={100} onCommit={(v) => onShape({ ...s, x: clamp01(v / 100) })} />
          <NumberField label="Y" value={s.y * 100} min={0} max={100} onCommit={(v) => onShape({ ...s, y: clamp01(v / 100) })} />
          <NumberField label="Width" value={s.w * 100} min={0.1} max={100} onCommit={(v) => onShape({ ...s, w: Math.max(0.001, v / 100) })} />
          <NumberField label="Height" value={s.h * 100} min={0.1} max={100} onCommit={(v) => onShape({ ...s, h: Math.max(0.001, v / 100) })} />
        </div>
      </section>
    )
  }
  if (shape.kind === 'obb') {
    const s = shape
    return (
      <section aria-label="Rotated box geometry" className="mt-2 rounded-lg border bg-card p-2">
        <h3 className="pb-1.5 text-[11px] font-semibold">Rotated box (%)</h3>
        <div className="grid grid-cols-2 gap-1.5">
          <NumberField label="Centre X" value={s.cx * 100} min={0} max={100} onCommit={(v) => onShape({ ...s, cx: clamp01(v / 100) })} />
          <NumberField label="Centre Y" value={s.cy * 100} min={0} max={100} onCommit={(v) => onShape({ ...s, cy: clamp01(v / 100) })} />
          <NumberField label="Width" value={s.w * 100} min={0.1} max={100} onCommit={(v) => onShape({ ...s, w: Math.max(0.001, v / 100) })} />
          <NumberField label="Height" value={s.h * 100} min={0.1} max={100} onCommit={(v) => onShape({ ...s, h: Math.max(0.001, v / 100) })} />
          <NumberField label="Angle (°)" value={(s.angle * 180) / Math.PI} min={-180} max={180} step={1}
            onCommit={(v) => onShape({ ...s, angle: wrapAngle((v * Math.PI) / 180) })} />
        </div>
        <div className="mt-1.5 grid grid-cols-2 gap-1.5">
          <Button size="sm" variant="outline" className="h-7 min-h-6 text-[11px]" aria-label="Rotate −15 degrees"
            onClick={() => onShape({ ...s, angle: wrapAngle(s.angle - Math.PI / 12) })}>Rotate −15°</Button>
          <Button size="sm" variant="outline" className="h-7 min-h-6 text-[11px]" aria-label="Rotate +15 degrees"
            onClick={() => onShape({ ...s, angle: wrapAngle(s.angle + Math.PI / 12) })}>Rotate +15°</Button>
        </div>
      </section>
    )
  }
  if (shape.kind === 'keypoints') {
    const names = skeleton?.names ?? []
    const count = Math.max(names.length, Math.floor(shape.points.length / 3))
    const active = count ? Math.min(activeJoint, count - 1) : 0
    const triples = (): number[] => {
      const pts = shape.points.slice()
      while (pts.length < count * 3) pts.push(0.5, 0.5, 0)
      return pts
    }
    const setJoint = (i: number, x: number, y: number, v: number) => {
      const pts = triples()
      pts[i * 3] = clamp01(x); pts[i * 3 + 1] = clamp01(y); pts[i * 3 + 2] = v
      onShape({ kind: 'keypoints', points: pts })
    }
    const nudge = (dx: number, dy: number) => {
      const pts = triples()
      setJoint(active, (pts[active * 3] ?? 0.5) + dx, (pts[active * 3 + 1] ?? 0.5) + dy, pts[active * 3 + 2] || 2)
    }
    const allPts = triples()
    return (
      <section aria-label="Keypoint editor" className="mt-2 rounded-lg border bg-card p-2">
        <div className="flex items-baseline justify-between pb-1.5">
          <h3 className="text-[11px] font-semibold">Keypoints</h3>
          <span className="text-[10px] text-muted-foreground">{allPts.filter((_, i) => i % 3 === 2 && allPts[i] > 0).length}/{count || '—'} placed</span>
        </div>
        {count > 0 ? (
          <div role="group" aria-label="Joints" className="grid max-h-40 grid-cols-2 gap-1 overflow-y-auto">
            {Array.from({ length: count }, (_, i) => {
              const v = allPts[i * 3 + 2] ?? 0
              const state = v === 2 ? 'visible' : v === 1 ? 'occluded' : 'absent'
              return (
                <button key={i} type="button" aria-pressed={active === i} aria-label={`${names[i] ?? `Joint ${i + 1}`} (${state})`}
                  title={names[i] ?? `Joint ${i + 1}`} onClick={() => onActiveJoint(i)}
                  className={cn('flex min-h-6 min-w-0 cursor-pointer items-center gap-1 rounded border px-1.5 py-1 text-left text-[10px]',
                    active === i ? 'border-primary bg-accent font-medium text-accent-foreground' : 'border-transparent text-muted-foreground hover:bg-muted hover:text-foreground')}>
                  <span aria-hidden className={cn('h-1.5 w-1.5 shrink-0 rounded-full', v > 0 ? 'bg-current' : 'border border-current')} />
                  <span className="min-w-0 truncate">{names[i] ?? `Joint ${i + 1}`}</span>
                  <span aria-hidden className="ml-auto shrink-0 opacity-70">{v === 2 ? '●' : v === 1 ? '◐' : '○'}</span>
                </button>
              )
            })}
          </div>
        ) : (
          <p className="text-[10px] leading-relaxed text-muted-foreground">This class has no skeleton. Add joint names to the class, then start a keypoint annotation.</p>
        )}
        <div className="mt-1.5 grid grid-cols-2 gap-1.5">
          <Button size="sm" variant="outline" className="h-7 min-h-6 text-[11px]" disabled={!count} onClick={() => setJoint(active, 0.5, 0.5, 2)}>Set at centre</Button>
          <Button size="sm" variant="outline" className="h-7 min-h-6 text-[11px]" disabled={!count}
            onClick={() => onShape({ kind: 'keypoints', points: Array.from({ length: count }, () => [0.5, 0.5, 0]).flat() })}>Clear keypoints</Button>
        </div>
        <div className="mt-1.5 grid grid-cols-3 gap-1" role="group" aria-label="Nudge active joint">
          <span aria-hidden />
          <Button size="sm" variant="outline" className="h-7 min-h-6 p-0" aria-label="Nudge up" disabled={!count} onClick={() => nudge(0, -0.01)}><ArrowUp className="h-3.5 w-3.5" /></Button>
          <span aria-hidden />
          <Button size="sm" variant="outline" className="h-7 min-h-6 p-0" aria-label="Nudge left" disabled={!count} onClick={() => nudge(-0.01, 0)}><ArrowLeft className="h-3.5 w-3.5" /></Button>
          <Button size="sm" variant="outline" className="h-7 min-h-6 p-0" aria-label="Nudge down" disabled={!count} onClick={() => nudge(0, 0.01)}><ArrowDown className="h-3.5 w-3.5" /></Button>
          <Button size="sm" variant="outline" className="h-7 min-h-6 p-0" aria-label="Nudge right" disabled={!count} onClick={() => nudge(0.01, 0)}><ArrowRight className="h-3.5 w-3.5" /></Button>
        </div>
      </section>
    )
  }
  return null
}

function useHtmlImage(src: string) {
  const [img, setImg] = useState<HTMLImageElement | null>(null)
  useEffect(() => {
    if (!src) return
    setImg(null)
    const i = new window.Image()
    i.crossOrigin = 'anonymous'
    i.onload = () => setImg(i)
    i.src = src
  }, [src])
  return img
}

export default function Editor() {
  const { ws = '', project = '', imageId = '' } = useParams()
  const nav = useNavigate()
  const qc = useQueryClient()
  const [sp] = useSearchParams()
  const can = useApp((s) => s.can)
  const reviewMode = sp.get('review') === 'true'
  const listQuery = useMemo(() => ({
    status: sp.get('status') ?? '', batch_id: sp.get('batch') ?? '', split: sp.get('split') ?? '', class_id: sp.get('class_id') ?? '',
    tag: sp.get('tag') ?? '', q: sp.get('q') ?? '', annotated: sp.get('annotated') ?? '', sort: sp.get('sort') ?? 'newest', limit: 1000,
  }), [sp])

  const proj = useQuery({ queryKey: ['project', ws, project], queryFn: () => api.project(ws, project) })
  const classesQ = useQuery({ queryKey: ['classes', ws, project], queryFn: () => api.classes(ws, project) })
  const list = useQuery({ queryKey: ['images', ws, project, listQuery], queryFn: () => api.images(ws, project, listQuery) })
  const imgQ = useQuery({ queryKey: ['image', imageId], queryFn: () => api.image(imageId) })
  const models = useQuery({ queryKey: ['models', ws, project], queryFn: () => api.models(ws, project), enabled: can('annotator') })
  const commentsQ = useQuery({ queryKey: ['comments', imageId], queryFn: () => get<EditorComment[]>(`/images/${imageId}/comments`) })
  const img = imgQ.data
  const classes: LabelClass[] = classesQ.data ?? []
  const projectType = proj.data?.type
  const isCls = projectType === 'classification'
  const isKp = projectType === 'keypoint-detection'
  const obbEnabled = projectType === 'object-detection' || projectType === 'instance-segmentation'
  const H = img ? Math.round((W * img.height) / img.width) : 600
  const htmlImg = useHtmlImage(fileUrl(img?.url))
  const items = list.data?.items ?? []
  const idx = items.findIndex((i) => i.id === imageId)
  const go = (d: number) => {
    const t = items[idx + d]
    if (t) nav(`/${ws}/${project}/images/${t.id}?${sp}`)
  }

  const [tool, setTool] = useState<string>('bbox')
  const wrapRef = useRef<HTMLDivElement>(null)
  const [zoom, setZoom] = useState(0.5)
  const fit = useCallback(() => {
    const el = wrapRef.current
    if (el) setZoom(Math.min(el.clientWidth / W, el.clientHeight / H) * 0.92)
  }, [H])
  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const ro = new ResizeObserver(fit); ro.observe(el)
    return () => ro.disconnect()
  }, [fit])
  useEffect(() => {
    if (isCls) setTool('pan')
    else if (isKp) setTool('keypoints')
  }, [isCls, isKp])

  const [anns, setAnns] = useState<Annotation[]>([])
  const [loadedFor, setLoadedFor] = useState('')
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [selId, setSelId] = useState<string | null>(null)
  const [selClass, setSelClass] = useState('')
  const [activeJoint, setActiveJoint] = useState(0)
  const [drawing, setDrawing] = useState<{ x: number; y: number; w: number; h: number } | null>(null)
  const [boxAnchor, setBoxAnchor] = useState<{ x: number; y: number } | null>(null)
  const [polyPts, setPolyPts] = useState<number[]>([])
  const [smartPts, setSmartPts] = useState<number[]>([])
  const [smartNeg, setSmartNeg] = useState<number[]>([])
  const [smartPoly, setSmartPoly] = useState<number[] | null>(null)
  const [smartFresh, setSmartFresh] = useState(false)
  const [smartSource, setSmartSource] = useState('')
  const [smartBusy, setSmartBusy] = useState(false)
  const [smartErr, setSmartErr] = useState('')
  const [epsilon, setEpsilon] = useState(EPS_DEFAULT)
  const [classQuery, setClassQuery] = useState('')
  const [shortcutKeys, setShortcutKeys] = useState<ShortcutMap>(
    () => loadShortcuts(typeof window === 'undefined' ? null : window.localStorage),
  )
  const [hidden, setHidden] = useState<Set<string>>(new Set())
  const [locked, setLocked] = useState<Set<string>>(new Set())
  const [displayOpen, setDisplayOpen] = useState(false)
  const [brightness, setBrightness] = useState(100)
  const [contrast, setContrast] = useState(100)
  const [suggestion, setSuggestion] = useState<ClassSuggestion | null>(null)
  const [suggestBusy, setSuggestBusy] = useState(false)
  const [suggestErr, setSuggestErr] = useState('')
  const [assistBusy, setAssistBusy] = useState(false)
  const [tab, setTab] = useState('classes')
  const [rail, setRail] = useState('labels')
  const [history, setHistory] = useState<Annotation[][]>([])
  const [future, setFuture] = useState<Annotation[][]>([])
  const [log, setLog] = useState<LogEntry[]>([])
  const [shortcuts, setShortcuts] = useState(false)
  // Below md the annotation side panels become a drawer so the canvas keeps the full width.
  const [panelsOpen, setPanelsOpen] = useState(() => typeof window === 'undefined' || window.innerWidth >= 768)
  const [newClass, setNewClass] = useState('')
  const [tagInput, setTagInput] = useState('')
  const classCountId = useId()
  const stageRef = useRef<any>(null)
  const trRef = useRef<any>(null)
  const smartReq = useRef(0)
  const suggestReq = useRef(0)
  const classSearchRef = useRef<HTMLInputElement>(null)
  const simplifyTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastGoodEps = useRef(EPS_DEFAULT)
  const resetSmart = useCallback(() => {
    smartReq.current++
    if (simplifyTimer.current) { clearTimeout(simplifyTimer.current); simplifyTimer.current = null }
    setSmartPts([]); setSmartNeg([]); setSmartPoly(null); setSmartSource(''); setSmartFresh(false)
    setSmartErr(''); setSmartBusy(false); setEpsilon(EPS_DEFAULT)
    lastGoodEps.current = EPS_DEFAULT
  }, [])
  useEffect(() => () => { if (simplifyTimer.current) clearTimeout(simplifyTimer.current) }, [])
  useEffect(() => { setBoxAnchor(null); setDrawing(null); if (tool !== 'smart') resetSmart() }, [tool, resetSmart])

  // load annotations when the image changes
  useEffect(() => {
    if (img && loadedFor !== img.id) {
      setAnns(img.annotations ?? []); setLoadedFor(img.id); setDirty(false)
      setHistory([]); setFuture([]); setSelId(null); setPolyPts([]); setBoxAnchor(null)
      resetSmart()
      setHidden(new Set()); setLocked(new Set())
      suggestReq.current++; setSuggestion(null); setSuggestBusy(false); setSuggestErr('')
    }
  }, [img, loadedFor, resetSmart])
  useEffect(() => { if (!selClass && classes[0]) setSelClass(classes[0].id) }, [classes, selClass])

  const save = useCallback(async (next = anns) => {
    if (!img) return
    setSaving(true)
    try {
      await put(`/images/${img.id}/annotations`, { annotations: next })
      setDirty(false)
      qc.invalidateQueries({ queryKey: ['images', ws, project] })
    } catch (e) { toast.err(e as Error) } finally { setSaving(false) }
  }, [anns, img, qc, ws, project])
  // autosave shortly after the last edit
  useEffect(() => {
    if (!dirty) return
    const t = setTimeout(() => save(), 700)
    return () => clearTimeout(t)
  }, [dirty, anns, save])

  const sel = anns.find((a) => a.id === selId) ?? null
  const selCls = classes.find((c) => c.id === selClass) ?? null
  const skelOf = (classId: string) => classes.find((c) => c.id === classId)?.skeleton ?? null
  const keypointsEnabled = isKp || !!selCls?.skeleton
  const transformable = !!sel && sel.shape.kind === 'bbox' && !locked.has(sel.id)
  useEffect(() => {
    if (trRef.current && selId && transformable) {
      const node = stageRef.current?.findOne('#' + selId)
      if (node) trRef.current.nodes([node])
    } else trRef.current?.nodes([])
  }, [selId, sel, transformable])
  useEffect(() => { suggestReq.current++; setSuggestion(null); setSuggestErr(''); setSuggestBusy(false) }, [selId])

  const cls = (id: string) => classes.find((c) => c.id === id) ?? { id, name: '?', color: '#999', count: 0 }
  const record = (action: string, detail?: string) => setLog((l) => [...l.slice(-60), { id: `${Date.now()}-${l.length}`, action, detail, at: Date.now() }])
  const push = (next: Annotation[], action = 'Edit annotations', detail?: string) => {
    setHistory((h) => [...h.slice(-50), anns]); setFuture([]); setAnns(next); setDirty(true); record(action, detail)
  }
  const undo = () => { if (!history.length) return; setFuture((f) => [anns, ...f]); setAnns(history[history.length - 1]); setHistory((h) => h.slice(0, -1)); setDirty(true); record('Undo') }
  const redo = () => { if (!future.length) return; setHistory((h) => [...h, anns]); setAnns(future[0]); setFuture((f) => f.slice(1)); setDirty(true); record('Redo') }
  const addShape = (shape: Shape, action: string, classId = selClass) => {
    if (!classId) { toast.err('Create a class first'); return }
    push([...anns, { id: uid(), classId, shape, source: 'human' }], action, cls(classId).name)
  }
  const pointer = () => {
    const st = stageRef.current
    const p = st.getPointerPosition()
    const t = st.getAbsoluteTransform().copy().invert()
    return t.point(p)
  }

  const smartPairs = (pts: number[]) => {
    const out: number[][] = []
    for (let i = 0; i < pts.length; i += 2) out.push([clamp01(pts[i] / W), clamp01(pts[i + 1] / H)])
    return out
  }
  const runSmart = (pts: number[], neg: number[], eps = epsilon) => {
    const req = ++smartReq.current
    setSmartBusy(true); setSmartErr(''); setSmartFresh(false)
    post<{ polygon: number[]; source: string; epsilon: number }>(`/images/${imageId}/smart-polygon`, { points: smartPairs(pts), negatives: smartPairs(neg), epsilon: eps })
      .then((r) => {
        if (req !== smartReq.current) return
        setSmartPoly(r.polygon); setSmartSource(r.source); setSmartFresh(true)
        setEpsilon(r.epsilon); lastGoodEps.current = r.epsilon
      })
      .catch((e) => { if (req === smartReq.current) setSmartErr((e as Error).message) })
      .finally(() => { if (req === smartReq.current) setSmartBusy(false) })
  }
  /** Slider moves re-simplify the same clicks: debounced, and the API reuses its cached mask (no SAM). */
  const simplify = (next: number) => {
    setEpsilon(next)
    if (simplifyTimer.current) clearTimeout(simplifyTimer.current)
    simplifyTimer.current = setTimeout(() => {
      simplifyTimer.current = null
      if (!smartPts.length) return
      const req = ++smartReq.current
      setSmartBusy(true); setSmartErr('')
      post<{ polygon: number[]; source: string; epsilon: number }>(`/images/${imageId}/smart-polygon`,
        { points: smartPairs(smartPts), negatives: smartPairs(smartNeg), epsilon: next })
        .then((r) => {
          if (req !== smartReq.current) return
          setSmartPoly(r.polygon); setSmartSource(r.source); setSmartFresh(true)
          setEpsilon(r.epsilon); lastGoodEps.current = r.epsilon
        })
        .catch((e) => {
          if (req !== smartReq.current) return
          setSmartErr(`Could not simplify that far — ${(e as Error).message}`)
          setEpsilon(lastGoodEps.current)     // keep the shape that is on screen valid
        })
        .finally(() => { if (req === smartReq.current) setSmartBusy(false) })
    }, SIMPLIFY_DEBOUNCE_MS)
  }
  const addSmartPoint = (x: number, y: number, forceNegative: boolean) => {
    if (smartBusy) return              // a prompt is in flight; the preview is not current yet
    const negative = forceNegative || (!!smartPoly && inPoly(x / W, y / H, smartPoly))
    if (negative) {
      if (!smartPts.length) { setSmartErr('Click the object first'); return }
      const neg = [...smartNeg, x, y]
      setSmartNeg(neg); setSmartErr(''); runSmart(smartPts, neg)
    } else {
      const pts = [...smartPts, x, y]
      setSmartPts(pts); setSmartErr(''); runSmart(pts, smartNeg)
    }
  }
  const removeSmartPoint = (negative: boolean, i: number) => {
    const pos = smartPts.slice(), neg = smartNeg.slice()
    if (negative) neg.splice(i, 2); else pos.splice(i, 2)
    setSmartPts(pos); setSmartNeg(neg)
    if (!pos.length) { resetSmart(); return }
    runSmart(pos, neg)
  }
  const commitSmart = () => {
    if (!smartPoly || smartPoly.length < 6 || !smartPts.length || !smartFresh) return
    const shape: Shape = proj.data?.type === 'object-detection'
      ? (() => {
          const xs = smartPoly.filter((_, i) => i % 2 === 0), ys = smartPoly.filter((_, i) => i % 2)
          return { kind: 'bbox', x: Math.min(...xs), y: Math.min(...ys), w: Math.max(...xs) - Math.min(...xs), h: Math.max(...ys) - Math.min(...ys) } as Shape
        })()
      : { kind: 'polygon', points: smartPoly }
    addShape(shape, `Smart polygon (${smartSource || 'sam3'})`)
    resetSmart()
  }
  const lockedMsg = () => toast.err('This annotation is locked — unlock it in Objects first')
  /** Finalize a box from two stage-space corners, clamped to the image and ignoring slivers. */
  const finishBox = (x1: number, y1: number, x2: number, y2: number, kind: 'bbox' | 'obb' = 'bbox') => {
    const nx = clamp01(Math.min(x1, x2) / W), ny = clamp01(Math.min(y1, y2) / H)
    const nx2 = clamp01(Math.max(x1, x2) / W), ny2 = clamp01(Math.max(y1, y2) / H)
    if (nx2 - nx < 0.005 || ny2 - ny < 0.005) return
    if (kind === 'obb') {
      addShape({ kind: 'obb', cx: nx + (nx2 - nx) / 2, cy: ny + (ny2 - ny) / 2, w: nx2 - nx, h: ny2 - ny, angle: 0 }, 'Add rotated box')
      return
    }
    addShape({ kind: 'bbox', x: nx, y: ny, w: nx2 - nx, h: ny2 - ny }, 'Add bounding box')
  }
  /** The annotation the keypoint tool edits: the selection, else the newest one for the active class. */
  const keypointTarget = () => {
    if (sel && sel.shape.kind === 'keypoints') return sel
    return [...anns].reverse().find((a) => a.shape.kind === 'keypoints' && a.classId === selClass) ?? null
  }
  /** Place the next missing joint in skeleton order at a stage point. */
  const addKeypoint = (x: number, y: number) => {
    const target = keypointTarget()
    if (!target || target.shape.kind !== 'keypoints') { toast.err('Start a keypoint annotation first — use the Objects panel'); return }
    if (locked.has(target.id)) return lockedMsg()
    const names = skelOf(target.classId)?.names ?? []
    const count = names.length || Math.floor(target.shape.points.length / 3)
    if (!count) { toast.err('This class has no skeleton'); return }
    const pts = target.shape.points.slice()
    while (pts.length < count * 3) pts.push(0.5, 0.5, 0)
    let next = -1
    for (let i = 0; i < count; i++) if ((pts[i * 3 + 2] ?? 0) === 0) { next = i; break }
    if (next < 0) { toast.ok('All joints placed — nudge them in Objects'); return }
    pts[next * 3] = clamp01(x / W); pts[next * 3 + 1] = clamp01(y / H); pts[next * 3 + 2] = 2
    editShape(target.id, { kind: 'keypoints', points: pts })
    if (!sel || sel.id !== target.id) setSelId(target.id)
    for (let i = next + 1; i < count; i++) if ((pts[i * 3 + 2] ?? 0) === 0) { setActiveJoint(i); return }
    setActiveJoint(next)
  }
  const onDown = (e: any) => {
    const name = e?.target?.name?.()
    if (name === 'smart-pt' || name === 'smart-neg') return
    if (tool === 'pan' || isCls) return
    const p = pointer()
    if (tool === 'bbox' || tool === 'obb') {
      // Two-click drawing: the first press anchors, the next press (or a real drag) completes.
      if (boxAnchor) { finishBox(boxAnchor.x, boxAnchor.y, p.x, p.y, tool); setBoxAnchor(null); setDrawing(null) }
      else { setSelId(null); setBoxAnchor({ x: p.x, y: p.y }); setDrawing({ x: p.x, y: p.y, w: 0, h: 0 }) }
      return
    }
    if (tool === 'keypoints') { addKeypoint(p.x, p.y); return }
    setSelId(null)
    if (tool === 'polygon') setPolyPts((pts) => [...pts, p.x, p.y])
    else if (tool === 'smart') addSmartPoint(p.x, p.y, !!e.evt?.altKey || e.evt?.button === 2)
  }
  const onMove = () => {
    if (drawing && boxAnchor) { const p = pointer(); setDrawing({ x: boxAnchor.x, y: boxAnchor.y, w: p.x - boxAnchor.x, h: p.y - boxAnchor.y }) }
  }
  const onUp = () => {
    if (drawing && boxAnchor && Math.abs(drawing.w) > 4 && Math.abs(drawing.h) > 4) {
      finishBox(boxAnchor.x, boxAnchor.y, boxAnchor.x + drawing.w, boxAnchor.y + drawing.h, tool === 'obb' ? 'obb' : 'bbox')
      setBoxAnchor(null); setDrawing(null)
    }
  }
  const closePoly = () => {
    if (polyPts.length >= 6) addShape({ kind: 'polygon', points: polyPts.map((v, i) => v / (i % 2 ? H : W)) }, 'Add polygon')
    setPolyPts([])
  }
  const remove = (id: string) => {
    if (locked.has(id)) return lockedMsg()
    push(anns.filter((a) => a.id !== id), 'Delete annotation')
    if (selId === id) setSelId(null)
  }
  const editShape = (id: string, shape: Shape) => {
    if (locked.has(id)) return lockedMsg()
    // A hand edit to a tracked box becomes a keyframe: interpolation/tracking never overwrites it.
    push(anns.map((a) => (a.id === id ? { ...a, shape, source: 'human', ...(a.trackId ? { keyframe: true } : {}) } : a)),
      'Edit annotation')
  }
  /** Click-only alternative to two-click drawing (WCAG 2.5.7). */
  const addCentredBox = () => {
    if (tool === 'obb' || sel?.shape.kind === 'obb') {
      addShape({ kind: 'obb', cx: 0.5, cy: 0.5, w: 0.3, h: 0.3, angle: 0 }, 'Add centred rotated box')
    } else {
      addShape({ kind: 'bbox', x: 0.35, y: 0.35, w: 0.3, h: 0.3 }, 'Add centred box')
    }
  }
  /** Create the empty keypoint annotation for the active class's skeleton. */
  const startKeypoints = () => {
    if (!selClass) { toast.err('Pick a class first'); return }
    const skeleton = skelOf(selClass)
    if (!skeleton?.names.length) { toast.err('This class has no skeleton'); return }
    const ann: Annotation = {
      id: uid(), classId: selClass, source: 'human',
      shape: { kind: 'keypoints', points: skeleton.names.flatMap(() => [0.5, 0.5, 0]) },
    }
    push([...anns, ann], 'Start keypoints', cls(selClass).name)
    setSelId(ann.id); setActiveJoint(0)
  }
  const relabel = (id: string, classId: string) => {
    if (locked.has(id)) return lockedMsg()
    push(anns.map((a) => (a.id === id ? { ...a, classId, source: 'human' } : a)), 'Change class', cls(classId).name)
  }
  const toggleHidden = (id: string) => {
    const hiding = !hidden.has(id)
    setHidden((prev) => { const next = new Set(prev); if (hiding) next.add(id); else next.delete(id); return next })
    if (hiding && selId === id) setSelId(null)
  }
  const toggleLocked = (id: string) => {
    setLocked((prev) => { const next = new Set(prev); if (next.has(id)) next.delete(id); else next.add(id); return next })
  }
  const toggleAttribute = (id: string, key: string) => {
    if (locked.has(id)) return lockedMsg()
    push(anns.map((a) => (a.id === id ? { ...a, attributes: { ...(a.attributes ?? {}), [key]: !a.attributes?.[key] }, source: 'human' } : a)), 'Edit attributes', key)
  }
  const suggestClass = async () => {
    if (!sel || isCls) return
    const req = ++suggestReq.current
    setSuggestBusy(true); setSuggestErr(''); setSuggestion(null)
    try {
      const r = await post<ClassSuggestion>(`/images/${imageId}/suggest-class`, { annotation_id: sel.id })
      if (req === suggestReq.current) setSuggestion(r)
    } catch (e) {
      if (req === suggestReq.current) {
        setSuggestErr(e instanceof ApiError && e.status === 503 ? 'Model unavailable — start the VLM or try again later.' : (e as Error).message)
      }
    } finally { if (req === suggestReq.current) setSuggestBusy(false) }
  }
  const applySuggestion = (classId: string, name: string) => {
    if (!sel) return
    relabel(sel.id, classId)
    record('VLM class suggestion', name)
    setSuggestion(null)
  }
  const toggleClassLabel = (classId: string) => {
    if (anns.some((a) => a.classId === classId && locked.has(a.id))) return lockedMsg()
    const has = anns.some((a) => a.classId === classId)
    if (has) push(anns.filter((a) => a.classId !== classId), 'Remove label', cls(classId).name)
    else push([...(proj.data?.multilabel ? anns : []), { id: uid(), classId, shape: { kind: 'class' }, source: 'human' }], 'Set label', cls(classId).name)
  }

  const createClass = async () => {
    const name = newClass.trim()
    if (!name) return
    try {
      const c = await post<LabelClass>(`${api.P(ws, project)}/classes`, { name })
      setNewClass(''); setSelClass(c.id); qc.invalidateQueries({ queryKey: ['classes', ws, project] })
    } catch (e) { toast.err(e as Error) }
  }
  const setTags = async (tags: string[]) => {
    try { await patch(`/images/${imageId}`, { tags }); qc.invalidateQueries({ queryKey: ['image', imageId] }) } catch (e) { toast.err(e as Error) }
  }
  const review = async (approved: boolean) => {
    if (dirty) await save()
    try {
      await post(`/images/${imageId}/review`, { approved })
      record(approved ? 'Approved' : 'Rejected'); qc.invalidateQueries({ queryKey: ['image', imageId] }); qc.invalidateQueries({ queryKey: ['board', ws, project] })
      toast.ok(approved ? 'Approved — added to dataset' : 'Rejected — sent back to annotating')
      go(1)
    } catch (e) { toast.err(e as Error) }
  }
  const submitForReview = async () => {
    if (dirty) await save()
    try { await patch(`/images/${imageId}`, { status: 'review' }); qc.invalidateQueries({ queryKey: ['image', imageId] }); toast.ok('Sent to review'); go(1) } catch (e) { toast.err(e as Error) }
  }
  // Autosave keeps the draft private; only this sends it to the consensus job.
  const submitConsensusDraft = async () => {
    if (!img?.consensusJob) return
    setSubmitting(true)
    try {
      await api.submitConsensus(ws, project, img.consensusJob, imageId, anns)
      toast.ok('Consensus draft submitted')
      qc.invalidateQueries({ queryKey: ['labeling-tasks', ws, project] })
      qc.invalidateQueries({ queryKey: ['labeling-dashboard', ws, project] })
      qc.invalidateQueries({ queryKey: ['labeling-jobs', ws, project] })
      qc.invalidateQueries({ queryKey: ['labeling-job', ws, project] })
      qc.invalidateQueries({ queryKey: ['image', imageId] })
    } catch (e) { toast.err(e as Error) } finally { setSubmitting(false) }
  }
  const labelAssist = async (modelId: string) => {
    setAssistBusy(true)
    try {
      const r = await post<{ annotations: Annotation[] }>(`/images/${imageId}/label-assist`, { model_id: modelId, confidence: 0.35 })
      qc.invalidateQueries({ queryKey: ['classes', ws, project] })
      if (!r.annotations.length) toast.ok('Model found nothing on this image')
      else push(isCls ? r.annotations : [...anns, ...r.annotations], 'Label Assist', `${r.annotations.length} predictions`)
    } catch (e) { toast.err(e as Error) } finally { setAssistBusy(false) }
  }
  const addComment = async (text: string) => {
    try { await post(`/images/${imageId}/comments`, { text }); qc.invalidateQueries({ queryKey: ['comments', imageId] }) } catch (e) { toast.err(e as Error) }
  }

  const classListVisible = tab === 'classes' && panelsOpen
  const classSearch = classListQuery(classQuery, classListVisible)
  const classHotkeys = useMemo(() => visibleClasses(classes, classSearch), [classes, classSearch])
  const focusClassSearch = () => {
    setRail('labels'); setTab('classes'); setPanelsOpen(true)
    requestAnimationFrame(() => classSearchRef.current?.focus())
  }

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement) return
      if (e.key === '/' && !e.ctrlKey && !e.metaKey && !e.altKey) { e.preventDefault(); focusClassSearch(); return }
      if (e.key === 'ArrowRight') go(1)
      if (e.key === 'ArrowLeft') go(-1)
      if (e.key === 'Escape') { setPolyPts([]); setBoxAnchor(null); setDrawing(null); resetSmart(); setSelId(null); setDisplayOpen(false) }
      if (e.key === 'Enter') {
        if (smartPts.length && smartPoly && smartFresh && !smartBusy) commitSmart()
        else if (polyPts.length) closePoly()
      }
      if (e.key === '?') setShortcuts((o) => !o)
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); e.shiftKey ? redo() : undo() }
      const action = resolveShortcut(e, shortcutKeys)
      if (action === 'save') { e.preventDefault(); save(); return }
      if (action === 'delete') { if (selId) remove(selId); return }
      // Backspace keeps deleting while the action still has its default key.
      if (e.key === 'Backspace' && selId && shortcutKeys.delete === 'delete') { remove(selId); return }
      if (action) {
        const available = action === 'polygon' ? projectType === 'instance-segmentation'
          : action === 'obb' ? obbEnabled
          : action === 'keypoints' ? keypointsEnabled
          : true
        if (available && !isCls) setTool(action)
      }
      // 1–9 follow the rows the class search shows, so a filtered list stays predictable.
      const target = hotkeyClass(classHotkeys, e.key)
      if (target && !e.ctrlKey && !e.metaKey && !e.altKey) {
        if (isCls) toggleClassLabel(target.id)
        else if (selId) relabel(selId, target.id)
        else setSelClass(target.id)
      }
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  })

  // Toolbar titles show the assigned key, so a remap stays discoverable.
  const keyHint = (id: ShortcutId) => keyLabel(shortcutKeys[id]).replace(/ \+ /g, '+')

  const tools: { id: string; icon: LucideIcon; label: string }[] = isCls
    ? [{ id: 'pan', icon: Hand, label: `Pan (${keyHint('pan')})` }]
    : [
      { id: 'pan', icon: Hand, label: `Pan (${keyHint('pan')})` },
      { id: 'bbox', icon: SquareDashed, label: `Bounding Box (${keyHint('bbox')})` },
      ...(projectType === 'instance-segmentation' ? [{ id: 'polygon', icon: Spline, label: `Polygon (${keyHint('polygon')})` }] : []),
      ...(obbEnabled ? [{ id: 'obb', icon: RotateCw, label: `Rotated Box (${keyHint('obb')})` }] : []),
      ...(keypointsEnabled ? [{ id: 'keypoints', icon: Waypoints, label: `Keypoints (${keyHint('keypoints')})` }] : []),
      { id: 'smart', icon: Sparkles, label: `Smart Polygon (${keyHint('smart')}) — click an object` },
    ]
  const ready = (models.data ?? []).filter((m) => m.status === 'ready')
  const used = new Set(anns.map((a) => a.classId))

  if (imgQ.isError) return <div className="p-10 text-sm text-muted-foreground">Can't open this image: {(imgQ.error as Error).message} <Link className="text-primary" to={`/${ws}/${project}/browse`}>Back</Link></div>

  return (
    <main className="flex h-screen flex-col bg-background text-foreground">
      <div className="flex items-center gap-2 border-b px-3 py-2">
        <Link to={reviewMode || sp.get('status') ? `/${ws}/${project}/annotate` : `/${ws}/${project}/browse`} className="rounded p-1.5 hover:bg-accent" aria-label="Back"><ArrowLeft className="h-4 w-4" /></Link>
        <h1 className="truncate text-sm font-medium">{img?.name}</h1>
        {img && <StatusPill status={img.review ?? img.status} />}
        <span className="flex items-center gap-1 text-xs text-muted-foreground">{saving ? <><LoaderCircle className="h-3 w-3 animate-spin" /> Saving…</> : dirty ? 'Unsaved' : <><Check className="h-3.5 w-3.5" /> Saved</>}</span>
        <div className="ml-auto flex items-center gap-1.5">
          {img && can('reviewer') && (
            <Select aria-label="Train / valid / test split" className="h-7 text-xs" value={img.split} onChange={(e) => patch(`/images/${imageId}`, { split: e.target.value }).then(() => qc.invalidateQueries({ queryKey: ['image', imageId] })).catch(toast.err)}>
              <option value="train">TRAIN</option><option value="valid">VALID</option><option value="test">TEST</option>
            </Select>
          )}
          {ready.length > 0 && (
            <Button size="sm" variant="outline" className="h-7 text-xs" disabled={assistBusy} onClick={() => labelAssist(ready[0].id)} title={`Label Assist with ${ready[0].name}`}>
              {assistBusy ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <Bot className="h-3.5 w-3.5" />} Label Assist
            </Button>
          )}
          {img?.status === 'annotating' && <Button size="sm" variant="outline" className="h-7 text-xs" onClick={submitForReview}><Send className="h-3.5 w-3.5" /> Submit for review</Button>}
          {img?.consensusJob && (
            <Button size="sm" variant="outline" className="h-7 text-xs" disabled={submitting} onClick={submitConsensusDraft}>
              {submitting ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />} Submit consensus draft
            </Button>
          )}
          {can('reviewer') && <>
            <Button size="sm" className="h-7 bg-success text-xs text-background hover:bg-success/90" onClick={() => review(true)}><Check className="h-3.5 w-3.5" /> Approve</Button>
            <Button size="sm" variant="outline" className="h-7 border-destructive/50 text-xs text-destructive hover:bg-destructive/10" onClick={() => review(false)}><Ban className="h-3.5 w-3.5" /> Reject</Button>
          </>}
          <Button variant="ghost" size="icon" className="md:hidden" aria-pressed={panelsOpen} aria-label="Toggle annotation panels" onClick={() => setPanelsOpen((o) => !o)}><SlidersHorizontal className="h-4 w-4" /></Button>
          <Button variant="ghost" size="icon" onClick={() => setShortcuts(true)} title="Shortcuts (?)"><Keyboard className="h-4 w-4" /></Button>
        </div>
      </div>
      {img?.consensusJob && (
        <div role="status" className="flex items-center gap-2 border-b border-info/40 bg-info/10 px-4 py-1.5 text-xs font-medium text-info">
          <Info className="h-3.5 w-3.5 shrink-0" aria-hidden />
          Consensus draft — autosave is private; press Submit consensus draft when you are done.
        </div>
      )}
      {reviewMode && <div className="flex items-center gap-2 border-b border-warning/50 bg-warning/15 px-4 py-1.5 text-xs font-medium text-foreground"><TriangleAlert className="h-3.5 w-3.5" /> Review mode — approve to add to the dataset, reject to send back.</div>}
      <div className="flex min-h-0 flex-1">
        <div className={cn('w-16 flex-col items-center border-r py-2 md:flex', panelsOpen ? 'flex' : 'hidden')}>
          {[{ id: 'labels', label: 'Labels', icon: Tag }, { id: 'attrs', label: 'Attributes', icon: SlidersHorizontal }, { id: 'comments', label: 'Comments', icon: MessageSquare }, { id: 'history', label: 'History', icon: History }, { id: 'raw', label: 'Raw', icon: FileCode }].map(({ id, label, icon: Icon }) => (
            <button key={id} onClick={() => setRail(id)} className={cn('flex w-full cursor-pointer flex-col items-center gap-1 px-1 py-2.5 text-[10px]', rail === id ? 'text-accent-foreground' : 'text-muted-foreground hover:text-foreground')}>
              <span className={cn('rounded-lg p-1.5', rail === id && 'bg-accent')}><Icon className="h-4 w-4" /></span>{label}
            </button>
          ))}
        </div>
        <div className={cn('w-64 flex-col overflow-hidden border-r md:flex', panelsOpen ? 'flex' : 'hidden')}>
          {rail === 'labels' && (
            <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
              <div className="px-4 pt-4"><h2 className="text-sm font-semibold">{isCls ? 'Image label' : 'Annotations'} <Badge>{anns.length}</Badge></h2>
                <p className="pt-1 text-xs text-muted-foreground">Group: {proj.data?.annotationGroup}</p>
                {!isCls && anns.some(isAi) && (
                  <p className="flex items-center gap-1.5 pt-1 text-[11px] text-muted-foreground">
                    <span aria-hidden className="inline-block w-4 border-t-2 border-dashed border-muted-foreground" /> Dashed = AI-generated
                  </p>
                )}</div>
              <div className="px-4 pt-2"><Tabs tabs={[{ id: 'classes', label: 'Classes' }, { id: 'objects', label: 'Objects' }]} active={tab} onChange={setTab} /></div>
              {tab === 'classes' ? (
                <div className="flex min-h-0 flex-1 flex-col">
                  <div className="shrink-0 px-4 pt-2">
                    <input ref={classSearchRef} type="search" value={classQuery} data-testid="class-search"
                      aria-label="Search classes" aria-describedby={classCountId} placeholder="Search classes…"
                      autoComplete="off" spellCheck={false} title="Press / to focus"
                      onChange={(e) => setClassQuery(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Escape') { e.stopPropagation(); setClassQuery(''); e.currentTarget.blur() } }}
                      className="h-8 w-full rounded-md border border-input bg-card px-3 text-sm outline-none focus:border-ring placeholder:text-muted-foreground" />
                    <p id={classCountId} aria-live="polite" data-testid="class-count"
                      className="flex h-5 items-center text-[11px] text-muted-foreground">
                      {classResultText(classes.length, classHotkeys.length, classSearch)}
                    </p>
                  </div>
                  <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-2">
                    {classHotkeys.map((c, i) => {
                      const active = isCls ? used.has(c.id) : selClass === c.id
                      return (
                        <button key={c.id} data-testid="class-option" data-hotkey={i < 9 ? i + 1 : undefined}
                          aria-keyshortcuts={i < 9 ? String(i + 1) : undefined}
                          onClick={() => (isCls ? toggleClassLabel(c.id) : selId ? relabel(selId, c.id) : setSelClass(c.id))}
                          className={cn('flex min-h-8 w-full cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-left text-sm', active ? 'bg-accent font-medium text-accent-foreground' : 'hover:bg-muted')}>
                          <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: c.color }} aria-hidden />{c.name}
                          {active && <Check className="h-3.5 w-3.5 shrink-0 text-primary" />}
                          <span className="ml-auto pl-2 text-[10px] tabular-nums text-muted-foreground">{i < 9 ? i + 1 : ''}</span>
                        </button>
                      )
                    })}
                    {!classHotkeys.length && (
                      <div data-testid="class-empty" className="rounded-lg border border-dashed p-3 text-center text-xs text-muted-foreground">
                        No class matches
                      </div>
                    )}
                    <div className="mt-2 flex gap-1.5">
                      <Input className="h-8" placeholder="New class…" value={newClass} onChange={(e) => setNewClass(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && createClass()} />
                      <Button size="sm" onClick={createClass} aria-label="Add class"><Plus className="h-3.5 w-3.5" /></Button>
                    </div>
                    {selId && !isCls && <p className="mt-2 text-[11px] text-muted-foreground">Click a class (or press 1–9) to relabel the selected annotation.</p>}
                  </div>
                </div>
              ) : (
                <div className="px-2 py-2">
                  {anns.map((a) => {
                    const c = cls(a.classId)
                    const isHidden = hidden.has(a.id)
                    const isLocked = locked.has(a.id)
                    return (
                      <div key={a.id} data-testid="object-row" onClick={() => setSelId(a.id)}
                        className={cn('flex cursor-pointer items-center gap-1 rounded px-1.5 py-1 text-sm', selId === a.id ? 'bg-accent text-accent-foreground' : 'hover:bg-muted')}>
                        <button type="button" data-testid="object-select"
                          onClick={(e) => { e.stopPropagation(); setSelId(a.id) }}
                          className="flex min-w-0 flex-1 cursor-pointer items-center gap-1.5 text-left">
                          <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: c.color }} aria-hidden />
                          <span className={cn('min-w-0 flex-1 truncate', isHidden && 'text-muted-foreground line-through')}>{c.name}</span>
                          <SourceChip source={a.source} confidence={a.confidence} kind={a.shape.kind === 'class' ? 'label' : a.shape.kind} />
                        </button>
                        <button type="button" aria-pressed={isHidden} aria-label={`${isHidden ? 'Show' : 'Hide'} ${c.name}`} data-testid="object-hide"
                          onClick={(e) => { e.stopPropagation(); toggleHidden(a.id) }}
                          className="flex h-6 w-6 shrink-0 cursor-pointer items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground">
                          {isHidden ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                        </button>
                        <button type="button" aria-pressed={isLocked} aria-label={`${isLocked ? 'Unlock' : 'Lock'} ${c.name}`} data-testid="object-lock"
                          onClick={(e) => { e.stopPropagation(); toggleLocked(a.id) }}
                          className="flex h-6 w-6 shrink-0 cursor-pointer items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground">
                          {isLocked ? <Lock className="h-3.5 w-3.5" /> : <Unlock className="h-3.5 w-3.5" />}
                        </button>
                        <button type="button" aria-label={`Delete ${c.name}`} data-testid="object-delete"
                          onClick={(e) => { e.stopPropagation(); remove(a.id) }}
                          className="flex h-6 w-6 shrink-0 cursor-pointer items-center justify-center rounded text-muted-foreground hover:text-destructive">
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    )
                  })}
                  {!anns.length && (
                    <div className="rounded-lg border border-dashed p-3 text-center text-xs text-muted-foreground">
                      No objects yet
                      <br />
                      Draw a box or polygon on the image, or use Smart Polygon.
                    </div>
                  )}
                  {sel && !isCls && (
                    <div className="pt-2">
                      <Button variant="outline" size="sm" data-testid="suggest-class" disabled={suggestBusy} onClick={suggestClass}
                        className="h-7 w-full text-xs">
                        {suggestBusy ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5 text-tertiary" />} Suggest class
                      </Button>
                      {suggestErr && <p role="alert" className="pt-1.5 text-[11px] text-destructive">{suggestErr}</p>}
                    </div>
                  )}
                  {suggestion && (
                    <div data-testid="class-suggestion" className="mt-2 rounded-lg border border-tertiary/40 bg-tertiary-container/40 p-2.5 text-xs">
                      {suggestion.classId && suggestion.name ? (
                        <>
                          <div className="flex items-center gap-1.5 font-medium">
                            <Sparkles className="h-3.5 w-3.5 shrink-0 text-tertiary" /> VLM suggests {suggestion.name}
                          </div>
                          <p className="pt-0.5 text-[10px] text-muted-foreground">First match among {suggestion.checked} {suggestion.checked === 1 ? 'class' : 'classes'} checked.</p>
                          <div className="mt-2 flex gap-1.5">
                            <Button size="sm" className="h-7 text-xs" onClick={() => applySuggestion(suggestion.classId!, suggestion.name!)}>Apply</Button>
                            <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => setSuggestion(null)}>Dismiss</Button>
                          </div>
                          {suggestion.candidates.some((c) => c.classId !== suggestion.classId) && (
                            <div className="mt-2 flex flex-wrap gap-1">
                              {suggestion.candidates.filter((c) => c.classId !== suggestion.classId).slice(0, 4).map((c) => (
                                <button key={c.classId} type="button" onClick={() => applySuggestion(c.classId, c.name)}
                                  className="cursor-pointer rounded border px-1.5 py-0.5 text-[10px] text-muted-foreground hover:bg-muted hover:text-foreground">{c.name}</button>
                              ))}
                            </div>
                          )}
                        </>
                      ) : (
                        <div className="flex items-start justify-between gap-2">
                          <span>No class matched — check the label.</span>
                          <button type="button" onClick={() => setSuggestion(null)} className="cursor-pointer text-[10px] text-muted-foreground hover:text-foreground">Dismiss</button>
                        </div>
                      )}
                    </div>
                  )}
                  {!sel && !isCls && !!selCls?.skeleton?.names.length && (
                    <div className="mt-2 rounded-lg border border-dashed p-2.5 text-center">
                      <p className="pb-1.5 text-[11px] text-muted-foreground">
                        {selCls.name} — {selCls.skeleton.names.length} joints
                      </p>
                      <Button size="sm" variant="outline" className="h-7 min-h-6 w-full text-xs" data-testid="start-keypoints" onClick={startKeypoints}>
                        <Waypoints className="h-3.5 w-3.5" /> Start keypoints
                      </Button>
                    </div>
                  )}
                  {sel && !isCls && sel.shape.kind !== 'class' && (
                    <GeometryPanel key={sel.id} shape={sel.shape} skeleton={skelOf(sel.classId)}
                      activeJoint={activeJoint} onActiveJoint={setActiveJoint}
                      onShape={(shape) => editShape(sel.id, shape)} />
                  )}
                  {!isCls && (tool === 'bbox' || tool === 'obb' || sel?.shape.kind === 'bbox' || sel?.shape.kind === 'obb') && (
                    <Button size="sm" variant="outline" className="mt-2 h-7 min-h-6 w-full text-xs" data-testid="add-centred-box" onClick={addCentredBox}>
                      <SquareDashed className="h-3.5 w-3.5" /> Add centred box
                    </Button>
                  )}
                  {sel && (
                    <p className="px-1 pt-2 text-[11px] leading-relaxed text-muted-foreground">
                      Selected: Delete removes it, 1–9 relabels it.
                      {locked.has(sel.id) ? ' Locked — unlock to move or resize on the canvas.' : hidden.has(sel.id) ? ' Hidden on the canvas.' : ' Lock keeps it still while you work.'}
                    </p>
                  )}
                </div>
              )}
              {!isCls && (
                <div className="px-4 pt-2">
                  <Button variant="outline" className="w-full border-tertiary/60 bg-tertiary-container text-foreground hover:bg-tertiary-container/80" onClick={() => setTool('smart')}>
                    <Sparkles className="h-4 w-4" /> Smart Polygon
                  </Button>
                </div>
              )}
              <div className="mt-auto px-4 py-4">
                <h3 className="mb-2 text-sm font-semibold">Tags</h3>
                <div className="mb-2 flex flex-wrap gap-1">
                  {img?.tags.map((t) => <Badge key={t}>{t}<button className="cursor-pointer" onClick={() => setTags(img.tags.filter((x) => x !== t))} aria-label={`Remove ${t}`}><X className="h-3 w-3" /></button></Badge>)}
                  {!img?.tags.length && <span className="text-xs text-muted-foreground">No tags</span>}
                </div>
                <div className="flex gap-1.5">
                  <Input placeholder="Add tag…" className="h-8" value={tagInput} onChange={(e) => setTagInput(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && tagInput.trim() && img) { setTags([...img.tags, tagInput.trim()]); setTagInput('') } }} />
                  <Button size="sm" aria-label="Add tag" onClick={() => { if (tagInput.trim() && img) { setTags([...img.tags, tagInput.trim()]); setTagInput('') } }}><Plus className="h-3.5 w-3.5" /></Button>
                </div>
              </div>
            </div>
          )}
          {rail === 'attrs' && (
            <AttributesPanel anns={anns as any} selId={selId} onSelect={setSelId} classOf={cls as any} values={sel?.attributes ?? {}}
              onToggle={(k) => sel && toggleAttribute(sel.id, k)} />
          )}
          {rail === 'comments' && <CommentsPanel comments={commentsQ.data ?? []} onAdd={addComment} />}
          {rail === 'history' && <HistoryPanel log={log} />}
          {rail === 'raw' && <RawDataPanel payload={{ image: img && { id: img.id, name: img.name, width: img.width, height: img.height, split: img.split, status: img.status, tags: img.tags }, annotations: anns }} />}
        </div>

        <div ref={wrapRef} data-testid="canvas-area" className="canvas-well relative flex-1 overflow-hidden">
          <div data-testid="stage-filter" data-ai={anns.filter(isAi).length} className="absolute inset-0" style={{ filter: `brightness(${brightness}%) contrast(${contrast}%)` }}>
            <Stage ref={stageRef} width={wrapRef.current?.clientWidth ?? 800} height={wrapRef.current?.clientHeight ?? 600}
              scaleX={zoom} scaleY={zoom}
              x={((wrapRef.current?.clientWidth ?? 800) - W * zoom) / 2} y={((wrapRef.current?.clientHeight ?? 600) - H * zoom) / 2}
              draggable={tool === 'pan'} onMouseDown={onDown} onMouseMove={onMove} onMouseUp={onUp} onDblClick={() => polyPts.length && closePoly()}
              onContextMenu={(e) => e.evt.preventDefault()}
              onWheel={(e) => { e.evt.preventDefault(); setZoom((z) => Math.min(8, Math.max(0.05, z * (e.evt.deltaY > 0 ? 0.9 : 1.1)))) }}>
              <Layer listening={false}>{htmlImg && <KImage image={htmlImg} width={W} height={H} />}</Layer>
              <Layer>
                {anns.filter((a) => !hidden.has(a.id)).map((a) => {
                  const color = cls(a.classId).color
                  if (a.shape.kind === 'bbox') {
                    const s = a.shape
                    return <Rect key={a.id} id={a.id} x={s.x * W} y={s.y * H} width={s.w * W} height={s.h * H} stroke={color} strokeWidth={2 / zoom}
                      dash={isAi(a) ? [8 / zoom, 5 / zoom] : undefined}
                      fill={selId === a.id ? color + '22' : undefined} draggable={tool !== 'pan' && selId === a.id && !locked.has(a.id)}
                      onMouseDown={(e) => { if (boxAnchor || locked.has(a.id) || tool === 'smart' || tool === 'polygon' || tool === 'keypoints') return; e.cancelBubble = true; setSelId(a.id) }}
                      onDragEnd={(e) => editShape(a.id, { ...s, x: e.target.x() / W, y: e.target.y() / H })}
                      onTransformEnd={(e) => { const n = e.target; const sx = n.scaleX(), sy = n.scaleY(); n.scaleX(1); n.scaleY(1); editShape(a.id, { ...s, x: n.x() / W, y: n.y() / H, w: (s.w * sx), h: (s.h * sy) }) }} />
                  }
                  if (a.shape.kind === 'polygon') {
                    const s = a.shape
                    return <Line key={a.id} id={a.id} points={s.points.map((v, i) => v * (i % 2 ? H : W))} closed stroke={color} strokeWidth={2 / zoom}
                      dash={isAi(a) ? [8 / zoom, 5 / zoom] : undefined} fill={color + (selId === a.id ? '55' : '33')}
                      draggable={tool !== 'pan' && selId === a.id && !locked.has(a.id)}
                      onMouseDown={(e) => { if (boxAnchor || locked.has(a.id) || tool === 'smart' || tool === 'polygon' || tool === 'keypoints') return; e.cancelBubble = true; setSelId(a.id) }}
                      onDragEnd={(e) => { const dx = e.target.x(), dy = e.target.y(); e.target.position({ x: 0, y: 0 }); editShape(a.id, { ...s, points: s.points.map((v, i) => v + (i % 2 ? dy / H : dx / W)) }) }} />
                  }
                  if (a.shape.kind === 'obb') {
                    const s = a.shape
                    return <Line key={a.id} id={a.id} points={obbCorners(s, H)} closed stroke={color} strokeWidth={2 / zoom}
                      dash={isAi(a) ? [8 / zoom, 5 / zoom] : undefined} fill={selId === a.id ? color + '22' : undefined}
                      draggable={tool !== 'pan' && selId === a.id && !locked.has(a.id)}
                      onMouseDown={(e) => { if (boxAnchor || locked.has(a.id) || tool === 'smart' || tool === 'polygon' || tool === 'keypoints') return; e.cancelBubble = true; setSelId(a.id) }}
                      onDragEnd={(e) => {
                        const dx = e.target.x(), dy = e.target.y()
                        e.target.position({ x: 0, y: 0 })
                        editShape(a.id, { ...s, cx: clamp01(s.cx + dx / W), cy: clamp01(s.cy + dy / H) })
                      }} />
                  }
                  if (a.shape.kind === 'keypoints') {
                    const s = a.shape
                    const n = Math.floor(s.points.length / 3)
                    const sk = skelOf(a.classId)
                    const jx = (i: number) => s.points[i * 3] * W
                    const jy = (i: number) => s.points[i * 3 + 1] * H
                    return (
                      <Group key={a.id} id={a.id}>
                        {(sk?.edges ?? []).filter(([i, j]) => i < n && j < n && s.points[i * 3 + 2] > 0 && s.points[j * 3 + 2] > 0)
                          .map(([i, j], k) => (
                            <Line key={`b${k}`} points={[jx(i), jy(i), jx(j), jy(j)]} stroke={color} strokeWidth={1.5 / zoom} opacity={0.8}
                              dash={isAi(a) ? [6 / zoom, 4 / zoom] : undefined} listening={false} />
                          ))}
                        {Array.from({ length: n }, (_, i) => {
                          const v = s.points[i * 3 + 2]
                          const r = v === 2 ? 5 : v === 1 ? 4.5 : 3
                          return (
                            <Circle key={i} x={jx(i)} y={jy(i)} radius={r / zoom} fill={v === 2 ? color : undefined} stroke={color}
                              strokeWidth={(v === 0 ? 1.5 : 2) / zoom} opacity={v === 0 ? 0.55 : 1} hitStrokeWidth={12 / zoom}
                              dash={isAi(a) ? [3 / zoom, 2 / zoom] : undefined}
                              onMouseDown={(e) => { if (locked.has(a.id)) return; e.cancelBubble = true; setSelId(a.id); setActiveJoint(i) }} />
                          )
                        })}
                        {selId === a.id && activeJoint < n && (
                          <Circle x={jx(activeJoint)} y={jy(activeJoint)} radius={9 / zoom} stroke={color}
                            strokeWidth={1 / zoom} dash={[2 / zoom, 2 / zoom]} listening={false} />
                        )}
                      </Group>
                    )
                  }
                  return null
                })}
                {drawing && <Rect x={drawing.x} y={drawing.y} width={drawing.w} height={drawing.h} stroke={cls(selClass).color} strokeWidth={2 / zoom} dash={[6 / zoom, 4 / zoom]} />}
                {polyPts.length > 0 && <Line points={polyPts} stroke={cls(selClass).color} strokeWidth={2 / zoom} />}
                {polyPts.map((v, i) => i % 2 === 0 && <Circle key={i} x={v} y={polyPts[i + 1]} radius={4 / zoom} fill={cls(selClass).color} />)}
                {smartPoly && smartPoly.length >= 6 && (
                  <Line points={smartPoly.map((v, i) => v * (i % 2 ? H : W))} closed stroke={SMART} strokeWidth={2 / zoom}
                    dash={[8 / zoom, 5 / zoom]} fill={SMART + '18'} listening={false} />
                )}
                {smartPts.map((v, i) => i % 2 === 0 && <Circle key={'p' + i} name="smart-pt" x={v} y={smartPts[i + 1]} radius={6 / zoom} fill={SMART} stroke="#fff" strokeWidth={1.5 / zoom}
                  onClick={() => removeSmartPoint(false, i)} />)}
                {smartNeg.map((v, i) => i % 2 === 0 && <Circle key={'n' + i} name="smart-neg" x={v} y={smartNeg[i + 1]} radius={6 / zoom} stroke={SMART} strokeWidth={2 / zoom} fill={SMART + '18'}
                  onClick={() => removeSmartPoint(true, i)} />)}
                {transformable && <Transformer ref={trRef} rotateEnabled={false} ignoreStroke />}
              </Layer>
            </Stage>
          </div>
          {!isCls && tool === 'bbox' && !boxAnchor && !anns.length && (
            <div className={HINT}>
              Click two corners to draw a box — no dragging needed
            </div>
          )}
          {!isCls && tool === 'obb' && !boxAnchor && (
            <div className={HINT}>
              Click two corners for the rotated box · set the angle in Objects
            </div>
          )}
          {!isCls && tool === 'keypoints' && (
            <div className={HINT}>
              Click the image to place the next joint · pick a joint in Objects to place it at the centre
            </div>
          )}
          {!isCls && tool === 'smart' && !smartPts.length && !smartBusy && !smartErr && (
            <div className={HINT}>
              Click the object to segment · click inside it to shrink · Alt-click or right-click a spot to exclude it · Enter commits
            </div>
          )}
          {isCls && (
            <div className="absolute left-1/2 top-3 -translate-x-1/2 rounded-full border bg-card px-3 py-1.5 text-xs shadow">
              {anns.length ? <>Labeled: <b>{anns.map((a) => cls(a.classId).name).join(', ')}</b></> : 'Pick a class on the left (or press 1–9)'}
            </div>
          )}
          {tool === 'smart' && (smartBusy || smartErr || smartPts.length > 0) && (
            <div className="absolute left-1/2 top-3 flex w-full max-w-[20rem] -translate-x-1/2 flex-col items-center gap-1 px-1">
              {smartBusy && <div className="flex items-center gap-1.5 rounded-full border bg-card px-3 py-1.5 text-xs shadow"><LoaderCircle className="h-3.5 w-3.5 animate-spin text-tertiary" /> Segmenting…</div>}
              {smartErr && <div role="alert" className="flex items-center gap-1.5 rounded-full border border-destructive/40 bg-destructive/10 px-3 py-1.5 text-xs text-destructive shadow"><TriangleAlert className="h-3.5 w-3.5" /> {smartErr}</div>}
              {!smartBusy && !smartErr && smartPts.length > 0 && (
                <div className="rounded-full border bg-card px-3 py-1.5 text-center text-xs shadow">
                  {(smartPts.length + smartNeg.length) / 2} {(smartPts.length + smartNeg.length) / 2 === 1 ? 'point' : 'points'} · Enter to commit · Esc to cancel
                </div>
              )}
              {smartPoly && smartPts.length > 0 && (
                <div data-testid="simplify-control" className="w-full rounded-xl border bg-card p-2.5 text-left shadow">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[11px] font-medium">Simplify polygon</span>
                    <span data-testid="simplify-points" className="text-[11px] tabular-nums text-muted-foreground">
                      {smartPoly.length / 2} points
                    </span>
                  </div>
                  <input type="range" min={EPS_MIN} max={EPS_MAX} step={0.0005} value={epsilon} data-testid="simplify-slider"
                    aria-label="Polygon simplification" aria-valuetext={`${smartPoly.length / 2} points`}
                    aria-busy={smartBusy || undefined} onChange={(e) => simplify(Number(e.target.value))}
                    onKeyDown={(e) => { if (e.key === 'Enter' && smartFresh && !smartBusy) commitSmart() }}
                    className="mt-1 w-full cursor-pointer accent-primary" />
                  <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                    <span>Detailed</span><span>Simple</span>
                  </div>
                </div>
              )}
            </div>
          )}
          <Glass strength="chrome" className="absolute right-3 top-1/2 flex -translate-y-1/2 flex-col items-center gap-0.5 rounded-xl p-1">
            {tools.map(({ id, icon: Icon, label }) => (
              <button key={id} data-testid={`tool-${id}`} onClick={() => setTool(id)} title={label} aria-label={label} aria-pressed={tool === id} className={cn('cursor-pointer rounded-lg p-2', tool === id ? 'bg-accent text-accent-foreground' : 'text-muted-foreground hover:bg-muted')}><Icon className="h-4 w-4" /></button>
            ))}
            <div className="my-1 h-px w-6 bg-border" />
            <button onClick={undo} title="Undo (Ctrl+Z)" aria-label="Undo" className="cursor-pointer rounded-lg p-2 text-muted-foreground hover:bg-muted"><Undo2 className="h-4 w-4" /></button>
            <button onClick={redo} title="Redo (Ctrl+Shift+Z)" aria-label="Redo" className="cursor-pointer rounded-lg p-2 text-muted-foreground hover:bg-muted"><Redo2 className="h-4 w-4" /></button>
            <button onClick={() => selId && remove(selId)} title="Delete selected" aria-label="Delete selected" className="cursor-pointer rounded-lg p-2 text-muted-foreground hover:bg-muted"><Ban className="h-4 w-4" /></button>
          </Glass>
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2">
            {displayOpen && (
              <Glass strength="overlay" id="display-settings" role="dialog" aria-label="Display settings"
                className="anim-pop absolute bottom-full left-1/2 mb-2 w-60 -translate-x-1/2 rounded-xl p-3 text-popover-foreground">
                <div className="flex items-center justify-between pb-1.5">
                  <span className="text-xs font-semibold">Display</span>
                  <button type="button" onClick={() => { setBrightness(100); setContrast(100) }} className="cursor-pointer rounded px-1.5 py-0.5 text-[11px] text-muted-foreground hover:bg-accent hover:text-accent-foreground">Reset</button>
                </div>
                <label className="block pb-1.5">
                  <span className="flex items-center justify-between text-[11px]"><span>Brightness</span><span className="tabular-nums text-muted-foreground">{brightness}%</span></span>
                  <input type="range" min={50} max={150} value={brightness} aria-label="Brightness" onChange={(e) => setBrightness(Number(e.target.value))} className="mt-1 w-full cursor-pointer accent-primary" />
                </label>
                <label className="block">
                  <span className="flex items-center justify-between text-[11px]"><span>Contrast</span><span className="tabular-nums text-muted-foreground">{contrast}%</span></span>
                  <input type="range" min={50} max={150} value={contrast} aria-label="Contrast" onChange={(e) => setContrast(Number(e.target.value))} className="mt-1 w-full cursor-pointer accent-primary" />
                </label>
                <p className="pt-1.5 text-[10px] text-muted-foreground">Display only — saved annotations are unchanged.</p>
              </Glass>
            )}
            <Glass strength="chrome" className="flex items-center rounded-full px-3 py-1.5 text-xs">
              <button type="button" aria-expanded={displayOpen} aria-controls="display-settings" onClick={() => setDisplayOpen((o) => !o)} className="flex cursor-pointer items-center gap-1 rounded px-1 hover:text-foreground">
                <SlidersHorizontal className="h-3.5 w-3.5" /> Display
              </button>
              <span className="mx-2 h-4 w-px bg-border" aria-hidden />
              <button onClick={() => setZoom((z) => Math.max(0.05, z / 1.2))} className="cursor-pointer px-1" aria-label="Zoom out">−</button>
              <span className="w-12 text-center">{Math.round(zoom * 100)}%</span>
              <button onClick={() => setZoom((z) => Math.min(8, z * 1.2))} className="cursor-pointer px-1" aria-label="Zoom in">+</button>
              <button onClick={fit} className="ml-1 cursor-pointer rounded px-1.5 text-muted-foreground hover:bg-accent">FIT</button>
            </Glass>
          </div>
        </div>

        <div className="hidden w-48 flex-col border-l lg:flex">
          <div className="flex items-center justify-between border-b px-3 py-2.5">
            <span className="text-xs font-semibold">Images</span>
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <button onClick={() => go(-1)} className="cursor-pointer" aria-label="Previous"><ChevronLeft className="h-3.5 w-3.5" /></button>
              {idx + 1} / {items.length}
              <button onClick={() => go(1)} className="cursor-pointer" aria-label="Next"><ChevronRight className="h-3.5 w-3.5" /></button>
            </div>
          </div>
          <div className="flex-1 space-y-2 overflow-y-auto p-2">
            {items.slice(Math.max(0, idx - 20), idx + 40).map((im) => (
              <Link key={im.id} to={`/${ws}/${project}/images/${im.id}?${sp}`} className={cn('block overflow-hidden rounded-md border-2', im.id === imageId ? 'border-primary' : 'border-transparent')}>
                <div className="relative">
                  <img src={fileUrl(im.thumbnail)} className="aspect-[7/4] w-full object-cover" alt="" loading="lazy" />
                  {im.annotated && <span className="absolute right-1 top-1 flex h-4 w-4 items-center justify-center rounded-full bg-primary text-primary-foreground"><Check className="h-2.5 w-2.5" /></span>}
                </div>
                <div className="truncate px-1.5 py-1 text-[10px] text-muted-foreground">{im.name}</div>
              </Link>
            ))}
          </div>
        </div>
      </div>
      <ShortcutModal open={shortcuts} onClose={() => setShortcuts(false)} keys={shortcutKeys} onSave={setShortcutKeys} />
    </main>
  )
}
