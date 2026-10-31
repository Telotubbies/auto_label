import { useState } from 'react'
import { NavLink, Navigate, Route, Routes, useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Copy, KeyRound, Trash2 } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, del, get, patch, post } from '@/lib/api'
import { useApp } from '@/lib/store'
import type { Role } from '@/lib/types'
import { Badge, Button, Card, EmptyState, Field, Input, PageHeader, Progress, Select, Stat, fmtAgo, fmtDate, toast } from '@/components/ui'
import { cn } from '@/lib/utils'

const copy = (s: string) => { navigator.clipboard.writeText(s); toast.ok('Copied') }

function Account() {
  const me = useApp((s) => s.me)
  const qc = useQueryClient()
  const [name, setName] = useState(me?.name ?? '')
  const [pw, setPw] = useState({ current_password: '', password: '' })
  return (
    <div className="space-y-4">
      <Card className="space-y-3 p-5">
        <h3 className="font-semibold">Profile</h3>
        <Field label="Email"><Input value={me?.email ?? ''} disabled /></Field>
        <Field label="Name"><Input value={name} onChange={(e) => setName(e.target.value)} /></Field>
        <Button onClick={() => patch('/me', { name }).then(() => { qc.invalidateQueries({ queryKey: ['me'] }); toast.ok('Saved') }).catch(toast.err)}>Save</Button>
      </Card>
      <Card className="space-y-3 p-5">
        <h3 className="font-semibold">Change password</h3>
        <Input type="password" placeholder="Current password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} />
        <Input type="password" placeholder="New password (8+)" value={pw.password} onChange={(e) => setPw({ ...pw, password: e.target.value })} />
        <Button disabled={pw.password.length < 8} onClick={() => patch('/me', pw).then(() => { setPw({ current_password: '', password: '' }); toast.ok('Password changed') }).catch(toast.err)}>Update password</Button>
      </Card>
    </div>
  )
}

function Workspace() {
  const { ws = '' } = useParams()
  const qc = useQueryClient()
  const info = useQuery({ queryKey: ['ws', ws], queryFn: () => api.workspace(ws) })
  const [name, setName] = useState('')
  return (
    <Card className="space-y-3 p-5">
      <h3 className="font-semibold">Workspace</h3>
      <Field label="Name"><Input defaultValue={info.data?.name} key={info.data?.name} onChange={(e) => setName(e.target.value)} /></Field>
      <Field label="URL slug" hint="Used in URLs and the upload API."><Input value={ws} disabled /></Field>
      <Button disabled={!name.trim()} onClick={() => patch(`/ws/${ws}`, { name }).then(() => { qc.invalidateQueries({ queryKey: ['me'] }); qc.invalidateQueries({ queryKey: ['ws', ws] }); toast.ok('Saved') }).catch(toast.err)}>Save</Button>
    </Card>
  )
}

