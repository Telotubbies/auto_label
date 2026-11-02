import { useQuery } from '@tanstack/react-query'
import { api } from './api'

/**
 * Public capabilities the marketing page may rely on. It reads ``GET /api/config``, the same
 * endpoint the app uses, so landing copy and the running deployment cannot disagree (I14).
 */
export function useCapabilities() {
  const q = useQuery({ queryKey: ['public-config'], queryFn: api.config, staleTime: 5 * 60_000 })
  return {
    samAvailable: q.data?.sam.loaded === true,
    loaded: q.isSuccess,
  }
}
