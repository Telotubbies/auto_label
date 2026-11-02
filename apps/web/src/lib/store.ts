import { create } from 'zustand'
import { API_ORIGIN, tokens } from './api'
import type { Me, Role } from './types'

/** What /auth/login needs from the caller: either a live session or an MFA challenge. */
export type SignInResult = { mfa_required?: boolean; mfa_token?: string }

interface Session {
  authed: boolean
  me: Me | null
  role: Role | null              // role in the workspace currently open
  collapsed: boolean
  setMe: (me: Me | null) => void
  setRole: (r: Role | null) => void
  signIn: (path: 'login' | 'signup', body: Record<string, string>) => Promise<SignInResult>
  completeMfa: (mfaToken: string, code: string) => Promise<void>
  logout: () => void
  can: (...roles: Role[]) => boolean
  toggleSidebar: () => void
}

type AuthPayload = { token: string; refresh_token: string; session?: string; user?: { id: string } }

async function authRequest(path: string, body: Record<string, string>): Promise<AuthPayload & SignInResult> {
  const r = await fetch(`${API_ORIGIN}/api/auth/${path}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  const d = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(typeof d.detail === 'string' ? d.detail : d.detail?.[0]?.msg ?? 'Something went wrong')
  return d
}

export const useApp = create<Session>((set, get) => {
  const adopt = (d: AuthPayload) => {
    tokens.set(d.token, d.refresh_token, d.session)
    set({ authed: true })
  }
  return {
    authed: !!tokens.access,
    me: null,
    role: null,
    // narrow screens start with the icon rail so the project page keeps usable width
    collapsed: typeof window !== 'undefined' && window.innerWidth < 900,
    setMe: (me) => set({ me }),
    setRole: (role) => set({ role }),
    signIn: async (path, body) => {
      const d = await authRequest(path, body)
      if (d.mfa_required) return { mfa_required: true, mfa_token: d.mfa_token }
      adopt(d)
      return {}
    },
    completeMfa: async (mfaToken, code) => {
      adopt(await authRequest('mfa/verify', { mfa_token: mfaToken, code }))
    },
    logout: () => {
      const rt = tokens.refresh
      if (rt) fetch(`${API_ORIGIN}/api/auth/logout`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh_token: rt }) }).catch(() => {})
      tokens.clear()
      set({ authed: false, me: null, role: null })
    },
    // admin > reviewer > annotator — `can('reviewer')` means "reviewer or higher"
    can: (...roles) => {
      const r = get().role
      if (!r) return false
      const rank = { annotator: 1, reviewer: 2, admin: 3 }
      return roles.some((x) => rank[r] >= rank[x])
    },
    toggleSidebar: () => set((s) => ({ collapsed: !s.collapsed })),
  }
})

window.addEventListener('ld:logout', () => useApp.getState().logout())
