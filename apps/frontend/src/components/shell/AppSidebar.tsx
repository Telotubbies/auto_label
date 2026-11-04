import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { Link, useLocation, useMatch, useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, ChevronDown, ChevronsLeft, LogOut, Plus, User, X, Zap } from 'lucide-react'
import { api, post } from '@/lib/api'
import { useApp } from '@/lib/store'
import { isWorkspaceNavActive, RESERVED_WORKSPACE_SEGMENTS, visibleWorkspaceNav } from '@/lib/nav'
import { useProjectPermissions } from '@/lib/perms'
import { cn } from '@/lib/utils'
import { Glass } from '../glass'
import { Button, Dropdown, Input, Modal, toast } from '../ui'
import { ICONS } from './icons'

/** Elements the drawer's Tab trap cycles through, in DOM order. */
const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

function NewWorkspace({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [name, setName] = useState('')
  const nav = useNavigate()
  const qc = useQueryClient()
  const create = async () => {
    try {
      const w = await post<{ slug: string }>('/workspaces', { name })
      await qc.invalidateQueries({ queryKey: ['me'] })
      onClose(); nav(`/${w.slug}`)
    } catch (e) { toast.err(e as Error) }
  }
  return (
    <Modal open={open} onClose={onClose} title="Create a workspace">
      <p className="mb-3 text-sm text-muted-foreground">Workspaces hold projects, members, models and billing separately.</p>
      <Input autoFocus placeholder="Acme Vision Team" value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && name.trim() && create()} />
      <div className="mt-4 flex justify-end gap-2"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={!name.trim()} onClick={create}>Create</Button></div>
    </Modal>
  )
}

function SideNavLink({ to, label, icon: Icon, active, collapsed, onClick }: {
  to: string; label: string; icon: typeof ICONS[keyof typeof ICONS]; active: boolean; collapsed: boolean; onClick?: () => void
}) {
  return (
    <Link to={to} onClick={onClick} aria-label={label} aria-current={active ? 'page' : undefined} title={collapsed ? label : undefined}
      className={cn(
        'flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] transition-all duration-150',
        active ? 'bg-sidebar-accent font-medium text-sidebar-accent-foreground' : 'text-sidebar-foreground hover:bg-sidebar-accent/60',
        collapsed && 'justify-center px-0',
      )}>
      <Icon className="h-4 w-4 shrink-0" aria-hidden />{!collapsed && <span className="truncate">{label}</span>}
    </Link>
  )
}

