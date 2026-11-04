import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { FileText, Lock, ScanFace, ShieldCheck, Trash2 } from 'lucide-react'
import { api } from '@/lib/api'
import { useProjectPermissions } from '@/lib/perms'
import { useApp } from '@/lib/store'
import type { ProjectPrivacy, WorkspacePrivacyProject } from '@/lib/types'
import { Badge, Button, Card, EmptyState, Field, Input, PageHeader, Select, Spinner, Switch, toast } from '@/components/ui'

const REGION_LABELS: Record<string, string> = {
  th: 'Thailand', tha: 'Thailand', thailand: 'Thailand',
  sg: 'Singapore', sgp: 'Singapore', singapore: 'Singapore',
  us: 'United States', usa: 'United States', 'united-states': 'United States',
  eu: 'European Union', global: 'Global',
}
const regionName = (id: string) => REGION_LABELS[id.toLowerCase()] ?? id

const DEFAULT_PRESETS = [7, 30, 90, 180, 365]
const retentionLabel = (d: number | null) => (d == null ? 'Keep forever' : `${d} day${d === 1 ? '' : 's'}`)

/** Retention select plus an optional custom number field. */
function RetentionPicker({ value, presets, disabled, onChange, label }: {
  value: number | null; presets: number[]; disabled: boolean; onChange: (v: number | null) => void; label: string
}) {
  const options = [...new Set([...DEFAULT_PRESETS, ...presets])].sort((a, b) => a - b)
  const [customRequested, setCustomRequested] = useState(false)
  // A value outside the presets (for example 45) always opens the custom field, even when it arrives late.
  const custom = customRequested || (value != null && !options.includes(value))
  const chosen = custom ? 'custom' : value == null ? 'forever' : String(value)
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Select aria-label={label} disabled={disabled} value={chosen}
        onChange={(e) => {
          if (e.target.value === 'custom') { setCustomRequested(true); return }
          setCustomRequested(false)
          onChange(e.target.value === 'forever' ? null : Number(e.target.value))
        }}>
        <option value="forever">Keep forever</option>
        {options.map((d) => <option key={d} value={d}>{retentionLabel(d)}</option>)}
        <option value="custom">Custom…</option>
      </Select>
      {custom && (
        <Input aria-label={`${label} (custom days)`} type="number" min={1} inputMode="numeric" disabled={disabled}
          className="w-24" value={value ?? ''} placeholder="Days"
          onChange={(e) => onChange(e.target.value ? Math.max(1, Math.round(Number(e.target.value))) : null)} />
      )}
    </div>
  )
}

function CleanupButton({ ws, project }: { ws: string; project: string }) {
  const qc = useQueryClient()
  const [busy, setBusy] = useState(false)
  const run = async () => {
    setBusy(true)
    try {
      const r = await api.runRetention(ws, project)
      toast.ok(`Cleanup queued — job ${r.job_id.slice(0, 8)}`)
      qc.invalidateQueries({ queryKey: ['project-privacy', ws] })
      qc.invalidateQueries({ queryKey: ['privacy', ws] })
    } catch (e) {
      toast.err(e as Error)
    } finally {
      setBusy(false)
    }
  }
  return (
    <Button variant="outline" size="sm" onClick={run} disabled={busy} aria-busy={busy}>
      {busy ? <Spinner className="h-3.5 w-3.5" /> : <Trash2 className="h-3.5 w-3.5" aria-hidden />}
      {busy ? 'Queueing…' : 'Run cleanup now'}
    </Button>
  )
}

function LegalBasis({ value, disabled, onChange }: { value: string; disabled: boolean; onChange: (v: string) => void }) {
  return (
    <Field label="Legal basis for biometrics" hint="PDPA s.26 treats biometric data as sensitive personal data. Record the lawful basis (at least 10 characters, for example explicit consent) before enabling face recognition.">
      <textarea required rows={2} disabled={disabled} value={value} onChange={(e) => onChange(e.target.value)}
        placeholder="e.g. Explicit consent collected at site entry, form v2.1"
        className="w-full rounded-md border border-input bg-card px-3 py-2 text-sm outline-none focus:border-ring disabled:opacity-60" />
    </Field>
  )
}

