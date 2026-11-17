import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, CheckCircle2, CircleAlert, Copy, KeyRound, ShieldCheck, ShieldOff, XCircle } from 'lucide-react'
import { del, get, patch, post, tokens } from '@/lib/api'
import { useApp } from '@/lib/store'
import type { LoginEvent, Me, MfaSetup, SessionRow } from '@/lib/types'
import { Badge, Button, Card, EmptyState, Field, Input, Spinner, fmtAgo, fmtDate, toast } from '@/components/ui'
import { cn } from '@/lib/utils'
import { copy } from './SettingsChrome'

export function Account() {
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

export function Security() {
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
