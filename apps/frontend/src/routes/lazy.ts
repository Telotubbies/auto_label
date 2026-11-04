import { lazy } from 'react'

/**
 * Pages two route files share, declared once so both keep one component identity.
 * Light, frequently used pages load eagerly: React 19 holds each Suspense fallback for ~300 ms,
 * so nested lazy routes cost a visible delay. Heavy pages (konva editor, recharts) stay lazy.
 */
export const Settings = lazy(() => import('@/features/settings/Settings'))
