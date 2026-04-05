import { DEFAULT_USER_ID } from '../constants'

export const queryKeys = {
  wallets: (userId: number = DEFAULT_USER_ID) => ['wallets', userId] as const,
  wallet: (walletId: number) => ['wallet', walletId] as const,
  cards: () => ['cards'] as const,
  spend: () => ['spend'] as const,
  appSpendCategories: () => ['app-spend-categories'] as const,
  currencies: () => ['currencies'] as const,
  walletCurrencies: (walletId: number | null) => ['wallet-currencies', walletId] as const,
  walletCurrencyBalances: (walletId: number | null) => ['wallet-currency-balances', walletId] as const,
  walletSettingsCurrencyIds: (walletId: number | null) =>
    ['wallet-settings-currency-ids', walletId] as const,
  walletSpendCategories: (walletId: number | null) =>
    ['wallet-spend-categories', walletId] as const,
  walletSpendItems: (walletId: number | null) =>
    ['wallet-spend-items', walletId] as const,
  roadmap: (walletId: number) => ['roadmap', walletId] as const,
  walletCardCredits: (walletId: number | null, cardId: number | null) =>
    ['wallet-card-credits', walletId, cardId] as const,
} as const