export function AppSidebar({ mobileOpen = false, onClose }: { mobileOpen?: boolean; onClose?: () => void }) {
  const { collapsed, toggleSidebar, logout, me } = useApp()
  // Subscribe to the role itself: `can` is a stable function reference, so selecting it alone would
  // not re-render the sidebar when the workspace role arrives after /me loads.
  const role = useApp((s) => s.role)
  const superadmin = useApp((s) => s.superadmin)
  const { ws = '' } = useParams()
  const { pathname } = useLocation()
  const nav = useNavigate()
  const [newWs, setNewWs] = useState(false)
  // Inside a project the effective project role narrows the IA; workspace-level URLs are not projects.
  const projectMatch = useMatch('/:ws/:project/*')
  const projectSlug = projectMatch?.params.project ?? ''
  const inProject = !!projectSlug && !RESERVED_WORKSPACE_SEGMENTS.has(projectSlug)
  const { role: projectRole } = useProjectPermissions(ws, inProject ? projectSlug : '')
  const info = useQuery({ queryKey: ['ws', ws], queryFn: () => api.workspace(ws), enabled: !!ws })
  const current = me?.workspaces.find((w) => w.slug === ws)
  const u = info.data?.usage
  const pct = u ? (u.credits_used / u.limits.credits) * 100 : 0
  const base = `/${ws}`
  const groups = visibleWorkspaceNav(role, superadmin, inProject ? projectRole : null)
  const main = groups.filter((g) => g.id !== 'footer')
  const footer = groups.find((g) => g.id === 'footer')?.items ?? []
  // Active nesting is resolved against what this role renders, so a hidden longer item
  // (Members / Plan & Usage for a member) never leaves the sidebar with no current entry.
  const navItems = groups.flatMap((g) => g.items)
  // The icon rail is a desktop affordance; the phone drawer always shows labels.
  const rail = collapsed && !mobileOpen
  const closeRef = useRef<HTMLButtonElement>(null)
  // A phone drawer is modal: move focus in on open and keep Tab inside until it closes.
  useEffect(() => { if (mobileOpen) closeRef.current?.focus() }, [mobileOpen])
  const trapFocus = (e: KeyboardEvent<HTMLElement>) => {
    if (!mobileOpen || e.key !== 'Tab') return
    // Only stops the browser would actually tab to: the desktop collapse button is in this DOM but
    // display:none on a phone, so counting it sent Tab out from under the scrim.
    const nodes = [...e.currentTarget.querySelectorAll<HTMLElement>(FOCUSABLE)]
      .filter((n) => n.getClientRects().length > 0)
    if (!nodes.length) return
    const first = nodes[0]
    const last = nodes[nodes.length - 1]
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
  }
  return (
    <Glass as="aside" id="app-sidebar" onKeyDown={trapFocus} className={cn(
      'glass-sidebar relative m-2 mr-0 shrink-0 flex-col rounded-2xl text-sidebar-foreground transition-[width] print:hidden',
      mobileOpen ? 'fixed inset-y-0 left-0 z-50 flex w-64' : 'hidden',
      'md:relative md:inset-auto md:z-auto md:flex md:h-[calc(100vh-1rem)]',
      collapsed ? 'md:w-14' : 'md:w-56',
    )}>
      {mobileOpen && (
        <div className="flex items-center justify-between px-3 pt-2 md:hidden">
          <span className="text-[11px] font-semibold tracking-wider text-muted-foreground">Navigation</span>
          <button ref={closeRef} type="button" onClick={onClose} aria-label="Close navigation"
            className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-full hover:bg-sidebar-accent">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}
      <div className="p-2">
        <Dropdown
          trigger={
            <button className="flex w-full cursor-pointer items-center gap-2 rounded-md border border-sidebar-border bg-sidebar-accent/50 px-2 py-1.5 text-sm hover:bg-sidebar-accent hover:text-sidebar-accent-foreground">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-sidebar-primary text-[11px] font-bold text-sidebar-primary-foreground">{current?.name?.[0]?.toUpperCase() ?? 'L'}</span>
              {!rail && <><span className="flex-1 truncate text-left font-medium">{current?.name ?? 'LabelDesk'}</span><ChevronDown className="h-3.5 w-3.5" /></>}
            </button>
          }
          items={[
            ...(me?.workspaces ?? []).map((w) => ({
              label: <><span className="flex-1 truncate">{w.name}</span>{w.slug === ws && <Check className="h-3.5 w-3.5 text-primary" />}</>,
              onClick: () => nav(`/${w.slug}`),
            })),
            { divider: true, label: '' },
            { label: <><Plus className="h-3.5 w-3.5" /> Create Workspace</>, onClick: () => setNewWs(true) },
          ]}
        />
      </div>
      <nav aria-label="Workspace" className="flex-1 space-y-0.5 overflow-y-auto px-2">
        {main.map((g) => (
          <div key={g.id} role={g.label ? 'group' : undefined} aria-labelledby={g.label ? `ws-nav-${g.id}` : undefined}
            className={cn('space-y-0.5', rail && g.label && 'mt-1 border-t border-sidebar-border/60 pt-1')}>
            {g.label && (rail
              ? <span id={`ws-nav-${g.id}`} className="sr-only">{g.label}</span>
              : <div id={`ws-nav-${g.id}`} className="px-2.5 pb-1 pt-2 text-[11px] font-semibold tracking-wider text-muted-foreground">{g.label}</div>)}
            {g.items.map((i) => (
              <SideNavLink key={i.label} to={`${base}/${i.to}`} label={i.label} icon={ICONS[i.icon]}
                active={isWorkspaceNavActive(i, pathname, base, navItems)} collapsed={rail} onClick={onClose} />
            ))}
          </div>
        ))}
      </nav>
      <div className="space-y-0.5 p-2">
        {!rail && u && (
          <Link to={`/${ws}/settings/usage`} className="mb-2 block rounded-lg border border-sidebar-border px-3 py-2 text-[12px] hover:bg-sidebar-accent/60">
            <div className="flex items-center justify-between"><span className="flex items-center gap-1.5 font-medium"><Zap className="h-3.5 w-3.5 text-warning" /> {u.plan_label} plan</span><span>{Math.round(u.credits_left)} cr</span></div>
            <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-sidebar-accent"><div className={cn('h-full', pct > 80 ? 'bg-destructive' : 'bg-sidebar-primary')} style={{ width: `${Math.min(100, pct)}%` }} /></div>
          </Link>
        )}
        {footer.map((i) => (
          <SideNavLink key={i.label} to={`${base}/${i.to}`} label={i.label} icon={ICONS[i.icon]}
            active={isWorkspaceNavActive(i, pathname, base, navItems)} collapsed={rail} onClick={onClose} />
        ))}
        <div className="flex items-center gap-2 px-2.5 py-2">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-[11px] font-bold text-primary-foreground">{me?.name?.[0]?.toUpperCase() ?? '?'}</span>
          {!rail && <span className="flex-1 truncate text-[12px]">{me?.name}</span>}
          {!rail && (
            <Dropdown align="right" trigger={<button className="cursor-pointer" aria-label="Account menu"><ChevronDown className="h-3.5 w-3.5" /></button>}
              items={[{ label: <><User className="h-3.5 w-3.5" /> Account</>, onClick: () => nav(`/${ws}/settings/account`) },
                { label: <><LogOut className="h-3.5 w-3.5" /> Sign Out</>, onClick: logout, danger: true }]} />
          )}
        </div>
      </div>
      <button onClick={toggleSidebar} aria-label="Toggle sidebar" className="absolute -right-3 top-1/2 z-10 hidden -translate-y-1/2 rounded-full border bg-card p-1 text-muted-foreground shadow hover:text-foreground md:block">
        <ChevronsLeft className={cn('h-3.5 w-3.5 transition-transform', collapsed && 'rotate-180')} />
      </button>
      <NewWorkspace open={newWs} onClose={() => setNewWs(false)} />
    </Glass>
  )
}