/** One project row in the workspace privacy table. Fetches its own detail for counts and legal basis. */
function PrivacyRow({ ws, project }: { ws: string; project: WorkspacePrivacyProject }) {
  const qc = useQueryClient()
  const { can } = useProjectPermissions(ws, project.slug)
  // The API checks project.privacy on every row save; a project manager who is a workspace
  // member may edit, while a workspace billing/viewer user sees the row read-only.
  const canEdit = can('project.privacy')
  const detail = useQuery({ queryKey: ['project-privacy', ws, project.slug], queryFn: () => api.projectPrivacy(ws, project.slug) })
  const [draft, setDraft] = useState<Pick<ProjectPrivacy, 'retention_days' | 'face_blur' | 'biometrics' | 'legal_basis'> | null>(null)
  const [saving, setSaving] = useState(false)
  const source = detail.data
  useEffect(() => {
    if (source && !draft) {
      setDraft({ retention_days: source.retention_days, face_blur: source.face_blur, biometrics: source.biometrics, legal_basis: source.legal_basis ?? '' })
    }
  }, [source, draft])
  const v = draft ?? {
    retention_days: project.retention_days, face_blur: project.face_blur ?? true,
    biometrics: project.biometrics, legal_basis: source?.legal_basis ?? '',
  }
  const presets = source?.retention_presets ?? []
  const needsBasis = v.biometrics && v.legal_basis.trim().length < 10

  const save = async () => {
    setSaving(true)
    try {
      await api.setProjectPrivacy(ws, project.slug, v)
      await qc.invalidateQueries({ queryKey: ['project-privacy', ws, project.slug] })
      await qc.invalidateQueries({ queryKey: ['privacy', ws] })
      toast.ok(`Privacy saved for ${project.name}`)
    } catch (e) {
      toast.err(e as Error)
    } finally {
      setSaving(false)
    }
  }

  return (
    <tr className="border-t align-top">
      <td className="px-4 py-3">
        <Link to={`/${ws}/${project.slug}/settings?tab=privacy`} className="font-medium hover:text-primary">{project.name}</Link>
        <div className="text-xs text-muted-foreground">{project.slug}</div>
      </td>
      <td className="px-4 py-3">
        <RetentionPicker label={`Retention for ${project.name}`} value={v.retention_days} presets={presets}
          disabled={!canEdit} onChange={(retention_days) => setDraft({ ...v, retention_days })} />
        <div className="mt-1.5 text-xs text-muted-foreground">
          {detail.isLoading ? 'Counting…' : detail.data
            ? `${detail.data.images_expiring} images · ${detail.data.snapshots_expiring} snapshots past retention`
            : '—'}
        </div>
      </td>
      <td className="min-w-56 px-4 py-3">
        <fieldset disabled={!canEdit} className={`m-0 min-w-0 border-0 p-0 ${canEdit ? '' : 'opacity-60'}`}>
          <div className="flex items-center gap-2">
            <Switch label={`Blur faces in uploaded images and video frames of ${project.name}`} checked={v.face_blur} onChange={(face_blur) => setDraft({ ...v, face_blur })} />
            <span className="text-xs text-muted-foreground">Blur faces {v.face_blur ? 'on' : 'off'}</span>
          </div>
          <div className="mt-2 flex items-center gap-2">
            <Switch label={`Biometrics in ${project.name}`} checked={v.biometrics} onChange={(biometrics) => setDraft({ ...v, biometrics })} />
            <span className="text-xs text-muted-foreground">{v.biometrics ? 'Face recognition on' : 'No face recognition'}</span>
          </div>
          {v.biometrics && (
            <div className="mt-2">
              <LegalBasis value={v.legal_basis} disabled={!canEdit} onChange={(legal_basis) => setDraft({ ...v, legal_basis })} />
            </div>
          )}
        </fieldset>
      </td>
      <td className="px-4 py-3">
        {canEdit ? (
          <div className="flex flex-col items-start gap-2">
            <Button size="sm" onClick={save} disabled={saving || needsBasis || detail.isLoading || !draft} title={needsBasis ? 'Record a legal basis first' : undefined}>
              {saving ? 'Saving…' : 'Save'}
            </Button>
            <CleanupButton ws={ws} project={project.slug} />
            {needsBasis && <span className="text-xs text-destructive">Legal basis needs 10+ characters</span>}
          </div>
        ) : <span className="text-xs text-muted-foreground">Read only</span>}
      </td>
    </tr>
  )
}

