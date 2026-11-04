import { useEffect, useRef, useState, type ChangeEvent, type FormEvent, type InputHTMLAttributes, type ReactNode } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Copy, TriangleAlert } from 'lucide-react'
import { get, post } from '@/lib/api'
import { useApp } from '@/lib/store'
import type { MfaSetup } from '@/lib/types'
import { cn } from '@/lib/utils'
import { Glass } from '@/components/glass'
import { Button, Input, Spinner, toast } from '@/components/ui'
import { CornerMarks, DotGrid } from '@/features/landing/primitives'

// ---------------------------------------------------------------------------------------------
// Entry surface: Operate, but the door to a Persuade page. One glass panel, a quiet security
// argument on the left, borrowed landing coordinates (corner marks, dot field). No second card.
// ---------------------------------------------------------------------------------------------

/** Three claims, each backed by an endpoint this app actually calls. */
const FACTS = [
  {
    title: 'Single-use reset links',
    body: 'A reset link expires after 30 minutes and stops working the moment a new password is set.',
  },
  {
    title: 'Two-factor with recovery codes',
    body: 'An authenticator app on every sign-in, plus eight single-use codes for a lost phone.',
  },
  {
    title: 'A session per device',
    body: 'Every device is listed with its IP and last activity. Sign one out and the rest stay signed in.',
  },
] as const

const primaryLink =
  'inline-flex h-10 w-full items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90'

const textLink = 'rounded-sm font-medium text-primary underline decoration-primary/40 underline-offset-4 hover:decoration-primary'

/** Server messages are sentence fragments ("invalid email or password"); give them a capital and a stop. */
function tidy(message: string): string {
  const text = message.trim()
  if (!text) return text
  const capitalised = text[0].toUpperCase() + text.slice(1)
  return /[.!?]$/.test(capitalised) ? capitalised : `${capitalised}.`
}

function useTitle(title: string) {
  useEffect(() => {
    const previous = document.title
    document.title = `${title} — LabelDesk`
    return () => { document.title = previous }
  }, [title])
}

function Brand() {
  return (
    <Link to="/" className="inline-flex items-center gap-2 rounded-md">
      <span
        aria-hidden
        className="grid h-8 w-8 place-items-center rounded-md bg-primary text-sm font-semibold leading-none text-primary-foreground [font-stretch:88%]"
      >
        L
      </span>
      <span className="text-[15px] font-semibold tracking-[-0.02em] text-foreground">LabelDesk</span>
    </Link>
  )
}

function Rail() {
  return (
    <div className="max-w-sm">
      <h2 className="text-balance text-2xl font-semibold leading-[1.15] tracking-[-0.03em] [font-stretch:92%]">
        Access stays with you
      </h2>
      <ul className="mt-6 space-y-5 border-t border-border/60 pt-6">
        {FACTS.map((fact) => (
          <li key={fact.title} className="flex gap-3">
            <span aria-hidden className="mt-[0.4rem] h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
            <div>
              <p className="text-sm font-medium text-foreground">{fact.title}</p>
              <p className="mt-1 text-pretty text-sm leading-relaxed text-muted-foreground">{fact.body}</p>
            </div>
          </li>
        ))}
      </ul>
      {/* Crop marks + dot field from the landing: the one flourish on this page. */}
      <div aria-hidden className="relative mt-8 h-20 w-40 text-primary">
        <DotGrid className="opacity-[0.22] dark:opacity-[0.45]" />
        <CornerMarks className="opacity-40 dark:opacity-50" />
      </div>
    </div>
  )
}

