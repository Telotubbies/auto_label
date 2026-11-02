import { useState } from 'react'
import { Link, NavLink, Navigate, Route, Routes, useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, CheckCircle2, CircleAlert, Copy, KeyRound, ShieldCheck, ShieldOff, Trash2, XCircle } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, del, get, patch, post, tokens } from '@/lib/api'
import { useApp } from '@/lib/store'
import type { LoginEvent, Me, MfaSetup, Role, SessionRow, Usage, UsageMeter, UsageMeterKey } from '@/lib/types'
import { Badge, Button, Card, EmptyState, Field, Input, PageHeader, Progress, Select, Spinner, Stat, Switch, fmtAgo, fmtDate, toast } from '@/components/ui'
import { DEFAULT_SEED, dateLocale, setThemePrefs, useThemePrefs, type Contrast, type ModePref, type Scheme } from '@/lib/theme'
import { cn } from '@/lib/utils'
import PrivacyWorkspace from '@/features/governance/Privacy'
import { WorkspaceRoles } from '@/features/governance/Roles'

const ROLE_LABEL: Record<Role, string> = {
  owner: 'Owner', admin: 'Admin', billing: 'Billing', member: 'Member', reviewer: 'Reviewer', annotator: 'Labeler',
}
const ASSIGNABLE_ROLES: Role[] = ['admin', 'billing', 'member', 'reviewer', 'annotator']

const copy = (s: string, message = 'Copied') => {
  navigator.clipboard.writeText(s).then(() => toast.ok(message)).catch(() => toast.err('Could not copy — select the text and copy it by hand.'))
}

function Account() {
  const me = useApp((s) => s.me)
  const qc = useQueryClient()
  const [name, setName] = useState(me?.name ?? '')
  const [pw, setPw] = useState({ current_password: '', password: '' })
  return (
    <div className="space-y-4">
      <Card className="space-y-3 p-5">
        <h2 className="font-semibold">Profile</h2>
        <Field label="Email"><Input value={me?.email ?? ''} disabled /></Field>
        <Field label="Name"><Input value={name} onChange={(e) => setName(e.target.value)} /></Field>
        <Button onClick={() => patch('/me', { name }).then(() => { qc.invalidateQueries({ queryKey: ['me'] }); toast.ok('Saved') }).catch(toast.err)}>Save</Button>
      </Card>
      <Card className="space-y-3 p-5">
        <h2 className="font-semibold">Change password</h2>
        <Field label="Current password">
          <Input type="password" autoComplete="current-password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} />
        </Field>
        <Field label="New password" hint="At least 8 characters.">
          <Input type="password" autoComplete="new-password" value={pw.password} onChange={(e) => setPw({ ...pw, password: e.target.value })} />
        </Field>
        <Button disabled={pw.password.length < 8} onClick={() => patch('/me', pw).then(() => { setPw({ current_password: '', password: '' }); toast.ok('Password changed') }).catch(toast.err)}>Update password</Button>
      </Card>
    </div>
  )
}

// --- security -----------------------------------------------------------------

