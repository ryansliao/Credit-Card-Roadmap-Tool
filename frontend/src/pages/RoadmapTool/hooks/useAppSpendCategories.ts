import { useQuery } from '@tanstack/react-query'
import { appSpendCategoriesApi, type SpendCategory } from '../../../api/client'
import { queryKeys } from '../lib/queryKeys'

export function useAppSpendCategories() {
  return useQuery<SpendCategory[]>({
    queryKey: queryKeys.appSpendCategories(),
    queryFn: appSpendCategoriesApi.list,
    staleTime: Infinity, // categories are seeded on startup, rarely change
  })
}
