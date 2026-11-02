import { useRef, useState } from 'react'
import { Link, NavLink, Outlet, useMatch, useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  BarChart3, Bell, Boxes, BrainCircuit, Cctv, Check, ChevronDown, ChevronRight, ChevronsLeft, Cpu,
  Database, FlaskConical, FolderGit2, GitBranch, KeyRound, Layers, LayoutDashboard, LineChart, LogOut, Monitor, Moon,
  Plus, Rocket, ScrollText, Settings, ShieldCheck, Sun, Tag, Tags, Upload, User, X,
  Zap, Wrench, Activity,
} from 'lucide-react'
import { api, fileUrl, get, post } from '@/lib/api'
import { useApp } from '@/lib/store'
import { setThemePrefs, useThemePrefs, type ModePref } from '@/lib/theme'
import type { Job, Project } from '@/lib/types'
import { useProjectPermissions } from '@/lib/perms'
import { cn } from '@/lib/utils'
import { Glass } from './glass'
import { Button, Dropdown, Input, Modal, Progress, toast } from './ui'

const mainNav = [
  { to: '', label: 'Projects', icon: Layers, end: true },
  { to: 'models', label: 'Models', icon: Boxes },
  { to: 'playground', label: 'Playground', icon: FlaskConical },
  { to: 'deployments', label: 'Deployments', icon: Rocket },
]

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

