export const queryKeys = {
  wallets: () => ['wallets'] as const,
  wallet: (walletId: number) => ['wallet', walletId] as const,
  cards: () => ['cards'] as const,
  credits: () => ['credits'] as const,
  appSpendCategories: () => ['app-spend-categories'] as const,
  walletCurrencies: (walletId: number | null) => ['wallet-currencies', walletId] as const,
  walletCurrencyBalances: (walletId: number | null) => ['wallet-currency-balances', walletId] as const,
  walletSettingsCurrencyIds: (walletId: number | null) =>
    ['wallet-settings-currency-ids', walletId] as const,
  walletSpendItems: (walletId: number | null) =>
    ['wallet-spend-items', walletId] as const,
  roadmap: (walletId: number) => ['roadmap', walletId] as const,
  walletCardCredits: (walletId: number | null, cardId: number | null) =>
    ['wallet-card-credits', walletId, cardId] as const,
  walletCardGroupSelections: (walletId: number | null, cardId: number | null) =>
    ['wallet-card-group-selections', walletId, cardId] as const,
  walletCategoryPriorities: (walletId: number | null) =>
    ['wallet-category-priorities', walletId] as const,
  walletPortalShares: (walletId: number | null) =>
    ['wallet-portal-shares', walletId] as const,
  travelPortals: ['travel-portals'] as const,
} as const