const UA_BROWSERS: { re: RegExp; name: string }[] = [
  { re: /Edg\//, name: 'Edge' },
  { re: /Firefox\//, name: 'Firefox' },
  { re: /Chrome\//, name: 'Chrome' },
  { re: /Safari\//, name: 'Safari' },
]
const UA_PLATFORMS: { re: RegExp; name: string }[] = [
  { re: /Android/, name: 'Android' },
  { re: /iPhone|iPad|iPod/, name: 'iOS' },
  { re: /Windows/, name: 'Windows' },
  { re: /Macintosh|Mac OS X/, name: 'macOS' },
  { re: /Linux/, name: 'Linux' },
]

/** Compact device label from a raw User-Agent, or "Unknown device". */
function describeDevice(ua: string) {
  const browser = UA_BROWSERS.find((u) => u.re.test(ua))?.name ?? ''
  const platform = UA_PLATFORMS.find((u) => u.re.test(ua))?.name ?? ''
  return [browser, platform].filter(Boolean).join(' on ') || 'Unknown device'
}

const LOGIN_METHOD: Record<LoginEvent['method'], string> = {
  password: 'Password',
  mfa: 'Password + 2FA',
  oidc: 'SSO',
}

function TableLoading({ label }: { label: string }) {
  return (
    <div role="status" className="flex items-center justify-center gap-2 border-t px-4 py-10 text-sm text-muted-foreground">
      <Spinner /> {label}
    </div>
  )
}

function TableError({ label, onRetry }: { label: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center gap-2 border-t px-4 py-8 text-center">
      <p role="alert" className="text-sm text-destructive">{label}</p>
      <Button variant="outline" size="sm" onClick={onRetry}>Try again</Button>
    </div>
  )
}

function EmailCard({ me }: { me: Me }) {
  const qc = useQueryClient()
  const [sending, setSending] = useState(false)
  const verified = me.email_verified != null

  const resend = async () => {
    setSending(true)
    try {
      const r = await post<{ ok: boolean; already_verified?: boolean }>('/auth/email/resend')
      if (r.already_verified) {
        toast.ok('This address is already verified')
        qc.invalidateQueries({ queryKey: ['me'] })
      } else {
        toast.ok('Verification email sent — check your inbox')
      }
    } catch (e) {
      toast.err(e as Error)
    } finally {
      setSending(false)
    }
  }

  return (
    <Card className="space-y-3 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold">Email address</h2>
        <Badge className={cn('gap-1 text-foreground', verified ? 'bg-success/15' : 'bg-warning/15')}>
          {verified
            ? <Check className="h-3 w-3 text-success" aria-hidden />
            : <CircleAlert className="h-3 w-3 text-warning" aria-hidden />}
          {verified ? 'Verified' : 'Not verified'}
        </Badge>
      </div>
      <div>
        <div className="break-all text-sm font-medium">{me.email}</div>
        <p className="mt-0.5 text-xs text-muted-foreground">
          {me.email_verified != null
            ? `Verified on ${fmtDate(me.email_verified)}. We send password resets here.`
            : 'This is the address you sign in with. We also use it for password resets.'}
        </p>
      </div>
      {!verified && (
        <div className="rounded-lg border border-warning/40 bg-warning/10 p-3">
          <p className="flex items-start gap-2 text-sm">
            <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden />
            <span>Confirm this address so you can recover your account if you forget your password — and so nobody else can sign up with it.</span>
          </p>
          <Button variant="outline" size="sm" className="mt-3 bg-card" disabled={sending} aria-busy={sending} onClick={resend}>
            {sending && <Spinner className="h-3.5 w-3.5" />}
            {sending ? 'Sending…' : 'Resend verification email'}
          </Button>
        </div>
      )}
    </Card>
  )
}

type MfaPhase = 'idle' | 'password' | 'setup' | 'codes'

function TwoFactorCard({ me }: { me: Me }) {
  const qc = useQueryClient()
  const [phase, setPhase] = useState<MfaPhase>('idle')
  const [setup, setSetup] = useState<MfaSetup | null>(null)
  const [code, setCode] = useState('')
  const [starting, setStarting] = useState(false)
  const [enabling, setEnabling] = useState(false)
  const [recovery, setRecovery] = useState<string[]>([])
  const [saved, setSaved] = useState(false)
  const [offOpen, setOffOpen] = useState(false)
  const [password, setPassword] = useState('')
  const [setupPassword, setSetupPassword] = useState('')
  const [disabling, setDisabling] = useState(false)
  const [error, setError] = useState('')

  const enabled = me.mfa_enabled || phase === 'codes'
  const enforcedBy = me.workspaces.filter((w) => w.mfa_required)
  const errText = (e: unknown) => (e instanceof Error ? e.message : 'Something went wrong — try again.')

  const start = async (pw: string) => {
    setError('')
    setStarting(true)
    try {
      const s = await post<MfaSetup>('/auth/mfa/setup', { password: pw })
      setSetup(s)
      setCode('')
      setSetupPassword('')
      setPhase('setup')
    } catch (e) {
      setError(errText(e))
    } finally {
      setStarting(false)
    }
  }

  const enable = async () => {
    if (!setup || code.length !== 6) return
    setError('')
    setEnabling(true)
    try {
      const r = await post<{ recovery_codes: string[] }>('/auth/mfa/enable', { code })
      setRecovery(r.recovery_codes)
      setSetup(null)
      setCode('')
      setSaved(false)
      setPhase('codes')
      qc.setQueryData<Me>(['me'], (old) => (old ? { ...old, mfa_enabled: true } : old))
      qc.invalidateQueries({ queryKey: ['me'] })
    } catch (e) {
      setError(errText(e))
    } finally {
      setEnabling(false)
    }
  }

  const cancelSetup = () => {
    setPhase('idle')
    setSetup(null)
    setCode('')
    setSetupPassword('')
    setError('')
  }

  const finish = () => {
    setPhase('idle')
    setRecovery([])
    setSaved(false)
    setError('')
  }

  const disable = async () => {
    if (!password) return
    setError('')
    setDisabling(true)
    try {
      await post('/auth/mfa/disable', { password })
      setPassword('')
      setOffOpen(false)
      qc.setQueryData<Me>(['me'], (old) => (old ? { ...old, mfa_enabled: false } : old))
      await qc.invalidateQueries({ queryKey: ['me'] })
      toast.ok('Two-factor authentication is off')
    } catch (e) {
      setError(errText(e))
    } finally {
      setDisabling(false)
    }
  }

  return (
    <Card className="space-y-3 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold">Two-factor authentication</h2>
        <Badge className={cn('gap-1 text-foreground', enabled ? 'bg-success/15' : 'bg-muted')}>
          {enabled
            ? <ShieldCheck className="h-3 w-3 text-success" aria-hidden />
            : <ShieldOff className="h-3 w-3 text-muted-foreground" aria-hidden />}
          {enabled ? 'On' : 'Off'}
        </Badge>
      </div>
      <p className="text-sm text-muted-foreground">
        {enabled
          ? 'A 6-digit code from your authenticator app is required after your password.'
          : 'Add a second step to sign-in. Even if someone learns your password, they still need your authenticator.'}
      </p>

      {phase === 'codes' ? (
        <div className="space-y-3 rounded-lg border border-primary/40 bg-primary/5 p-4">
          <div>
            <h3 className="font-medium">Save your recovery codes</h3>
            <p className="mt-0.5 text-sm text-muted-foreground">
              Each code signs you in once if you lose your authenticator. This is the only time they're shown — leaving this page hides them for good.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {recovery.map((c) => (
              <code key={c} className="select-all rounded-md border bg-card px-2 py-1.5 text-center font-mono text-xs tracking-wide sm:text-sm">{c}</code>
            ))}
          </div>
          <Button type="button" variant="outline" size="sm" onClick={() => copy(recovery.join('\n'), 'Recovery codes copied')}>
            <Copy className="h-3.5 w-3.5" /> Copy codes
          </Button>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="h-4 w-4 accent-primary" checked={saved} onChange={(e) => setSaved(e.target.checked)} />
            I've saved these codes
          </label>
          <div><Button disabled={!saved} onClick={finish}>Done</Button></div>
        </div>
      ) : phase === 'password' ? (
        <form
          className="space-y-3 rounded-lg border bg-muted/40 p-4"
          onSubmit={(e) => { e.preventDefault(); if (setupPassword) void start(setupPassword) }}
        >
          <Field label="Account password" hint="Confirm it's you before adding a second factor.">
            <Input
              type="password"
              autoComplete="current-password"
              required
              autoFocus
              value={setupPassword}
              onChange={(e) => { setSetupPassword(e.target.value); setError('') }}
            />
          </Field>
          {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={!setupPassword || starting}>{starting ? 'Preparing…' : 'Continue'}</Button>
            <Button type="button" variant="ghost" onClick={cancelSetup}>Cancel</Button>
          </div>
        </form>
      ) : phase === 'setup' && setup ? (
        <form
          className="space-y-4 rounded-lg border bg-muted/40 p-4"
          onSubmit={(e) => { e.preventDefault(); enable() }}
        >
          <ol className="space-y-4">
            <li className="flex gap-3">
              <span aria-hidden className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-primary/10 text-[11px] font-semibold text-primary">1</span>
              <div className="min-w-0 flex-1 space-y-2">
                <div className="text-sm font-medium">Scan the QR code</div>
                <p className="text-xs text-muted-foreground">Open your authenticator app, add an account and scan this code.</p>
                {setup.qr
                  ? <img src={setup.qr} alt="QR code to scan with your authenticator app" className="h-auto w-40 max-w-full rounded-md border bg-white p-2" />
                  : <p className="text-xs text-muted-foreground">The QR code isn't available — enter the key below instead.</p>}
              </div>
            </li>
            <li className="flex gap-3">
              <span aria-hidden className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-primary/10 text-[11px] font-semibold text-primary">2</span>
              <div className="min-w-0 flex-1 space-y-2">
                <div className="text-sm font-medium">Or enter the key manually</div>
                <div className="flex items-start gap-2">
                  <code className="min-w-0 flex-1 select-all break-all rounded-md border bg-card px-2.5 py-2 font-mono text-xs">{setup.secret}</code>
                  <Button type="button" variant="outline" size="icon" aria-label="Copy setup key" onClick={() => copy(setup.secret, 'Setup key copied')}>
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">Choose time-based (TOTP) if your app asks.</p>
              </div>
            </li>
            <li className="flex gap-3">
              <span aria-hidden className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-primary/10 text-[11px] font-semibold text-primary">3</span>
              <div className="min-w-0 flex-1">
                <Field label="Verification code" hint="The 6-digit code your app shows now.">
                  <Input
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    pattern="[0-9]*"
                    maxLength={6}
                    placeholder="123456"
                    value={code}
                    onChange={(e) => { setCode(e.target.value.replace(/\D/g, '').slice(0, 6)); setError('') }}
                    className="max-w-40 font-mono tracking-[0.3em]"
                    autoFocus
                  />
                </Field>
              </div>
            </li>
          </ol>
          {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={code.length !== 6 || enabling}>{enabling ? 'Turning on…' : 'Turn on two-factor'}</Button>
            <Button type="button" variant="ghost" onClick={cancelSetup}>Cancel</Button>
          </div>
        </form>
      ) : enabled ? (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">Keep your recovery codes somewhere safe — they're the way back in if you lose your authenticator.</p>
          {enforcedBy.length > 0 ? (
            <div className="space-y-1.5">
              <Button variant="outline" disabled>Turn off two-factor</Button>
              <p className="text-xs text-muted-foreground">
                Required by {enforcedBy.map((w) => w.name).join(', ')}. You can't turn it off while {enforcedBy.length > 1 ? 'these workspaces require it' : 'this workspace requires it'}.
              </p>
            </div>
          ) : offOpen ? (
            <div className="space-y-3 rounded-lg border p-4">
              <Field label="Account password" hint="Every device stays signed in. After this, future sign-ins only need your password.">
                <Input
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => { setPassword(e.target.value); setError('') }}
                />
              </Field>
              {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
              <div className="flex flex-wrap gap-2">
                <Button variant="destructive" disabled={!password || disabling} onClick={disable}>{disabling ? 'Turning off…' : 'Turn off two-factor'}</Button>
                <Button variant="ghost" onClick={() => { setOffOpen(false); setPassword(''); setError('') }}>Cancel</Button>
              </div>
            </div>
          ) : (
            <Button variant="outline" onClick={() => { setOffOpen(true); setError('') }}>Turn off two-factor</Button>
          )}
        </div>
      ) : (
        <>
          <p className="flex items-start gap-2 text-sm text-muted-foreground">
            <KeyRound className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            <span>Use any authenticator app — 1Password, Google Authenticator, Authy or a hardware key.</span>
          </p>
          {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
          <Button onClick={() => { setPhase('password'); setError('') }}>Turn on two-factor</Button>
        </>
      )}
    </Card>
  )
}

function SessionsCard() {
  const qc = useQueryClient()
  const logout = useApp((s) => s.logout)
  const current = tokens.session
  const q = useQuery({ queryKey: ['me', 'sessions'], queryFn: () => get<SessionRow[]>('/me/sessions') })
  const rows = q.data ?? []

  const revoke = async (s: SessionRow) => {
    const device = describeDevice(s.user_agent)
    if (s.id === current) {
      if (confirm('Sign out this device?')) logout()
      return
    }
    if (!confirm(`Revoke the session from ${device}? That device will be signed out.`)) return
    try {
      await del(`/me/sessions/${encodeURIComponent(s.id)}`)
      await qc.invalidateQueries({ queryKey: ['me', 'sessions'] })
      toast.ok('Session revoked')
    } catch (e) {
      toast.err(e as Error)
    }
  }

  return (
    <Card className="overflow-hidden">
      <div className="p-5 pb-4">
        <h2 className="font-semibold">Sessions</h2>
        <p className="mt-0.5 text-xs text-muted-foreground">Every browser signed in to your account. Revoke anything you don't recognise.</p>
      </div>
      {q.isLoading ? (
        <TableLoading label="Loading sessions…" />
      ) : q.isError ? (
        <TableError label={q.error instanceof Error ? q.error.message : 'Could not load sessions.'} onRetry={() => void q.refetch()} />
      ) : !rows.length ? (
        <EmptyState title="No active sessions." hint="Devices you sign in with will appear here." />
      ) : (
        <div className="overflow-x-auto border-t" role="region" aria-label="Sessions" tabIndex={0}>
          <table className="w-full min-w-[40rem] text-sm">
            <caption className="sr-only">Devices signed in to your account</caption>
            <thead className="bg-muted/60 text-left text-xs text-muted-foreground">
              <tr>
                <th scope="col" className="px-4 py-2 font-medium">Device</th>
                <th scope="col" className="whitespace-nowrap px-4 py-2 font-medium">IP address</th>
                <th scope="col" className="whitespace-nowrap px-4 py-2 font-medium">Last active</th>
                <th scope="col" className="whitespace-nowrap px-4 py-2 font-medium">Signed in</th>
                <th scope="col" className="px-4 py-2 text-right font-medium"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((s) => {
                const isCurrent = s.id === current
                return (
                  <tr key={s.id} className="border-t align-top">
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">{describeDevice(s.user_agent)}</span>
                        {isCurrent && <Badge>This device</Badge>}
                      </div>
                      <div className="mt-0.5 max-w-[18rem] truncate text-[11px] text-muted-foreground" title={s.user_agent || undefined}>
                        {s.user_agent || 'No device details'}
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 font-mono text-xs">{s.ip || '—'}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-muted-foreground">
                      <time dateTime={new Date(s.last_seen * 1000).toISOString()} title={fmtDate(s.last_seen)}>{fmtAgo(s.last_seen)}</time>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-muted-foreground">{fmtDate(s.created)}</td>
                    <td className="px-4 py-3 text-right">
                      {!isCurrent && (
                        <Button variant="ghost" size="sm" aria-label={`Revoke the session from ${describeDevice(s.user_agent)}`} onClick={() => revoke(s)}>
                          Revoke
                        </Button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

function LoginHistoryCard() {
  const q = useQuery({ queryKey: ['me', 'logins'], queryFn: () => get<LoginEvent[]>('/me/logins?limit=50') })
  const rows = q.data ?? []

  return (
    <Card className="overflow-hidden">
      <div className="p-5 pb-4">
        <h2 className="font-semibold">Login history</h2>
        <p className="mt-0.5 text-xs text-muted-foreground">The last 50 sign-in attempts on this account.</p>
      </div>
      {q.isLoading ? (
        <TableLoading label="Loading login history…" />
      ) : q.isError ? (
        <TableError label={q.error instanceof Error ? q.error.message : 'Could not load login history.'} onRetry={() => void q.refetch()} />
      ) : !rows.length ? (
        <EmptyState title="No sign-ins recorded yet." hint="Attempts to sign in to this account will appear here." />
      ) : (
        <div className="overflow-x-auto border-t" role="region" aria-label="Login history" tabIndex={0}>
          <table className="w-full min-w-[36rem] text-sm">
            <caption className="sr-only">Recent sign-in attempts</caption>
            <thead className="bg-muted/60 text-left text-xs text-muted-foreground">
              <tr>
                <th scope="col" className="px-4 py-2 font-medium">Result</th>
                <th scope="col" className="px-4 py-2 font-medium">Method</th>
                <th scope="col" className="whitespace-nowrap px-4 py-2 font-medium">IP address</th>
                <th scope="col" className="whitespace-nowrap px-4 py-2 font-medium">When</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((l, i) => (
                <tr key={`${l.created}-${l.ip}-${i}`} className="border-t">
                  <td className="px-4 py-2.5">
                    {l.ok ? (
                      <span className="inline-flex items-center gap-1.5">
                        <CheckCircle2 className="h-4 w-4 text-success" aria-hidden />
                        <span className="font-medium">Signed in</span>
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5">
                        <XCircle className="h-4 w-4 text-destructive" aria-hidden />
                        <span className="font-medium">Failed attempt</span>
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">{LOGIN_METHOD[l.method] ?? l.method}</td>
                  <td className="whitespace-nowrap px-4 py-2.5 font-mono text-xs">{l.ip || '—'}</td>
                  <td className="whitespace-nowrap px-4 py-2.5 text-muted-foreground">
                    <time dateTime={new Date(l.created * 1000).toISOString()} title={fmtDate(l.created)}>{fmtAgo(l.created)}</time>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

function Security() {
  const me = useApp((s) => s.me)
  if (!me) {
    return (
      <Card className="flex items-center gap-2 p-5 text-sm text-muted-foreground" role="status">
        <Spinner /> Loading your security settings…
      </Card>
    )
  }
  return (
    <div className="space-y-4">
      <EmailCard me={me} />
      <TwoFactorCard me={me} />
      <SessionsCard />
      <LoginHistoryCard />
    </div>
  )
}

const SEEDS = [
  { hex: '#3b6cf6', name: 'Blue' }, { hex: '#7c4dff', name: 'Violet' }, { hex: '#0b8f8f', name: 'Teal' },
  { hex: '#1e8e3e', name: 'Green' }, { hex: '#e8710a', name: 'Orange' }, { hex: '#d93378', name: 'Magenta' },
]

function Appearance() {
  const p = useThemePrefs()
  const seg = <T extends string | number>(label: string, value: T, opts: { v: T; l: string }[], set: (v: T) => void) => (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-lg border border-input p-0.5">
      {opts.map((o) => (
        <button key={String(o.v)} type="button" role="radio" aria-checked={value === o.v} onClick={() => set(o.v)}
          className={cn('h-8 cursor-pointer rounded-md px-3 text-sm', value === o.v ? 'bg-primary text-primary-foreground' : 'hover:bg-accent hover:text-accent-foreground')}>{o.l}</button>
      ))}
    </div>
  )
  return (
    <div className="space-y-4">
      <Card className="space-y-4 p-5">
        <h2 className="font-semibold">Colour</h2>
        <Field label="Seed colour" hint="The whole palette (light and dark) is generated from this colour with Material HCT.">
          <div className="flex flex-wrap items-center gap-2">
            {SEEDS.map((s) => (
              <button key={s.hex} type="button" aria-label={s.name} aria-pressed={p.seed.toLowerCase() === s.hex} onClick={() => setThemePrefs({ seed: s.hex })}
                className={cn('h-8 w-8 cursor-pointer rounded-full border-2', p.seed.toLowerCase() === s.hex ? 'border-foreground' : 'border-transparent')} style={{ background: s.hex }} />
            ))}
            <input type="color" aria-label="Custom seed colour" value={p.seed} onChange={(e) => setThemePrefs({ seed: e.target.value })} className="h-8 w-10 cursor-pointer rounded-md border border-input bg-card p-0.5" />
            <Button variant="ghost" size="sm" onClick={() => setThemePrefs({ seed: DEFAULT_SEED })}>Reset</Button>
          </div>
        </Field>
        <div className="flex flex-wrap gap-x-8 gap-y-4">
          <div><div className="mb-1.5 text-sm font-medium">Mode</div>{seg<ModePref>('Mode', p.mode, [{ v: 'system', l: 'System' }, { v: 'light', l: 'Light' }, { v: 'dark', l: 'Dark' }], (mode) => setThemePrefs({ mode }))}</div>
          <div><div className="mb-1.5 text-sm font-medium">Style</div>{seg<Scheme>('Style', p.scheme, [{ v: 'vibrant', l: 'Vibrant' }, { v: 'tonal-spot', l: 'Tonal' }, { v: 'expressive', l: 'Expressive' }], (scheme) => setThemePrefs({ scheme }))}</div>
          <div><div className="mb-1.5 text-sm font-medium">Contrast</div>{seg<Contrast>('Contrast', p.contrast, [{ v: 0, l: 'Standard' }, { v: 0.5, l: 'Medium' }, { v: 1, l: 'High' }], (contrast) => setThemePrefs({ contrast }))}</div>
        </div>
      </Card>
      <Card className="space-y-4 p-5">
        <h2 className="font-semibold">Display</h2>
        <div className="flex items-center justify-between gap-4">
          <div><div className="text-sm font-medium">Reduce transparency</div><div className="text-xs text-muted-foreground">Turns the glass sidebar, top bar, dialogs and job tray into solid surfaces. Also follows your system setting.</div></div>
          <Switch label="Reduce transparency" checked={p.reduceTransparency} onChange={(reduceTransparency) => setThemePrefs({ reduceTransparency })} />
        </div>
        <div className="flex items-center justify-between gap-4">
          <div><div className="text-sm font-medium">Buddhist Era dates</div><div className="text-xs text-muted-foreground">Show years as B.E. (2569) instead of Gregorian (2026).</div></div>
          <Switch label="Buddhist Era dates" checked={p.buddhistEra} onChange={(buddhistEra) => setThemePrefs({ buddhistEra })} />
        </div>
      </Card>
    </div>
  )
}

function Workspace() {
  const { ws = '' } = useParams()
  const qc = useQueryClient()
  const me = useApp((s) => s.me)
  const info = useQuery({ queryKey: ['ws', ws], queryFn: () => api.workspace(ws) })
  const [name, setName] = useState('')
  const [mfaPending, setMfaPending] = useState(false)
  const enrolled = !!me?.mfa_enabled

  const setRequireMfa = async (v: boolean) => {
    if (!enrolled || mfaPending) return
    setMfaPending(true)
    try {
      await patch(`/ws/${ws}`, { require_mfa: v })
      await qc.invalidateQueries({ queryKey: ['ws', ws] })
      qc.invalidateQueries({ queryKey: ['me'] })
      toast.ok(v ? 'Two-factor authentication is now required' : 'Two-factor authentication is no longer required')
    } catch (e) {
      toast.err(e as Error)
    } finally {
      setMfaPending(false)
    }
  }

  return (
    <div className="space-y-4">
      <Card className="space-y-3 p-5">
        <h2 className="font-semibold">Workspace</h2>
        <Field label="Name"><Input defaultValue={info.data?.name} key={info.data?.name} onChange={(e) => setName(e.target.value)} /></Field>
        <Field label="URL slug" hint="Used in URLs and the upload API."><Input value={ws} disabled /></Field>
        <Button disabled={!name.trim()} onClick={() => patch(`/ws/${ws}`, { name }).then(() => { qc.invalidateQueries({ queryKey: ['me'] }); qc.invalidateQueries({ queryKey: ['ws', ws] }); toast.ok('Saved') }).catch(toast.err)}>Save</Button>
      </Card>
      <Card className="space-y-3 p-5">
        <h2 className="font-semibold">Sign-in security</h2>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <div className="text-sm font-medium">Require two-factor authentication</div>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Each member must secure their account with an authenticator before they can open this workspace. Members who haven't enrolled lose access until they do.
            </p>
            {!enrolled && <p className="mt-1 text-xs font-medium">Turn on two-factor authentication in Security first.</p>}
            {info.isLoading && <p role="status" className="mt-1 text-xs text-muted-foreground">Loading security settings…</p>}
            {info.isError && <p role="alert" className="mt-1 text-xs text-destructive">Could not load this workspace's security setting.</p>}
            {mfaPending && <p role="status" className="mt-1 text-xs text-muted-foreground">Saving…</p>}
          </div>
          <fieldset
            disabled={!enrolled || mfaPending || !info.data}
            className={cn('m-0 min-w-0 border-0 p-0', (!enrolled || mfaPending || !info.data) && 'opacity-50 [&_button]:cursor-not-allowed')}
          >
            <Switch
              label="Require two-factor authentication"
              checked={!!info.data?.require_mfa}
              onChange={setRequireMfa}
            />
          </fieldset>
        </div>
        {info.isError && <Button variant="outline" size="sm" onClick={() => void info.refetch()}>Try again</Button>}
      </Card>
    </div>
  )
}

function Members() {
  const { ws = '' } = useParams()
  const qc = useQueryClient()
  const me = useApp((s) => s.me)
  const can = useApp((s) => s.can)
  const q = useQuery({ queryKey: ['members', ws], queryFn: () => api.members(ws) })
  const custom = useQuery({ queryKey: ['custom-roles', ws], queryFn: () => api.customRoles(ws), enabled: can('admin') })
  const wsRoles = (custom.data ?? []).filter((r) => r.level === 'workspace')
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<Role>('member')
  const refresh = () => qc.invalidateQueries({ queryKey: ['members', ws] })
  const invite = async () => {
    try {
      const r = await post<{ link: string }>(`/ws/${ws}/invites`, { email, role })
      setEmail(''); refresh(); copy(r.link); toast.ok(`Invite emailed to ${email} — link copied too`)
    } catch (e) { toast.err(e as Error) }
  }
  return (
    <div className="space-y-4">
      {can('admin') && (
        <Card className="p-5">
          <h2 className="mb-3 font-semibold">Invite teammates</h2>
          <div className="flex flex-wrap gap-2">
            <Input type="email" className="min-w-48 flex-1" placeholder="teammate@company.com" value={email} onChange={(e) => setEmail(e.target.value)} aria-label="Email address to invite" />
            <Select value={role} onChange={(e) => setRole(e.target.value as Role)} aria-label="Workspace role">
              <option value="owner" disabled>Owner (not assignable)</option>
              {ASSIGNABLE_ROLES.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
            </Select>
            <Button disabled={!email.includes('@')} onClick={invite}>Invite</Button>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">Admins manage members, billing, keys and training · Billing manages the plan · Members label, review and view · Labeler and Reviewer are the legacy names for member-level access.</p>
        </Card>
      )}
      <Card className="overflow-x-auto">
        <table className="w-full min-w-[34rem] text-sm">
          <caption className="sr-only">Workspace members and pending invites</caption>
          <thead className="bg-muted/60 text-left text-xs text-muted-foreground"><tr><th scope="col" className="px-4 py-2 font-medium">Member</th><th scope="col" className="px-4 py-2 font-medium">Role</th><th scope="col" className="px-4 py-2 font-medium">Joined</th><th scope="col" className="px-4 py-2 text-right font-medium"><span className="sr-only">Actions</span></th></tr></thead>
          <tbody>
            {q.data?.members.map((m) => (
              <tr key={m.id} className="border-t">
                <td className="px-4 py-2.5"><div className="font-medium">{m.name} {m.owner && <Badge>Owner</Badge>}</div><div className="text-xs text-muted-foreground">{m.email}</div></td>
                <td className="px-4 py-2.5">{can('admin') && !m.owner
                  ? <div className="flex flex-col gap-1">
                      <Select className="h-8" aria-label={`Role for ${m.name}`} value={m.role} onChange={(e) => patch(`/ws/${ws}/members/${m.id}`, { role: e.target.value }).then(refresh).catch(toast.err)}>
                        {!ASSIGNABLE_ROLES.includes(m.role) && <option value={m.role}>{ROLE_LABEL[m.role] ?? m.role}</option>}
                        {ASSIGNABLE_ROLES.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
                      </Select>
                      {wsRoles.length > 0 && (
                        <Select className="h-8" aria-label={`Custom role for ${m.name}`} value={m.custom_role_id ?? ''}
                          onChange={(e) => api.setWorkspaceCustomRole(ws, m.id, e.target.value || null).then(refresh).catch(toast.err)}>
                          <option value="">No custom role</option>
                          {wsRoles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
                        </Select>
                      )}
                    </div>
                  : <span>{ROLE_LABEL[m.role] ?? m.role}</span>}</td>
                <td className="px-4 py-2.5 text-muted-foreground">{fmtDate(m.joined)}</td>
                <td className="pr-3 text-right">{!m.owner && (can('admin') || m.id === me?.id) && <Button variant="ghost" size="sm" onClick={() => confirm(m.id === me?.id ? 'Leave this workspace?' : `Remove ${m.name}?`) && del(`/ws/${ws}/members/${m.id}`).then(refresh).catch(toast.err)}>{m.id === me?.id ? 'Leave' : 'Remove'}</Button>}</td>
              </tr>
            ))}
            {q.data?.invites.map((i) => (
              <tr key={i.token} className="border-t bg-warning/10">
                <td className="px-4 py-2.5"><div className="font-medium">{i.email}</div><div className="text-xs text-muted-foreground">Invite pending</div></td>
                <td className="px-4 py-2.5">{ROLE_LABEL[i.role as Role] ?? i.role}</td>
                <td className="px-4 py-2.5"><button type="button" className="inline-flex min-h-6 cursor-pointer items-center gap-1 text-xs text-primary" onClick={() => copy(i.link)}><Copy className="h-3 w-3" aria-hidden /> Copy link</button></td>
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
        <h2 className="mb-1 font-semibold">API keys</h2>
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

const METER_ORDER: UsageMeterKey[] = ['gpu_seconds', 'stream_hours', 'ai_calls', 'storage_bytes']
const METER_LABEL: Record<UsageMeterKey, string> = {
  gpu_seconds: 'GPU time', stream_hours: 'Stream hours', ai_calls: 'AI calls', storage_bytes: 'Storage',
}
const num1 = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 })

const fmtGpuSeconds = (seconds: number) => {
  const minutes = Math.round(Math.max(0, seconds) / 60)
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  if (!hours) return `${rest}m`
  return rest ? `${hours}h ${rest}m` : `${hours}h`
}
const fmtStreamHours = (hours: number) => `${num1.format(hours)} h`
const fmtStorage = (bytes: number) =>
  bytes >= 1024 ** 3 ? `${(bytes / 1024 ** 3).toFixed(1)} GB` : `${(bytes / 1024 ** 2).toFixed(1)} MB`
const METER_VALUE: Record<UsageMeterKey, (value: number) => string> = {
  gpu_seconds: fmtGpuSeconds,
  stream_hours: fmtStreamHours,
  ai_calls: (value) => value.toLocaleString(),
  storage_bytes: fmtStorage,
}

const dayLabel = (date: string) => new Date(`${date}T00:00:00`).toLocaleDateString(dateLocale(), { month: 'short', day: 'numeric' })
const fullDayLabel = (date: string) => new Date(`${date}T00:00:00`).toLocaleDateString(dateLocale(), { month: 'short', day: 'numeric', year: 'numeric' })

const TOOLTIP_STYLE = { background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }
const TOOLTIP_LABEL_STYLE = { color: 'var(--muted-foreground)' }

/** Activity breakdown still returned in `daily`: images, inferences, training runs and versions. */
const ACTIVITY_SERIES = [
  { key: 'image', label: 'Images uploaded', color: 'var(--tertiary)' },
  { key: 'infer', label: 'Inferences', color: 'var(--info)' },
  { key: 'train', label: 'Training runs', color: 'var(--success)' },
  { key: 'version', label: 'Versions', color: 'var(--warning)' },
] as const

function MeterCard({ meterKey, meter }: { meterKey: UsageMeterKey; meter: UsageMeter }) {
  const fmt = METER_VALUE[meterKey]
  const label = meter.label || METER_LABEL[meterKey]
  return (
    <Card className="p-4">
      <div className="flex items-baseline justify-between gap-2">
        <div className="text-xs text-muted-foreground">{label}</div>
        <span className="text-[11px] text-muted-foreground">{meter.period === 'month' ? 'this month' : 'current'}</span>
      </div>
      <div className="mt-1 text-xl font-bold tracking-tight">
        {fmt(meter.used)}
        <span className="text-sm font-normal text-muted-foreground"> / {fmt(meter.quota)}</span>
      </div>
      {meter.quota > 0 && (
        <div aria-hidden="true">
          <Progress className="mt-2" value={(meter.used / meter.quota) * 100} />
        </div>
      )}
    </Card>
  )
}

function UsageSkeleton() {
  return (
    <div role="status" className="space-y-4">
      <span className="sr-only">Loading usage…</span>
      <Card className="p-5">
        <div className="skeleton h-3 w-24" />
        <div className="skeleton mt-2 h-8 w-40" />
        <div className="skeleton mt-2 h-3 w-64" />
      </Card>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((card) => (
          <Card key={card} className="p-4">
            <div className="skeleton h-3 w-16" />
            <div className="skeleton mt-2 h-5 w-28" />
            <div className="skeleton mt-2 h-1.5 w-full" />
          </Card>
        ))}
      </div>
      <Card className="p-4">
        <div className="skeleton h-4 w-40" />
        <div className="skeleton mt-3 h-56 w-full" />
      </Card>
    </div>
  )
}

function Usage() {
  const { ws = '' } = useParams()
  const q = useQuery({ queryKey: ['usage', ws], queryFn: () => get<Usage>(`/ws/${ws}/usage`) })
  const u = q.data
  if (q.isPending) return <UsageSkeleton />
  if (q.isError) {
    return (
      <Card className="p-6">
        <EmptyState
          icon={<CircleAlert className="h-8 w-8 text-destructive" aria-hidden />}
          title="Couldn't load usage."
          hint={q.error instanceof Error ? q.error.message : 'Something went wrong — try again.'}
          action={<Button variant="outline" size="sm" onClick={() => void q.refetch()}>Try again</Button>}
        />
      </Card>
    )
  }
  if (!u) return null

  const bar = (used: number, lim: number) => <Progress className="mt-2" value={(used / lim) * 100} />
  const meters = METER_ORDER.flatMap((key) => {
    const meter = u.meters?.[key]
    return meter ? [{ key, meter }] : []
  })
  const dailyMeters = (u.daily_meters ?? []).map((d) => ({
    date: d.date,
    label: dayLabel(d.date),
    ai_calls: d.ai_calls,
    gpu_minutes: Math.round((d.gpu_seconds / 60) * 10) / 10,
    stream_hours: d.stream_hours,
    storage_bytes: d.storage_bytes,
  }))
  const activity = (u.daily ?? []).map((d) => ({
    ...d,
    label: typeof d.date === 'string' ? dayLabel(d.date) : d.date,
  }))

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

      {meters.length > 0 && (
        <section aria-labelledby="metered-usage-heading" className="space-y-3">
          <div>
            <h2 id="metered-usage-heading" className="text-sm font-semibold">Metered usage</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">Consumption measured across this workspace for the current period.</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {meters.map(({ key, meter }) => <MeterCard key={key} meterKey={key} meter={meter} />)}
          </div>
        </section>
      )}

      {dailyMeters.length > 0 ? (
        <Card className="p-4">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-sm font-semibold">Metered activity, last 30 days</h2>
            <p className="text-xs text-muted-foreground">AI calls (bars) and GPU minutes (line)</p>
          </div>
          <div className="mt-3 h-64" role="img" aria-label="AI calls shown as bars and GPU minutes shown as a line for each of the last 30 days. The table view below lists the same figures.">
            <div className="h-full" aria-hidden="true">
              <ResponsiveContainer>
                <ComposedChart data={dailyMeters} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                  <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="label" minTickGap={24} tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }} tickLine={false} axisLine={{ stroke: 'var(--border)' }} />
                  <YAxis yAxisId="calls" tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }} tickLine={false} axisLine={false} allowDecimals={false} width={32} />
                  <YAxis yAxisId="gpu" orientation="right" tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }} tickLine={false} axisLine={false} width={36} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={TOOLTIP_LABEL_STYLE}
                    formatter={(value, name) => [name === 'GPU minutes' ? `${num1.format(Number(value))} min` : Number(value).toLocaleString(), name]} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar yAxisId="calls" dataKey="ai_calls" name="AI calls" fill="var(--primary)" radius={[3, 3, 0, 0]} isAnimationActive={false} />
                  <Line yAxisId="gpu" type="monotone" dataKey="gpu_minutes" name="GPU minutes" stroke="var(--info)" strokeWidth={2} dot={false} isAnimationActive={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>
          <details className="mt-2">
            <summary className="inline-flex min-h-6 cursor-pointer items-center rounded px-1 py-1 text-xs font-medium text-muted-foreground hover:text-foreground">Table view</summary>
            <div className="mt-2 max-h-72 overflow-auto rounded-md border" role="region" aria-label="Metered activity table" tabIndex={0}>
              <table className="w-full min-w-[34rem] text-sm">
                <caption className="sr-only">Daily metered usage for the last 30 days</caption>
                <thead className="sticky top-0 bg-muted/80 text-left text-xs text-muted-foreground">
                  <tr>
                    <th scope="col" className="px-3 py-2 font-medium">Date</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">AI calls</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">GPU minutes</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">Stream hours</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">Storage</th>
                  </tr>
                </thead>
                <tbody>
                  {dailyMeters.map((d) => (
                    <tr key={d.date} className="border-t">
                      <th scope="row" className="px-3 py-2 text-left font-normal text-muted-foreground">{fullDayLabel(d.date)}</th>
                      <td className="px-3 py-2 text-right tabular-nums">{d.ai_calls.toLocaleString()}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{num1.format(d.gpu_minutes)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{num1.format(d.stream_hours)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{fmtStorage(d.storage_bytes)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </Card>
      ) : (
        <Card className="p-6">
          <EmptyState title="No metered activity yet." hint="Daily AI calls, GPU time, stream hours and storage appear here once the workspace starts working." />
        </Card>
      )}

      <Card className="p-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-sm font-semibold">Activity, last 30 days</h2>
          <p className="text-xs text-muted-foreground">Uploads, inferences, training runs and versions</p>
        </div>
        {activity.length > 0 ? (
          <div className="mt-3 h-56" role="img" aria-label="Stacked bars of images uploaded, inferences, training runs and versions created per day for the last 30 days.">
            <div className="h-full" aria-hidden="true">
              <ResponsiveContainer>
                <BarChart data={activity}>
                  <CartesianGrid vertical={false} strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="label" minTickGap={24} tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }} tickLine={false} axisLine={{ stroke: 'var(--border)' }} />
                  <YAxis tick={{ fontSize: 10, fill: 'var(--muted-foreground)' }} tickLine={false} axisLine={false} allowDecimals={false} width={32} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={TOOLTIP_LABEL_STYLE} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  {ACTIVITY_SERIES.map((s) => <Bar key={s.key} dataKey={s.key} name={s.label} stackId="a" fill={s.color} isAnimationActive={false} />)}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        ) : (
          <p className="mt-2 text-sm text-muted-foreground">No activity recorded in the last 30 days.</p>
        )}
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
  // Subscribe to the role itself: `can` is a stable function, so selecting it alone would not re-render when the
  // workspace role arrives after /me loads (deep links would keep admin tabs hidden).
  const role = useApp((s) => s.role)
  const { ws = '' } = useParams()
  const isAdmin = role === 'owner' || role === 'admin'
  if (firstRun) return <FirstRun />
  const base = `/${ws}/settings`
  const tabs = [
    { to: 'account', label: 'Account', show: true },
    { to: 'security', label: 'Security', show: true },
    { to: 'appearance', label: 'Appearance', show: true },
    { to: 'workspace', label: 'Workspace', show: isAdmin },
    { to: 'members', label: 'Members', show: true },
    { to: 'roles', label: 'Roles', show: isAdmin },
    { to: 'privacy', label: 'Privacy', show: isAdmin },
    { to: 'api', label: 'API Keys', show: isAdmin },
    { to: 'usage', label: 'Plan & Usage', show: true },
    { to: 'trash', label: 'Trash', show: isAdmin },
  ].filter((t) => t.show)
  return (
    <div className="anim-page max-w-5xl">
      <PageHeader title="Settings" />
      <div className="flex flex-col gap-4 px-8 pb-10 sm:flex-row sm:gap-6">
        <nav aria-label="Settings sections" className="-mx-1 grid grid-cols-2 gap-1 px-1 pb-1 sm:mx-0 sm:flex sm:w-44 sm:shrink-0 sm:flex-col sm:gap-0.5 sm:px-0 sm:pb-0">
          {tabs.map((t) => <NavLink key={t.to} to={`${base}/${t.to}`} className={({ isActive }) => cn('block shrink-0 truncate whitespace-nowrap rounded-md px-3 py-2 text-sm', isActive ? 'bg-accent font-medium text-accent-foreground' : 'hover:bg-muted')}>{t.label}</NavLink>)}
          <Link to={`/${ws}/legal/dpa`} className="block shrink-0 truncate whitespace-nowrap rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted">Data Processing Agreement</Link>
        </nav>
        <div className="min-w-0 flex-1">
          <Routes>
            <Route index element={<Navigate to="account" replace />} />
            <Route path="account" element={<Account />} />
            <Route path="security" element={<Security />} />
            <Route path="appearance" element={<Appearance />} />
            <Route path="workspace" element={<Workspace />} />
            <Route path="members" element={<Members />} />
            <Route path="roles" element={<WorkspaceRoles />} />
            <Route path="privacy" element={<PrivacyWorkspace />} />
            <Route path="api" element={<ApiKeys />} />
            <Route path="usage" element={<Usage />} />
            <Route path="trash" element={<Trash />} />
          </Routes>
        </div>
      </div>
    </div>
  )
}
