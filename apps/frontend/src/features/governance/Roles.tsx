import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { KeyRound, Pencil, Plus, ShieldCheck, Trash2 } from 'lucide-react'
import { useParams } from 'react-router-dom'
import { api } from '@/lib/api'
import type { CustomRole, ProjectRole, RoleLevel } from '@/lib/types'
import { Badge, Button, Card, EmptyState, Field, Input, Modal, Select, Spinner, fmtDate, toast } from '@/components/ui'

const PERMISSION_LABELS: Record<string, string> = {
  'workspace.read': 'View workspace',
  'workspace.update': 'Rename workspace',
  'workspace.delete': 'Delete workspace',
  'workspace.members': 'Manage members',
  'workspace.billing': 'Manage billing',
  'workspace.keys': 'Manage API keys',
  'workspace.audit': 'Read audit log',
  'workspace.trash': 'Restore from trash',
  'workspace.connectors': 'Manage connectors',
  'workspace.project.create': 'Create projects',
  'workspace.project.delete': 'Delete projects',
  'project.read': 'View project',
  'project.annotate': 'Annotate images',
  'project.review': 'Review annotations',
  'project.upload': 'Upload images',
  'project.export': 'Export versions',
  'project.settings': 'Change project settings',
  'project.classes': 'Manage classes & tags',
  'project.train': 'Train models',
  'project.models': 'Use models',
  'project.infer': 'Run inference',
  'project.streams': 'Watch streams',
  'project.privacy': 'Manage privacy',
  'project.roles': 'Assign project roles',
}

const PROJECT_ROLES: ProjectRole[] = ['manager', 'reviewer', 'labeler', 'viewer']
const ROLE_LABEL: Record<ProjectRole, string> = { manager: 'Manager', reviewer: 'Reviewer', labeler: 'Labeler', viewer: 'Viewer' }

/** All permissions for one scope, grouped by their prefix. */
const permissionsFor = (level: RoleLevel) => {
  const prefix = level === 'workspace' ? 'workspace.' : 'project.'
  return Object.keys(PERMISSION_LABELS).filter((p) => p.startsWith(prefix))
}

function PermissionGrid({ level, value, onChange }: { level: RoleLevel; value: string[]; onChange: (v: string[]) => void }) {
  return (
    <fieldset>
      <legend className="mb-1.5 text-sm font-medium">{level === 'workspace' ? 'Workspace permissions' : 'Project permissions'}</legend>
      <div className="grid gap-x-4 gap-y-1.5 rounded-lg border bg-card p-3 sm:grid-cols-2">
        {permissionsFor(level).map((p) => (
          <label key={p} className="flex min-h-6 items-center gap-2 text-sm">
            <input type="checkbox" className="h-4 w-4 accent-primary" checked={value.includes(p)}
              onChange={(e) => onChange(e.target.checked ? [...value, p] : value.filter((x) => x !== p))} />
            <span>{PERMISSION_LABELS[p]}</span>
            <code className="ml-auto hidden text-xs text-muted-foreground lg:inline">{p}</code>
          </label>
        ))}
      </div>
    </fieldset>
  )
}

