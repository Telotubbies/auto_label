import { useQuery } from '@tanstack/react-query'
import { get } from '@/lib/api'
import type { ComputeData } from './computeView'

const POLL_MS = 3_000

/** Workers, running jobs and the queue for a workspace; polls while the tab is visible. */
export const useCompute = (ws: string) => useQuery({
  queryKey: ['compute', ws], enabled: !!ws, retry: 1,
  queryFn: () => get<ComputeData>(`/ws/${ws}/compute`),
  refetchInterval: POLL_MS,
})