function AuthShell({ children }: { children: ReactNode }) {
  return (
    <div className="app-bg min-h-svh text-foreground">
      <div className="mx-auto flex min-h-svh w-full max-w-4xl flex-col px-4 sm:px-8">
        <header className="py-4 sm:py-5">
          <Brand />
        </header>
        <main id="main" className="flex flex-1 items-center pb-12 pt-2 sm:pb-16">
          <div className="grid w-full gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,23rem)] lg:items-start lg:gap-16">
            {/* Form column is first in the DOM so the heading and the fields come first for keyboards. */}
            <div className="mx-auto w-full max-w-md lg:order-2 lg:mx-0 lg:max-w-none">{children}</div>
            <div className="hidden lg:order-1 lg:block">
              <Rail />
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}

function AuthCard({ title, sub, children, footer }: {
  title: ReactNode
  sub?: ReactNode
  children: ReactNode
  footer?: ReactNode
}) {
  return (
    <Glass strength="overlay" className="w-full rounded-2xl p-5 sm:p-6">
      <h1 className="text-pretty text-xl font-semibold leading-snug tracking-[-0.02em] text-foreground [font-stretch:96%]">{title}</h1>
      {sub ? <p className="mt-1.5 text-pretty text-sm leading-relaxed text-muted-foreground">{sub}</p> : null}
      <div className="mt-5">{children}</div>
      {footer ? <div className="mt-5 border-t border-border/60 pt-4 text-sm text-muted-foreground">{footer}</div> : null}
    </Glass>
  )
}

function TextField({ id, label, hint, className, ...input }: {
  id: string
  label: string
  hint?: ReactNode
  className?: string
} & Omit<InputHTMLAttributes<HTMLInputElement>, 'id' | 'className'>) {
  const hintId = hint ? `${id}-hint` : undefined
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-foreground">{label}</label>
      <Input id={id} {...input} aria-describedby={hintId} className={cn('h-10', className)} />
      {hint ? <p id={hintId} className="mt-1 text-pretty text-xs leading-relaxed text-muted-foreground">{hint}</p> : null}
    </div>
  )
}

function FormError({ message, hint }: { message?: string; hint?: ReactNode }) {
  if (!message) return null
  return (
    <div role="alert" className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2.5">
      <p className="flex items-start gap-2 text-sm font-medium leading-relaxed text-foreground">
        <TriangleAlert aria-hidden className="mt-1 h-4 w-4 shrink-0 text-destructive" />
        <span>{tidy(message)}</span>
      </p>
      {hint ? <p className="mt-1 pl-6 text-xs leading-relaxed text-muted-foreground">{hint}</p> : null}
    </div>
  )
}

function Submit({ busy, children }: { busy: boolean; children: ReactNode }) {
  return (
    <Button type="submit" disabled={busy} aria-busy={busy} className="h-10 w-full">
      {busy ? <Spinner className="h-4 w-4" /> : null}
      {children}
    </Button>
  )
}

function useSubmit(fn: () => Promise<void>) {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const inFlight = useRef(false)
  const run = async (e: FormEvent) => {
    e.preventDefault()
    if (inFlight.current) return
    inFlight.current = true
    setBusy(true)
    setErr('')
    try {
      await fn()
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : 'Something went wrong.')
    } finally {
      inFlight.current = false
      setBusy(false)
    }
  }
  return { busy, err, run, clear: () => setErr('') }
}

/** Post-login destination from ?next=; only same-origin paths are accepted. */
function useNext(): string {
  const { search } = useLocation()
  const raw = new URLSearchParams(search).get('next') ?? ''
  // Backslashes and control characters can be normalised into an off-site path by some browsers.
  const unsafe = raw.includes('\\') || /[\u0000-\u001f]/.test(raw)
  return raw.startsWith('/') && !raw.startsWith('//') && !unsafe ? raw : '/'
}

const withNext = (path: string, next: string) => next === '/' ? path : `${path}?next=${encodeURIComponent(next)}`

// ---------------------------------------------------------------------------------------------
// Two-factor step, shared by password sign-in and the invite flow.
// ---------------------------------------------------------------------------------------------