export function AppSidebar() {
  const { collapsed, toggleSidebar, logout, me } = useApp()
  const role = useApp((s) => s.role)
  const superadmin = useApp((s) => s.superadmin)
  const isAdmin = role === 'owner' || role === 'admin'
  const { ws = '' } = useParams()
  const nav = useNavigate()
  const [newWs, setNewWs] = useState(false)
  const info = useQuery({ queryKey: ['ws', ws], queryFn: () => api.workspace(ws), enabled: !!ws })
  const current = me?.workspaces.find((w) => w.slug === ws)
  const u = info.data?.usage
  const pct = u ? (u.credits_used / u.limits.credits) * 100 : 0
  return (
    <Glass as="aside" className={cn('glass-sidebar relative m-2 mr-0 flex h-[calc(100vh-1rem)] shrink-0 flex-col rounded-2xl text-sidebar-foreground transition-[width] print:hidden', collapsed ? 'w-14' : 'w-56')}>
      <div className="p-2">
        <Dropdown
          trigger={
            <button className="flex w-full cursor-pointer items-center gap-2 rounded-md border border-sidebar-border bg-sidebar-accent/50 px-2 py-1.5 text-sm hover:bg-sidebar-accent hover:text-sidebar-accent-foreground">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-sidebar-primary text-[11px] font-bold text-sidebar-primary-foreground">{current?.name?.[0]?.toUpperCase() ?? 'L'}</span>
              {!collapsed && <><span className="flex-1 truncate text-left font-medium">{current?.name ?? 'LabelDesk'}</span><ChevronDown className="h-3.5 w-3.5" /></>}
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
      <nav className="flex-1 space-y-0.5 overflow-y-auto px-2">
        {mainNav.map(({ to, label, icon: Icon, end }) => (
          <NavLink key={label} to={`/${ws}/${to}`} end={end}
            className={({ isActive }) => cn(
              'flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] transition-all duration-150',
              isActive ? 'bg-sidebar-accent font-medium text-sidebar-accent-foreground' : 'text-sidebar-foreground hover:bg-sidebar-accent/60',
              collapsed && 'justify-center px-0',
            )}>
            <Icon className="h-4 w-4 shrink-0" />{!collapsed && label}
          </NavLink>
        ))}
      </nav>
      <div className="space-y-0.5 p-2">
        {!collapsed && u && (
          <Link to={`/${ws}/settings/usage`} className="mb-2 block rounded-lg border border-sidebar-border px-3 py-2 text-[12px] hover:bg-sidebar-accent/60">
            <div className="flex items-center justify-between"><span className="flex items-center gap-1.5 font-medium"><Zap className="h-3.5 w-3.5 text-warning" /> {u.plan_label} plan</span><span>{Math.round(u.credits_left)} cr</span></div>
            <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-sidebar-accent"><div className={cn('h-full', pct > 80 ? 'bg-destructive' : 'bg-sidebar-primary')} style={{ width: `${Math.min(100, pct)}%` }} /></div>
          </Link>
        )}
        <NavLink to={`/${ws}/activity`} className={cn('flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] text-sidebar-foreground hover:bg-sidebar-accent/60', collapsed && 'justify-center px-0')}>
          <Bell className="h-4 w-4" />{!collapsed && 'Activity'}
        </NavLink>
        {isAdmin && (
          <NavLink to={`/${ws}/audit`} className={cn('flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] text-sidebar-foreground hover:bg-sidebar-accent/60', collapsed && 'justify-center px-0')}>
            <ScrollText className="h-4 w-4" />{!collapsed && 'Audit log'}
          </NavLink>
        )}
        {superadmin && (
          <NavLink to={`/${ws}/admin`} className={cn('flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] text-sidebar-foreground hover:bg-sidebar-accent/60', collapsed && 'justify-center px-0')}>
            <ShieldCheck className="h-4 w-4" />{!collapsed && 'Admin'}
          </NavLink>
        )}
        <NavLink to={`/${ws}/settings`} className={cn('flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] text-sidebar-foreground hover:bg-sidebar-accent/60', collapsed && 'justify-center px-0')}>
          <Settings className="h-4 w-4" />{!collapsed && 'Settings'}
        </NavLink>
        <div className="flex items-center gap-2 px-2.5 py-2">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-[11px] font-bold text-primary-foreground">{me?.name?.[0]?.toUpperCase() ?? '?'}</span>
          {!collapsed && <span className="flex-1 truncate text-[12px]">{me?.name}</span>}
          {!collapsed && (
            <Dropdown align="right" trigger={<button className="cursor-pointer" aria-label="Account menu"><ChevronDown className="h-3.5 w-3.5" /></button>}
              items={[{ label: <><User className="h-3.5 w-3.5" /> Account</>, onClick: () => nav(`/${ws}/settings/account`) },
                { label: <><LogOut className="h-3.5 w-3.5" /> Sign Out</>, onClick: logout, danger: true }]} />
          )}
        </div>
      </div>
      <button onClick={toggleSidebar} aria-label="Toggle sidebar" className="absolute -right-3 top-1/2 z-10 -translate-y-1/2 rounded-full border bg-card p-1 text-muted-foreground shadow hover:text-foreground">
        <ChevronsLeft className={cn('h-3.5 w-3.5 transition-transform', collapsed && 'rotate-180')} />
      </button>
      <NewWorkspace open={newWs} onClose={() => setNewWs(false)} />
    </Glass>
  )
}

export const projNav: { group: string; items: { to: string; label: string; icon: typeof Upload; perm: string; count?: boolean }[] }[] = [
  { group: 'DATA', items: [
    { to: 'upload', label: 'Upload Data', icon: Upload, perm: 'project.upload' },
    { to: 'annotate', label: 'Annotate', icon: Tag, perm: 'project.annotate' },
    { to: 'browse', label: 'Dataset', icon: Database, perm: 'project.read', count: true },
    { to: 'versions', label: 'Versions', icon: FolderGit2, perm: 'project.export' },
    { to: 'analytics', label: 'Analytics', icon: BarChart3, perm: 'project.review' },
    { to: 'insights', label: 'Insights', icon: LineChart, perm: 'project.review' },
    { to: 'classes', label: 'Classes & Tags', icon: Tags, perm: 'project.classes' },
  ]},
  { group: 'LIVE', items: [
    { to: 'streams', label: 'Streams', icon: Cctv, perm: 'project.read' },
  ]},
  { group: 'MODELS', items: [
    { to: 'train', label: 'Train', icon: BrainCircuit, perm: 'project.train' },
    { to: 'models', label: 'Models', icon: Boxes, perm: 'project.models' },
    { to: 'model-insights', label: 'Model insights', icon: BarChart3, perm: 'project.review' },
  ]},
  { group: 'STUDIO', items: [
    { to: 'lineage', label: 'Lineage', icon: GitBranch, perm: 'project.review' },
    { to: 'dashboards', label: 'Dashboards', icon: LayoutDashboard, perm: 'project.review' },
    { to: 'stream-analytics', label: 'Stream analytics', icon: Activity, perm: 'project.review' },
  ]},
  { group: 'DEPLOY', items: [
    { to: 'deploy', label: 'Deploy & Test', icon: Rocket, perm: 'project.models' },
    { to: 'access', label: 'Access', icon: KeyRound, perm: 'project.settings' },
    { to: 'settings', label: 'Project Settings', icon: Wrench, perm: 'project.settings' },
  ]},
]

export const typeLabel = (t: string) =>
  ({ 'object-detection': 'Object Detection', 'instance-segmentation': 'Instance Segmentation', classification: 'Classification' } as Record<string, string>)[t] ?? t

export function ProjectPanel({ project }: { project: Project }) {
  const { ws = '' } = useParams()
  const can = useApp((s) => s.can)
  // Project routes follow the resolved project role (manager/reviewer may sit on a member workspace
  // account). Until the fetch lands, workspace admins keep seeing the full nav.
  const { can: canProject, ready } = useProjectPermissions(ws, project.slug)
  const visible = (perm: string) => (ready ? canProject(perm) : can('admin'))
  return (
    <Glass as="div" className="glass-sidebar m-2 mr-0 mt-16 hidden h-[calc(100%-4.5rem)] w-56 shrink-0 flex-col overflow-y-auto rounded-2xl md:flex">
      <div className="p-3">
        <div className="overflow-hidden rounded-lg border">
          <div className="relative h-20 bg-muted">
            {project.thumbnail && <img src={fileUrl(project.thumbnail)} alt="" className="h-full w-full object-cover" />}
            <span className="absolute left-2 top-2 rounded bg-scrim/70 px-1.5 py-0.5 text-[10px] text-white">{typeLabel(project.type)}</span>
          </div>
          <div className="px-2.5 py-2 text-sm font-semibold">{project.name}</div>
        </div>
      </div>
      <nav className="flex-1 px-2 pb-4">
        {projNav.map((g) => {
          const items = g.items.filter((i) => visible(i.perm))
          return items.length ? (
            <div key={g.group} className="mb-3">
              <div className="px-2 pb-1 text-[11px] font-semibold tracking-wider text-muted-foreground">{g.group}</div>
              {items.map(({ to, label, icon: Icon, count }) => (
                <NavLink key={to} to={`/${ws}/${project.slug}/${to}`}
                  className={({ isActive }) => cn('flex items-center gap-2 rounded-md px-2 py-1.5 text-[13px]',
                    isActive ? 'bg-sidebar-accent font-medium text-sidebar-accent-foreground' : 'text-foreground hover:bg-sidebar-accent/60')}>
                  <Icon className="h-4 w-4 text-muted-foreground" />
                  <span className="flex-1">{label}</span>
                  {count && <span className="text-[11px] text-muted-foreground">{project.images}</span>}
                </NavLink>
              ))}
            </div>
          ) : null
        })}
      </nav>
    </Glass>
  )
}

const THEME_CYCLE: { id: ModePref; icon: typeof Sun; label: string }[] = [
  { id: 'system', icon: Monitor, label: 'System theme' }, { id: 'light', icon: Sun, label: 'Light theme' }, { id: 'dark', icon: Moon, label: 'Dark theme' },
]

/** Shows who holds the GPU. GET /api/gpu may not exist yet: on any error the badge renders nothing and stops polling. */
export function GpuBadge() {
  const q = useQuery({
    queryKey: ['gpu'], retry: false, staleTime: 5_000,
    queryFn: () => get<{ label?: string; holder?: string; state?: string }>('/gpu'),
    refetchInterval: (query) => (query.state.status === 'error' ? false : 10_000),
  })
  const text = q.data && (q.data.label ?? q.data.holder ?? q.data.state)
  if (!text) return null
  return <span className="inline-flex items-center gap-1.5 rounded-full border bg-secondary px-2.5 py-1 text-xs font-medium text-secondary-foreground" title="GPU holder"><Cpu className="h-3.5 w-3.5" aria-hidden />{text}</span>
}

const pageLabels: Record<string, string> = {
  models: 'Models', deployments: 'Deployments', activity: 'Activity', audit: 'Audit log', admin: 'Admin console',
  settings: 'Settings', legal: 'Legal',
}

export function TopBar() {
  const { ws = '' } = useParams()
  const me = useApp((s) => s.me)
  const m = useMatch('/:ws/:project/*')
  const slug = m?.params.project ?? ''
  const isProject = !!slug && !RESERVED.has(slug)
  const proj = useQuery({ queryKey: ['project', ws, slug], queryFn: () => api.project(ws, slug), enabled: isProject })
  const rest = (m?.params['*'] ?? '').split('/')[0]
  const page = isProject
    ? projNav.flatMap((g) => g.items).find((i) => i.to === rest)?.label
    : slug === 'legal' && rest === 'dpa' ? 'Data Processing Agreement' : (slug ? pageLabels[slug] : 'Projects')
  const wsName = me?.workspaces.find((w) => w.slug === ws)?.name ?? 'LabelDesk'
  const { mode } = useThemePrefs()
  const next = THEME_CYCLE[(THEME_CYCLE.findIndex((x) => x.id === mode) + 1) % THEME_CYCLE.length]
  const cur = THEME_CYCLE.find((x) => x.id === mode) ?? THEME_CYCLE[0]
  const Icon = cur.icon
  // The workspace switcher already names the workspace; the breadcrumb root only appears on project pages.
  const crumbs = isProject
    ? [{ label: wsName, to: `/${ws}` }, { label: proj.data?.name ?? slug, to: `/${ws}/${slug}` }, ...(page ? [{ label: page, to: '' }] : [])]
    : page ? [{ label: page, to: '' }] : []
  return (
    <Glass as="header" className="absolute inset-x-2 top-2 z-20 flex h-11 items-center gap-3 rounded-2xl px-4 print:hidden">
      <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1.5 text-sm">
        {crumbs.map((c, i) => (
          <span key={i} className="flex min-w-0 items-center gap-1.5">
            {i > 0 && <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden />}
            {c.to && i < crumbs.length - 1
              ? <Link to={c.to} className="truncate text-muted-foreground hover:text-foreground">{c.label}</Link>
              : <span className="truncate font-semibold" aria-current={i === crumbs.length - 1 ? 'page' : undefined}>{c.label}</span>}
          </span>
        ))}
      </nav>
      <div className="ml-auto flex items-center gap-2">
        <div id="topbar-actions" className="flex items-center gap-2" />
        <GpuBadge />
        <button type="button" onClick={() => setThemePrefs({ mode: next.id })} aria-label={`${cur.label}. Switch to ${next.label.toLowerCase()}`}
          className="flex h-8 w-8 cursor-pointer items-center justify-center rounded-full hover:bg-accent hover:text-accent-foreground">
          <Icon className="h-4 w-4" />
        </button>
      </div>
    </Glass>
  )
}

const RESERVED = new Set(['models', 'deployments', 'activity', 'settings', 'audit', 'admin', 'legal'])
const JOB_LABEL: Record<Job['kind'] | 'insights_images' | 'insights_leakage' | 'insights_embedding', string> = {
  train: 'Training', autolabel: 'Auto-label', version: 'Version', export: 'Export', export_engine: 'TensorRT export', health: 'Health check',
  insights_images: 'Image stats', insights_leakage: 'Leakage scan', insights_embedding: 'Embedding map',
}
const ACTIVE = new Set<Job['status']>(['queued', 'running', 'cancelling'])

/** Bottom-right glass tray with determinate progress for long jobs, so users can leave the page. Reads the current project's jobs. */
export function JobTray() {
  const m = useMatch('/:ws/:project/*')
  const ws = m?.params.ws ?? '', project = m?.params.project ?? ''
  const enabled = !!ws && !!project && !RESERVED.has(project)
  const seen = useRef(new Map<string, Job>())
  const [dismissed, setDismissed] = useState<Set<string>>(new Set())
  const q = useQuery({
    queryKey: ['jobs-tray', ws, project], enabled, retry: false,
    queryFn: () => api.jobs(ws, project),
    refetchInterval: (query) => ((query.state.data ?? []).some((j) => ACTIVE.has(j.status)) ? 2500 : 15_000),
  })
  for (const j of q.data ?? []) if (ACTIVE.has(j.status) || seen.current.has(j.id)) seen.current.set(j.id, j)
  const rows = enabled ? [...seen.current.values()].filter((j) => !dismissed.has(j.id) && (q.data ?? []).some((x) => x.id === j.id)) : []
  if (!rows.length) return null
  return (
    <Glass as="section" aria-label="Background jobs" className="fixed bottom-4 right-4 z-[150] w-80 space-y-2.5 rounded-2xl p-3 print:hidden">
      {rows.map((j) => {
        const live = ACTIVE.has(j.status)
        return (
          <div key={j.id} className="text-sm">
            <div className="flex items-center gap-2">
              <span className="min-w-0 flex-1 truncate font-medium">{JOB_LABEL[j.kind]}{j.project_name ? ` · ${j.project_name}` : ''}</span>
              <span className={cn('text-xs tabular-nums', j.status === 'failed' ? 'text-destructive' : 'text-muted-foreground')}>{live ? `${Math.round(j.progress)}%` : j.status}</span>
              {!live && <button type="button" aria-label="Dismiss" onClick={() => setDismissed((d) => new Set(d).add(j.id))} className="flex h-6 w-6 cursor-pointer items-center justify-center rounded-full hover:bg-accent"><X className="h-3.5 w-3.5" /></button>}
            </div>
            {live && <Progress className="mt-1.5" value={j.progress} />}
          </div>
        )
      })}
    </Glass>
  )
}

export function AppLayout() {
  const m = useMatch('/:ws/:project/*')
  const isProject = !!m?.params.project && !RESERVED.has(m.params.project)
  return (
    <div className="app-bg flex h-screen overflow-hidden print:block print:h-auto print:overflow-visible">
      <AppSidebar />
      <div className="relative min-w-0 flex-1 print:min-w-full">
        <TopBar />
        {/* Content scrolls underneath the floating glass bar, so the blur has something to blur. Project pages scroll inside ProjectLayout. */}
        <main data-scroll className={cn('h-full print:h-auto print:overflow-visible print:pt-0', isProject ? 'overflow-hidden' : 'overflow-y-auto pt-14')}><Outlet /></main>
      </div>
      <JobTray />
    </div>
  )
}
