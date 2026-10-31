import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { del, api, patch } from '@/lib/api'
import { Button, Card, Field, Input, PageHeader, Select, Switch, toast } from '@/components/ui'
import { typeLabel } from '@/components/shell'
import { useProject } from './ProjectLayout'

export default function ProjectSettings() {
  const { project, ws } = useProject()
  const qc = useQueryClient()
  const nav = useNavigate()
  const [f, setF] = useState({ name: project.name, visibility: project.visibility, license: project.license, annotation_group: project.annotationGroup })
  const al = project.settings.active_learning ?? {}
  const [learn, setLearn] = useState({ enabled: !!al.enabled, below: al.below ?? 0.5, sample_pct: al.sample_pct ?? 0, include_empty: al.include_empty ?? true })
  const save = (body: Record<string, unknown>) => patch(api.P(ws, project.slug), body)
    .then(() => { qc.invalidateQueries({ queryKey: ['project', ws, project.slug] }); qc.invalidateQueries({ queryKey: ['projects', ws] }); toast.ok('Saved') }).catch(toast.err)
  return (
    <div className="anim-page max-w-3xl">
      <PageHeader title="Project Settings" desc={typeLabel(project.type)} />
      <div className="space-y-4 px-8 pb-10">
        <Card className="space-y-4 p-5">
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Name"><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
            <Field label="Annotation group"><Input value={f.annotation_group} onChange={(e) => setF({ ...f, annotation_group: e.target.value })} /></Field>
            <Field label="Visibility"><Select className="w-full" value={f.visibility} onChange={(e) => setF({ ...f, visibility: e.target.value as any })}><option value="private">Private</option><option value="public">Public</option></Select></Field>
            <Field label="License"><Select className="w-full" value={f.license} onChange={(e) => setF({ ...f, license: e.target.value })}><option>CC BY 4.0</option><option>MIT</option><option>Public Domain</option><option>Proprietary</option></Select></Field>
          </div>
          <div className="flex justify-end"><Button onClick={() => save(f)}>Save</Button></div>
        </Card>
        <Card className="space-y-4 p-5">
          <div>
            <h3 className="font-semibold">Active Learning</h3>
            <p className="text-sm text-muted-foreground">Images sent to the hosted API are saved back into this project (batch “Active Learning”) so you can label the cases the model struggles with.</p>
          </div>
          <label className="flex items-center gap-2 text-sm"><Switch checked={learn.enabled} onChange={(v) => setLearn({ ...learn, enabled: v })} /> Enable active learning</label>
          {learn.enabled && (
            <div className="grid gap-4 md:grid-cols-2">
              <Field label={`Collect when any prediction is below ${Math.round(learn.below * 100)}% confidence`}><input type="range" min={5} max={95} value={learn.below * 100} onChange={(e) => setLearn({ ...learn, below: +e.target.value / 100 })} className="w-full accent-primary" /></Field>
              <Field label={`Also randomly sample ${learn.sample_pct}% of all calls`}><input type="range" min={0} max={50} value={learn.sample_pct} onChange={(e) => setLearn({ ...learn, sample_pct: +e.target.value })} className="w-full accent-primary" /></Field>
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="accent-primary" checked={learn.include_empty} onChange={(e) => setLearn({ ...learn, include_empty: e.target.checked })} /> Collect images with no predictions</label>
            </div>
          )}
          <div className="flex justify-end"><Button onClick={() => save({ settings: { active_learning: learn } })}>Save</Button></div>
        </Card>
        <Card className="border-destructive/40 p-5">
          <h3 className="font-semibold text-destructive">Delete project</h3>
          <p className="mb-3 text-sm text-muted-foreground">Moves the project to Trash. Workspace admins can restore it from Settings → Trash.</p>
          <Button variant="destructive" onClick={() => confirm(`Move "${project.name}" to trash?`) && del(api.P(ws, project.slug)).then(() => { qc.invalidateQueries({ queryKey: ['projects', ws] }); nav(`/${ws}`) }).catch(toast.err)}>Delete Project</Button>
        </Card>
      </div>
    </div>
  )
}
