import { useQuery } from '@tanstack/react-query'
import { walletsApi } from '../../../api/client'
import { useAuth } from '../../../auth/useAuth'
import { queryKeys } from '../../../lib/queryKeys'

export function useMyWallet() {
  const { isAuthenticated } = useAuth()

  return useQuery({
    queryKey: queryKeys.myWallet(),
    queryFn: () => walletsApi.getMyWallet(),
    enabled: isAuthenticated,
  })
}
