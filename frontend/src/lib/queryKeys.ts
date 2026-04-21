export const queryKeys = {
  wallet: (walletId: number) => ['wallet', walletId] as const,
  myWallet: () => ['my-wallet'] as const,
  cards: () => ['cards'] as const,
  credits: () => ['credits'] as const,
  currencies: () => ['currencies'] as const,
  walletCurrencies: (walletId: number | null) => ['wallet-currencies', walletId] as const,
  walletSpendItems: (walletId: number | null) =>
    ['wallet-spend-items', walletId] as const,
  roadmap: (walletId: number) => ['roadmap', walletId] as const,
  walletLatestResults: (walletId: number | null) =>
    ['wallet-latest-results', walletId] as const,
  walletCardCredits: (walletId: number | null, cardId: number | null) =>
    ['wallet-card-credits', walletId, cardId] as const,
  walletCategoryPriorities: (walletId: number | null) =>
    ['wallet-category-priorities', walletId] as const,
  walletPortalShares: (walletId: number | null) =>
    ['wallet-portal-shares', walletId] as const,
  travelPortals: ['travel-portals'] as const,
} as const
