import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Activity, Box, FolderOpen, FolderPlus, Globe, Lock, Plus, Scan, Search, Shapes, TriangleAlert, UserPlus } from 'lucide-react'
import { ApiError, api, del, fileUrl, get, patch, post } from '@/lib/api'
import { projectPath } from '@/lib/routes'
import { projectSlug } from '@/lib/slug'
import { useFlag } from '@/lib/flags'
import { useApp } from '@/lib/store'
import type { Project } from '@/lib/types'
import { Badge, Button, Card, Dropdown, EmptyState, Field, Input, Modal, PageHeader, Select, fmtAgo, toast } from '@/components/ui'
import { typeLabel } from '@/components/shell'
import { WorkspaceDashboard } from './Dashboard'
import { cn } from '@/lib/utils'

const TYPES = [
  { id: 'object-detection', icon: Box, desc: 'Identify objects and their positions with bounding boxes.', tags: ['Bounding Boxes', 'Counts'] },
  { id: 'instance-segmentation', icon: Shapes, desc: 'Detect objects and their exact shape with polygons.', tags: ['Polygons', 'Measuring'] },
  { id: 'classification', icon: Scan, desc: 'Assign a label to the whole image.', tags: ['Image Labels', 'Filtering'] },
  { id: 'keypoint-detection', icon: Scan, desc: 'Place named joints and draw skeletons for pose, faces or products.', tags: ['Keypoints', 'Skeletons'] },
  { id: 'anomaly-detection', icon: Activity, desc: 'Learn what a good product looks like and flag deviations with a heatmap.', tags: ['Good-only', 'Heatmap'] },
]

type Folder = { id: string; name: string; projectCount: number }

