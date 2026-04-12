import { useQuery } from '@tanstack/react-query'
import { cardsApi } from '../../../api/client'
import { queryKeys } from '../lib/queryKeys'

export function useCardLibrary() {
  return useQuery({
    queryKey: queryKeys.cards(),
    queryFn: cardsApi.list,
  })
}
