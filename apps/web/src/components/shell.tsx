import { useState } from 'react'
import { Link, NavLink, Outlet, useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  BarChart3, Bell, Boxes, BrainCircuit, Check, ChevronDown, ChevronsLeft, Database, FolderGit2, Layers, LogOut,
  Plus, Rocket, Settings, Tag, Tags, Upload, User, Zap, Wrench,
} from 'lucide-react'
import { api, fileUrl, post } from '@/lib/api'
import { useApp } from '@/lib/store'
import type { Project, Role } from '@/lib/types'
import { cn } from '@/lib/utils'
import { Button, Dropdown, Input, Modal, toast } from './ui'

const mainNav = [
  { to: '', label: 'Projects', icon: Layers, end: true },
  { to: 'models', label: 'Models', icon: Boxes },
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
  const { ws = '' } = useParams()
  const nav = useNavigate()
  const [newWs, setNewWs] = useState(false)
  const info = useQuery({ queryKey: ['ws', ws], queryFn: () => api.workspace(ws), enabled: !!ws })
  const current = me?.workspaces.find((w) => w.slug === ws)
  const u = info.data?.usage
  const pct = u ? (u.credits_used / u.limits.credits) * 100 : 0
  return (
    <aside className={cn('relative flex h-screen shrink-0 flex-col bg-sidebar text-sidebar-foreground transition-all dark-scroll', collapsed ? 'w-14' : 'w-56')}>
      <div className="p-2">
        <Dropdown
          trigger={
            <button className="flex w-full cursor-pointer items-center gap-2 rounded-md border border-sidebar-border/50 bg-sidebar-accent/40 px-2 py-1.5 text-sm hover:bg-sidebar-accent">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-sidebar-primary text-[11px] font-bold text-sidebar-primary-foreground">{current?.name?.[0]?.toUpperCase() ?? 'L'}</span>
              {!collapsed && <><span className="flex-1 truncate text-left font-medium">{current?.name ?? 'LabelDesk'}</span><ChevronDown className="h-3.5 w-3.5 opacity-60" /></>}
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
              isActive ? 'border border-sidebar-border/60 bg-sidebar-accent/60 font-medium text-white' : 'text-sidebar-foreground/80 hover:bg-sidebar-accent/40 hover:text-white',
              collapsed && 'justify-center px-0',
            )}>
            <Icon className="h-4 w-4 shrink-0" />{!collapsed && label}
          </NavLink>
        ))}
      </nav>
      <div className="space-y-0.5 p-2">
        {!collapsed && u && (
          <Link to={`/${ws}/settings/usage`} className="mb-2 block rounded-lg border border-sidebar-border/50 px-3 py-2 text-[12px] hover:bg-sidebar-accent/40">
            <div className="flex items-center justify-between"><span className="flex items-center gap-1.5 font-medium text-white"><Zap className="h-3.5 w-3.5 text-upgrade" /> {u.plan_label} plan</span><span>{Math.round(u.credits_left)} cr</span></div>
            <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-sidebar-accent"><div className={cn('h-full', pct > 80 ? 'bg-red-400' : 'bg-sidebar-primary')} style={{ width: `${Math.min(100, pct)}%` }} /></div>
          </Link>
        )}
        <NavLink to={`/${ws}/activity`} className={cn('flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] text-sidebar-foreground/80 hover:bg-sidebar-accent/40', collapsed && 'justify-center px-0')}>
          <Bell className="h-4 w-4" />{!collapsed && 'Activity'}
        </NavLink>
        <NavLink to={`/${ws}/settings`} className={cn('flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] text-sidebar-foreground/80 hover:bg-sidebar-accent/40', collapsed && 'justify-center px-0')}>
          <Settings className="h-4 w-4" />{!collapsed && 'Settings'}
        </NavLink>
        <div className="flex items-center gap-2 px-2.5 py-2">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-500 text-[11px] font-bold text-white">{me?.name?.[0]?.toUpperCase() ?? '?'}</span>
          {!collapsed && <span className="flex-1 truncate text-[12px]">{me?.name}</span>}
          {!collapsed && (
            <Dropdown align="right" trigger={<button className="cursor-pointer" aria-label="Account menu"><ChevronDown className="h-3.5 w-3.5 opacity-60" /></button>}
              items={[{ label: <><User className="h-3.5 w-3.5" /> Account</>, onClick: () => nav(`/${ws}/settings/account`) },
                { label: <><LogOut className="h-3.5 w-3.5" /> Sign Out</>, onClick: logout, danger: true }]} />
          )}
        </div>
      </div>
      <button onClick={toggleSidebar} aria-label="Toggle sidebar" className="absolute -right-3 top-1/2 z-10 -translate-y-1/2 rounded-full border bg-card p-0.5 text-muted-foreground shadow hover:text-foreground">
        <ChevronsLeft className={cn('h-3.5 w-3.5 transition-transform', collapsed && 'rotate-180')} />
      </button>
      <NewWorkspace open={newWs} onClose={() => setNewWs(false)} />
    </aside>
  )
}

