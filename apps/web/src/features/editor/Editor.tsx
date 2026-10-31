import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Circle, Image as KImage, Layer, Line, Rect, Stage, Transformer } from 'react-konva'
import {
  ArrowLeft, Ban, Bot, Check, ChevronLeft, ChevronRight, FileCode, Hand, History, Keyboard, LoaderCircle,
  MessageSquare, Plus, Redo2, Send, SlidersHorizontal, Sparkles, SquareDashed, Spline, Tag, TriangleAlert, Undo2, X,
  type LucideIcon,
} from 'lucide-react'
import { api, fileUrl, get, patch, post, put } from '@/lib/api'
import { useApp } from '@/lib/store'
import type { Annotation, LabelClass, Shape } from '@/lib/types'
import { Badge, Button, Input, Select, StatusPill, Tabs, toast } from '@/components/ui'
import { cn } from '@/lib/utils'
import { AttributesPanel, CommentsPanel, HistoryPanel, RawDataPanel, SourceChip, type EditorComment, type LogEntry } from './Panels'
import { ShortcutModal } from './ShortcutModal'

const W = 1000                      // canvas width in stage units; height follows the image aspect
const SMART = '#7c3aed'
const uid = () => 'a' + Math.random().toString(36).slice(2, 12)
const isAi = (a: Annotation) => !!a.source && a.source !== 'human'

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
  const isCls = proj.data?.type === 'classification'
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
  useEffect(() => { if (isCls) setTool('pan') }, [isCls])

  const [anns, setAnns] = useState<Annotation[]>([])
  const [loadedFor, setLoadedFor] = useState('')
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [selId, setSelId] = useState<string | null>(null)
  const [selClass, setSelClass] = useState('')
  const [drawing, setDrawing] = useState<{ x: number; y: number; w: number; h: number } | null>(null)
  const [polyPts, setPolyPts] = useState<number[]>([])
  const [smartPts, setSmartPts] = useState<number[]>([])
  const [smartBusy, setSmartBusy] = useState(false)
  const [smartErr, setSmartErr] = useState('')
  const [assistBusy, setAssistBusy] = useState(false)
  const [tab, setTab] = useState('classes')
  const [rail, setRail] = useState('labels')
  const [history, setHistory] = useState<Annotation[][]>([])
  const [future, setFuture] = useState<Annotation[][]>([])
  const [log, setLog] = useState<LogEntry[]>([])
  const [shortcuts, setShortcuts] = useState(false)
  const [newClass, setNewClass] = useState('')
  const [tagInput, setTagInput] = useState('')
  const stageRef = useRef<any>(null)
  const trRef = useRef<any>(null)

  // load annotations when the image changes
  useEffect(() => {
    if (img && loadedFor !== img.id) {
      setAnns(img.annotations ?? []); setLoadedFor(img.id); setDirty(false)
      setHistory([]); setFuture([]); setSelId(null); setPolyPts([]); setSmartPts([]); setSmartErr('')
    }
  }, [img, loadedFor])
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
  useEffect(() => {
    if (trRef.current && selId && sel?.shape.kind === 'bbox') {
      const node = stageRef.current?.findOne('#' + selId)
      if (node) trRef.current.nodes([node])
    }
  }, [selId, sel])

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

  const runSmart = (pts: number[]) => {
    setSmartBusy(true); setSmartErr('')
    const pairs: number[][] = []
    for (let i = 0; i < pts.length; i += 2) pairs.push([pts[i] / W, pts[i + 1] / H])
    post<{ polygon: number[]; source: string }>(`/images/${imageId}/smart-polygon`, { points: pairs })
      .then((r) => {
        const shape: Shape = proj.data?.type === 'object-detection'
          ? (() => { const xs = r.polygon.filter((_, i) => i % 2 === 0), ys = r.polygon.filter((_, i) => i % 2); return { kind: 'bbox', x: Math.min(...xs), y: Math.min(...ys), w: Math.max(...xs) - Math.min(...xs), h: Math.max(...ys) - Math.min(...ys) } as Shape })()
          : { kind: 'polygon', points: r.polygon }
        addShape(shape, `Smart polygon (${r.source})`); setSmartPts([])
      })
      .catch((e) => setSmartErr((e as Error).message))
      .finally(() => setSmartBusy(false))
  }
  const onDown = (e: any) => {
    if (e?.target?.name?.() === 'smart-pt') return
    if (tool === 'pan' || isCls) return
    setSelId(null)
    const p = pointer()
    if (tool === 'bbox') setDrawing({ x: p.x, y: p.y, w: 0, h: 0 })
    else if (tool === 'polygon') setPolyPts((pts) => [...pts, p.x, p.y])
    else if (tool === 'smart') { const pts = [...smartPts, p.x, p.y]; setSmartPts(pts); runSmart(pts) }
  }
  const onMove = () => { if (drawing) { const p = pointer(); setDrawing({ ...drawing, w: p.x - drawing.x, h: p.y - drawing.y }) } }
  const onUp = () => {
    if (drawing && Math.abs(drawing.w) > 4 && Math.abs(drawing.h) > 4) {
      addShape({ kind: 'bbox', x: Math.min(drawing.x, drawing.x + drawing.w) / W, y: Math.min(drawing.y, drawing.y + drawing.h) / H, w: Math.abs(drawing.w) / W, h: Math.abs(drawing.h) / H }, 'Add bounding box')
    }
    setDrawing(null)
  }
  const closePoly = () => {
    if (polyPts.length >= 6) addShape({ kind: 'polygon', points: polyPts.map((v, i) => v / (i % 2 ? H : W)) }, 'Add polygon')
    setPolyPts([])
  }
  const remove = (id: string) => { push(anns.filter((a) => a.id !== id), 'Delete annotation'); if (selId === id) setSelId(null) }
  const editShape = (id: string, shape: Shape) => push(anns.map((a) => (a.id === id ? { ...a, shape, source: 'human' } : a)), 'Edit annotation')
  const relabel = (id: string, classId: string) => push(anns.map((a) => (a.id === id ? { ...a, classId, source: 'human' } : a)), 'Change class', cls(classId).name)
  const toggleClassLabel = (classId: string) => {
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

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement) return
      if (e.key === 'ArrowRight') go(1)
      if (e.key === 'ArrowLeft') go(-1)
      if ((e.key === 'Delete' || e.key === 'Backspace') && selId) remove(selId)
      if (e.key === 'Escape') { setPolyPts([]); setSmartPts([]); setSmartErr(''); setSelId(null) }
      if (e.key === 'Enter' && polyPts.length) closePoly()
      if (e.key === '?') setShortcuts((o) => !o)
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); e.shiftKey ? redo() : undo() }
      if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); save() }
      const t = { v: 'pan', b: 'bbox', p: 'polygon', s: 'smart' } as Record<string, string>
      if (!e.ctrlKey && !e.metaKey && t[e.key] && !isCls) setTool(t[e.key])
      const n = Number(e.key)
      if (n >= 1 && n <= 9 && classes[n - 1]) { if (isCls) toggleClassLabel(classes[n - 1].id); else if (selId) relabel(selId, classes[n - 1].id); else setSelClass(classes[n - 1].id) }
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  })

  const tools: { id: string; icon: LucideIcon; label: string }[] = isCls ? [{ id: 'pan', icon: Hand, label: 'Pan (V)' }] : [
    { id: 'pan', icon: Hand, label: 'Pan (V)' },
    { id: 'bbox', icon: SquareDashed, label: 'Bounding Box (B)' },
    ...(proj.data?.type === 'instance-segmentation' ? [{ id: 'polygon', icon: Spline, label: 'Polygon (P)' }] : []),
    { id: 'smart', icon: Sparkles, label: 'Smart Polygon (S) — click an object' },
  ]
  const ready = (models.data ?? []).filter((m) => m.status === 'ready')
  const used = new Set(anns.map((a) => a.classId))

  if (imgQ.isError) return <div className="p-10 text-sm text-muted-foreground">Can't open this image: {(imgQ.error as Error).message} <Link className="text-primary" to={`/${ws}/${project}/browse`}>Back</Link></div>

  return (
    <div className="flex h-screen flex-col bg-white">
      <div className="flex items-center gap-2 border-b px-3 py-2">
        <Link to={reviewMode || sp.get('status') ? `/${ws}/${project}/annotate` : `/${ws}/${project}/browse`} className="rounded p-1.5 hover:bg-accent" aria-label="Back"><ArrowLeft className="h-4 w-4" /></Link>
        <span className="truncate text-sm font-medium">{img?.name}</span>
        {img && <StatusPill status={img.review ?? img.status} />}
        <span className="flex items-center gap-1 text-xs text-muted-foreground">{saving ? <><LoaderCircle className="h-3 w-3 animate-spin" /> Saving…</> : dirty ? 'Unsaved' : <><Check className="h-3.5 w-3.5" /> Saved</>}</span>
        <div className="ml-auto flex items-center gap-1.5">
          {img && can('reviewer') && (
            <Select className="h-7 text-xs" value={img.split} onChange={(e) => patch(`/images/${imageId}`, { split: e.target.value }).then(() => qc.invalidateQueries({ queryKey: ['image', imageId] })).catch(toast.err)}>
              <option value="train">TRAIN</option><option value="valid">VALID</option><option value="test">TEST</option>
            </Select>
          )}
          {ready.length > 0 && (
            <Button size="sm" variant="outline" className="h-7 text-xs" disabled={assistBusy} onClick={() => labelAssist(ready[0].id)} title={`Label Assist with ${ready[0].name}`}>
              {assistBusy ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <Bot className="h-3.5 w-3.5" />} Label Assist
            </Button>
          )}
          {img?.status === 'annotating' && <Button size="sm" variant="outline" className="h-7 text-xs" onClick={submitForReview}><Send className="h-3.5 w-3.5" /> Submit for review</Button>}
          {can('reviewer') && <>
            <Button size="sm" className="h-7 bg-green-600 text-xs hover:bg-green-700" onClick={() => review(true)}><Check className="h-3.5 w-3.5" /> Approve</Button>
            <Button size="sm" variant="outline" className="h-7 border-destructive/50 text-xs text-destructive hover:bg-destructive/10" onClick={() => review(false)}><Ban className="h-3.5 w-3.5" /> Reject</Button>
          </>}
          <Button variant="ghost" size="icon" onClick={() => setShortcuts(true)} title="Shortcuts (?)"><Keyboard className="h-4 w-4" /></Button>
        </div>
      </div>
      {reviewMode && <div className="flex items-center gap-2 border-b border-amber-300 bg-amber-100 px-4 py-1.5 text-xs font-medium text-amber-900"><TriangleAlert className="h-3.5 w-3.5" /> Review mode — approve to add to the dataset, reject to send back.</div>}
      <div className="flex min-h-0 flex-1">
        <div className="flex w-16 flex-col items-center border-r py-2">
          {[{ id: 'labels', label: 'Labels', icon: Tag }, { id: 'attrs', label: 'Attributes', icon: SlidersHorizontal }, { id: 'comments', label: 'Comments', icon: MessageSquare }, { id: 'history', label: 'History', icon: History }, { id: 'raw', label: 'Raw', icon: FileCode }].map(({ id, label, icon: Icon }) => (
            <button key={id} onClick={() => setRail(id)} className={cn('flex w-full cursor-pointer flex-col items-center gap-1 px-1 py-2.5 text-[10px]', rail === id ? 'text-accent-foreground' : 'text-muted-foreground hover:text-foreground')}>
              <span className={cn('rounded-lg p-1.5', rail === id && 'bg-accent')}><Icon className="h-4 w-4" /></span>{label}
            </button>
          ))}
        </div>
        <div className="flex w-64 flex-col overflow-hidden border-r">
          {rail === 'labels' && (
            <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
              <div className="px-4 pt-4"><h3 className="text-sm font-semibold">{isCls ? 'Image label' : 'Annotations'} <Badge>{anns.length}</Badge></h3>
                <p className="pt-1 text-xs text-muted-foreground">Group: {proj.data?.annotationGroup}</p>
                {!isCls && anns.some(isAi) && (
                  <p className="flex items-center gap-1.5 pt-1 text-[11px] text-muted-foreground">
                    <span aria-hidden className="inline-block w-4 border-t-2 border-dashed border-muted-foreground" /> Dashed = AI-generated
                  </p>
                )}</div>
              <div className="px-4 pt-2"><Tabs tabs={[{ id: 'classes', label: 'Classes' }, { id: 'layers', label: 'Layers' }]} active={tab} onChange={setTab} /></div>
              {tab === 'classes' ? (
                <div className="px-4 py-2">
                  {classes.map((c, i) => {
                    const active = isCls ? used.has(c.id) : selClass === c.id
                    return (
                      <button key={c.id} onClick={() => (isCls ? toggleClassLabel(c.id) : selId ? relabel(selId, c.id) : setSelClass(c.id))}
                        className={cn('flex w-full cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-left text-sm', active ? 'bg-accent font-medium text-accent-foreground' : 'hover:bg-muted')}>
                        <span className="h-2.5 w-2.5 rounded-full" style={{ background: c.color }} />{c.name}
                        {active && <Check className="h-3.5 w-3.5 text-violet-600" />}
                        <span className="ml-auto text-[10px] text-muted-foreground">{i < 9 ? i + 1 : ''}</span>
                      </button>
                    )
                  })}
                  <div className="mt-2 flex gap-1.5">
                    <Input className="h-8" placeholder="New class…" value={newClass} onChange={(e) => setNewClass(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && createClass()} />
                    <Button size="sm" onClick={createClass} aria-label="Add class"><Plus className="h-3.5 w-3.5" /></Button>
                  </div>
                  {selId && !isCls && <p className="mt-2 text-[11px] text-muted-foreground">Click a class (or press 1–9) to relabel the selected annotation.</p>}
                </div>
              ) : (
                <div className="px-2 py-2">
                  {anns.map((a) => (
                    <div key={a.id} onClick={() => setSelId(a.id)} className={cn('flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm', selId === a.id ? 'bg-accent' : 'hover:bg-muted')}>
                      <span className="h-2.5 w-2.5 rounded-full" style={{ background: cls(a.classId).color }} />
                      <span className="flex-1 truncate">{cls(a.classId).name}</span>
                      <SourceChip source={a.source} confidence={a.confidence} kind={a.shape.kind} />
                      <button onClick={(e) => { e.stopPropagation(); remove(a.id) }} className="cursor-pointer text-muted-foreground hover:text-destructive" aria-label="Delete"><X className="h-3.5 w-3.5" /></button>
                    </div>
                  ))}
                  {!anns.length && <p className="px-2 text-xs text-muted-foreground">No annotations yet.</p>}
                </div>
              )}
              {!isCls && (
                <div className="px-4 pt-2">
                  <Button variant="outline" className="w-full border-violet-500/70 bg-violet-50 text-violet-800 hover:bg-violet-100" onClick={() => setTool('smart')}>
                    <Sparkles className="h-4 w-4" /> Smart Polygon
                  </Button>
                </div>
              )}
              <div className="mt-auto px-4 py-4">
                <h4 className="mb-2 text-sm font-semibold">Tags</h4>
                <div className="mb-2 flex flex-wrap gap-1">
                  {img?.tags.map((t) => <Badge key={t}>{t}<button className="cursor-pointer" onClick={() => setTags(img.tags.filter((x) => x !== t))} aria-label={`Remove ${t}`}><X className="h-3 w-3" /></button></Badge>)}
                  {!img?.tags.length && <span className="text-xs text-muted-foreground">No tags</span>}
                </div>
                <div className="flex gap-1.5">
                  <Input placeholder="Add tag…" className="h-8" value={tagInput} onChange={(e) => setTagInput(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && tagInput.trim() && img) { setTags([...img.tags, tagInput.trim()]); setTagInput('') } }} />
                  <Button size="sm" onClick={() => { if (tagInput.trim() && img) { setTags([...img.tags, tagInput.trim()]); setTagInput('') } }}><Plus className="h-3.5 w-3.5" /></Button>
                </div>
              </div>
            </div>
          )}
          {rail === 'attrs' && (
            <AttributesPanel anns={anns as any} selId={selId} onSelect={setSelId} classOf={cls as any} values={sel?.attributes ?? {}}
              onToggle={(k) => sel && push(anns.map((a) => (a.id === sel.id ? { ...a, attributes: { ...(a.attributes ?? {}), [k]: !a.attributes?.[k] }, source: 'human' } : a)), 'Edit attributes', k)} />
          )}
          {rail === 'comments' && <CommentsPanel comments={commentsQ.data ?? []} onAdd={addComment} />}
          {rail === 'history' && <HistoryPanel log={log} />}
          {rail === 'raw' && <RawDataPanel payload={{ image: img && { id: img.id, name: img.name, width: img.width, height: img.height, split: img.split, status: img.status, tags: img.tags }, annotations: anns }} />}
        </div>

        <div ref={wrapRef} className="relative flex-1 overflow-hidden bg-neutral-100">
          <Stage ref={stageRef} width={wrapRef.current?.clientWidth ?? 800} height={wrapRef.current?.clientHeight ?? 600}
            scaleX={zoom} scaleY={zoom}
            x={((wrapRef.current?.clientWidth ?? 800) - W * zoom) / 2} y={((wrapRef.current?.clientHeight ?? 600) - H * zoom) / 2}
            draggable={tool === 'pan'} onMouseDown={onDown} onMouseMove={onMove} onMouseUp={onUp} onDblClick={() => polyPts.length && closePoly()}
            onWheel={(e) => { e.evt.preventDefault(); setZoom((z) => Math.min(8, Math.max(0.05, z * (e.evt.deltaY > 0 ? 0.9 : 1.1)))) }}>
            <Layer listening={false}>{htmlImg && <KImage image={htmlImg} width={W} height={H} />}</Layer>
            <Layer>
              {anns.map((a) => {
                const color = cls(a.classId).color
                if (a.shape.kind === 'bbox') {
                  const s = a.shape
                  return <Rect key={a.id} id={a.id} x={s.x * W} y={s.y * H} width={s.w * W} height={s.h * H} stroke={color} strokeWidth={2 / zoom}
                    dash={isAi(a) ? [8 / zoom, 5 / zoom] : undefined}
                    fill={selId === a.id ? color + '22' : undefined} draggable={tool !== 'pan' && selId === a.id} onMouseDown={(e) => { if (tool === 'smart' || tool === 'polygon') return; e.cancelBubble = true; setSelId(a.id) }}
                    onDragEnd={(e) => editShape(a.id, { ...s, x: e.target.x() / W, y: e.target.y() / H })}
                    onTransformEnd={(e) => { const n = e.target; const sx = n.scaleX(), sy = n.scaleY(); n.scaleX(1); n.scaleY(1); editShape(a.id, { ...s, x: n.x() / W, y: n.y() / H, w: (s.w * sx), h: (s.h * sy) }) }} />
                }
                if (a.shape.kind === 'polygon') {
                  const s = a.shape
                  return <Line key={a.id} id={a.id} points={s.points.map((v, i) => v * (i % 2 ? H : W))} closed stroke={color} strokeWidth={2 / zoom}
                    dash={isAi(a) ? [8 / zoom, 5 / zoom] : undefined} fill={color + (selId === a.id ? '55' : '33')}
                    draggable={tool !== 'pan' && selId === a.id} onMouseDown={(e) => { if (tool === 'smart' || tool === 'polygon') return; e.cancelBubble = true; setSelId(a.id) }}
                    onDragEnd={(e) => { const dx = e.target.x(), dy = e.target.y(); e.target.position({ x: 0, y: 0 }); editShape(a.id, { ...s, points: s.points.map((v, i) => v + (i % 2 ? dy / H : dx / W)) }) }} />
                }
                return null
              })}
              {drawing && <Rect x={drawing.x} y={drawing.y} width={drawing.w} height={drawing.h} stroke={cls(selClass).color} strokeWidth={2 / zoom} dash={[6 / zoom, 4 / zoom]} />}
              {polyPts.length > 0 && <Line points={polyPts} stroke={cls(selClass).color} strokeWidth={2 / zoom} />}
              {polyPts.map((v, i) => i % 2 === 0 && <Circle key={i} x={v} y={polyPts[i + 1]} radius={4 / zoom} fill={cls(selClass).color} />)}
              {smartPts.map((v, i) => i % 2 === 0 && <Circle key={i} name="smart-pt" x={v} y={smartPts[i + 1]} radius={6 / zoom} fill={SMART} stroke="#fff" strokeWidth={1.5 / zoom}
                onClick={() => { const p = smartPts.slice(); p.splice(i, 2); setSmartPts(p) }} />)}
              {sel?.shape.kind === 'bbox' && <Transformer ref={trRef} rotateEnabled={false} ignoreStroke />}
            </Layer>
          </Stage>
          {isCls && (
            <div className="absolute left-1/2 top-3 -translate-x-1/2 rounded-full border bg-card px-3 py-1.5 text-xs shadow">
              {anns.length ? <>Labeled: <b>{anns.map((a) => cls(a.classId).name).join(', ')}</b></> : 'Pick a class on the left (or press 1–9)'}
            </div>
          )}
          {tool === 'smart' && (smartBusy || smartErr || smartPts.length > 0) && (
            <div className="absolute left-1/2 top-3 -translate-x-1/2">
              {smartBusy && <div className="flex items-center gap-1.5 rounded-full border bg-card px-3 py-1.5 text-xs shadow"><LoaderCircle className="h-3.5 w-3.5 animate-spin text-violet-600" /> Segmenting…</div>}
              {smartErr && <div className="flex items-center gap-1.5 rounded-full border border-destructive/40 bg-red-50 px-3 py-1.5 text-xs text-destructive shadow"><TriangleAlert className="h-3.5 w-3.5" /> {smartErr}</div>}
            </div>
          )}
          <div className="absolute right-3 top-1/2 flex -translate-y-1/2 flex-col items-center gap-0.5 rounded-xl border bg-card p-1 shadow-lg">
            {tools.map(({ id, icon: Icon, label }) => (
              <button key={id} onClick={() => setTool(id)} title={label} className={cn('cursor-pointer rounded-lg p-2', tool === id ? 'bg-accent text-accent-foreground' : 'text-muted-foreground hover:bg-muted')}><Icon className="h-4 w-4" /></button>
            ))}
            <div className="my-1 h-px w-6 bg-border" />
            <button onClick={undo} title="Undo (Ctrl+Z)" className="cursor-pointer rounded-lg p-2 text-muted-foreground hover:bg-muted"><Undo2 className="h-4 w-4" /></button>
            <button onClick={redo} title="Redo (Ctrl+Shift+Z)" className="cursor-pointer rounded-lg p-2 text-muted-foreground hover:bg-muted"><Redo2 className="h-4 w-4" /></button>
            <button onClick={() => selId && remove(selId)} title="Delete selected" className="cursor-pointer rounded-lg p-2 text-muted-foreground hover:bg-muted"><Ban className="h-4 w-4" /></button>
          </div>
          <div className="absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center rounded-full border bg-card px-3 py-1.5 text-xs shadow">
            <button onClick={() => setZoom((z) => Math.max(0.05, z / 1.2))} className="cursor-pointer px-1">−</button>
            <span className="w-12 text-center">{Math.round(zoom * 100)}%</span>
            <button onClick={() => setZoom((z) => Math.min(8, z * 1.2))} className="cursor-pointer px-1">+</button>
            <button onClick={fit} className="ml-1 cursor-pointer rounded px-1.5 text-muted-foreground hover:bg-accent">FIT</button>
          </div>
        </div>

        <div className="flex w-48 flex-col border-l">
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
                  {im.annotated && <span className="absolute right-1 top-1 flex h-4 w-4 items-center justify-center rounded-full bg-violet-600 text-white"><Check className="h-2.5 w-2.5" /></span>}
                </div>
                <div className="truncate px-1.5 py-1 text-[10px] text-muted-foreground">{im.name}</div>
              </Link>
            ))}
          </div>
        </div>
      </div>
      <ShortcutModal open={shortcuts} onClose={() => setShortcuts(false)} />
    </div>
  )
}