function MfaForm({ onVerify, onBack, backLabel = 'Back to password' }: {
  onVerify: (code: string) => Promise<void>
  onBack: () => void
  backLabel?: string
}) {
  const [code, setCode] = useState('')
  const [recovery, setRecovery] = useState(false)
  const { busy, err, run, clear } = useSubmit(() => onVerify(code.trim()))

  return (
    <form className="space-y-4" onSubmit={run}>
      <TextField
        // Re-key on mode change so the input remounts and its autoFocus returns the caret to the field.
        key={recovery ? 'recovery' : 'totp'}
        id="mfa-code"
        label={recovery ? 'Recovery code' : '6-digit code'}
        hint={recovery
          ? 'One of the eight codes you saved when you turned on two-factor. Each works once.'
          : 'From your authenticator app. The code changes every 30 seconds.'}
        className="font-mono tracking-[0.18em]"
        inputMode={recovery ? 'text' : 'numeric'}
        autoComplete={recovery ? 'off' : 'one-time-code'}
        maxLength={recovery ? 32 : 6}
        pattern={recovery ? undefined : '[0-9]*'}
        autoCapitalize="off"
        spellCheck={false}
        required
        autoFocus
        value={code}
        onChange={(e) => setCode(e.target.value)}
      />

      <button
        type="button"
        onClick={() => { setRecovery((v) => !v); setCode(''); clear() }}
        className={cn(textLink, '-mt-1 block text-sm')}
      >
        {recovery ? 'Use an authenticator code' : 'Use a recovery code'}
      </button>

      <FormError
        message={err}
        hint={/expired/i.test(err)
          ? 'Go back and start again with your password.'
          : 'Codes move every 30 seconds. Check the code in your app, then try again.'}
      />

      <Submit busy={busy}>Verify code</Submit>

      <button
        type="button"
        onClick={onBack}
        className="inline-flex items-center gap-1.5 rounded-sm text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
      >
        <ArrowLeft aria-hidden className="h-4 w-4" />
        {backLabel}
      </button>
    </form>
  )
}

// ---------------------------------------------------------------------------------------------
// Sign in
// ---------------------------------------------------------------------------------------------

export function Login() {
  const signIn = useApp((s) => s.signIn)
  const completeMfa = useApp((s) => s.completeMfa)
  const nav = useNavigate()
  const next = useNext()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [mfaToken, setMfaToken] = useState('')
  useTitle(mfaToken ? 'Enter your code' : 'Sign in')

  const cfg = useQuery({
    queryKey: ['config'],
    queryFn: () => get<{ signup_enabled: boolean }>('/config'),
    staleTime: 5 * 60_000,
  })

  const pw = useSubmit(async () => {
    const result = await signIn('login', { email: email.trim(), password })
    if (result.mfa_required && result.mfa_token) {
      setMfaToken(result.mfa_token)
      return
    }
    nav(next, { replace: true })
  })

  if (mfaToken) {
    return (
      <AuthShell>
        <AuthCard
          title="Enter your code"
          sub={<>Two-factor is on for <span className="font-medium text-foreground">{email.trim()}</span>.</>}
        >
          <MfaForm
            onVerify={async (code) => {
              await completeMfa(mfaToken, code)
              nav(next, { replace: true })
            }}
            onBack={() => setMfaToken('')}
          />
        </AuthCard>
      </AuthShell>
    )
  }

  return (
    <AuthShell>
      <AuthCard
        title="Sign in"
        sub="Use the email and password for your workspace."
        footer={cfg.data?.signup_enabled
          ? <>New to LabelDesk? <Link to={withNext('/signup', next)} className={textLink}>Create an account</Link></>
          : null}
      >
        <form className="space-y-4" onSubmit={pw.run}>
          <TextField
            id="login-email"
            label="Email"
            type="email"
            name="email"
            autoComplete="email"
            required
            autoFocus
            value={email}
            onChange={(e: ChangeEvent<HTMLInputElement>) => setEmail(e.target.value)}
          />
          <div>
            <TextField
              id="login-password"
              label="Password"
              type="password"
              name="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e: ChangeEvent<HTMLInputElement>) => setPassword(e.target.value)}
            />
            <p className="mt-2 text-right">
              <Link to={withNext('/forgot', next)} className={cn(textLink, 'text-xs')}>Forgot password?</Link>
            </p>
          </div>

          <FormError
            message={pw.err}
            hint="Check the email and password, then try again. After several failed tries, sign-in pauses for five minutes."
          />

          <Submit busy={pw.busy}>Sign in</Submit>
        </form>
      </AuthCard>
    </AuthShell>
  )
}

// ---------------------------------------------------------------------------------------------
// Sign up
// ---------------------------------------------------------------------------------------------

