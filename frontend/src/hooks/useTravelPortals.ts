import { useQuery } from '@tanstack/react-query'
import { travelPortalApi } from '../api/client'
import { queryKeys } from '../lib/queryKeys'

export function useTravelPortals() {
  return useQuery({
    queryKey: queryKeys.travelPortals(),
    queryFn: () => travelPortalApi.list(),
    staleTime: Infinity,
    gcTime: Infinity,
  })
}
