import { useEffect, useRef, useState } from 'react'
import { Outlet, useMatch } from 'react-router-dom'
import { RESERVED_WORKSPACE_SEGMENTS } from '@/lib/nav'
import { cn } from '@/lib/utils'
import { AppSidebar } from './AppSidebar'
import { JobTray } from './JobTray'
import { TopBar } from './TopBar'

export function AppLayout() {
  const m = useMatch('/:ws/:project/*')
  const isProject = !!m?.params.project && !RESERVED_WORKSPACE_SEGMENTS.has(m.params.project)
  const [navOpen, setNavOpen] = useState(false)
  const menuRef = useRef<HTMLButtonElement>(null)
  const drawerWasOpen = useRef(false)
  useEffect(() => {
    if (!navOpen) return
    const onKey = (e: globalThis.KeyboardEvent) => { if (e.key === 'Escape') setNavOpen(false) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [navOpen])
  // Closing the drawer (Escape, scrim or a link) returns focus to the button that opened it.
  useEffect(() => {
    if (navOpen) { drawerWasOpen.current = true; return }
    if (!drawerWasOpen.current) return
    drawerWasOpen.current = false
    menuRef.current?.focus()
  }, [navOpen])
  return (
    <div className="app-bg flex h-screen overflow-hidden print:block print:h-auto print:overflow-visible">
      {navOpen && (
        <button type="button" aria-label="Close navigation" onClick={() => setNavOpen(false)}
          className="fixed inset-0 z-40 cursor-pointer bg-scrim/50 md:hidden" />
      )}
      <AppSidebar mobileOpen={navOpen} onClose={() => setNavOpen(false)} />
      <div className="relative min-w-0 flex-1 print:min-w-full">
        <TopBar onMenu={() => setNavOpen(true)} menuOpen={navOpen} menuButtonRef={menuRef} />
        {/* Content scrolls underneath the floating glass bar, so the blur has something to blur. Project pages scroll inside ProjectLayout. */}
        <main data-scroll className={cn('h-full print:h-auto print:overflow-visible print:pt-0', isProject ? 'overflow-hidden' : 'overflow-y-auto pt-14')}><Outlet /></main>
      </div>
      <JobTray />
    </div>
  )
}