export function Signup() {
  const signIn = useApp((s) => s.signIn)
  const nav = useNavigate()
  const next = useNext()
  const [form, setForm] = useState({ name: '', email: '', password: '', workspace: '' })
  useTitle('Create account')

  const cfg = useQuery({
    queryKey: ['config'],
    queryFn: () => get<{ signup_enabled: boolean }>('/config'),
    staleTime: 5 * 60_000,
  })

  const { busy, err, run } = useSubmit(async () => {
    await signIn('signup', {
      name: form.name.trim(),
      email: form.email.trim(),
      password: form.password,
      workspace: form.workspace.trim(),
    })
    nav(next, { replace: true })
  })

  const set = (key: keyof typeof form) => (e: ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [key]: e.target.value }))

  return (
    <AuthShell>
      <AuthCard
        title="Create your account"
        sub="Start free: 3 projects, 10,000 images, 3 seats."
        footer={<>Already have an account? <Link to={withNext('/login', next)} className={textLink}>Sign in</Link></>}
      >
        {cfg.data && !cfg.data.signup_enabled ? (
          <p className="mb-4 rounded-lg border border-border/70 bg-muted px-3 py-2 text-xs leading-relaxed text-muted-foreground">
            New sign-ups are closed on this server. If you have an invite link, open it from your email.
          </p>
        ) : null}

        <form className="space-y-4" onSubmit={run}>
          <TextField
            id="signup-name"
            label="Full name"
            type="text"
            name="name"
            autoComplete="name"
            required
            autoFocus
            value={form.name}
            onChange={set('name')}
          />
          <TextField
            id="signup-email"
            label="Work email"
            type="email"
            name="email"
            autoComplete="email"
            required
            value={form.email}
            onChange={set('email')}
          />
          <TextField
            id="signup-password"
            label="Password"
            type="password"
            name="password"
            autoComplete="new-password"
            minLength={8}
            required
            hint="At least 8 characters. A passphrase you don’t reuse is best."
            value={form.password}
            onChange={set('password')}
          />
          <TextField
            id="signup-workspace"
            label="Workspace name"
            type="text"
            name="organization"
            autoComplete="organization"
            hint="Optional. Leave it blank and we’ll name it after you."
            value={form.workspace}
            onChange={set('workspace')}
          />

          <FormError
            message={err}
            hint={/already exists/i.test(err) ? 'Sign in instead, or use a different address.' : undefined}
          />

          <Submit busy={busy}>Create account</Submit>
        </form>
      </AuthCard>
    </AuthShell>
  )
}

// ---------------------------------------------------------------------------------------------
// Forgot password
// ---------------------------------------------------------------------------------------------

export function Forgot() {
  const next = useNext()
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  useTitle(sent ? 'Check your email' : 'Reset your password')

  const { busy, err, run } = useSubmit(async () => {
    await post<{ ok: boolean }>('/auth/password/forgot', { email: email.trim() })
    setSent(true)
  })

  if (sent) {
    return (
      <AuthShell>
        <AuthCard
          title="Check your email"
          sub={<>If an account exists for <span className="font-medium text-foreground">{email.trim()}</span>, a reset link is on its way.</>}
        >
          <p className="text-sm leading-relaxed text-muted-foreground">
            The link expires in 30 minutes and works once. Nothing after a few minutes? Check spam, then try a different address.
          </p>
          <div className="mt-4 flex flex-col gap-2">
            <Link to={withNext('/login', next)} className={primaryLink}>Back to sign in</Link>
            <Button type="button" variant="ghost" className="h-10 w-full" onClick={() => setSent(false)}>
              Use a different email
            </Button>
          </div>
          {import.meta.env.DEV ? (
            <p className="mt-4 border-t border-border/60 pt-4 text-xs leading-relaxed text-muted-foreground">
              Local development: the message is in{' '}
              <a href="/__mail" target="_blank" rel="noreferrer" className={textLink}>/__mail</a>.
            </p>
          ) : null}
        </AuthCard>
      </AuthShell>
    )
  }

  return (
    <AuthShell>
      <AuthCard
        title="Reset your password"
        sub="Enter the email on your account and we’ll send a reset link."
        footer={<>Remembered it? <Link to={withNext('/login', next)} className={textLink}>Sign in</Link></>}
      >
        <form className="space-y-4" onSubmit={run}>
          <TextField
            id="forgot-email"
            label="Email"
            type="email"
            name="email"
            autoComplete="email"
            required
            autoFocus
            value={email}
            onChange={(e: ChangeEvent<HTMLInputElement>) => setEmail(e.target.value)}
          />

          <FormError
            message={err}
            hint="Too many requests pause sending for 15 minutes. Try again a little later."
          />

          <Submit busy={busy}>Send reset link</Submit>
        </form>
      </AuthCard>
    </AuthShell>
  )
}

