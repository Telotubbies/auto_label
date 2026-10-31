import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { BrainCircuit, Cpu } from 'lucide-react'
import { api, get, post } from '@/lib/api'
import type { ModelItem } from '@/lib/types'
import { Button, Card, EmptyState, Field, Input, PageHeader, Select, toast } from '@/components/ui'
import { cn } from '@/lib/utils'
import { useProject } from './ProjectLayout'

type Options = { supported: boolean; reason?: string; task?: string; sizes?: { id: string; label: string; weights: string }[] }

export default function Train() {
  const { project, ws } = useProject()
  const [sp] = useSearchParams()
  const nav = useNavigate()
  const qc = useQueryClient()
  const versions = useQuery({ queryKey: ['versions', ws, project.slug], queryFn: () => api.versions(ws, project.slug) })
  const opts = useQuery({ queryKey: ['train-opts', ws, project.slug], queryFn: () => get<Options>(`${api.P(ws, project.slug)}/train/options`) })
  const ready = (versions.data ?? []).filter((v) => v.status === 'ready')
  const [f, setF] = useState({ version_id: sp.get('version') ?? '', size: 'n', epochs: 50, imgsz: 640, batch: 16, name: '' })
  useEffect(() => { if (!f.version_id && ready[0]) setF((x) => ({ ...x, version_id: ready[0].id })) }, [ready, f.version_id])
  const start = async () => {
    try {
      const m = await post<ModelItem>(`${api.P(ws, project.slug)}/train`, f)
      qc.invalidateQueries({ queryKey: ['models', ws, project.slug] }); toast.ok('Training queued'); nav(`../models?model=${m.id}`)
    } catch (e) { toast.err(e as Error) }
  }
  if (opts.data && !opts.data.supported) return <EmptyState title="Training isn't available" hint={opts.data.reason} />
  return (
    <div className="anim-page max-w-4xl">
      <PageHeader title="Train a Model" desc="Fine-tune a YOLO model on a dataset version. Training runs on the worker — your GPU box, Kaggle or Colab." />
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
              <h3 className="mb-3 font-semibold">2. Model size</h3>
              <div className="grid gap-2 md:grid-cols-5">
                {opts.data?.sizes?.map((s) => (
                  <button key={s.id} onClick={() => setF({ ...f, size: s.id })} className={cn('cursor-pointer rounded-lg border p-3 text-left text-sm', f.size === s.id ? 'border-primary bg-accent/40' : 'hover:bg-muted')}>
                    <div className="font-semibold uppercase">{s.id}</div><div className="text-xs text-muted-foreground">{s.label}</div>
                    <div className="mt-1 truncate font-mono text-[10px] text-muted-foreground">{s.weights}</div>
                  </button>
                ))}
              </div>
            </Card>
            <Card className="p-5">
              <h3 className="mb-3 font-semibold">3. Hyperparameters</h3>
              <div className="grid gap-4 md:grid-cols-4">
                <Field label="Epochs"><Input type="number" min={1} max={500} value={f.epochs} onChange={(e) => setF({ ...f, epochs: +e.target.value })} /></Field>
                <Field label="Image size"><Select className="w-full" value={f.imgsz} onChange={(e) => setF({ ...f, imgsz: +e.target.value })}>{[320, 416, 512, 640, 800, 1024].map((n) => <option key={n}>{n}</option>)}</Select></Field>
                <Field label="Batch"><Select className="w-full" value={f.batch} onChange={(e) => setF({ ...f, batch: +e.target.value })}>{[2, 4, 8, 16, 32, 64].map((n) => <option key={n}>{n}</option>)}</Select></Field>
                <Field label="Name (optional)"><Input value={f.name} placeholder={`${project.slug}/…`} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
              </div>
              <p className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground"><Cpu className="h-3.5 w-3.5" /> Costs 3 credits. Starts from COCO-pretrained weights (transfer learning).</p>
            </Card>
            <div className="flex justify-end"><Button size="md" disabled={!f.version_id} onClick={start}><BrainCircuit className="h-4 w-4" /> Start Training</Button></div>
          </>
        )}
      </div>
    </div>
  )
}