function Members() {
  const { ws = '' } = useParams()
  const qc = useQueryClient()
  const me = useApp((s) => s.me)
  const can = useApp((s) => s.can)
  const q = useQuery({ queryKey: ['members', ws], queryFn: () => api.members(ws) })
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<Role>('annotator')
  const refresh = () => qc.invalidateQueries({ queryKey: ['members', ws] })
  const invite = async () => {
    try {
      const r = await post<{ link: string }>(`/ws/${ws}/invites`, { email, role })
      setEmail(''); refresh(); copy(r.link); toast.ok('Invite link copied — send it to your teammate')
    } catch (e) { toast.err(e as Error) }
  }
  return (
    <div className="space-y-4">
      {can('admin') && (
        <Card className="p-5">
          <h3 className="mb-3 font-semibold">Invite teammates</h3>
          <div className="flex gap-2">
            <Input type="email" placeholder="teammate@company.com" value={email} onChange={(e) => setEmail(e.target.value)} />
            <Select value={role} onChange={(e) => setRole(e.target.value as Role)}><option value="annotator">Labeler</option><option value="reviewer">Reviewer</option><option value="admin">Admin</option></Select>
            <Button disabled={!email.includes('@')} onClick={invite}>Invite</Button>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">Labelers annotate assigned images · Reviewers approve work, manage data and versions · Admins also train, deploy and manage billing.</p>
        </Card>
      )}
      <Card className="overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/60 text-left text-xs text-muted-foreground"><tr><th className="px-4 py-2">Member</th><th>Role</th><th>Joined</th><th /></tr></thead>
          <tbody>
            {q.data?.members.map((m) => (
              <tr key={m.id} className="border-t">
                <td className="px-4 py-2.5"><div className="font-medium">{m.name} {m.owner && <Badge>Owner</Badge>}</div><div className="text-xs text-muted-foreground">{m.email}</div></td>
                <td>{can('admin') && !m.owner
                  ? <Select className="h-8" value={m.role} onChange={(e) => patch(`/ws/${ws}/members/${m.id}`, { role: e.target.value }).then(refresh).catch(toast.err)}><option value="annotator">Labeler</option><option value="reviewer">Reviewer</option><option value="admin">Admin</option></Select>
                  : <span className="capitalize">{m.role === 'annotator' ? 'labeler' : m.role}</span>}</td>
                <td className="text-muted-foreground">{fmtDate(m.joined)}</td>
                <td className="pr-3 text-right">{!m.owner && (can('admin') || m.id === me?.id) && <Button variant="ghost" size="sm" onClick={() => confirm(m.id === me?.id ? 'Leave this workspace?' : `Remove ${m.name}?`) && del(`/ws/${ws}/members/${m.id}`).then(refresh).catch(toast.err)}>{m.id === me?.id ? 'Leave' : 'Remove'}</Button>}</td>
              </tr>
            ))}
            {q.data?.invites.map((i) => (
              <tr key={i.token} className="border-t bg-amber-50/40">
                <td className="px-4 py-2.5"><div className="font-medium">{i.email}</div><div className="text-xs text-muted-foreground">Invite pending</div></td>
                <td className="capitalize">{i.role === 'annotator' ? 'labeler' : i.role}</td>
                <td><button className="inline-flex cursor-pointer items-center gap-1 text-xs text-primary" onClick={() => copy(i.link)}><Copy className="h-3 w-3" /> Copy link</button></td>
                <td className="pr-3 text-right"><Button variant="ghost" size="sm" onClick={() => del(`/ws/${ws}/invites/${i.token}`).then(refresh).catch(toast.err)}>Revoke</Button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  )
}

type Key = { id: string; name: string; prefix: string; created: number; last_used: number | null }
function ApiKeys() {
  const { ws = '' } = useParams()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['keys', ws], queryFn: () => get<Key[]>(`/ws/${ws}/keys`) })
  const [name, setName] = useState('')
  const [fresh, setFresh] = useState('')
  return (
    <div className="space-y-4">
      <Card className="p-5">
        <h3 className="mb-1 font-semibold">API keys</h3>
        <p className="mb-3 text-sm text-muted-foreground">Keys authorise the hosted inference and upload APIs for this workspace. They're shown once — store them as secrets.</p>
        <div className="flex gap-2"><Input placeholder="Key name, e.g. production camera" value={name} onChange={(e) => setName(e.target.value)} />
          <Button disabled={!name.trim()} onClick={() => post<{ key: string }>(`/ws/${ws}/keys`, { name }).then((r) => { setFresh(r.key); setName(''); qc.invalidateQueries({ queryKey: ['keys', ws] }) }).catch(toast.err)}><KeyRound className="h-4 w-4" /> Create key</Button></div>
        {fresh && (
          <div className="mt-3 rounded-lg border border-green-300 bg-green-50 p-3 text-sm">
            <div className="mb-1 font-medium text-green-900">Copy your new key now — it won't be shown again.</div>
            <div className="flex items-center gap-2"><code className="flex-1 break-all rounded bg-white px-2 py-1 font-mono text-xs">{fresh}</code><Button size="sm" variant="outline" onClick={() => copy(fresh)}><Copy className="h-3.5 w-3.5" /></Button></div>
          </div>
        )}
      </Card>
      <Card className="overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/60 text-left text-xs text-muted-foreground"><tr><th className="px-4 py-2">Name</th><th>Key</th><th>Created</th><th>Last used</th><th /></tr></thead>
          <tbody>{q.data?.map((k) => (
            <tr key={k.id} className="border-t"><td className="px-4 py-2.5 font-medium">{k.name}</td><td className="font-mono text-xs">{k.prefix}…</td><td>{fmtDate(k.created)}</td><td className="text-muted-foreground">{k.last_used ? fmtAgo(k.last_used) : 'never'}</td>
              <td className="pr-3 text-right"><Button variant="ghost" size="icon" onClick={() => confirm(`Revoke "${k.name}"? Apps using it stop working.`) && del(`/ws/${ws}/keys/${k.id}`).then(() => qc.invalidateQueries({ queryKey: ['keys', ws] })).catch(toast.err)}><Trash2 className="h-4 w-4" /></Button></td></tr>
          ))}</tbody>
        </table>
        {q.isSuccess && !q.data.length && <EmptyState title="No API keys yet." />}
      </Card>
    </div>
  )
}

function Usage() {
  const { ws = '' } = useParams()
  const q = useQuery({ queryKey: ['usage', ws], queryFn: () => get<any>(`/ws/${ws}/usage`) })
  const u = q.data
  if (!u) return null
  const bar = (used: number, lim: number) => <Progress className="mt-2" value={(used / lim) * 100} />
  return (
    <div className="space-y-4">
      <Card className="flex items-center justify-between p-5">
        <div><div className="text-xs text-muted-foreground">Current plan</div><div className="text-2xl font-bold">{u.plan_label}</div><div className="text-xs text-muted-foreground">Credits reset monthly · period {u.period}</div></div>
        <p className="max-w-xs text-right text-xs text-muted-foreground">To change plans, contact your LabelDesk operator. Plan limits are enforced on every upload, training run and API call.</p>
      </Card>
      <div className="grid gap-3 md:grid-cols-4">
        <Card className="p-4"><div className="text-xs text-muted-foreground">Credits</div><div className="text-xl font-bold">{u.credits_used.toFixed(2)} <span className="text-sm font-normal text-muted-foreground">/ {u.limits.credits}</span></div>{bar(u.credits_used, u.limits.credits)}</Card>
        <Card className="p-4"><div className="text-xs text-muted-foreground">Images</div><div className="text-xl font-bold">{u.images.toLocaleString()} <span className="text-sm font-normal text-muted-foreground">/ {u.limits.images.toLocaleString()}</span></div>{bar(u.images, u.limits.images)}</Card>
        <Card className="p-4"><div className="text-xs text-muted-foreground">Projects</div><div className="text-xl font-bold">{u.projects} <span className="text-sm font-normal text-muted-foreground">/ {u.limits.projects}</span></div>{bar(u.projects, u.limits.projects)}</Card>
        <Card className="p-4"><div className="text-xs text-muted-foreground">Seats</div><div className="text-xl font-bold">{u.seats} <span className="text-sm font-normal text-muted-foreground">/ {u.limits.seats}</span></div>{bar(u.seats, u.limits.seats)}</Card>
      </div>
      <Card className="p-4">
        <h3 className="mb-3 text-sm font-semibold">Activity, last 30 days</h3>
        <div className="h-56"><ResponsiveContainer><BarChart data={u.daily}><CartesianGrid vertical={false} strokeDasharray="3 3" stroke="#eee" /><XAxis dataKey="date" tick={{ fontSize: 10 }} /><YAxis tick={{ fontSize: 10 }} allowDecimals={false} /><Tooltip />
          {['image', 'infer', 'train', 'version'].map((k, i) => <Bar key={k} dataKey={k} stackId="a" fill={['#8b5cf6', '#3b82f6', '#22c55e', '#f97316'][i]} />)}</BarChart></ResponsiveContainer></div>
      </Card>
      <Stat label="Models trained" value={u.models} />
    </div>
  )
}

type TrashRow = { id: string; name: string; type: string; deleted_at: number }
function Trash() {
  const { ws = '' } = useParams()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['trash', ws], queryFn: () => get<TrashRow[]>(`/ws/${ws}/trash`) })
  const refresh = () => { qc.invalidateQueries({ queryKey: ['trash', ws] }); qc.invalidateQueries({ queryKey: ['projects', ws] }) }
  return (
    <Card className="overflow-hidden">
      {q.data?.map((p) => (
        <div key={p.id} className="flex items-center gap-3 border-b px-4 py-3 text-sm last:border-0">
          <span className="flex-1 font-medium">{p.name}</span><span className="text-xs text-muted-foreground">deleted {fmtAgo(p.deleted_at)}</span>
          <Button size="sm" variant="outline" onClick={() => post(`/ws/${ws}/trash/${p.id}/restore`).then(refresh).catch(toast.err)}>Restore</Button>
          <Button size="sm" variant="destructive" onClick={() => confirm(`Permanently delete "${p.name}" and all its images?`) && del(`/ws/${ws}/trash/${p.id}`).then(refresh).catch(toast.err)}>Delete forever</Button>
        </div>
      ))}
      {q.isSuccess && !q.data.length && <EmptyState title="Trash is empty." />}
    </Card>
  )
}