// ---------------------------------------------------------------------------------------------
// Reset password (the link from the email)
// ---------------------------------------------------------------------------------------------

export function Reset() {
  const { token = '' } = useParams()
  const next = useNext()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [done, setDone] = useState(false)
  useTitle(done ? 'Password updated' : 'Choose a new password')

  const { busy, err, run } = useSubmit(async () => {
    if (password.length < 8) throw new Error('Use at least 8 characters.')
    if (password !== confirm) throw new Error('The two passwords do not match.')
    await post<{ ok: boolean }>('/auth/password/reset', { token, password })
    // The server revoked every refresh token; drop this browser's stale session too.
    useApp.getState().logout()
    setDone(true)
  })

  if (done) {
    return (
      <AuthShell>
        <AuthCard
          title="Password updated"
          sub="Every device was signed out, including this browser. Sign in with the new password."
        >
          <Link to={withNext('/login', next)} className={primaryLink}>Sign in</Link>
        </AuthCard>
      </AuthShell>
    )
  }

  return (
    <AuthShell>
      <AuthCard
        title="Choose a new password"
        sub="The link works once. Pick something you don’t use anywhere else."
        footer={<>Need a new link? <Link to={withNext('/forgot', next)} className={textLink}>Request another</Link></>}
      >
        <form className="space-y-4" onSubmit={run}>
          <TextField
            id="reset-password"
            label="New password"
            type="password"
            name="new-password"
            autoComplete="new-password"
            minLength={8}
            required
            autoFocus
            hint="At least 8 characters."
            value={password}
            onChange={(e: ChangeEvent<HTMLInputElement>) => setPassword(e.target.value)}
          />
          <TextField
            id="reset-confirm"
            label="Confirm new password"
            type="password"
            name="confirm-password"
            autoComplete="new-password"
            minLength={8}
            required
            value={confirm}
            onChange={(e: ChangeEvent<HTMLInputElement>) => setConfirm(e.target.value)}
          />

          <FormError
            message={err}
            hint={/invalid or expired/i.test(err)
              ? <>Reset links expire after 30 minutes and work once. <Link to={withNext('/forgot', next)} className={textLink}>Request a new link</Link>.</>
              : undefined}
          />

          <Submit busy={busy}>Update password</Submit>
        </form>
      </AuthCard>
    </AuthShell>
  )
}

// ---------------------------------------------------------------------------------------------
// Verify email (token from the email, posts once on mount)
// ---------------------------------------------------------------------------------------------

type VerifyState = 'checking' | 'verified' | 'invalid'

export function VerifyEmail() {
  const { token = '' } = useParams()
  const authed = useApp((s) => s.authed)
  const qc = useQueryClient()
  const [state, setState] = useState<VerifyState>('checking')
  const [email, setEmail] = useState('')
  const fired = useRef(false)
  useTitle(state === 'verified' ? 'Email verified' : state === 'invalid' ? 'Invalid link' : 'Verify email')

  // StrictMode mounts effects twice: the token is single-use, so the request must happen exactly once.
  useEffect(() => {
    if (fired.current) return
    fired.current = true
    post<{ ok: boolean; email: string }>('/auth/email/verify', { token })
      .then((r) => {
        setEmail(r.email)
        setState('verified')
        if (authed) void qc.invalidateQueries({ queryKey: ['me'] })
      })
      .catch(() => setState('invalid'))
  }, [token, authed, qc])

  if (state === 'checking') {
    return (
      <AuthShell>
        <AuthCard title="Verifying your email" sub="This takes a second.">
          <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner className="h-4 w-4" />
            Checking this link…
          </p>
        </AuthCard>
      </AuthShell>
    )
  }

  if (state === 'verified') {
    return (
      <AuthShell>
        <AuthCard
          title="Email verified"
          sub={<>We can now reach {email ? <span className="font-medium text-foreground">{email}</span> : 'you'} about your account.</>}
        >
          <p className="text-sm leading-relaxed text-muted-foreground">You can close this tab, or carry on where you left off.</p>
          <Link to={authed ? '/' : '/login'} className={cn(primaryLink, 'mt-4')}>
            {authed ? 'Open LabelDesk' : 'Sign in'}
          </Link>
        </AuthCard>
      </AuthShell>
    )
  }

  return (
    <AuthShell>
      <AuthCard
        title="This link won’t work"
        sub="It was probably used already, or it expired after 24 hours."
      >
        <p className="text-sm leading-relaxed text-muted-foreground">
          {authed
            ? 'Request a new verification email from your account, then open that link.'
            : 'Sign in and request a new verification email from your account.'}
        </p>
        <Link to={authed ? '/' : '/login'} className={cn(primaryLink, 'mt-4')}>
          {authed ? 'Open LabelDesk' : 'Sign in'}
        </Link>
      </AuthCard>
    </AuthShell>
  )
}

