import { useQuery } from '@tanstack/react-query'
import { creditsApi } from '../../../api/client'
import { queryKeys } from '../lib/queryKeys'

/**
 * Global standardized credit library (Priority Pass, Global Entry, etc.).
 *
 * This is reference data — it only changes via the admin endpoints — so we
 * cache it indefinitely. The hook is called eagerly from the RoadmapTool root
 * so that by the time the user opens a card modal the credits picker has
 * something to render immediately instead of waiting for a fresh round-trip.
 */
export function useCreditLibrary() {
  return useQuery({
    queryKey: queryKeys.credits(),
    queryFn: () => creditsApi.list(),
    staleTime: Infinity,
    gcTime: Infinity,
  })
}
