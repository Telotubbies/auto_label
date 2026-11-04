import type { ComponentPropsWithoutRef, ElementType } from 'react'
import { cn } from '@/lib/utils'

type GlassProps<T extends ElementType> = {
  as?: T
  /** chrome: sidebar, top bar, toolbars, tray (blur 16). overlay: dialogs, popovers, palette (blur 20, denser tint). */
  strength?: 'chrome' | 'overlay'
} & Omit<ComponentPropsWithoutRef<T>, 'as' | 'strength'>

/**
 * Liquid Glass surface. Solid unless the browser supports backdrop-filter AND the user has not asked for reduced
 * transparency (see .glass in index.css). Use on chrome only, never on content (canvas, grids, tables, charts).
 */
export function Glass<T extends ElementType = 'div'>({ as, strength = 'chrome', className, ...props }: GlassProps<T>) {
  const Tag: ElementType = as ?? 'div'
  return <Tag data-glass={strength} className={cn('glass', strength === 'overlay' && 'glass-overlay', className)} {...props} />
}
