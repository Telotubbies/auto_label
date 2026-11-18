import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Copy, ImageUp, KeyRound } from 'lucide-react'
import { API_ORIGIN, api, fileUrl, upload } from '@/lib/api'
import { projectPath } from '@/lib/routes'
import type { Prediction } from '@/lib/types'
import { Button, Card, EmptyState, Field, PageHeader, Select, toast } from '@/components/ui'
import { useProject } from './ProjectLayout'
import { headline } from './Models'
import { Deployments } from './Deployments'

const COLORS = ['#8b5cf6', '#22c55e', '#3b82f6', '#f97316', '#ec4899', '#eab308', '#14b8a6', '#ef4444']

export default function Deploy() {
  const { project, ws } = useProject()
  const [sp] = useSearchParams()
  const models = useQuery({ queryKey: ['models', ws, project.slug], queryFn: () => api.models(ws, project.slug) })
  const ready = (models.data ?? []).filter((m) => m.status === 'ready')
  const [mid, setMid] = useState(sp.get('model') ?? '')
  useEffect(() => { if (!mid && ready[0]) setMid(ready[0].id) }, [ready, mid])
  const model = ready.find((m) => m.id === mid)
  const [conf, setConf] = useState(40)
  const [overlap, setOverlap] = useState(50)
  const [opacity, setOpacity] = useState(25)
  const [labelMode, setLabelMode] = useState<'conf' | 'name' | 'none'>('conf')
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState('')
  const [res, setRes] = useState<{ predictions: Prediction[]; image: { width: number; height: number }; time: number; top?: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const testSet = useQuery({ queryKey: ['test-set', ws, project.slug], queryFn: () => api.images(ws, project.slug, { split: 'test', limit: 6 }) })

  const run = async (f = file) => {
    if (!f || !mid) return
    setBusy(true)
    const fd = new FormData(); fd.append('file', f); fd.append('confidence', String(conf / 100)); fd.append('overlap', String(overlap / 100))
    try { setRes(await upload(`${api.P(ws, project.slug)}/models/${mid}/predict`, fd, () => {})) } catch (e) { toast.err(e as Error) } finally { setBusy(false) }
  }
  const pick = (f: File) => { setFile(f); setPreview(URL.createObjectURL(f)); run(f) }
  const pickUrl = (url: string, name: string) => fetch(fileUrl(url)).then((r) => r.blob()).then((b) => pick(new File([b], name, { type: b.type }))).catch(toast.err)
  const endpoint = `${API_ORIGIN || location.origin}/api/v1/models/${mid}/predict`
  const classIdx = (name: string) => Math.max(0, (model?.classes ?? []).indexOf(name))

  if (models.isSuccess && !ready.length) return <EmptyState title="No trained model to deploy yet." hint="Train a model, then test and call it here." />
  return (
    <div className="anim-page">
      <PageHeader title="Deploy & Test" desc="Try the model on your own images, then call it from any app with the hosted API."
        actions={<div className="flex items-center gap-2">
          <Select aria-label="Switch model" value={mid} onChange={(e) => { setMid(e.target.value); setRes(null) }}>{ready.map((m) => <option key={m.id} value={m.id}>{m.name} · {headline(m)}</option>)}</Select>
          <Button variant="outline" disabled={!mid} onClick={() => api.setDeployment(ws, project.slug, 'production', mid).then(() => toast.ok('Set as default (production)')).catch(toast.err)}>Set as default</Button>
        </div>} />
      <div className="grid gap-4 px-8 pb-6 lg:grid-cols-[16rem_1fr_18rem]">
        <Card className="space-y-3 p-4">
          <div className="flex items-center justify-between"><h3 className="text-sm font-semibold">Test set</h3>
            <Link to={projectPath(ws, project.slug, 'browse?split=test')} className="text-xs text-primary hover:underline">View test set</Link></div>
          <div className="grid grid-cols-3 gap-1.5">
            {(testSet.data?.items ?? []).map((im) => (
              <button key={im.id} type="button" aria-label={`Test ${im.name}`} onClick={() => pickUrl(im.url, im.name)} className="cursor-pointer overflow-hidden rounded border hover:ring-2 hover:ring-primary">
                <img src={fileUrl(im.thumbnail)} alt={im.name} loading="lazy" className="aspect-square w-full object-cover" />
              </button>
            ))}
            {testSet.isSuccess && !testSet.data.items.length && <p className="col-span-3 text-xs text-muted-foreground">No test images yet.</p>}
          </div>
          <label className="flex cursor-pointer flex-col items-center gap-1 rounded-lg border-2 border-dashed p-4 text-center text-sm text-muted-foreground hover:border-primary"
            onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); e.dataTransfer.files[0] && pick(e.dataTransfer.files[0]) }}>
            <ImageUp className="h-5 w-5" />
            <span>Drop files or <span className="text-primary underline">Select files</span></span>
            <input type="file" accept="image/*" hidden onChange={(e) => e.target.files?.[0] && pick(e.target.files[0])} />
          </label>
        </Card>
        <Card className="p-4">
          <div className="relative flex min-h-72 items-center justify-center overflow-hidden rounded-lg border bg-muted">
            {!preview && <p className="text-sm text-muted-foreground">Pick a test image or drop one</p>}
            {preview && (
              <div className="relative">
                <img src={preview} alt="test" className="max-h-[520px] w-auto" />
                {res && !res.top && (
                  <svg className="absolute inset-0 h-full w-full" viewBox={`0 0 ${res.image.width} ${res.image.height}`} preserveAspectRatio="none">
                    {res.predictions.map((p, i) => {
                      const c = COLORS[classIdx(p.class) % COLORS.length]
                      return (
                        <g key={i}>
                          {p.points ? <polygon points={p.points.map((q) => `${q.x},${q.y}`).join(' ')} fill={c} fillOpacity={opacity / 100} stroke={c} strokeWidth={res.image.width / 300} />
                            : <rect x={p.x - p.width / 2} y={p.y - p.height / 2} width={p.width} height={p.height} fill={c} fillOpacity={opacity / 100} stroke={c} strokeWidth={res.image.width / 300} />}
                          {labelMode !== 'none' && <text x={p.x - p.width / 2} y={p.y - p.height / 2 - 4} fill={c} fontSize={res.image.width / 45} fontWeight="bold">{labelMode === 'name' ? p.class : `${p.class} ${(p.confidence * 100).toFixed(0)}%`}</text>}
                        </g>
                      )
                    })}
                  </svg>
                )}
              </div>
            )}
            {res && <span data-testid="detected-pill" className="absolute bottom-2 right-2 rounded-full bg-card px-3 py-1 text-xs font-medium shadow">{res.top ? `Top class: ${res.top}` : `${res.predictions.length} objects detected`}</span>}
          </div>
          {busy && <p className="mt-2 text-xs text-muted-foreground">Running inference…</p>}
        </Card>
        <Card className="space-y-3 p-4">
          <h3 className="text-sm font-semibold">Model visualizations</h3>
          <Field label={`Confidence ${conf}%`}><input type="range" min={1} max={99} value={conf} onChange={(e) => setConf(+e.target.value)} onMouseUp={() => run()} onKeyUp={() => run()} className="w-full accent-primary" /></Field>
          <Field label={`Overlap ${overlap}%`}><input type="range" min={1} max={99} value={overlap} onChange={(e) => setOverlap(+e.target.value)} onMouseUp={() => run()} onKeyUp={() => run()} className="w-full accent-primary" /></Field>
          <Field label={`Opacity ${opacity}%`}><input type="range" min={0} max={100} value={opacity} onChange={(e) => setOpacity(+e.target.value)} className="w-full accent-primary" /></Field>
          <Field label="Label display"><Select className="w-full" value={labelMode} onChange={(e) => setLabelMode(e.target.value as 'conf' | 'name' | 'none')}><option value="conf">Name and confidence</option><option value="name">Name only</option><option value="none">Hidden</option></Select></Field>
          {res && (
            <div>
              <div className="mb-1 flex items-center justify-between text-xs"><span className="font-semibold">Output JSON</span>
                <button className="cursor-pointer rounded p-1 text-muted-foreground hover:text-foreground" onClick={() => { navigator.clipboard.writeText(JSON.stringify(res, null, 2)); toast.ok('Copied') }} aria-label="Copy JSON"><Copy className="h-3.5 w-3.5" /></button></div>
              <pre className="max-h-56 overflow-auto rounded-lg bg-muted p-3 font-mono text-[11px]">{JSON.stringify(res, null, 2)}</pre>
              <p className="mt-1 text-xs text-muted-foreground">{(res.time * 1000).toFixed(0)} ms</p>
            </div>
          )}
        </Card>
      </div>
      <Deployments ws={ws} project={project.slug} endpoint={endpoint} />
      <div className="grid gap-4 px-8 pb-10 xl:grid-cols-2">
        <Card className="h-fit p-4 text-sm">
          <h3 className="mb-1 font-semibold">API keys</h3>
          <p className="text-muted-foreground">Authenticate with a workspace API key. Each call uses 0.001 credits.
            <Link to={`/${ws}/settings/api`} className="ml-1 inline-flex items-center gap-1 text-primary hover:underline"><KeyRound className="h-3.5 w-3.5" /> Manage API keys</Link></p>
        </Card>
        <div className="space-y-4">
          <Card className="p-4 text-sm">
            <h3 className="mb-1 font-semibold">Response format</h3>
            <pre className="overflow-x-auto rounded-lg bg-muted p-3 font-mono text-xs">{`{
  "predictions": [
    { "x": 320.5, "y": 210.0, "width": 80.2, "height": 120.4,
      "confidence": 0.91, "class": "${model?.classes[0] ?? 'object'}", "class_id": 0 }
  ],
  "image": { "width": 1280, "height": 720 },
  "time": 0.042
}`}</pre>
            <p className="mt-2 text-muted-foreground">
              Boxes are centre-based pixels. Segmentation models add <code>points</code>. Weights from the Ultralytics
              families (YOLO, RT-DETR, YOLO-World) are licensed under{' '}
              <a href="https://github.com/ultralytics/ultralytics" className="text-primary hover:underline">
                AGPL-3.0
              </a>
              , so self-hosting them carries that licence&apos;s obligations. Download the weights on the Models page,
              keep the{' '}
              <a href="https://github.com/ultralytics/ultralytics" className="text-primary hover:underline">
                Corresponding Source
              </a>{' '}
              with your deployment, and ship the notices in{' '}
              <a href="/licenses.txt" className="text-primary hover:underline">licenses.txt</a>.
            </p>
          </Card>
          <Card className="p-4 text-sm">
            <h3 className="mb-1 font-semibold">Upload API</h3>
            <pre className="overflow-x-auto rounded-lg bg-muted p-3 font-mono text-xs">{`curl -X POST "${API_ORIGIN || location.origin}/api/v1/${ws}/${project.slug}/upload?api_key=$KEY&split=train&tag=field" \\\n  -F "file=@new.jpg"`}</pre>
          </Card>
        </div>
      </div>
    </div>
  )
}
