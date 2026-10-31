import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, FolderGit2, Plus, Trash2 } from 'lucide-react'
import { api, del, fileUrl, post } from '@/lib/api'
import { useApp } from '@/lib/store'
import type { Version } from '@/lib/types'
import { Badge, Button, Card, EmptyState, Field, Input, Modal, PageHeader, Progress, Select, StatusPill, Switch, fmtDate, toast } from '@/components/ui'
import { cn } from '@/lib/utils'
import { useProject } from './ProjectLayout'

const AUGS: { key: string; label: string; kind: 'bool' | 'range'; max?: number; unit?: string }[] = [
  { key: 'flip_h', label: 'Horizontal flip', kind: 'bool' },
  { key: 'flip_v', label: 'Vertical flip', kind: 'bool' },
  { key: 'rotate90', label: '90° rotate', kind: 'bool' },
  { key: 'rotation', label: 'Rotation', kind: 'range', max: 45, unit: '°' },
  { key: 'brightness', label: 'Brightness', kind: 'range', max: 50, unit: '%' },
  { key: 'exposure', label: 'Exposure', kind: 'range', max: 50, unit: '%' },
  { key: 'saturation', label: 'Saturation', kind: 'range', max: 80, unit: '%' },
  { key: 'blur', label: 'Blur', kind: 'range', max: 5, unit: 'px' },
  { key: 'noise', label: 'Noise', kind: 'range', max: 10, unit: '%' },
  { key: 'grayscale_pct', label: 'Grayscale', kind: 'range', max: 50, unit: '% of images' },
]

