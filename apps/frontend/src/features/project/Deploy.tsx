import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Copy, ImageUp, KeyRound } from 'lucide-react'
import { API_ORIGIN, api, upload } from '@/lib/api'
import type { Prediction } from '@/lib/types'
import { Button, Card, EmptyState, Field, PageHeader, Select, Tabs, toast } from '@/components/ui'
import { useProject } from './ProjectLayout'
import { headline } from './Models'

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
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState('')
  const [res, setRes] = useState<{ predictions: Prediction[]; image: { width: number; height: number }; time: number; top?: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const [lang, setLang] = useState('curl')

  const run = async (f = file, c = conf) => {
    if (!f || !mid) return
    setBusy(true)
    const fd = new FormData(); fd.append('file', f); fd.append('confidence', String(c / 100))
    try { setRes(await upload(`${api.P(ws, project.slug)}/models/${mid}/predict`, fd, () => {})) } catch (e) { toast.err(e as Error) } finally { setBusy(false) }
  }
  const pick = (f: File) => { setFile(f); setPreview(URL.createObjectURL(f)); run(f) }
  const endpoint = `${API_ORIGIN || location.origin}/api/v1/models/${mid}/predict`
  const snippets: Record<string, string> = {
    curl: `curl -X POST "${endpoint}?api_key=$LABELDESK_API_KEY&confidence=0.4" \\\n  -F "file=@image.jpg"`,
    python: `import requests\n\nr = requests.post(\n    "${endpoint}",\n    params={"api_key": API_KEY, "confidence": 0.4},\n    files={"file": open("image.jpg", "rb")},\n)\nfor p in r.json()["predictions"]:\n    print(p["class"], p["confidence"], p["x"], p["y"], p["width"], p["height"])`,
    javascript: `const form = new FormData()\nform.append('file', fileInput.files[0])\nconst r = await fetch('${endpoint}?api_key=' + API_KEY, { method: 'POST', body: form })\nconst { predictions } = await r.json()`,
    url: `# image by URL — no upload needed\ncurl -X POST "${endpoint}?api_key=$LABELDESK_API_KEY&image=https://example.com/photo.jpg"`,
  }
  const classIdx = (name: string) => Math.max(0, (model?.classes ?? []).indexOf(name))

  if (models.isSuccess && !ready.length) return <EmptyState title="No trained model to deploy yet." hint="Train a model, then test and call it here." />
  return (
    <div className="anim-page">
      <PageHeader title="Deploy & Test" desc="Try the model on your own images, then call it from any app with the hosted API."
        actions={<Select value={mid} onChange={(e) => { setMid(e.target.value); setRes(null) }}>{ready.map((m) => <option key={m.id} value={m.id}>{m.name} · {headline(m)}</option>)}</Select>} />
      <div className="grid gap-6 px-8 pb-10 xl:grid-cols-2">
        <Card className="p-4">
          <div className="mb-3 flex items-center gap-3">
            <label className="cursor-pointer"><input type="file" accept="image/*" hidden onChange={(e) => e.target.files?.[0] && pick(e.target.files[0])} />
              <span className="inline-flex h-9 items-center gap-1.5 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground"><ImageUp className="h-4 w-4" /> Upload test image</span></label>
            <div className="flex-1"><Field label={`Confidence ${conf}%`}><input type="range" min={1} max={99} value={conf} onChange={(e) => setConf(+e.target.value)} onMouseUp={() => run()} onKeyUp={() => run()} className="w-full accent-primary" /></Field></div>
          </div>
          <div className="relative flex min-h-72 items-center justify-center overflow-hidden rounded-lg border bg-muted"
            onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); e.dataTransfer.files[0] && pick(e.dataTransfer.files[0]) }}>
            {!preview && <p className="text-sm text-muted-foreground">Drop an image here</p>}
            {preview && (
              <div className="relative">
                <img src={preview} alt="test" className="max-h-[520px] w-auto" />
                {res && !res.top && (
                  <svg className="absolute inset-0 h-full w-full" viewBox={`0 0 ${res.image.width} ${res.image.height}`} preserveAspectRatio="none">
                    {res.predictions.map((p, i) => {
                      const c = COLORS[classIdx(p.class) % COLORS.length]
                      return (
                        <g key={i}>
                          {p.points ? <polygon points={p.points.map((q) => `${q.x},${q.y}`).join(' ')} fill={c + '40'} stroke={c} strokeWidth={res.image.width / 300} />
                            : <rect x={p.x - p.width / 2} y={p.y - p.height / 2} width={p.width} height={p.height} fill="none" stroke={c} strokeWidth={res.image.width / 300} />}
                          <text x={p.x - p.width / 2} y={p.y - p.height / 2 - 4} fill={c} fontSize={res.image.width / 45} fontWeight="bold">{p.class} {(p.confidence * 100).toFixed(0)}%</text>
                        </g>
                      )
                    })}
                  </svg>
                )}
              </div>
            )}
          </div>
          {res && (
            <div className="mt-3 text-sm">
              {res.top ? <p>Top class: <b>{res.top}</b></p> : <p><b>{res.predictions.length}</b> objects · {(res.time * 1000).toFixed(0)} ms</p>}
              <pre className="mt-2 max-h-56 overflow-auto rounded-lg bg-muted p-3 font-mono text-[11px]">{JSON.stringify(res, null, 2)}</pre>
            </div>
          )}
          {busy && <p className="mt-2 text-xs text-muted-foreground">Running inference…</p>}
        </Card>
        <div className="space-y-4">
          <Card className="p-4">
            <h3 className="mb-1 font-semibold">Hosted API</h3>
            <p className="mb-3 text-sm text-muted-foreground">Authenticate with a workspace API key. Each call uses 0.001 credits.
              <Link to={`/${ws}/settings/api`} className="ml-1 inline-flex items-center gap-1 text-primary hover:underline"><KeyRound className="h-3.5 w-3.5" /> Manage API keys</Link></p>
            <Tabs tabs={[{ id: 'curl', label: 'cURL' }, { id: 'python', label: 'Python' }, { id: 'javascript', label: 'JavaScript' }, { id: 'url', label: 'Image URL' }]} active={lang} onChange={setLang} />
            <div className="relative">
              <pre className="mt-3 overflow-x-auto rounded-lg bg-sidebar p-4 font-mono text-xs text-sidebar-foreground">{snippets[lang]}</pre>
              <button className="absolute right-2 top-2 cursor-pointer rounded p-1 text-sidebar-foreground/70 hover:text-white" onClick={() => { navigator.clipboard.writeText(snippets[lang]); toast.ok('Copied') }} aria-label="Copy"><Copy className="h-4 w-4" /></button>
            </div>
          </Card>
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
