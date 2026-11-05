import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { BarChart3, Play, Plus, Save } from 'lucide-react'
import { api } from '@/lib/api'
import type { Workflow, WorkflowBlock, WorkflowRunResult } from '@/lib/types'
import { useFlag } from '@/lib/flags'
import { Badge, Button, Card, EmptyState, Field, Input, PageHeader, Select, Spinner, toast } from '@/components/ui'
import { useProject } from './ProjectLayout'
import { WorkflowBlocks, newBlock } from './WorkflowBlocks'
import { WorkflowVersions } from './WorkflowVersions'

const SINK = { type: 'sink', kind: 'response' } as WorkflowBlock

function ResultPanel({ result }: { result: WorkflowRunResult }) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2 text-xs">
        <Badge>{result.detections.length} detections</Badge>
        <Badge>{result.texts.length} text blocks</Badge>
        <Badge>{result.events.length} events</Badge>
        {result.annotations_added > 0 && <Badge>{result.annotations_added} annotations saved</Badge>}
        <Badge>{result.elapsed_ms} ms</Badge>
      </div>
      {result.detections.length > 0 && (
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-left text-xs">
            <caption className="sr-only">Workflow detections</caption>
            <thead className="bg-muted text-muted-foreground">
              <tr><th className="px-2 py-1.5 font-medium">Class</th><th className="px-2 py-1.5 font-medium">Confidence</th>
                <th className="hidden px-2 py-1.5 font-medium sm:table-cell">Model</th></tr>
            </thead>
            <tbody className="divide-y">
              {result.detections.map((d, i) => (
                <tr key={i}><td className="px-2 py-1.5">{d.class}</td>
                  <td className="px-2 py-1.5 tabular-nums">{Math.round(d.confidence * 100)}%</td>
                  <td className="hidden max-w-40 truncate px-2 py-1.5 text-muted-foreground sm:table-cell">{d.model}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {result.texts.length > 0 && (
        <div>
          <h3 className="mb-1 text-xs font-medium text-muted-foreground">OCR</h3>
          <ul className="space-y-1">{result.texts.map((t, i) => (
            <li key={i}><pre className="max-h-32 overflow-auto rounded-lg bg-muted p-2 text-[11px] whitespace-pre-wrap">{t.text}</pre></li>
          ))}</ul>
        </div>
      )}
      {result.events.length > 0 && (
        <div>
          <h3 className="mb-1 text-xs font-medium text-muted-foreground">Rule events</h3>
          <ul className="space-y-1 text-xs">{result.events.map((e, i) => (
            <li key={i} className="flex items-center gap-2"><Badge>{e.kind}</Badge><span>{e.summary}</span></li>
          ))}</ul>
        </div>
      )}
      {result.detections.length + result.texts.length + result.events.length === 0 && (
        <p className="text-sm text-muted-foreground">The chain ran but produced nothing on this image.</p>
      )}
    </div>
  )
}

export default function Workflows() {
  const { project, ws } = useProject()
  const slug = project.slug
  const enabled = useFlag('task_31')
  const qc = useQueryClient()
  const workflows = useQuery({ queryKey: ['workflows', ws, slug], queryFn: () => api.workflows(ws, slug) })
  const registry = useQuery({ queryKey: ['registry', ws], queryFn: () => api.registry(ws) })
  const classes = useQuery({ queryKey: ['classes', ws, slug], queryFn: () => api.classes(ws, slug) })
  const images = useQuery({ queryKey: ['images', ws, slug, 'workflow-run'], queryFn: () => api.images(ws, slug, { limit: 50 }) })
  const [selId, setSelId] = useState('')
  const current: Workflow | undefined = workflows.data?.find((w) => w.id === selId) ?? workflows.data?.[0]
  const [name, setName] = useState('')
  const [blocks, setBlocks] = useState<WorkflowBlock[]>([])
  const [imageId, setImageId] = useState('')
  const [result, setResult] = useState<WorkflowRunResult | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!current) return
    setName(current.name)
    setBlocks(current.blocks)
    setResult(null)
  }, [current?.id, current?.version])

  useEffect(() => {
    if (!imageId && images.data?.items.length) setImageId(images.data.items[0].id)
  }, [images.data, imageId])

  const modelRef = registry.data?.find((m) => m.kind === 'trained')?.ref ?? registry.data?.find((m) => m.available)?.ref ?? 'ultralytics:yolo26n'
  const dirty = !!current && (name !== current.name || JSON.stringify(blocks) !== JSON.stringify(current.blocks))

  const refresh = () => qc.invalidateQueries({ queryKey: ['workflows', ws, slug] })

  const create = async () => {
    setBusy(true)
    try {
      const w = await api.createWorkflow(ws, slug, {
        name: `Workflow ${(workflows.data?.length ?? 0) + 1}`,
        blocks: [newBlock('model', modelRef), SINK],
      })
      await refresh()
      setSelId(w.id)
      toast.ok('Workflow created')
    } catch (e) { toast.err(e as Error) } finally { setBusy(false) }
  }

  const save = async () => {
    if (!current) return
    setBusy(true)
    try {
      const w = await api.updateWorkflow(ws, slug, current.id, { name, blocks })
      await Promise.all([refresh(), qc.invalidateQueries({ queryKey: ['workflow-versions', ws, slug, current.id] })])
      setName(w.name); setBlocks(w.blocks)
      toast.ok(`Saved version ${w.version}`)
    } catch (e) { toast.err(e as Error) } finally { setBusy(false) }
  }

  const run = async () => {
    if (!current || !imageId) return
    setBusy(true)
    try {
      setResult(await api.runWorkflow(ws, slug, current.id, imageId))
      await qc.invalidateQueries({ queryKey: ['images', ws, slug, 'workflow-run'] })
    } catch (e) { toast.err(e as Error) } finally { setBusy(false) }
  }

  if (!enabled) {
    return <EmptyState title="Workflows are off in this workspace" hint="A workspace admin can enable the workflow builder flag." />
  }
  if (workflows.isLoading) return <div className="flex h-full items-center justify-center"><Spinner /></div>
  if (workflows.isError) return <EmptyState title="Workflows could not load" hint={(workflows.error as Error).message} />
  if (!current) {
    return (
      <div>
        <PageHeader title="Workflows" desc="Chain models, filters, crops, OCR, rules and outputs — no code." />
        <div className="px-8">
          <Card className="p-8">
            <EmptyState title="Build your first workflow" hint="Start with a model block and a response sink, then add filters, crops, OCR or a rule."
              action={<Button onClick={create} disabled={busy}><Plus className="h-4 w-4" /> New workflow</Button>} />
          </Card>
        </div>
      </div>
    )
  }

  return (
    <div>
      <PageHeader title="Workflows" desc="Chain models, filters, crops, OCR, rules and outputs — no code. Every save is a version you can restore."
        actions={<>
          <Select aria-label="Choose workflow" value={current.id} onChange={(e) => setSelId(e.target.value)}>
            {(workflows.data ?? []).map((w) => <option key={w.id} value={w.id}>{w.name} · v{w.version}</option>)}
          </Select>
          <Button variant="outline" onClick={create} disabled={busy}><Plus className="h-4 w-4" /> New</Button>
        </>} />
      <div className="grid gap-6 px-8 pb-10 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-4">
          <Card className="p-4">
            <div className="flex flex-wrap items-end gap-3">
              <div className="min-w-56 flex-1">
                <Field label="Name"><Input value={name} maxLength={120} onChange={(e) => setName(e.target.value)} /></Field>
              </div>
              <Badge>v{current.version}</Badge>
              {dirty && <Badge className="bg-warning/15 text-warning">Unsaved changes</Badge>}
              <Button onClick={save} disabled={busy || !name.trim() || !dirty}><Save className="h-4 w-4" /> Save</Button>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">Saving changed blocks creates v{current.version + 1}. Renaming keeps the current version.</p>
          </Card>
          <WorkflowBlocks blocks={blocks} models={registry.data ?? []} classNames={(classes.data ?? []).map((c) => c.name)}
            onChange={setBlocks} />
        </div>
        <div className="space-y-4">
          <section aria-labelledby="workflow-run" className="rounded-xl border bg-card">
            <div className="flex items-center gap-2 border-b px-3 py-2">
              <Play className="h-4 w-4 text-muted-foreground" aria-hidden />
              <h2 id="workflow-run" className="text-sm font-medium">Run</h2>
              <span className="ml-auto text-xs text-muted-foreground">saved v{current.version}</span>
            </div>
            <div className="space-y-3 p-3">
              <Field label="Project image">
                <Select value={imageId} onChange={(e) => setImageId(e.target.value)} disabled={!images.data?.items.length}>
                  {(images.data?.items ?? []).map((im) => <option key={im.id} value={im.id}>{im.name}</option>)}
                </Select>
              </Field>
              {images.isSuccess && !images.data.items.length && <p className="text-xs text-muted-foreground">Upload images to this project first.</p>}
              <Button className="w-full" onClick={run} disabled={busy || !imageId || dirty}>
                <Play className="h-4 w-4" /> Run workflow
              </Button>
              {dirty && <p className="text-xs text-warning">Save your changes before running.</p>}
              {busy && result === null && <div className="flex justify-center py-2"><Spinner /></div>}
              {result && <ResultPanel result={result} />}
              {result === null && !busy && <p className="flex items-start gap-2 text-xs text-muted-foreground">
                <BarChart3 className="mt-0.5 h-3.5 w-3.5 shrink-0" /> The panels fill with detections, OCR text and rule events after a run.
              </p>}
            </div>
          </section>
          <WorkflowVersions ws={ws} project={slug} workflow={current} onRestored={(w) => { setSelId(w.id); setBlocks(w.blocks); setName(w.name) }} />
        </div>
      </div>
    </div>
  )
}