// ---------------------------------------------------------------------------------------------
// Accept an invite (existing account signs in, new account signs up, signed-in users just join)
// ---------------------------------------------------------------------------------------------

type InviteInfo = {
  email: string
  role: string
  workspace: { name: string; slug: string }
  has_account: boolean
}

export function AcceptInvite() {
  const { token = '' } = useParams()
  const authed = useApp((s) => s.authed)
  const me = useApp((s) => s.me)
  const signIn = useApp((s) => s.signIn)
  const completeMfa = useApp((s) => s.completeMfa)
  const nav = useNavigate()
  const qc = useQueryClient()
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [mfaToken, setMfaToken] = useState('')
  useTitle('Join workspace')

  const info = useQuery({
    queryKey: ['invite', token],
    queryFn: () => get<InviteInfo>(`/invites/${token}`),
    retry: false,
  })

  const accept = async () => {
    const r = await post<{ workspace: string }>(`/invites/${token}/accept`)
    await qc.invalidateQueries({ queryKey: ['me'] })
    toast.ok('Joined workspace')
    nav(`/${r.workspace}`)
  }

  const { busy, err, run } = useSubmit(async () => {
    if (authed) {
      await accept()
      return
    }
    const d = info.data
    if (!d) return
    if (d.has_account) {
      const result = await signIn('login', { email: d.email, password })
      if (result.mfa_required && result.mfa_token) {
        setMfaToken(result.mfa_token)
        return
      }
      await accept()
      return
    }
    await signIn('signup', { name: name.trim(), email: d.email, password, invite: token })
    nav(`/${d.workspace.slug}`)
  })

  if (info.isLoading) {
    return (
      <AuthShell>
        <AuthCard title="Opening your invite" sub="Checking that this link is still valid.">
          <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner className="h-4 w-4" />
            Loading invite…
          </p>
        </AuthCard>
      </AuthShell>
    )
  }

  if (info.isError || !info.data) {
    return (
      <AuthShell>
        <AuthCard
          title="This invite isn’t available"
          sub="It may have been used already or revoked. Ask a workspace admin to send a new one."
        >
          <Link to="/" className={primaryLink}>Go to LabelDesk</Link>
        </AuthCard>
      </AuthShell>
    )
  }

  const d = info.data

  if (mfaToken) {
    return (
      <AuthShell>
        <AuthCard
          title="Enter your code"
          sub={<>Two-factor is on for <span className="font-medium text-foreground">{d.email}</span>.</>}
        >
          <MfaForm
            onVerify={async (code) => {
              await completeMfa(mfaToken, code)
              await accept()
            }}
            onBack={() => setMfaToken('')}
            backLabel="Back to the invite"
          />
        </AuthCard>
      </AuthShell>
    )
  }

  return (
    <AuthShell>
      <AuthCard
        title={`Join ${d.workspace.name}`}
        sub={<>Your role will be {d.role}. The invite is for <span className="font-medium text-foreground">{d.email}</span>.</>}
      >
        {authed ? (
          <p className="text-sm leading-relaxed text-muted-foreground">
            You’re signed in as <span className="font-medium text-foreground">{me?.email ?? 'this account'}</span>.
          </p>
        ) : null}

        <form className={cn('space-y-4', authed && 'mt-4')} onSubmit={run}>
          {!authed && !d.has_account ? (
            <TextField
              id="invite-name"
              label="Full name"
              type="text"
              name="name"
              autoComplete="name"
              required
              autoFocus
              value={name}
              onChange={(e: ChangeEvent<HTMLInputElement>) => setName(e.target.value)}
            />
          ) : null}

          {!authed ? (
            <TextField
              id="invite-password"
              label="Password"
              type="password"
              name={d.has_account ? 'current-password' : 'new-password'}
              autoComplete={d.has_account ? 'current-password' : 'new-password'}
              minLength={d.has_account ? undefined : 8}
              required
              autoFocus={d.has_account}
              hint={d.has_account ? 'This account already exists. Enter its password to join.' : 'At least 8 characters.'}
              value={password}
              onChange={(e: ChangeEvent<HTMLInputElement>) => setPassword(e.target.value)}
            />
          ) : null}

          <FormError
            message={err}
            hint={<>This invite only works for {d.email}. Check the password, or ask an admin for a new invite.</>}
          />

          <Submit busy={busy}>
            {authed ? 'Join workspace' : d.has_account ? 'Sign in and join' : 'Create account and join'}
          </Submit>
        </form>
      </AuthCard>
    </AuthShell>
  )
}