function Generate({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { project, ws } = useProject()
  const qc = useQueryClient()
  const [step, setStep] = useState(0)
  const [name, setName] = useState('')
  const [rebalance, setRebalance] = useState(false)
  const [split, setSplit] = useState({ train: 70, valid: 20, test: 10 })
  const [pre, setPre] = useState({ resize: true, w: 640, h: 640, mode: 'stretch', grayscale: false, contrast: false, filter_null: false })
  const [aug, setAug] = useState<Record<string, number | boolean>>({ outputs: 3 })
  const dataset = project.statusCounts?.done ?? 0
  const create = async () => {
    try {
      await post(`${api.P(ws, project.slug)}/versions`, {
        name, settings: {
          split: rebalance ? split : null,
          preprocessing: { ...(pre.resize ? { resize: { width: pre.w, height: pre.h, mode: pre.mode } } : {}), grayscale: pre.grayscale, contrast: pre.contrast, filter_null: pre.filter_null },
          augmentation: aug,
        },
      })
      qc.invalidateQueries({ queryKey: ['versions', ws, project.slug] }); toast.ok('Generating version…'); onClose(); setStep(0)
    } catch (e) { toast.err(e as Error) }
  }
  const steps = ['Source', 'Train/Test Split', 'Preprocessing', 'Augmentation', 'Create']
  const anyAug = Object.entries(aug).some(([k, v]) => k !== 'outputs' && v)
  return (
    <Modal open={open} onClose={onClose} wide title="Generate a dataset version">
      <div className="mb-5 flex gap-2">
        {steps.map((s, i) => <button key={s} onClick={() => setStep(i)} className={cn('flex-1 cursor-pointer border-b-2 pb-2 text-left text-xs font-medium', i === step ? 'border-primary text-primary' : i < step ? 'border-primary/40' : 'border-border text-muted-foreground')}>{i + 1}. {s}</button>)}
      </div>
      {step === 0 && <div className="text-sm"><p><b>{dataset}</b> approved images will be frozen into this version.</p><p className="mt-2 text-muted-foreground">Only images in the Dataset column of the Annotate board are included. Versions never change once generated, so trained models stay reproducible.</p></div>}
      {step === 1 && (
        <div className="space-y-4 text-sm">
          <label className="flex items-center gap-2"><Switch checked={rebalance} onChange={setRebalance} /> Rebalance splits (otherwise each image keeps its current split)</label>
          {rebalance && (
            <div className="grid grid-cols-3 gap-3">
              {(['train', 'valid', 'test'] as const).map((k) => (
                <Field key={k} label={`${k} %`}><Input type="number" min={0} max={100} value={split[k]} onChange={(e) => setSplit({ ...split, [k]: +e.target.value })} /></Field>
              ))}
              {split.train + split.valid + split.test !== 100 && <p className="col-span-3 text-xs text-destructive">Percentages must add to 100.</p>}
            </div>
          )}
        </div>
      )}
      {step === 2 && (
        <div className="space-y-3 text-sm">
          <label className="flex items-center gap-2"><Switch checked={pre.resize} onChange={(v) => setPre({ ...pre, resize: v })} /> Resize</label>
          {pre.resize && (
            <div className="grid grid-cols-3 gap-3 pl-11">
              <Field label="Width"><Input type="number" value={pre.w} onChange={(e) => setPre({ ...pre, w: +e.target.value })} /></Field>
              <Field label="Height"><Input type="number" value={pre.h} onChange={(e) => setPre({ ...pre, h: +e.target.value })} /></Field>
              <Field label="Mode"><Select className="w-full" value={pre.mode} onChange={(e) => setPre({ ...pre, mode: e.target.value })}><option value="stretch">Stretch to</option><option value="fit">Fit (black edges)</option></Select></Field>
            </div>
          )}
          <label className="flex items-center gap-2"><Switch checked={pre.grayscale} onChange={(v) => setPre({ ...pre, grayscale: v })} /> Grayscale</label>
          <label className="flex items-center gap-2"><Switch checked={pre.contrast} onChange={(v) => setPre({ ...pre, contrast: v })} /> Auto-adjust contrast</label>
          <label className="flex items-center gap-2"><Switch checked={pre.filter_null} onChange={(v) => setPre({ ...pre, filter_null: v })} /> Drop images with no annotations</label>
        </div>
      )}
      {step === 3 && (
        <div className="text-sm">
          <p className="mb-3 text-muted-foreground">Augmentations apply to the training split only.</p>
          <div className="grid gap-3 md:grid-cols-2">
            {AUGS.map((a) => (
              <div key={a.key} className="rounded-lg border p-3">
                {a.kind === 'bool'
                  ? <label className="flex items-center gap-2"><Switch checked={!!aug[a.key]} onChange={(v) => setAug({ ...aug, [a.key]: v })} /> {a.label}</label>
                  : <Field label={`${a.label}: ±${aug[a.key] ?? 0}${a.unit}`}><input type="range" min={0} max={a.max} value={Number(aug[a.key] ?? 0)} onChange={(e) => setAug({ ...aug, [a.key]: +e.target.value })} className="w-full accent-primary" /></Field>}
              </div>
            ))}
          </div>
          <div className="mt-4 max-w-xs"><Field label="Outputs per training example" hint="3 = original + 2 augmented copies"><Select className="w-full" value={String(aug.outputs)} onChange={(e) => setAug({ ...aug, outputs: +e.target.value })}>{[1, 2, 3, 4, 5].map((n) => <option key={n}>{n}</option>)}</Select></Field></div>
        </div>
      )}
      {step === 4 && (
        <div className="space-y-3 text-sm">
          <Field label="Version name (optional)"><Input placeholder={`v${'{n}'}`} value={name} onChange={(e) => setName(e.target.value)} /></Field>
          <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
            <li>{dataset} source images{rebalance ? `, rebalanced ${split.train}/${split.valid}/${split.test}` : ', existing splits'}</li>
            <li>{pre.resize ? `Resize ${pre.w}×${pre.h} (${pre.mode})` : 'No resize'}{pre.grayscale ? ', grayscale' : ''}</li>
            <li>{anyAug ? `Augmented ×${aug.outputs}: ${AUGS.filter((a) => aug[a.key]).map((a) => a.label).join(', ')}` : 'No augmentation'}</li>
          </ul>
        </div>
      )}
      <div className="mt-6 flex justify-between border-t pt-4">
        <Button variant="ghost" disabled={step === 0} onClick={() => setStep(step - 1)}>Back</Button>
        {step < 4 ? <Button onClick={() => setStep(step + 1)}>Continue</Button>
          : <Button disabled={!dataset || (rebalance && split.train + split.valid + split.test !== 100)} onClick={create}>Create Version</Button>}
      </div>
    </Modal>
  )
}

function VersionDetail({ v }: { v: Version }) {
  const { project, ws } = useProject()
  const qc = useQueryClient()
  const nav = useNavigate()
  const can = useApp((s) => s.can)
  const formats = useQuery({ queryKey: ['formats', ws, project.slug], queryFn: () => api.formats(ws, project.slug) })
  const [fmt, setFmt] = useState('')
  useEffect(() => { if (!fmt && formats.data?.[0]) setFmt(formats.data[0].id) }, [formats.data, fmt])
  const exp = v.exports[fmt]
  const doExport = () => post(`${api.P(ws, project.slug)}/versions/${v.id}/export`, { format: fmt })
    .then(() => qc.invalidateQueries({ queryKey: ['versions', ws, project.slug] })).catch(toast.err)
  const s = v.stats
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div><h2 className="text-xl font-bold">{v.name}</h2><p className="text-sm text-muted-foreground">Generated {fmtDate(v.created)}</p></div>
        <div className="flex gap-2">
          {v.status === 'ready' && can('admin') && <Button onClick={() => nav(`../train?version=${v.id}`)}>Train a model</Button>}
          {can('admin') && <Button variant="ghost" size="icon" onClick={() => confirm('Delete this version?') && del(`${api.P(ws, project.slug)}/versions/${v.id}`).then(() => qc.invalidateQueries({ queryKey: ['versions', ws, project.slug] })).catch(toast.err)}><Trash2 className="h-4 w-4" /></Button>}
        </div>
      </div>
      {v.status !== 'ready' && (
        <Card className="p-4">
          <div className="mb-2 flex items-center gap-2 text-sm"><StatusPill status={v.status} /> {v.job?.status === 'failed' ? v.job.error : 'Processing images…'}</div>
          {v.status !== 'failed' && <Progress value={v.job?.progress ?? 0} />}
        </Card>
      )}
      {v.status === 'ready' && (
        <>
          <div className="grid gap-3 md:grid-cols-4">
            <Card className="p-4"><div className="text-xs text-muted-foreground">Total images</div><div className="text-2xl font-bold">{s.images}</div><div className="text-xs text-muted-foreground">from {s.source_images} source</div></Card>
            {(['train', 'valid', 'test'] as const).map((k) => <Card key={k} className="p-4"><div className="text-xs capitalize text-muted-foreground">{k} set</div><div className="text-2xl font-bold">{s.splits?.[k] ?? 0}</div><div className="text-xs text-muted-foreground">{Math.round(((s.splits?.[k] ?? 0) / (s.images || 1)) * 100)}%</div></Card>)}
          </div>
          <Card className="p-4 text-sm">
            <h3 className="mb-2 font-semibold">Settings</h3>
            <div className="grid gap-2 md:grid-cols-2">
              <div><span className="text-muted-foreground">Preprocessing: </span>{Object.entries(v.settings.preprocessing ?? {}).filter(([, x]) => x).map(([k, x]) => k === 'resize' ? `resize ${(x as any).width}×${(x as any).height} ${(x as any).mode}` : k).join(', ') || 'none'}</div>
              <div><span className="text-muted-foreground">Augmentation: </span>{Object.entries(v.settings.augmentation ?? {}).filter(([k, x]) => x && k !== 'outputs').map(([k, x]) => (x === true ? k : `${k} ${x}`)).join(', ') || 'none'}</div>
            </div>
            <div className="mt-2 flex flex-wrap gap-1">{Object.entries(s.classes ?? {}).map(([c, n]) => <Badge key={c}>{c}: {n}</Badge>)}</div>
          </Card>
          <Card className="p-4">
            <h3 className="mb-3 font-semibold">Download dataset</h3>
            <div className="flex flex-wrap items-center gap-2">
              <Select value={fmt} onChange={(e) => setFmt(e.target.value)}>{formats.data?.map((f) => <option key={f.id} value={f.id}>{f.label}</option>)}</Select>
              {exp?.status === 'done' && exp.url
                ? <a href={fileUrl(exp.url)}><Button><Download className="h-4 w-4" /> Download zip ({((exp.result.bytes ?? 0) / 1e6).toFixed(1)} MB)</Button></a>
                : exp && ['queued', 'running'].includes(exp.status) ? <div className="flex w-56 items-center gap-2 text-sm"><Progress value={exp.progress || 10} /> Exporting…</div>
                  : <Button onClick={doExport}>Export</Button>}
              {exp?.status === 'failed' && <span className="text-sm text-destructive">{exp.error}</span>}
            </div>
            <pre className="mt-3 overflow-x-auto rounded-lg bg-muted p-3 font-mono text-xs">{`# Python — after export, download straight from the signed link
import requests, zipfile, io
z = requests.get("${exp?.url ? fileUrl(exp.url) : '<export link>'}").content
zipfile.ZipFile(io.BytesIO(z)).extractall("${project.slug}-v${v.number}")`}</pre>
          </Card>
        </>
      )}
    </div>
  )
}