function FirstRun() {
  const nav = useNavigate()
  const qc = useQueryClient()
  const [name, setName] = useState('')
  return (
    <div className="flex min-h-screen items-center justify-center bg-muted">
      <Card className="w-full max-w-sm p-6">
        <h1 className="mb-2 text-lg font-semibold">Create a workspace</h1>
        <p className="mb-4 text-sm text-muted-foreground">You're not part of any workspace yet.</p>
        <Input value={name} placeholder="My team" onChange={(e) => setName(e.target.value)} />
        <Button className="mt-3 w-full" disabled={!name.trim()} onClick={() => post<{ slug: string }>('/workspaces', { name }).then(async (w) => { await qc.invalidateQueries({ queryKey: ['me'] }); nav(`/${w.slug}`) }).catch(toast.err)}>Create</Button>
      </Card>
    </div>
  )
}

export default function Settings({ firstRun }: { firstRun?: boolean }) {
  const can = useApp((s) => s.can)
  if (firstRun) return <FirstRun />
  const tabs = [
    { to: 'account', label: 'Account', show: true },
    { to: 'workspace', label: 'Workspace', show: can('admin') },
    { to: 'members', label: 'Members', show: true },
    { to: 'api', label: 'API Keys', show: can('admin') },
    { to: 'usage', label: 'Plan & Usage', show: true },
    { to: 'trash', label: 'Trash', show: can('admin') },
  ].filter((t) => t.show)
  return (
    <div className="anim-page max-w-5xl">
      <PageHeader title="Settings" />
      <div className="flex gap-6 px-8 pb-10">
        <nav className="w-44 shrink-0 space-y-0.5">
          {tabs.map((t) => <NavLink key={t.to} to={t.to} className={({ isActive }) => cn('block rounded-md px-3 py-2 text-sm', isActive ? 'bg-accent font-medium text-accent-foreground' : 'hover:bg-muted')}>{t.label}</NavLink>)}
        </nav>
        <div className="min-w-0 flex-1">
          <Routes>
            <Route index element={<Navigate to="account" replace />} />
            <Route path="account" element={<Account />} />
            <Route path="workspace" element={<Workspace />} />
            <Route path="members" element={<Members />} />
            <Route path="api" element={<ApiKeys />} />
            <Route path="usage" element={<Usage />} />
            <Route path="trash" element={<Trash />} />
          </Routes>
        </div>
      </div>
    </div>
  )
}
