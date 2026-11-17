import { CircleSlash } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { EmptyState, PageHeader } from '@/components/ui'
import { useApp } from '@/lib/store'
import { cn } from '@/lib/utils'

/** `Button` sizes without its own element, so these read as links: they are navigation. */
const action = 'inline-flex h-9 items-center justify-center rounded-md px-4 text-sm font-medium transition-colors'

/**
 * Stands in for a flag-gated surface that is not switched on here. The route stays where the
 * caller's link put it, so the same link works the moment an administrator enables the surface.
 */
export function NotEnabled({ label }: { label: string }) {
  const { ws = '', project = '' } = useParams()
  const admin = useApp((s) => s.can)('admin')
  return (
    <div className="anim-page">
      <PageHeader title={label} />
      <div className="px-8 pb-10 pt-16">
        <EmptyState
          icon={<CircleSlash className="h-8 w-8 text-muted-foreground/50" aria-hidden />}
          title={`${label} is not enabled in this workspace.`}
          hint="An administrator turns it on in Workspace settings."
          action={
            <div className="mt-2 flex flex-wrap items-center justify-center gap-2">
              <Link to={`/${ws}/${project}/browse`} className={cn(action, 'bg-primary text-primary-foreground hover:bg-primary/90')}>
                Back to Dataset
              </Link>
              {admin && (
                <Link to={`/${ws}/settings`} className={cn(action, 'border border-input bg-card hover:bg-accent hover:text-accent-foreground')}>
                  Open workspace settings
                </Link>
              )}
            </div>
          }
        />
      </div>
    </div>
  )
}