// ---------------------------------------------------------------------------------------------
// Two-factor gate: a workspace requires MFA and this account has not enrolled yet.
// Setup key -> QR -> code -> recovery codes -> back into the workspace.
// ---------------------------------------------------------------------------------------------

type GatePhase = 'password' | 'loading' | 'ready' | 'failed' | 'codes'

export function MfaGate({ ws, workspaceName, next }: { ws: string; workspaceName: string; next?: string }) {
  const qc = useQueryClient()
  const me = useApp((s) => s.me)
  const logout = useApp((s) => s.logout)
  const nav = useNavigate()
  const [phase, setPhase] = useState<GatePhase>('password')
  const [password, setPassword] = useState('')
  const [setup, setSetup] = useState<MfaSetup | null>(null)
  const [loadError, setLoadError] = useState('')
  const [codes, setCodes] = useState<string[]>([])
  const [code, setCode] = useState('')
  useTitle(phase === 'codes' ? 'Recovery codes' : 'Two-factor setup')

  const start = async (pw: string) => {
    setPhase('loading')
    setLoadError('')
    try {
      setSetup(await post<MfaSetup>('/auth/mfa/setup', { password: pw }))
      setPhase('ready')
    } catch (ex) {
      setLoadError(ex instanceof Error ? ex.message : 'Could not start setup.')
      setPhase('failed')
    }
  }

  const enable = useSubmit(async () => {
    const r = await post<{ recovery_codes: string[] }>('/auth/mfa/enable', { code: code.trim() })
    setCodes(r.recovery_codes)
    setPhase('codes')
  })

  const copy = async (text: string, message: string) => {
    try {
      await navigator.clipboard.writeText(text)
      toast.ok(message)
    } catch {
      toast.err('Could not copy. Select the text and copy it by hand.')
    }
  }

  const finish = async () => {
    await qc.invalidateQueries({ queryKey: ['me'] })
    nav(next && next.startsWith(`/${ws}`) ? next : `/${ws}`, { replace: true })
  }

  const signOut = () => {
    logout()
    nav('/login', { replace: true })
  }

  return (
    <AuthShell>
      <AuthCard
        title={phase === 'codes' ? 'Two-factor is on' : 'Two-factor is required'}
        sub={phase === 'codes'
          ? 'These eight codes are shown once. Each works once — keep them somewhere other than this device.'
          : <>{workspaceName} asks everyone to sign in with a second factor. Add one now to open your workspace.</>}
        footer={<>Signed in as {me?.email ?? 'your account'}. <button type="button" onClick={signOut} className={textLink}>Sign out</button></>}
      >
        {phase === 'password' ? (
          <form
            className="space-y-4"
            onSubmit={(e) => { e.preventDefault(); if (password) void start(password) }}
          >
            <p className="text-sm leading-relaxed text-muted-foreground">
              Confirm your password, then scan a QR code with an authenticator app. This keeps a stolen session from
              attaching its own authenticator to your account.
            </p>
            <TextField
              id="gate-password"
              label="Account password"
              type="password"
              name="password"
              autoComplete="current-password"
              required
              autoFocus
              value={password}
              onChange={(e: ChangeEvent<HTMLInputElement>) => setPassword(e.target.value)}
            />
            <Submit busy={false}>Continue</Submit>
          </form>
        ) : null}

        {phase === 'loading' ? (
          <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner className="h-4 w-4" />
            Preparing your setup key…
          </p>
        ) : null}

        {phase === 'failed' ? (
          <div className="space-y-4">
            <FormError
              message={loadError}
              hint={/password/i.test(loadError)
                ? 'Check the password you use to sign in, then try again.'
                : 'The setup key is created on the server. Check your connection, then try again.'}
            />
            <Button type="button" className="h-10 w-full" disabled={!password} onClick={() => void start(password)}>
              Try setup again
            </Button>
            <button
              type="button"
              onClick={() => { setPhase('password'); setLoadError('') }}
              className="inline-flex items-center gap-1.5 rounded-sm text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
            >
              <ArrowLeft aria-hidden className="h-4 w-4" />
              Re-enter password
            </button>
          </div>
        ) : null}

        {phase === 'ready' && setup ? (
          <div className="space-y-5">
            <div className="space-y-4">
              {setup.qr ? (
                // A QR needs a light field to scan; the page tokens do not apply to the code itself.
                <img
                  src={setup.qr}
                  alt="QR code for adding this account to an authenticator app"
                  width={168}
                  height={168}
                  className="h-[168px] w-[168px] rounded-lg border border-border/70 bg-white p-2"
                />
              ) : (
                <p className="rounded-lg border border-border/70 bg-muted px-3 py-2 text-xs leading-relaxed text-muted-foreground">
                  No QR image in this environment. Enter the key below in your authenticator app instead.
                </p>
              )}
              <div className="min-w-0">
                <p className="text-sm font-medium text-foreground">Add LabelDesk to an authenticator app</p>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                  Google Authenticator, 1Password, Authy — any app that supports TOTP.
                </p>
                <p className="mt-3 text-xs font-medium text-foreground">Can’t scan? Enter this key instead:</p>
                <div className="mt-1.5 flex items-start gap-2">
                  <code className="min-w-0 flex-1 select-all break-all rounded-md border border-border/70 bg-muted px-2 py-1.5 font-mono text-[11px] leading-relaxed text-foreground">
                    {setup.secret}
                  </code>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    aria-label="Copy setup key"
                    className="shrink-0"
                    onClick={() => void copy(setup.secret, 'Setup key copied')}
                  >
                    <Copy aria-hidden className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            </div>

            <form className="space-y-4 border-t border-border/60 pt-4" onSubmit={enable.run}>
              <TextField
                id="gate-code"
                label="6-digit code"
                hint="From the app you just added."
                className="font-mono tracking-[0.18em]"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                pattern="[0-9]*"
                autoCapitalize="off"
                spellCheck={false}
                required
                autoFocus
                value={code}
                onChange={(e: ChangeEvent<HTMLInputElement>) => setCode(e.target.value)}
              />
              <FormError
                message={enable.err}
                hint="Enter the current code; they change every 30 seconds. The setup key above stays the same."
              />
              <Submit busy={enable.busy}>Turn on two-factor</Submit>
            </form>
          </div>
        ) : null}

        {phase === 'codes' ? (
          <div className="space-y-4">
            <ul className="grid grid-cols-2 gap-2">
              {codes.map((c) => (
                <li key={c} className="select-all rounded-md border border-border/70 bg-muted px-2 py-1.5 text-center font-mono text-xs tracking-wide text-foreground">
                  {c}
                </li>
              ))}
            </ul>
            <div className="flex flex-col gap-2">
              <Button
                type="button"
                variant="outline"
                className="h-10 w-full"
                onClick={() => void copy(codes.join('\n'), 'Recovery codes copied')}
              >
                <Copy aria-hidden className="h-3.5 w-3.5" />
                Copy codes
              </Button>
              <Button type="button" className="h-10 w-full" onClick={() => void finish()}>
                Continue to workspace
              </Button>
            </div>
          </div>
        ) : null}
      </AuthCard>
    </AuthShell>
  )
}
