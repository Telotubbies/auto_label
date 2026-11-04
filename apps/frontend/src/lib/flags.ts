import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { api } from './api'

/** One query key for every reader and the admin toggle, so a change shows up everywhere. */
export const flagsKey = (ws: string) => ['flags', ws] as const

function useFlagsQuery() {
  const { ws = '' } = useParams()
  return useQuery({
    queryKey: flagsKey(ws),
    queryFn: () => api.flags(ws),
    enabled: !!ws,
    staleTime: 60_000,
  })
}

/**
 * Effective flags for the workspace in the current route. Unset, unknown and not-yet-loaded
 * flags all read as off, so feature code never flashes enabled content while the request runs.
 */
export function useFlag(key: string): boolean {
  return useFlagsQuery().data?.enabled.includes(key) ?? false
}

/** The same cached read for the settings toggle, which also needs descriptions. */
export function useWorkspaceFlags() {
  return useFlagsQuery()
}