function RoleDialog({ ws, role, onClose }: { ws: string; role: CustomRole | null; onClose: (saved: boolean) => void }) {
  const [name, setName] = useState(role?.name ?? '')
  const [level, setLevel] = useState<RoleLevel>(role?.level ?? 'project')
  const [permissions, setPermissions] = useState<string[]>(role?.permissions ?? [])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const changeLevel = (next: RoleLevel) => {
    setLevel(next)
    const allowed = new Set(permissionsFor(next))
    setPermissions((p) => p.filter((x) => allowed.has(x)))
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (name.trim().length < 2) return
    setBusy(true); setError('')
    try {
      if (role) await api.updateCustomRole(ws, role.id, { name: name.trim(), permissions })
      else await api.createCustomRole(ws, { name: name.trim(), level, permissions })
      toast.ok(role ? 'Role updated' : 'Role created')
      onClose(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save this role.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open onClose={() => onClose(false)} title={role ? 'Edit custom role' : 'New custom role'}>
      <form onSubmit={submit} className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Name" hint="2–80 characters."><Input required minLength={2} maxLength={80} value={name} onChange={(e) => setName(e.target.value)} placeholder="Site safety reviewer" /></Field>
          <Field label="Level" hint={role ? 'The level is fixed after creation; create a new role to change scope.' : 'Workspace roles apply across projects; project roles apply inside one project.'}>
            <Select className="w-full" value={level} disabled={!!role} onChange={(e) => changeLevel(e.target.value as RoleLevel)}>
              <option value="workspace">Workspace</option>
              <option value="project">Project</option>
            </Select>
          </Field>
        </div>
        <PermissionGrid level={level} value={permissions} onChange={setPermissions} />
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={() => onClose(false)}>Cancel</Button>
          <Button type="submit" disabled={name.trim().length < 2 || busy}>{busy ? 'Saving…' : role ? 'Save role' : 'Create role'}</Button>
        </div>
      </form>
    </Modal>
  )
}

export function WorkspaceRoles() {
  const { ws = '' } = useParams()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['custom-roles', ws], queryFn: () => api.customRoles(ws), enabled: !!ws })
  const [editing, setEditing] = useState<CustomRole | null | undefined>(undefined)
  const [deleting, setDeleting] = useState<CustomRole | null>(null)
  const [busy, setBusy] = useState(false)
  const refresh = () => qc.invalidateQueries({ queryKey: ['custom-roles', ws] })

  const remove = async () => {
    if (!deleting) return
    setBusy(true)
    try {
      await api.deleteCustomRole(ws, deleting.id)
      toast.ok('Role deleted')
      setDeleting(null)
      await refresh()
    } catch (e) {
      toast.err(e as Error)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-2 p-5 pb-4">
        <div>
          <h2 className="font-semibold">Custom roles</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">Bundle permissions once, then assign the role to project members. Built-in roles stay available.</p>
        </div>
        <Button size="sm" onClick={() => setEditing(null)}><Plus className="h-4 w-4" aria-hidden />New role</Button>
      </div>
      {q.isLoading ? (
        <p role="status" className="flex items-center gap-2 border-t px-4 py-8 text-sm text-muted-foreground"><Spinner /> Loading roles…</p>
      ) : q.isError ? (
        <div className="flex flex-wrap items-center gap-2 border-t px-4 py-6">
          <p role="alert" className="text-sm text-destructive">Could not load custom roles.</p>
          <Button variant="outline" size="sm" onClick={() => void q.refetch()}>Try again</Button>
        </div>
      ) : !q.data?.length ? (
        <EmptyState icon={<ShieldCheck className="h-8 w-8 text-muted-foreground/50" aria-hidden />} title="No custom roles yet."
          hint="Create a role for a precise job — for example a reviewer who can see streams but cannot export." />
      ) : (
        <div className="overflow-x-auto border-t" role="region" aria-label="Custom roles" tabIndex={0}>
          <table className="w-full min-w-[34rem] text-sm">
            <caption className="sr-only">Custom workspace and project roles</caption>
            <thead className="bg-muted/60 text-left text-xs text-muted-foreground">
              <tr>
                <th scope="col" className="px-4 py-2 font-medium">Role</th>
                <th scope="col" className="px-4 py-2 font-medium">Level</th>
                <th scope="col" className="px-4 py-2 font-medium">Permissions</th>
                <th scope="col" className="px-4 py-2 font-medium">Created</th>
                <th scope="col" className="px-4 py-2 text-right font-medium"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {(q.data ?? []).map((r) => (
                <tr key={r.id} className="border-t">
                  <td className="px-4 py-2.5 font-medium">{r.name}</td>
                  <td className="px-4 py-2.5"><Badge className="capitalize">{r.level}</Badge></td>
                  <td className="px-4 py-2.5 text-muted-foreground" title={r.permissions.map((p) => PERMISSION_LABELS[p] ?? p).join(', ')}>
                    {r.permissions.length} permission{r.permissions.length === 1 ? '' : 's'}
                  </td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-muted-foreground">{fmtDate(r.created)}</td>
                  <td className="px-4 py-2.5 text-right">
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="sm" onClick={() => setEditing(r)} aria-label={`Edit ${r.name}`}><Pencil className="h-3.5 w-3.5" />Edit</Button>
                      <Button variant="ghost" size="sm" className="text-destructive" onClick={() => setDeleting(r)} aria-label={`Delete ${r.name}`}><Trash2 className="h-3.5 w-3.5" />Delete</Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {editing !== undefined && (
        <RoleDialog key={editing?.id ?? 'new'} ws={ws} role={editing}
          onClose={(saved) => { setEditing(undefined); if (saved) void refresh() }} />
      )}
      <Modal open={!!deleting} onClose={() => setDeleting(null)} title="Delete custom role?">
        <p className="text-sm text-muted-foreground">
          <span className="font-medium text-foreground">{deleting?.name}</span> will be removed from every project member using it. They keep their built-in project role.
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setDeleting(null)}>Cancel</Button>
          <Button variant="destructive" disabled={busy} onClick={remove}>{busy ? 'Deleting…' : 'Delete role'}</Button>
        </div>
      </Modal>
    </Card>
  )
}

/** Project members × project role + custom role. Manager-only writes; read-only otherwise. */
export function ProjectAccess({ ws, project, canEdit }: { ws: string; project: string; canEdit: boolean }) {
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['project-access', ws, project], queryFn: () => api.projectAccess(ws, project), enabled: !!ws && !!project })
  const custom = useQuery({ queryKey: ['custom-roles', ws], queryFn: () => api.customRoles(ws), enabled: !!ws, retry: false })
  const projectRoles = (custom.data ?? []).filter((r) => r.level === 'project')
  const [busy, setBusy] = useState<string | null>(null)
  const refresh = () => qc.invalidateQueries({ queryKey: ['project-access', ws, project] })

  const setRole = async (uid: string, role: ProjectRole, currentCustom: string | null) => {
    setBusy(uid)
    try {
      await api.setProjectMember(ws, project, uid, { role, custom_role_id: currentCustom })
      await refresh()
      toast.ok('Project role updated')
    } catch (e) {
      toast.err(e as Error)
    } finally {
      setBusy(null)
    }
  }

  const setCustom = async (uid: string, role: ProjectRole | null, customId: string) => {
    setBusy(uid)
    try {
      await api.setProjectMember(ws, project, uid, { role: role ?? 'viewer', custom_role_id: customId || null })
      await refresh()
      toast.ok(customId ? 'Custom role assigned' : 'Custom role cleared')
    } catch (e) {
      toast.err(e as Error)
    } finally {
      setBusy(null)
    }
  }

  const reset = async (uid: string) => {
    if (!confirm('Remove the explicit project role so this member inherits from the workspace?')) return
    setBusy(uid)
    try {
      await api.removeProjectMember(ws, project, uid)
      await refresh()
      toast.ok('Member now inherits their workspace role')
    } catch (e) {
      toast.err(e as Error)
    } finally {
      setBusy(null)
    }
  }

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-2 p-5 pb-4">
        <div>
          <h2 className="font-semibold">Project access</h2>
          <p className="mt-0.5 text-sm text-muted-foreground">Per-project roles override the workspace role. Members without a project row inherit from the workspace.</p>
        </div>
        <Badge className="gap-1 bg-card text-foreground"><KeyRound className="h-3 w-3" aria-hidden />RBAC</Badge>
      </div>
      {q.isLoading ? (
        <p role="status" className="flex items-center gap-2 border-t px-4 py-8 text-sm text-muted-foreground"><Spinner /> Loading project members…</p>
      ) : q.isError ? (
        <div className="flex flex-wrap items-center gap-2 border-t px-4 py-6">
          <p role="alert" className="text-sm text-destructive">Could not load project access.</p>
          <Button variant="outline" size="sm" onClick={() => void q.refetch()}>Try again</Button>
        </div>
      ) : !q.data?.members.length ? (
        <EmptyState title="No workspace members to assign." hint="Invite teammates in Settings → Members first." />
      ) : (
        <div className="overflow-x-auto border-t" role="region" aria-label="Project role assignments" tabIndex={0}>
          <table className="w-full min-w-[48rem] text-sm">
            <caption className="sr-only">Workspace members and their project roles</caption>
            <thead className="bg-muted/60 text-left text-xs text-muted-foreground">
              <tr>
                <th scope="col" className="px-4 py-2 font-medium">Member</th>
                <th scope="col" className="px-4 py-2 font-medium">Project role</th>
                <th scope="col" className="px-4 py-2 font-medium">Custom role</th>
                <th scope="col" className="px-4 py-2 font-medium">Effective</th>
                <th scope="col" className="px-4 py-2 text-right font-medium"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {q.data.members.map((m) => {
                const roles = q.data.roles.length ? q.data.roles : PROJECT_ROLES
                return (
                  <tr key={m.id} className="border-t align-middle">
                    <td className="px-4 py-2.5">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="font-medium">{m.name}</span>
                        {m.inherited && <Badge className="text-foreground" title="No project member row — inherited from the workspace">inherited</Badge>}
                      </div>
                      <div className="text-xs text-muted-foreground">{m.email}</div>
                    </td>
                    <td className="px-4 py-2.5">
                      <Select className="h-8" aria-label={`Project role for ${m.name}`} value={m.role ?? ''} disabled={!canEdit || busy === m.id}
                        onChange={(e) => void setRole(m.id, e.target.value as ProjectRole, m.custom_role_id)}>
                        <option value="" disabled>Inherited</option>
                        {roles.map((r) => <option key={r} value={r}>{ROLE_LABEL[r] ?? r}</option>)}
                      </Select>
                    </td>
                    <td className="px-4 py-2.5">
                      <Select className="h-8 max-w-44" aria-label={`Custom role for ${m.name}`} value={m.custom_role_id ?? ''} disabled={!canEdit || busy === m.id || !projectRoles.length}
                        onChange={(e) => void setCustom(m.id, m.role, e.target.value)}>
                        <option value="">{projectRoles.length ? 'No custom role' : 'None created'}</option>
                        {projectRoles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
                      </Select>
                    </td>
                    <td className="px-4 py-2.5 text-xs text-muted-foreground" title={m.effective.join(', ')}>
                      {m.effective.length} permission{m.effective.length === 1 ? '' : 's'}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      {canEdit && !m.inherited && <Button variant="ghost" size="sm" disabled={busy === m.id} onClick={() => void reset(m.id)}>Reset to inherited</Button>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      {!canEdit && q.isSuccess && <p className="border-t px-4 py-3 text-xs text-muted-foreground">Read only — a project manager or workspace admin can change roles.</p>}
    </Card>
  )
}