/** Workspace-level data residency plus every project's retention and PDPA switches. */
export default function PrivacyWorkspace() {
  const { ws = '' } = useParams()
  const qc = useQueryClient()
  const can = useApp((s) => s.can)
  // Residency is a workspace setting (workspace.update); per-project rows use their own role.
  const canEdit = can('admin')
  const q = useQuery({ queryKey: ['privacy', ws], queryFn: () => api.privacy(ws), enabled: !!ws })
  const [region, setRegion] = useState<string | null>(null)
  const [savingRegion, setSavingRegion] = useState(false)
  const data = q.data
  const currentRegion = region ?? data?.data_region ?? 'th'

  const saveRegion = async () => {
    if (!data) return
    setSavingRegion(true)
    try {
      await api.setWorkspacePrivacy(ws, { data_region: currentRegion })
      await qc.invalidateQueries({ queryKey: ['privacy', ws] })
      toast.ok('Data residency declaration saved')
    } catch (e) {
      toast.err(e as Error)
    } finally {
      setSavingRegion(false)
    }
  }

  return (
    <div className="space-y-4">
      <Card className="space-y-3 p-5">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h2 className="font-semibold">Data residency</h2>
            <p className="mt-0.5 text-sm text-muted-foreground">
              The region named in your Data Processing Agreement. This is a declaration for the DPA — changing it records where you state processing happens.
            </p>
          </div>
          <Badge className="gap-1 bg-card text-foreground"><Lock className="h-3 w-3" aria-hidden />PDPA</Badge>
        </div>
        {q.isLoading ? (
          <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground"><Spinner /> Loading privacy settings…</p>
        ) : q.isError ? (
          <div className="flex flex-wrap items-center gap-2">
            <p role="alert" className="text-sm text-destructive">Could not load privacy settings.</p>
            <Button variant="outline" size="sm" onClick={() => void q.refetch()}>Try again</Button>
          </div>
        ) : data && (
          <>
            <div className="flex flex-wrap items-end gap-2">
              <Field label="Region">
                <Select className="w-full sm:w-56" value={currentRegion} disabled={!canEdit}
                  onChange={(e) => setRegion(e.target.value)}>
                  {(data.regions.length ? data.regions : ['th', 'sg', 'us']).map((r) => <option key={r} value={r}>{regionName(r)}</option>)}
                </Select>
              </Field>
              {canEdit
                ? <Button onClick={saveRegion} disabled={savingRegion || currentRegion === data.data_region}>{savingRegion ? 'Saving…' : 'Save region'}</Button>
                : <p className="pb-2 text-xs text-muted-foreground">Only workspace admins can change residency.</p>}
            </div>
            <p className="text-xs text-muted-foreground">
              Declared region: <span className="font-medium text-foreground">{data.region_label || regionName(data.data_region)}</span>. Download the DPA template from{' '}
              <Link to={`/${ws}/legal/dpa`} className="text-primary underline underline-offset-2">Legal → Data Processing Agreement</Link>.
            </p>
          </>
        )}
      </Card>

      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-start justify-between gap-2 border-b p-5 pb-4">
          <div>
            <h2 className="font-semibold">Project retention &amp; biometrics</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">Frames, snapshots and events older than a project's retention are deleted by the cleanup job, along with cached exports containing deleted frames. Face blur is on by default.</p>
          </div>
          <Badge className="gap-1 bg-card text-foreground"><ShieldCheck className="h-3 w-3 text-success" aria-hidden />PDPA defaults</Badge>
        </div>
        {q.isLoading ? (
          <p role="status" className="flex items-center gap-2 border-t px-4 py-8 text-sm text-muted-foreground"><Spinner /> Loading project policies…</p>
        ) : !data ? null : !data.projects.length ? (
          <EmptyState icon={<ScanFace className="h-8 w-8 text-muted-foreground/50" aria-hidden />} title="No projects yet." hint="Create a project to set its retention policy." />
        ) : (
          <div className="overflow-x-auto" role="region" aria-label="Project privacy settings" tabIndex={0}>
            <table className="w-full min-w-[44rem] text-sm">
              <caption className="sr-only">Retention, face blur and biometrics per project</caption>
              <thead className="bg-muted/60 text-left text-xs text-muted-foreground">
                <tr>
                  <th scope="col" className="px-4 py-2 font-medium">Project</th>
                  <th scope="col" className="px-4 py-2 font-medium">Retention</th>
                  <th scope="col" className="px-4 py-2 font-medium">Privacy controls</th>
                  <th scope="col" className="px-4 py-2 font-medium"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {(q.data?.projects ?? []).map((p) => <PrivacyRow key={p.slug} ws={ws} project={p} />)}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card className="flex flex-wrap items-center justify-between gap-3 p-4">
        <div className="flex items-start gap-2 text-sm">
          <FileText className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
          <div>
            <div className="font-medium">Data Processing Agreement</div>
            <p className="text-xs text-muted-foreground">Generate the template for your workspace and region, then save it as PDF.</p>
          </div>
        </div>
        <Link to={`/${ws}/legal/dpa`}><Button variant="outline">Open DPA</Button></Link>
      </Card>
    </div>
  )
}

/** The single-project Privacy & retention section used inside Project Settings. */
export function ProjectPrivacySection({ ws, project, canEdit }: { ws: string; project: string; canEdit: boolean }) {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['project-privacy', ws, project], queryFn: () => api.projectPrivacy(ws, project) })
  const [draft, setDraft] = useState<Pick<ProjectPrivacy, 'retention_days' | 'face_blur' | 'biometrics' | 'legal_basis'> | null>(null)
  const [saving, setSaving] = useState(false)
  useEffect(() => {
    if (q.data && !draft) {
      setDraft({
        retention_days: q.data.retention_days,
        face_blur: q.data.face_blur ?? true,
        biometrics: q.data.biometrics ?? false,
        legal_basis: q.data.legal_basis ?? '',
      })
    }
  }, [q.data, draft])

  if (q.isLoading) return <Card className="flex items-center gap-2 p-5 text-sm text-muted-foreground" role="status"><Spinner /> Loading retention policy…</Card>
  if (q.isError) {
    return (
      <Card className="flex flex-wrap items-center gap-2 p-5">
        <p role="alert" className="text-sm text-destructive">Could not load this project's privacy policy.</p>
        <Button variant="outline" size="sm" onClick={() => void q.refetch()}>Try again</Button>
      </Card>
    )
  }
  if (!q.data || !draft) return null
  const v = draft
  const needsBasis = v.biometrics && v.legal_basis.trim().length < 10

  const save = async () => {
    setSaving(true)
    try {
      await api.setProjectPrivacy(ws, project, v)
      await qc.invalidateQueries({ queryKey: ['project-privacy', ws, project] })
      await qc.invalidateQueries({ queryKey: ['privacy', ws] })
      toast.ok('Privacy settings saved')
    } catch (e) {
      toast.err(e as Error)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-4">
      <Card className="space-y-4 p-5">
        <div>
          <h2 className="font-semibold">Privacy &amp; retention</h2>
          <p className="mt-0.5 text-sm text-muted-foreground">Old frames, snapshots and events are deleted after the retention window, together with cached exports that contain deleted frames. Deleting is permanent.</p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          <Badge className="bg-card text-foreground">{q.data.images_expiring} images past retention</Badge>
          <Badge className="bg-card text-foreground">{q.data.snapshots_expiring} snapshots past retention</Badge>
          <Badge className="bg-card text-foreground">{regionName(q.data.data_region)}</Badge>
        </div>
        <Field label="Retention" hint="Keep forever means the cleanup job never deletes media for this project.">
          <RetentionPicker label="Retention" value={v.retention_days} presets={q.data.retention_presets} disabled={!canEdit}
            onChange={(retention_days) => setDraft({ ...v, retention_days })} />
        </Field>
        <fieldset disabled={!canEdit} className={`m-0 min-w-0 space-y-4 border-0 p-0 ${canEdit ? '' : 'opacity-60'}`}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-sm font-medium">Blur faces in uploaded images and video frames</div>
              <p className="text-xs text-muted-foreground">Faces are blurred as uploaded images, connector imports and video frames are saved into datasets, so training data never contains identifiable faces. On by default.</p>
            </div>
            <Switch label="Blur faces in uploaded images and video frames" checked={v.face_blur} onChange={(face_blur) => setDraft({ ...v, face_blur })} />
          </div>
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-sm font-medium">Biometric processing (face recognition)</div>
              <p className="text-xs text-muted-foreground">Off by default. LabelDesk does not identify people unless you enable it and record a lawful basis under PDPA s.26.</p>
            </div>
            <Switch label="Biometric processing" checked={v.biometrics} onChange={(biometrics) => setDraft({ ...v, biometrics })} />
          </div>
          {v.biometrics && <LegalBasis value={v.legal_basis} disabled={!canEdit} onChange={(legal_basis) => setDraft({ ...v, legal_basis })} />}
        </fieldset>
        {canEdit ? (
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CleanupButton ws={ws} project={project} />
            <div className="flex items-center gap-2">
              {needsBasis && <span className="text-xs text-destructive">Record a legal basis (10+ characters) before saving.</span>}
              <Button onClick={save} disabled={saving || needsBasis}>{saving ? 'Saving…' : 'Save privacy settings'}</Button>
            </div>
          </div>
        ) : (
          <p className="rounded-lg border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">Read only — a project manager or workspace admin can change these settings.</p>
        )}
      </Card>
    </div>
  )
}
