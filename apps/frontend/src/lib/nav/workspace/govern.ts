import { BILLING_AUDIENCE, OWNER_ADMIN } from '../audience.ts'
import type { NavGroup, WorkspaceNavItem } from '../types'

export const governNav: NavGroup<WorkspaceNavItem> = {
  id: 'govern', label: 'GOVERN', items: [
    // Labels follow the Settings tab they open, so the sidebar and the page never name one screen twice.
    { to: 'settings/members', label: 'Members', icon: 'members', roles: OWNER_ADMIN },
    { to: 'audit', label: 'Audit log', icon: 'audit', roles: OWNER_ADMIN },
    { to: 'settings/usage', label: 'Plan & Usage', icon: 'usage', roles: BILLING_AUDIENCE },
    { to: 'settings/api', label: 'API Keys', icon: 'integrations', roles: OWNER_ADMIN },
  ],
}
