import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { BrainCircuit, Cpu } from 'lucide-react'
import { api, get, post } from '@/lib/api'
import type { ModelItem, TrainOptions } from '@/lib/types'
import { Badge, Button, Card, EmptyState, Field, Input, PageHeader, Select, toast } from '@/components/ui'
import { cn } from '@/lib/utils'
import { useProject } from './ProjectLayout'

export default function Train() {
  const { project, ws } = useProject()
  const [sp] = useSearchParams()
  const nav = useNavigate()
  const qc = useQueryClient()
  const versions = useQuery({ queryKey: ['versions', ws, project.slug], queryFn: () => api.versions(ws, project.slug) })
  const opts = useQuery({ queryKey: ['train-opts', ws, project.slug], queryFn: () => get<TrainOptions>(`${api.P(ws, project.slug)}/train/options`) })
  const models = useQuery({ queryKey: ['models', ws, project.slug], queryFn: () => api.models(ws, project.slug) })
  const ready = (versions.data ?? []).filter((v) => v.status === 'ready')
  const [f, setF] = useState({ version_id: sp.get('version') ?? '', family: 'yolo', variant: 'yolo26n', epochs: 50, imgsz: 640, batch: 16, name: '', max_minutes: '', resume_from: '' })
  const fams = opts.data?.families ?? []
  const fam = fams.find((x) => x.family === f.family)
  const resumable = (models.data ?? []).filter((m) => m.status === 'ready' && m.task === opts.data?.task)
  const pickFamily = (id: string) => { const n = fams.find((x) => x.family === id); if (n?.available) setF({ ...f, family: id, variant: n.variants[0].id, resume_from: '' }) }
  const pickResume = (id: string) => {
    const m = resumable.find((x) => x.id === id)
    const g = m && fams.find((x) => x.variants.some((v) => m.variant && (v.id === m.variant || m.variant.startsWith(v.id))))
    setF(m && g ? { ...f, resume_from: id, family: g.family, variant: g.variants.find((v) => m.variant?.startsWith(v.id))!.id } : { ...f, resume_from: '' })
  }
  useEffect(() => { if (!f.version_id && ready[0]) setF((x) => ({ ...x, version_id: ready[0].id })) }, [ready, f.version_id])
  const start = async () => {
    try {
      const { family: _ui, max_minutes, resume_from, ...rest } = f
      const body = { ...rest, family: 'ultralytics', max_minutes: max_minutes ? +max_minutes : null, resume_from: resume_from || null }
      const m = await post<ModelItem>(`${api.P(ws, project.slug)}/train`, body)
      qc.invalidateQueries({ queryKey: ['models', ws, project.slug] }); toast.ok('Training queued'); nav(`../models?model=${m.id}`)
    } catch (e) { toast.err(e as Error) }
  }
  if (opts.data && !opts.data.supported) return <EmptyState title="Training isn't available" hint={opts.data.reason} />
  return (
    <div className="anim-page max-w-4xl">
      <PageHeader title="Train a Model" desc="Fine-tune a YOLO, RT-DETR or YOLO-World model on a dataset version. Training runs on the worker — your GPU box, Kaggle or Colab." />
      <div className="space-y-4 px-8 pb-10">
        {versions.isSuccess && !ready.length ? (
          <EmptyState title="Generate a version first" hint="Models train on a frozen dataset version." action={<Button size="sm" onClick={() => nav('../versions')}>Go to Versions</Button>} />
        ) : (
          <>
            <Card className="p-5">
              <h3 className="mb-3 font-semibold">1. Dataset version</h3>
              <Select className="w-full" value={f.version_id} onChange={(e) => setF({ ...f, version_id: e.target.value })}>
                {ready.map((v) => <option key={v.id} value={v.id}>{v.name} — {v.stats.images} images ({v.stats.splits?.train ?? 0} train / {v.stats.splits?.valid ?? 0} valid)</option>)}
              </Select>
            </Card>
            <Card className="p-5">
              <h3 className="mb-3 font-semibold">2. Model family</h3>
              <div className="grid gap-2 md:grid-cols-3" role="radiogroup" aria-label="Model family">
                {fams.map((x) => (
                  <button key={x.family} role="radio" aria-checked={f.family === x.family} disabled={!x.available} title={x.available ? undefined : x.reason}
                    onClick={() => pickFamily(x.family)}
                    className={cn('rounded-lg border p-3 text-left text-sm', x.available ? 'cursor-pointer' : 'cursor-not-allowed opacity-50', f.family === x.family ? 'border-primary bg-accent/40' : x.available && 'hover:bg-muted')}>
                    <div className="flex items-center justify-between gap-2"><span className="font-semibold">{x.label}</span><Badge>{x.license}</Badge></div>
                    {!x.available && <div className="mt-1 text-xs text-muted-foreground">{x.reason}</div>}
                  </button>
                ))}
              </div>
              <div className="mt-3 flex flex-wrap gap-2" role="radiogroup" aria-label="Variant">
                {fam?.variants.map((v) => (
                  <button key={v.id} role="radio" aria-checked={f.variant === v.id} title={v.weights} onClick={() => setF({ ...f, variant: v.id, resume_from: '' })}
                    className={cn('cursor-pointer rounded-full border px-3 py-1 text-xs', f.variant === v.id ? 'border-primary bg-accent/40 font-semibold' : 'hover:bg-muted')}>{v.label}</button>
                ))}
              </div>
              {fam && <p className="mt-3 text-xs text-muted-foreground">Weights: <span className="font-mono">{fam.variants.find((v) => v.id === f.variant)?.weights}</span></p>}
            </Card>
            <Card className="p-5">
              <h3 className="mb-3 font-semibold">3. Hyperparameters</h3>
              <div className="grid gap-4 md:grid-cols-4">
                <Field label="Epochs"><Input type="number" min={1} max={500} value={f.epochs} onChange={(e) => setF({ ...f, epochs: +e.target.value })} /></Field>
                <Field label="Image size"><Select className="w-full" value={f.imgsz} onChange={(e) => setF({ ...f, imgsz: +e.target.value })}>{[320, 416, 512, 640, 800, 1024].map((n) => <option key={n}>{n}</option>)}</Select></Field>
                <Field label="Batch"><Select className="w-full" value={f.batch} onChange={(e) => setF({ ...f, batch: +e.target.value })}>{[2, 4, 8, 16, 32, 64].map((n) => <option key={n}>{n}</option>)}</Select></Field>
                <Field label="Name (optional)"><Input value={f.name} placeholder={`${project.slug}/…`} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
                <Field label="Max minutes (optional)"><Input type="number" min={1} value={f.max_minutes} placeholder="no limit" onChange={(e) => setF({ ...f, max_minutes: e.target.value })} /></Field>
                <Field label="Continue from model (optional)">
                  <Select className="w-full" value={f.resume_from} onChange={(e) => pickResume(e.target.value)}>
                    <option value="">Start from pretrained</option>
                    {resumable.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
                  </Select>
                </Field>
              </div>
              <p className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground"><Cpu className="h-3.5 w-3.5" /> Costs 3 credits. Starts from COCO-pretrained weights (transfer learning). The max-minutes cap stops training after the current epoch and keeps the best weights.</p>
            </Card>
            <div className="flex justify-end"><Button size="md" disabled={!f.version_id} onClick={start}><BrainCircuit className="h-4 w-4" /> Start Training</Button></div>
          </>
        )}
      </div>
    </div>
  )
}
