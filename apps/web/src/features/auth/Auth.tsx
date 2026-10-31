import { useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { get, post } from '@/lib/api'
import { useApp } from '@/lib/store'
import { Button, Input, toast } from '@/components/ui'

function Frame({ title, sub, children }: { title: string; sub: string; children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-muted px-4">
      <div className="w-full max-w-sm rounded-xl border bg-card p-8 shadow-sm">
        <div className="mb-6 flex items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-lg font-bold text-primary-foreground">L</span>
          <span className="text-xl font-bold tracking-tight">LabelDesk</span>
        </div>
        <h1 className="mb-1 text-lg font-semibold">{title}</h1>
        <p className="mb-5 text-sm text-muted-foreground">{sub}</p>
        {children}
      </div>
    </div>
  )
}

function useSubmit(fn: () => Promise<void>) {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const run = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setErr('')
    try { await fn() } catch (ex) { setErr((ex as Error).message) } finally { setBusy(false) }
  }
  return { busy, err, run }
}

/** Post-login destination from ?next=; only same-origin paths are accepted. */
function useNext(): string {
  const { search } = useLocation()
  const raw = new URLSearchParams(search).get('next') ?? ''
  return raw.startsWith('/') && !raw.startsWith('//') ? raw : '/'
}

const withNext = (path: string, next: string) => next === '/' ? path : `${path}?next=${encodeURIComponent(next)}`

export function Login() {
  const signIn = useApp((s) => s.signIn)
  const nav = useNavigate()
  const next = useNext()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const { busy, err, run } = useSubmit(async () => {
    await signIn('login', { email, password })
    nav(next, { replace: true })
  })
  const cfg = useQuery({ queryKey: ['config'], queryFn: () => get<{ signup_enabled: boolean }>('/config') })
  return (
    <Frame title="Sign in" sub="to continue to your workspace">
      <form className="space-y-3" onSubmit={run}>
        <Input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
        <Input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        {err && <p className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">{err}</p>}
        <Button type="submit" className="w-full" disabled={busy}>{busy && <Loader2 className="h-4 w-4 animate-spin" />} Sign In</Button>
      </form>
      {cfg.data?.signup_enabled && (
        <p className="mt-5 text-center text-sm text-muted-foreground">New here? <Link to={withNext('/signup', next)} className="font-medium text-primary hover:underline">Create an account</Link></p>
      )}
    </Frame>
  )
}

export function Signup() {
  const signIn = useApp((s) => s.signIn)
  const nav = useNavigate()
  const next = useNext()
  const [f, setF] = useState({ name: '', email: '', password: '', workspace: '' })
  const { busy, err, run } = useSubmit(async () => {
    await signIn('signup', { ...f, workspace: f.workspace || `${f.name.split(' ')[0]}'s Workspace` })
    nav(next, { replace: true })
  })
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value })
  return (
    <Frame title="Create your account" sub="Free plan · 3 projects · 10,000 images">
      <form className="space-y-3" onSubmit={run}>
        <Input placeholder="Full name" value={f.name} onChange={set('name')} required autoFocus />
        <Input type="email" placeholder="Work email" value={f.email} onChange={set('email')} required />
        <Input type="password" placeholder="Password (8+ characters)" minLength={8} value={f.password} onChange={set('password')} required />
        <Input placeholder="Workspace name (optional)" value={f.workspace} onChange={set('workspace')} />
        {err && <p className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">{err}</p>}
        <Button type="submit" className="w-full" disabled={busy}>{busy && <Loader2 className="h-4 w-4 animate-spin" />} Create Account</Button>
      </form>
      <p className="mt-5 text-center text-sm text-muted-foreground">Already have an account? <Link to={withNext('/login', next)} className="font-medium text-primary hover:underline">Sign in</Link></p>
    </Frame>
  )
}

export function AcceptInvite() {
  const { token = '' } = useParams()
  const { authed, signIn } = useApp()
  const nav = useNavigate()
  const qc = useQueryClient()
  const info = useQuery({ queryKey: ['invite', token], queryFn: () => get<{ email: string; role: string; workspace: { name: string; slug: string }; has_account: boolean }>(`/invites/${token}`), retry: false })
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const accept = async () => {
    const r = await post<{ workspace: string }>(`/invites/${token}/accept`)
    await qc.invalidateQueries({ queryKey: ['me'] })
    toast.ok('Joined workspace'); nav(`/${r.workspace}`)
  }
  const { busy, err, run } = useSubmit(async () => {
    if (authed) return accept()
    if (info.data?.has_account) await signIn('login', { email: info.data.email, password })
    else await signIn('signup', { name, email: info.data!.email, password, invite: token })
    if (info.data?.has_account) await accept()
    else nav(`/${info.data!.workspace.slug}`)
  })
  if (info.isLoading) return <Frame title="Loading invite…" sub=""><Loader2 className="h-5 w-5 animate-spin" /></Frame>
  if (info.isError || !info.data) return <Frame title="Invite not found" sub="This link was already used or revoked."><Link to="/" className="text-sm text-primary">Go home</Link></Frame>
  const d = info.data
  return (
    <Frame title={`Join ${d.workspace.name}`} sub={`You were invited as ${d.role} (${d.email}).`}>
      <form className="space-y-3" onSubmit={run}>
        {!authed && !d.has_account && <Input placeholder="Full name" value={name} onChange={(e) => setName(e.target.value)} required />}
        {!authed && <Input type="password" placeholder={d.has_account ? 'Your password' : 'Choose a password (8+)'} minLength={d.has_account ? 1 : 8} value={password} onChange={(e) => setPassword(e.target.value)} required />}
        {err && <p className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">{err}</p>}
        <Button type="submit" className="w-full" disabled={busy}>{busy && <Loader2 className="h-4 w-4 animate-spin" />} Accept Invite</Button>
      </form>
    </Frame>
  )
}
