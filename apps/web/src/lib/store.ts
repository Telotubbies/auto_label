import { create } from 'zustand'
import { API_ORIGIN, tokens } from './api'
import type { Me, Role } from './types'

interface Session {
  authed: boolean
  me: Me | null
  role: Role | null              // role in the workspace currently open
  collapsed: boolean
  setMe: (me: Me | null) => void
  setRole: (r: Role | null) => void
  signIn: (path: 'login' | 'signup', body: Record<string, string>) => Promise<void>
  logout: () => void
  can: (...roles: Role[]) => boolean
  toggleSidebar: () => void
}

export const useApp = create<Session>((set, get) => ({
  authed: !!tokens.access,
  me: null,
  role: null,
  collapsed: false,
  setMe: (me) => set({ me }),
  setRole: (role) => set({ role }),
  signIn: async (path, body) => {
    const r = await fetch(`${API_ORIGIN}/api/auth/${path}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    })
    const d = await r.json().catch(() => ({}))
    if (!r.ok) throw new Error(typeof d.detail === 'string' ? d.detail : d.detail?.[0]?.msg ?? 'Something went wrong')
    tokens.set(d.token, d.refresh_token)
    set({ authed: true })
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
}))

window.addEventListener('ld:logout', () => useApp.getState().logout())
