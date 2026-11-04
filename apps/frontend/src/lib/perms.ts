import { useQuery } from '@tanstack/react-query'
import { api } from './api'

/**
 * Effective permissions inside one project: the resolved project role (explicit row or the
 * workspace-inherited base) plus any custom-role grants. The workspace rank alone cannot say
 * whether a member may train or upload — GET /permissions?project= is the source the API enforces.
 */
export function useProjectPermissions(ws: string, project: string) {
  const q = useQuery({
    queryKey: ['permissions', ws, project],
    queryFn: () => api.permissions(ws, project),
    enabled: !!ws && !!project,
    staleTime: 60_000,
    retry: false,
  })
  const permissions = q.data?.permissions ?? []
  return {
    permissions,
    ready: q.isSuccess,
    isManager: q.data?.project_role === 'manager',
    /** Effective project role (explicit row or inherited); null until /permissions resolves. */
    role: q.data?.project_role ?? null,
    can: (perm: string) => permissions.includes(perm),
  }
}