function NewProject({ open, onClose, folders }: { open: boolean; onClose: () => void; folders: Folder[] }) {
  const { ws = '' } = useParams()
  const nav = useNavigate()
  const qc = useQueryClient()
  const anomalyOn = useFlag('task_29')
  const [f, setF] = useState({ name: '', type: 'object-detection', visibility: 'private', license: 'CC BY 4.0', annotation_group: '', classes: '', folder_id: '' })
  const [busy, setBusy] = useState(false)
  const [taken, setTaken] = useState<{ taken: string; suggestion: string } | null>(null)
  const slug = projectSlug(f.name)
  const create = async () => {
    setBusy(true); setTaken(null)
    try {
      const p = await post<Project>(`/ws/${ws}/projects`, {
        ...f, folder_id: f.folder_id || null, annotation_group: f.annotation_group || 'objects',
        classes: f.classes.split(',').map((s) => s.trim()).filter(Boolean),
      })
      qc.invalidateQueries({ queryKey: ['projects', ws] }); qc.invalidateQueries({ queryKey: ['ws', ws] })
      onClose(); nav(projectPath(ws, p.slug, 'upload'))
    } catch (e) {
      // The address is taken: say so in place, keep the dialog and the typed name (V2).
      if (e instanceof ApiError && e.status === 409) {
        const detail = (e.body as { detail?: { taken?: string; suggestion?: string } } | undefined)?.detail
        if (detail?.taken && detail.suggestion) { setTaken({ taken: detail.taken, suggestion: detail.suggestion }); return }
      }
      toast.err(e as Error)
    } finally { setBusy(false) }
  }
  return (
    <Modal open={open} onClose={onClose} wide aria-label="Create a project">
      <h1 className="mb-5 text-2xl font-bold tracking-tight">Let's create your project.</h1>
      <div className="grid gap-4 md:grid-cols-4">
        <Field label="Project Name" hint={f.name.trim() ? <>Address <span className="font-mono text-foreground">{projectPath(ws, slug)}</span></> : undefined}>
          <Input autoFocus placeholder="e.g. Hardhat Detection" value={f.name} onChange={(e) => { setF({ ...f, name: e.target.value }); setTaken(null) }} />
        </Field>
        <Field label="Annotation Group" hint="What you're labeling, e.g. 'ppe'"><Input placeholder="objects" value={f.annotation_group} onChange={(e) => setF({ ...f, annotation_group: e.target.value })} /></Field>
        <Field label="License"><Select className="w-full" value={f.license} onChange={(e) => setF({ ...f, license: e.target.value })}><option>CC BY 4.0</option><option>MIT</option><option>Public Domain</option><option>Proprietary</option></Select></Field>
        <Field label="Folder"><Select className="w-full" value={f.folder_id} onChange={(e) => setF({ ...f, folder_id: e.target.value })}><option value="">— none —</option>{folders.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</Select></Field>
      </div>
      <div className="mt-4"><Field label="Classes (optional)" hint="Comma separated — you can add more while labeling."><Input placeholder="person, helmet, vest" value={f.classes} onChange={(e) => setF({ ...f, classes: e.target.value })} /></Field></div>
      {taken && (
        <div role="alert" className="mt-4 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2.5">
          <p className="flex items-start gap-2 text-sm font-medium leading-relaxed text-foreground">
            <TriangleAlert aria-hidden className="mt-1 h-4 w-4 shrink-0 text-destructive" />
            <span>That address is taken: <span className="font-mono">{taken.taken}</span> already belongs to another project.</span>
          </p>
          <p className="mt-1 pl-6 text-xs leading-relaxed text-muted-foreground">
            Try <span className="font-mono text-foreground">{taken.suggestion}</span>, or rename this one.
          </p>
        </div>
      )}
      <h2 className="mb-3 mt-6 text-sm font-semibold">Project Type</h2>
      <div className="grid gap-3 md:grid-cols-3">
        {TYPES.filter((t) => t.id !== 'anomaly-detection' || anomalyOn).map((t) => (
          <button key={t.id} onClick={() => setF({ ...f, type: t.id })}
            className={cn('cursor-pointer rounded-lg border p-4 text-left transition-colors', f.type === t.id ? 'border-primary bg-accent/30' : 'hover:bg-muted')}>
            <div className="mb-1.5 flex items-center gap-2 font-semibold"><t.icon className="h-4 w-4 text-primary" />{typeLabel(t.id)}</div>
            <p className="text-sm text-muted-foreground">{t.desc}</p>
            <div className="mt-2 flex flex-wrap gap-1">{t.tags.map((x) => <Badge key={x}>{x}</Badge>)}</div>
          </button>
        ))}
      </div>
      <div className="mt-6 flex items-center justify-between border-t pt-4">
        <div className="flex gap-2">
          <Button variant={f.visibility === 'private' ? 'outline' : 'ghost'} size="sm" onClick={() => setF({ ...f, visibility: 'private' })}><Lock className="h-3.5 w-3.5" /> Private</Button>
          <Button variant={f.visibility === 'public' ? 'outline' : 'ghost'} size="sm" onClick={() => setF({ ...f, visibility: 'public' })}><Globe className="h-3.5 w-3.5" /> Public</Button>
        </div>
        <div className="flex gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={!f.name.trim() || busy} onClick={create}>Create Project</Button></div>
      </div>
    </Modal>
  )
}

export default function Home() {
  const { ws = '' } = useParams()
  const can = useApp((s) => s.can)
  const me = useApp((s) => s.me)
  const nav = useNavigate()
  const qc = useQueryClient()
  const projects = useQuery({ queryKey: ['projects', ws], queryFn: () => api.projects(ws) })
  const folders = useQuery({ queryKey: ['folders', ws], queryFn: () => get<Folder[]>(`/ws/${ws}/folders`) })
  const [q, setQ] = useState('')
  const [type, setType] = useState('')
  const [sort, setSort] = useState('updated')
  const [folder, setFolder] = useState<string | null>(null)
  const [showNew, setShowNew] = useState(false)
  const list = useMemo(() => {
    let l = (projects.data ?? []).filter((p) => p.name.toLowerCase().includes(q.toLowerCase()) && (!type || p.type === type))
    l = folder ? l.filter((p) => p.folderId === folder) : q ? l : l.filter((p) => !p.folderId)
    return [...l].sort((a, b) => sort === 'name' ? a.name.localeCompare(b.name) : sort === 'images' ? b.images - a.images : b.updated - a.updated)
  }, [projects.data, q, type, sort, folder])
  const refresh = () => { qc.invalidateQueries({ queryKey: ['projects', ws] }); qc.invalidateQueries({ queryKey: ['folders', ws] }) }
  const act = (fn: () => Promise<unknown>, ok?: string) => fn().then(() => { refresh(); ok && toast.ok(ok) }).catch(toast.err)
  const name = 'Projects'; void me
  const currentFolder = folders.data?.find((x) => x.id === folder)
  // One-time note from the creation screens, carried through the account guard's redirect.
  const [started, setStarted] = useState('')
  useEffect(() => {
    const tier = sessionStorage.getItem('startedPlan')
    if (!tier) return
    sessionStorage.removeItem('startedPlan')
    setStarted(tier)
  }, [])

  return (
    <div className="anim-page min-h-full">
      <PageHeader title={currentFolder ? <><button className="cursor-pointer text-muted-foreground hover:text-foreground" onClick={() => setFolder(null)}>{name}</button> / {currentFolder.name}</> : 'Home'}
        desc={currentFolder ? undefined : 'What needs you, what changed, and how to get set up.'}
        actions={can('admin') && <Button variant="outline" size="sm" onClick={() => nav(`/${ws}/settings/members`)}><UserPlus className="h-4 w-4" /> Invite Team</Button>} />
      {started ? (
        <p role="status" className="mx-8 mt-4 rounded-lg border border-border/70 bg-muted px-3 py-2.5 text-sm leading-relaxed text-foreground">
          Started on {started.charAt(0).toUpperCase() + started.slice(1)}. You can change this in Settings → Plan & Usage.
        </p>
      ) : null}
      {!currentFolder && <WorkspaceDashboard ws={ws} projects={projects.data ?? []} onCreateProject={() => setShowNew(true)} dialogOpen={showNew} />}
      <section data-tour="home-projects" aria-labelledby="projects-heading">
        <div className="flex flex-wrap items-end justify-between gap-3 px-8 pt-6">
          <div>
            <h2 id="projects-heading" className="text-lg font-semibold tracking-tight">Projects</h2>
            <p className="text-sm text-muted-foreground">Open a project to upload images, annotate them and train a model.</p>
          </div>
        </div>
      <div className="flex flex-wrap items-center gap-3 px-8">
        <div className="relative w-64"><Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" /><Input className="pl-8" placeholder="Search projects" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <Select aria-label="Filter by project type" value={type} onChange={(e) => setType(e.target.value)}><option value="">All types</option>{TYPES.map((t) => <option key={t.id} value={t.id}>{typeLabel(t.id)}</option>)}</Select>
        <Select aria-label="Sort projects" value={sort} onChange={(e) => setSort(e.target.value)}><option value="updated">Date edited</option><option value="name">Name</option><option value="images">Image count</option></Select>
        <div className="ml-auto flex gap-2">
          {can('reviewer') && <Button variant="outline" size="sm" onClick={() => { const n = prompt('Folder name'); n && act(() => post(`/ws/${ws}/folders`, { name: n })) }}><FolderPlus className="h-4 w-4" /> New Folder</Button>}
          {can('admin') && <Button size="sm" onClick={() => setShowNew(true)}><Plus className="h-4 w-4" /> New Project</Button>}
        </div>
      </div>
      <div className="grid grid-cols-1 gap-4 p-8 md:grid-cols-2 xl:grid-cols-3">
        {!folder && !q && folders.data?.map((f) => (
          <Card key={f.id} className="lift flex cursor-pointer items-center gap-3 p-4" onClick={() => setFolder(f.id)}>
            <span className="flex h-10 w-10 items-center justify-center rounded-md bg-muted"><FolderOpen className="h-5 w-5 text-muted-foreground" /></span>
            <div><div className="font-semibold">{f.name}</div><div className="text-xs text-muted-foreground">{f.projectCount} project{f.projectCount === 1 ? '' : 's'}</div></div>
            <div className="ml-auto" onClick={(e) => e.stopPropagation()}>
              <Dropdown align="right" trigger={<button className="cursor-pointer px-1 text-muted-foreground">⋮</button>} items={[
                { label: 'Rename', onClick: () => { const n = prompt('Rename folder', f.name); n && act(() => patch(`/ws/${ws}/folders/${f.id}`, { name: n })) } },
                { label: 'Delete', danger: true, onClick: () => confirm('Delete folder? Projects move to the top level.') && act(() => del(`/ws/${ws}/folders/${f.id}`)) },
              ]} />
            </div>
          </Card>
        ))}
        {list.map((p) => (
          <Link key={p.id} to={projectPath(ws, p.slug)}>
            <Card className="lift overflow-hidden">
              <div className="flex gap-4 p-4">
                <div className="h-24 w-36 shrink-0 overflow-hidden rounded-md bg-muted">{p.thumbnail && <img src={fileUrl(p.thumbnail)} alt="" className="h-full w-full object-cover" />}</div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <Badge className="bg-accent/60 text-accent-foreground">{typeLabel(p.type)}</Badge>
                    {can('admin') && (
                      <div onClick={(e) => e.preventDefault()}>
                        <Dropdown align="right" trigger={<button className="cursor-pointer px-1 text-muted-foreground">⋮</button>} items={[
                          { label: 'Rename', onClick: () => { const n = prompt('Rename project', p.name); n && act(() => patch(`/ws/${ws}/projects/${p.slug}`, { name: n })) } },
                          ...(folders.data ?? []).map((f) => ({ label: `Move to ${f.name}`, onClick: () => act(() => patch(`/ws/${ws}/projects/${p.slug}`, { folder_id: f.id })) })),
                          ...(p.folderId ? [{ label: 'Remove from folder', onClick: () => act(() => patch(`/ws/${ws}/projects/${p.slug}`, { folder_id: null })) }] : []),
                          { label: 'Delete Project', danger: true, onClick: () => confirm(`Move "${p.name}" to trash?`) && act(() => del(`/ws/${ws}/projects/${p.slug}`), 'Moved to trash') },
                        ]} />
                      </div>
                    )}
                  </div>
                  <div className="mt-1.5 flex items-center gap-1.5 font-bold">
                    {p.visibility === 'public' ? <Globe className="h-3.5 w-3.5 text-muted-foreground" /> : <Lock className="h-3.5 w-3.5 text-muted-foreground" />}
                    <span className="clamp-2" title={p.name}>{p.name}</span>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">Edited {fmtAgo(p.updated)}</div>
                  <div className="text-xs text-muted-foreground tabular-nums">{p.images} Images · {p.models} Models</div>
                </div>
              </div>
            </Card>
          </Link>
        ))}
        {projects.isSuccess && !list.length && (
          <div className="col-span-full"><EmptyState title={q ? 'No projects match.' : 'No projects yet.'} hint="Projects hold images, annotations, versions and models."
            action={can('admin') && <Button size="sm" onClick={() => setShowNew(true)}><Plus className="h-4 w-4" /> Create your first project</Button>} /></div>
        )}
      </div>
      </section>
      <NewProject open={showNew} onClose={() => setShowNew(false)} folders={folders.data ?? []} />
    </div>
  )
}