const projNav: { group: string; items: { to: string; label: string; icon: typeof Upload; min: Role; count?: boolean }[] }[] = [
  { group: 'DATA', items: [
    { to: 'upload', label: 'Upload Data', icon: Upload, min: 'reviewer' },
    { to: 'annotate', label: 'Annotate', icon: Tag, min: 'annotator' },
    { to: 'browse', label: 'Dataset', icon: Database, min: 'annotator', count: true },
    { to: 'versions', label: 'Versions', icon: FolderGit2, min: 'reviewer' },
    { to: 'analytics', label: 'Analytics', icon: BarChart3, min: 'reviewer' },
    { to: 'classes', label: 'Classes & Tags', icon: Tags, min: 'reviewer' },
  ]},
  { group: 'MODELS', items: [
    { to: 'train', label: 'Train', icon: BrainCircuit, min: 'admin' },
    { to: 'models', label: 'Models', icon: Boxes, min: 'reviewer' },
  ]},
  { group: 'DEPLOY', items: [
    { to: 'deploy', label: 'Deploy & Test', icon: Rocket, min: 'reviewer' },
    { to: 'settings', label: 'Project Settings', icon: Wrench, min: 'admin' },
  ]},
]

export const typeLabel = (t: string) =>
  ({ 'object-detection': 'Object Detection', 'instance-segmentation': 'Instance Segmentation', classification: 'Classification' } as Record<string, string>)[t] ?? t

export function ProjectPanel({ project }: { project: Project }) {
  const { ws = '' } = useParams()
  const can = useApp((s) => s.can)
  const me = useApp((s) => s.me)
  const wsName = me?.workspaces.find((w) => w.slug === ws)?.name ?? ws
  return (
    <div className="flex h-screen w-56 shrink-0 flex-col overflow-y-auto border-r bg-card">
      <div className="px-3 pt-3">
        <Link to={`/${ws}`} className="text-[10px] font-semibold tracking-wide text-muted-foreground hover:text-foreground">← {wsName.toUpperCase()}</Link>
      </div>
      <div className="p-3">
        <div className="overflow-hidden rounded-lg border">
          <div className="relative h-20 bg-muted">
            {project.thumbnail && <img src={fileUrl(project.thumbnail)} alt="" className="h-full w-full object-cover" />}
            <span className="absolute left-2 top-2 rounded bg-black/60 px-1.5 py-0.5 text-[10px] text-white">{typeLabel(project.type)}</span>
          </div>
          <div className="px-2.5 py-2 text-sm font-semibold">{project.name}</div>
        </div>
      </div>
      <nav className="flex-1 px-2 pb-4">
        {projNav.map((g) => {
          const items = g.items.filter((i) => can(i.min))
          return items.length ? (
            <div key={g.group} className="mb-3">
              <div className="px-2 pb-1 text-[10px] font-semibold tracking-wider text-muted-foreground">{g.group}</div>
              {items.map(({ to, label, icon: Icon, count }) => (
                <NavLink key={to} to={`/${ws}/${project.slug}/${to}`}
                  className={({ isActive }) => cn('flex items-center gap-2 rounded-md px-2 py-1.5 text-[13px]',
                    isActive ? 'bg-accent font-medium text-accent-foreground' : 'text-foreground/80 hover:bg-muted')}>
                  <Icon className="h-4 w-4 text-muted-foreground" />
                  <span className="flex-1">{label}</span>
                  {count && <span className="text-[11px] text-muted-foreground">{project.images}</span>}
                </NavLink>
              ))}
            </div>
          ) : null
        })}
      </nav>
    </div>
  )
}

export function AppLayout() {
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <AppSidebar />
      <main className="min-w-0 flex-1 overflow-y-auto"><Outlet /></main>
    </div>
  )
}
