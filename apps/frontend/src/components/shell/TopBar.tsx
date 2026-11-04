import type { RefObject } from 'react'
import { Link, useMatch, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ChevronRight, Cpu, Menu, Monitor, Moon, Sun } from 'lucide-react'
import { api, get } from '@/lib/api'
import { useApp } from '@/lib/store'
import { RESERVED_WORKSPACE_SEGMENTS, WORKSPACE_PAGE_LABELS } from '@/lib/nav'
import { setThemePrefs, useThemePrefs, type ModePref } from '@/lib/theme'
import { Glass } from '../glass'
import { projNav } from './ProjectPanel'

const THEME_CYCLE: { id: ModePref; icon: typeof Sun; label: string }[] = [
  { id: 'system', icon: Monitor, label: 'System theme' },
  { id: 'light', icon: Sun, label: 'Light theme' },
  { id: 'dark', icon: Moon, label: 'Dark theme' },
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
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border bg-secondary px-2.5 py-1 text-xs font-medium text-secondary-foreground" title="GPU holder">
      <Cpu className="h-3.5 w-3.5" aria-hidden />{text}
    </span>
  )
}

export function TopBar({ onMenu, menuOpen = false, menuButtonRef }: {
  onMenu?: () => void
  menuOpen?: boolean
  menuButtonRef?: RefObject<HTMLButtonElement | null>
}) {
  const { ws = '' } = useParams()
  const me = useApp((s) => s.me)
  const m = useMatch('/:ws/:project/*')
  const slug = m?.params.project ?? ''
  const isProject = !!slug && !RESERVED_WORKSPACE_SEGMENTS.has(slug)
  const proj = useQuery({ queryKey: ['project', ws, slug], queryFn: () => api.project(ws, slug), enabled: isProject })
  const rest = (m?.params['*'] ?? '').split('/')[0]
  const nested = slug && rest ? WORKSPACE_PAGE_LABELS[`${slug}/${rest}`] : undefined
  const page = isProject
    ? projNav.flatMap((g) => g.items).find((i) => i.to === rest)?.label
    : slug === 'legal' && rest === 'dpa'
      ? 'Data Processing Agreement'
      : (nested ?? (slug ? WORKSPACE_PAGE_LABELS[slug] : 'Projects'))
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
      <button ref={menuButtonRef} type="button" onClick={onMenu} aria-label="Open navigation menu"
        aria-expanded={menuOpen} aria-controls="app-sidebar"
        className="flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-full hover:bg-accent hover:text-accent-foreground md:hidden">
        <Menu className="h-4 w-4" />
      </button>
      <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1.5 text-sm">
        {crumbs.map((c, i) => (
          <span key={i} className="flex min-w-0 items-center gap-1.5">
            {i > 0 && <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden />}
            {c.to && i < crumbs.length - 1 ? (
              <Link to={c.to} className="truncate text-muted-foreground hover:text-foreground">{c.label}</Link>
            ) : (
              <span className="truncate font-semibold" aria-current={i === crumbs.length - 1 ? 'page' : undefined}>{c.label}</span>
            )}
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