export default function Versions() {
  const { project, ws } = useProject()
  const versions = useQuery({ queryKey: ['versions', ws, project.slug], queryFn: () => api.versions(ws, project.slug),
    refetchInterval: (q) => q.state.data?.some((v) => ['queued', 'generating'].includes(v.status) || Object.values(v.exports).some((e) => ['queued', 'running'].includes(e.status))) ? 1500 : false })
  const [open, setOpen] = useState(false)
  const [selId, setSelId] = useState<string | null>(null)
  const list = versions.data ?? []
  const sel = list.find((v) => v.id === selId) ?? list[0]
  return (
    <div className="anim-page">
      <PageHeader title="Versions" desc="Frozen snapshots of your dataset with preprocessing and augmentation." actions={<Button onClick={() => setOpen(true)}><Plus className="h-4 w-4" /> Generate New Version</Button>} />
      <div className="flex gap-6 px-8 pb-10">
        <div className="w-60 shrink-0 space-y-1.5">
          {list.map((v) => (
            <button key={v.id} onClick={() => setSelId(v.id)} className={cn('flex w-full cursor-pointer items-center gap-2 rounded-lg border px-3 py-2.5 text-left text-sm', sel?.id === v.id ? 'border-primary bg-accent/40' : 'hover:bg-muted')}>
              <FolderGit2 className="h-4 w-4 text-muted-foreground" />
              <div className="min-w-0 flex-1"><div className="truncate font-medium">{v.name}</div><div className="text-[11px] text-muted-foreground">{fmtDate(v.created)} · {v.stats.images ?? '…'} images</div></div>
              {v.status !== 'ready' && <StatusPill status={v.status} />}
            </button>
          ))}
        </div>
        <div className="min-w-0 flex-1">
          {sel ? <VersionDetail v={sel} /> : versions.isSuccess && <EmptyState title="No versions yet." hint="Generate a version to export your dataset or train a model." action={<Button size="sm" onClick={() => setOpen(true)}>Generate first version</Button>} />}
        </div>
      </div>
      <Generate open={open} onClose={() => setOpen(false)} />
    </div>
  )
}
