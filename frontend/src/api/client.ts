// Typed API client — all calls go through /api which Vite proxies to FastAPI in dev.
// In production the React build is served by FastAPI directly, so /api is the same origin.

const BASE = import.meta.env.VITE_API_BASE ?? '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(detail?.detail ?? `HTTP ${res.status}`)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

// ─── Types (mirror Pydantic schemas) ─────────────────────────────────────────

export interface CardMultiplier {
  category: string
  multiplier: number
  cap_per_billing_cycle?: number | null
  /** Length of one cap period in calendar months: 1=monthly, 3=quarterly, 6=semi-annual, 12=annual. */
  cap_period_months?: number | null
  is_portal?: boolean
}

export interface GroupCategoryItem {
  spend_category_id: number
  name: string
}

export interface RotationCategoryWeight {
  spend_category_id: number
  name: string
  /** Activation probability in [0, 1] — fraction of historical quarters this category was active. */
  weight: number
}

export interface CardMultiplierGroup {
  id: number
  multiplier: number
  cap_per_billing_cycle: number | null
  /** Length of one cap period in calendar months: 1=monthly, 3=quarterly, 6=semi-annual, 12=annual. */
  cap_period_months?: number | null
  /** When set, only the top N spending categories in this group get the rate (1=top 1, 2=top 2, etc.). Null = all get the rate. */
  top_n_categories?: number | null
  /** When true, the cap is allocated per-category by `rotation_weights` (Discover IT, Chase Freedom Flex). */
  is_rotating?: boolean
  categories: GroupCategoryItem[]
  /** Inferred per-category activation probabilities (only populated when is_rotating). */
  rotation_weights?: RotationCategoryWeight[]
}

export interface CardRotatingHistoryRow {
  id: number
  card_id: number
  year: number
  quarter: number
  spend_category_id: number
  category_name: string
}

export interface WalletCardRotationOverride {
  id: number
  wallet_card_id: number
  year: number
  quarter: number
  spend_category_id: number
  category_name: string
}

export interface WalletPortalShare {
  id: number
  wallet_id: number
  issuer_id: number
  share: number
  issuer_name: string
}

/** A standardized statement credit in the global library (e.g. Priority Pass). */
export interface CardCredit {
  id: number
  credit_name: string
  credit_value: number
}

export interface IssuerRead {
  id: number
  name: string
}

export interface CoBrandRead {
  id: number
  name: string
}

export interface CurrencyRead {
  id: number
  name: string
  /** Default `points` when omitted (older API). */
  reward_kind?: 'points' | 'cash'
  cents_per_point: number
  partner_transfer_rate: number | null
  cash_transfer_rate: number | null
  converts_to_currency_id?: number | null
  converts_at_rate?: number | null
  no_transfer_cpp: number | null
  no_transfer_rate: number | null
  /** When listing with user_id, effective CPP for that user (override or base). */
  user_cents_per_point?: number | null
}

export interface NetworkTierRead {
  id: number
  name: string
  network_id: number | null
}

export interface Card {
  id: number
  name: string
  issuer: IssuerRead
  co_brand: CoBrandRead | null
  currency_obj: CurrencyRead
  issuer_id: number
  co_brand_id: number | null
  currency_id: number
  annual_fee: number
  first_year_fee: number | null
  business: boolean
  network_tier_id: number | null
  network_tier: NetworkTierRead | null
  sub: number | null
  sub_min_spend: number | null
  sub_months: number | null
  sub_spend_earn: number | null
  annual_bonus: number | null
  transfer_enabler: boolean
  sub_recurrence_months: number | null
  sub_family: string | null
  multipliers: CardMultiplier[]
  multiplier_groups: CardMultiplierGroup[]
}

export interface SpendCategory {
  id: number
  category: string
  parent_id: number | null
  is_system: boolean
  children: SpendCategory[]
}

export interface WalletSpendItem {
  id: number
  wallet_id: number
  spend_category_id: number
  spend_category: SpendCategory
  amount: number
}

export interface CreateWalletSpendItemPayload {
  spend_category_id: number
  amount?: number
}

export interface UpdateWalletSpendItemPayload {
  amount: number
}

export interface CategoryEarnItem {
  category: string
  points: number
}

export interface CardResult {
  card_id: number
  card_name: string
  selected: boolean
  effective_annual_fee: number
  total_points: number
  annual_point_earn: number
  credit_valuation: number
  annual_fee: number
  first_year_fee: number | null
  sub: number
  annual_bonus: number
  sub_extra_spend: number
  sub_spend_earn: number
  sub_opp_cost_dollars: number
  sub_opp_cost_gross_dollars: number
  avg_spend_multiplier: number
  cents_per_point: number
  effective_currency_name: string
  effective_currency_id?: number
  effective_reward_kind?: 'points' | 'cash'
  category_earn: CategoryEarnItem[]
}

export interface WalletResult {
  years_counted: number
  total_effective_annual_fee: number
  total_points_earned: number
  total_annual_pts: number
  total_cash_reward_dollars?: number
  total_reward_value_usd?: number
  currency_pts: Record<string, number>
  /** Same as currency_pts but keyed by currency id (stable vs renames). */
  currency_pts_by_id?: Record<string, number>
  card_results: CardResult[]
}

export type WalletCardAcquisitionType = 'opened' | 'product_change'
export type WalletCardPanel = 'in_wallet' | 'future' | 'considering'

export interface WalletCard {
  id: number
  wallet_id: number
  card_id: number
  card_name: string | null
  added_date: string
  sub: number | null
  sub_min_spend: number | null
  sub_months: number | null
  sub_spend_earn: number | null
  /** Null = use library card annual bonus */
  annual_bonus: number | null
  years_counted: number
  /** Null = use library card annual fee */
  annual_fee: number | null
  /** Null = use library card first-year fee */
  first_year_fee: number | null
  sub_earned_date: string | null
  /** Auto-calculated projected SUB earn date based on wallet spend profile */
  sub_projected_earn_date: string | null
  closed_date: string | null
  transfer_enabler: boolean
  acquisition_type: WalletCardAcquisitionType
  panel: WalletCardPanel
}

export interface Wallet {
  id: number
  user_id: number
  name: string
  description: string | null
  as_of_date: string | null
  wallet_cards: WalletCard[]
  calc_start_date: string | null
  calc_end_date: string | null
  calc_duration_years: number
  calc_duration_months: number
  calc_window_mode: 'duration' | 'end'
}

export interface WalletResultResponse {
  wallet_id: number
  wallet_name: string
  start_date: string
  end_date: string | null
  duration_years: number
  duration_months: number
  total_months: number
  as_of_date: string | null
  projection_years: number
  projection_months: number
  years_counted: number
  wallet: WalletResult
}

export interface CreateWalletPayload {
  user_id: number
  name: string
  description?: string | null
  as_of_date?: string | null
}

export interface InitialWalletCardCredit {
  library_credit_id: number
  value: number
}

export interface AddCardToWalletPayload {
  card_id: number
  added_date: string
  sub?: number | null
  sub_min_spend?: number | null
  sub_months?: number | null
  sub_spend_earn?: number | null
  annual_bonus?: number | null
  years_counted?: number
  annual_fee?: number | null
  first_year_fee?: number | null
  sub_earned_date?: string | null
  closed_date?: string | null
  acquisition_type?: WalletCardAcquisitionType
  panel?: WalletCardPanel
  credits?: InitialWalletCardCredit[]
}

export interface WalletCurrencyBalance {
  id: number
  wallet_id: number
  currency_id: number
  currency_name: string
  initial_balance: number
  projection_earn: number
  balance: number
  user_tracked: boolean
  updated_date: string | null
}

export interface TrackWalletCurrencyPayload {
  currency_id: number
  initial_balance?: number
}

export interface UpdateWalletCardPayload {
  added_date?: string | null
  sub?: number | null
  sub_min_spend?: number | null
  sub_months?: number | null
  sub_spend_earn?: number | null
  annual_bonus?: number | null
  years_counted?: number | null
  annual_fee?: number | null
  first_year_fee?: number | null
  sub_earned_date?: string | null
  closed_date?: string | null
  acquisition_type?: WalletCardAcquisitionType | null
  panel?: WalletCardPanel
}

export const walletsApi = {
  list: (userId: number = 1) =>
    request<Wallet[]>(`/wallets?user_id=${userId}`),
  get: (id: number) => request<Wallet>(`/wallets/${id}`),
  create: (payload: CreateWalletPayload) =>
    request<Wallet>('/wallets', { method: 'POST', body: JSON.stringify(payload) }),
  update: (id: number, payload: Partial<CreateWalletPayload>) =>
    request<Wallet>(`/wallets/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  delete: (id: number) => request<void>(`/wallets/${id}`, { method: 'DELETE' }),
  addCard: (walletId: number, payload: AddCardToWalletPayload) =>
    request<WalletCard>(`/wallets/${walletId}/cards`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateCard: (walletId: number, cardId: number, payload: UpdateWalletCardPayload) =>
    request<WalletCard>(`/wallets/${walletId}/cards/${cardId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  removeCard: (walletId: number, cardId: number) =>
    request<void>(`/wallets/${walletId}/cards/${cardId}`, { method: 'DELETE' }),
  roadmap: (walletId: number, asOfDate?: string) => {
    const qs = asOfDate ? `?as_of_date=${asOfDate}` : ''
    return request<RoadmapResponse>(`/wallets/${walletId}/roadmap${qs}`)
  },
  results: (
    walletId: number,
    params?: {
      start_date?: string
      reference_date?: string
      end_date?: string
      duration_years?: number
      duration_months?: number
      projection_years?: number
      projection_months?: number
      spend_overrides?: Record<string, number>
    }
  ) => {
    const search = new URLSearchParams()
    if (params?.start_date) search.set('start_date', params.start_date)
    if (params?.reference_date) search.set('reference_date', params.reference_date)
    if (params?.end_date) search.set('end_date', params.end_date)
    if (params?.duration_years != null) search.set('duration_years', String(params.duration_years))
    if (params?.duration_months != null) search.set('duration_months', String(params.duration_months))
    if (params?.projection_years != null) search.set('projection_years', String(params.projection_years))
    if (params?.projection_months != null) search.set('projection_months', String(params.projection_months))
    if (params?.spend_overrides && Object.keys(params.spend_overrides).length > 0) {
      search.set('spend_overrides', JSON.stringify(params.spend_overrides))
    }
    const qs = search.toString()
    return request<WalletResultResponse>(
      `/wallets/${walletId}/results${qs ? `?${qs}` : ''}`
    )
  },
  listCurrencyBalances: (walletId: number) =>
    request<WalletCurrencyBalance[]>(`/wallets/${walletId}/currency-balances`),
  settingsCurrencyIds: (walletId: number) =>
    request<{ currency_ids: number[] }>(`/wallets/${walletId}/settings-currency-ids`),
  trackCurrencyBalance: (walletId: number, payload: TrackWalletCurrencyPayload) =>
    request<WalletCurrencyBalance>(`/wallets/${walletId}/currency-balances`, {
      method: 'POST',
      body: JSON.stringify({
        currency_id: payload.currency_id,
        initial_balance: payload.initial_balance ?? 0,
      }),
    }),
  setCurrencyInitialBalance: (walletId: number, currencyId: number, initialBalance: number) =>
    request<WalletCurrencyBalance>(`/wallets/${walletId}/currencies/${currencyId}/balance`, {
      method: 'PUT',
      body: JSON.stringify({ initial_balance: initialBalance }),
    }),
  deleteCurrencyBalance: (walletId: number, currencyId: number) =>
    request<void>(`/wallets/${walletId}/currencies/${currencyId}/balance`, { method: 'DELETE' }),
}

// ─── Roadmap types ────────────────────────────────────────────────────────────

export interface RoadmapCardStatus {
  wallet_card_id: number
  card_id: number
  card_name: string
  issuer_name: string
  is_business: boolean
  added_date: string
  closed_date: string | null
  is_active: boolean
  sub_earned_date: string | null
  /** Auto-calculated projected SUB earn date based on wallet spend profile */
  sub_projected_earn_date: string | null
  /** "no_sub" | "pending" | "earned" | "expired" */
  sub_status: string
  sub_window_end: string | null
  next_sub_eligible_date: string | null
  sub_days_remaining: number | null
}

export interface RoadmapRuleStatus {
  rule_id: number
  rule_name: string
  issuer_name: string | null
  description: string | null
  max_count: number
  period_days: number
  current_count: number
  is_violated: boolean
  personal_only: boolean
  scope_all_issuers: boolean
  counted_cards: string[]
}

export interface RoadmapResponse {
  wallet_id: number
  wallet_name: string
  as_of_date: string
  five_twenty_four_count: number
  five_twenty_four_eligible: boolean
  personal_cards_24mo: string[]
  rule_statuses: RoadmapRuleStatus[]
  cards: RoadmapCardStatus[]
}

// ─── Issuer application rules ─────────────────────────────────────────────────

export interface IssuerApplicationRule {
  id: number
  issuer_id: number | null
  issuer_name: string | null
  rule_name: string
  description: string | null
  max_count: number
  period_days: number
  personal_only: boolean
  scope_all_issuers: boolean
}

export const issuersApi = {
  listApplicationRules: () =>
    request<IssuerApplicationRule[]>('/issuers/application-rules'),
}


// ─── Currencies ───────────────────────────────────────────────────────────────

export const currenciesApi = {
  list: () => request<CurrencyRead[]>('/currencies'),
}

// ─── Cards ────────────────────────────────────────────────────────────────────

export interface UpdateCardLibraryPayload {
  sub?: number | null
  sub_min_spend?: number | null
  sub_months?: number | null
  annual_fee?: number | null
  first_year_fee?: number | null
}

export const cardsApi = {
  list: () => request<Card[]>('/cards'),
  update: (cardId: number, payload: UpdateCardLibraryPayload) =>
    request<Card>(`/cards/${cardId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
}

// ─── Standardized credit library ─────────────────────────────────────────────

export interface CreateCreditPayload {
  credit_name: string
  credit_value?: number
}

export interface UpdateCreditPayload {
  credit_name?: string
  credit_value?: number
}

export const creditsApi = {
  list: () => request<CardCredit[]>('/credits'),
  create: (payload: CreateCreditPayload) =>
    request<CardCredit>('/admin/credits', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  update: (creditId: number, payload: UpdateCreditPayload) =>
    request<CardCredit>(`/admin/credits/${creditId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  delete: (creditId: number) =>
    request<void>(`/admin/credits/${creditId}`, { method: 'DELETE' }),
}

// ─── Spend categories ─────────────────────────────────────────────────────────

export const spendApi = {
  list: () => request<SpendCategory[]>('/spend'),
}

export const appSpendCategoriesApi = {
  list: () => request<SpendCategory[]>('/app-spend-categories'),
}

export const walletSpendItemsApi = {
  list: (walletId: number) =>
    request<WalletSpendItem[]>(`/wallets/${walletId}/spend-items`),
  create: (walletId: number, payload: CreateWalletSpendItemPayload) =>
    request<WalletSpendItem>(`/wallets/${walletId}/spend-items`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  update: (walletId: number, itemId: number, payload: UpdateWalletSpendItemPayload) =>
    request<WalletSpendItem>(`/wallets/${walletId}/spend-items/${itemId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  delete: (walletId: number, itemId: number) =>
    request<void>(`/wallets/${walletId}/spend-items/${itemId}`, { method: 'DELETE' }),
}


// ─── Wallet spend categories ─────────────────────────────────────────────────

export interface WalletSpendCategoryMapping {
  id: number
  spend_category_id: number
  spend_category_name: string
  allocation: number
}

export interface WalletSpendCategory {
  id: number
  wallet_id: number
  name: string
  amount: number
  mappings: WalletSpendCategoryMapping[]
}

export interface WalletSpendCategoryMappingPayload {
  spend_category_id: number
  allocation: number
}

export interface CreateWalletSpendCategoryPayload {
  name: string
  amount?: number
  mappings?: WalletSpendCategoryMappingPayload[]
}

export interface UpdateWalletSpendCategoryPayload {
  name?: string
  amount?: number
  mappings?: WalletSpendCategoryMappingPayload[]
}

export const walletSpendCategoryApi = {
  list: (walletId: number) =>
    request<WalletSpendCategory[]>(`/wallets/${walletId}/spend-categories`),
  create: (walletId: number, payload: CreateWalletSpendCategoryPayload) =>
    request<WalletSpendCategory>(`/wallets/${walletId}/spend-categories`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  update: (walletId: number, id: number, payload: UpdateWalletSpendCategoryPayload) =>
    request<WalletSpendCategory>(`/wallets/${walletId}/spend-categories/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  delete: (walletId: number, id: number) =>
    request<void>(`/wallets/${walletId}/spend-categories/${id}`, { method: 'DELETE' }),
}

// ─── Wallet CPP overrides ────────────────────────────────────────────────────

export const walletCppApi = {
  listCurrencies: (walletId: number) =>
    request<CurrencyRead[]>(`/wallets/${walletId}/currencies`),
  set: (walletId: number, currencyId: number, centsPerPoint: number) =>
    request<void>(`/wallets/${walletId}/currencies/${currencyId}/cpp`, {
      method: 'PUT',
      body: JSON.stringify({ cents_per_point: centsPerPoint }),
    }),
  delete: (walletId: number, currencyId: number) =>
    request<void>(`/wallets/${walletId}/currencies/${currencyId}/cpp`, { method: 'DELETE' }),
}

// ─── Wallet card credit overrides ────────────────────────────────────────────

export interface WalletCardCreditOverride {
  id: number
  wallet_card_id: number
  library_credit_id: number
  credit_name: string
  value: number
}

export interface UpsertWalletCardCreditPayload {
  value: number
}

export const walletCardCreditApi = {
  list: (walletId: number, cardId: number) =>
    request<WalletCardCreditOverride[]>(`/wallets/${walletId}/cards/${cardId}/credits`),
  upsert: (walletId: number, cardId: number, libraryCreditId: number, payload: UpsertWalletCardCreditPayload) =>
    request<WalletCardCreditOverride>(`/wallets/${walletId}/cards/${cardId}/credits/${libraryCreditId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  delete: (walletId: number, cardId: number, libraryCreditId: number) =>
    request<void>(`/wallets/${walletId}/cards/${cardId}/credits/${libraryCreditId}`, { method: 'DELETE' }),
}

// ─── Wallet card multiplier overrides ────────────────────────────────────────

export interface WalletCardMultiplierOverride {
  id: number
  wallet_id: number
  card_id: number
  category_id: number
  category_name: string
  multiplier: number
}

export const walletCardMultiplierApi = {
  list: (walletId: number) =>
    request<WalletCardMultiplierOverride[]>(`/wallets/${walletId}/card-multipliers`),
  upsert: (walletId: number, cardId: number, categoryId: number, multiplier: number) =>
    request<WalletCardMultiplierOverride>(`/wallets/${walletId}/cards/${cardId}/multipliers/${categoryId}`, {
      method: 'PUT',
      body: JSON.stringify({ multiplier }),
    }),
  delete: (walletId: number, cardId: number, categoryId: number) =>
    request<void>(`/wallets/${walletId}/cards/${cardId}/multipliers/${categoryId}`, { method: 'DELETE' }),
}

// ─── Wallet card group category selections ─────────────────────────────────

export interface WalletCardGroupSelection {
  id: number
  wallet_card_id: number
  multiplier_group_id: number
  spend_category_id: number
  category_name: string
}

export const walletCardGroupSelectionApi = {
  list: (walletId: number, cardId: number) =>
    request<WalletCardGroupSelection[]>(`/wallets/${walletId}/cards/${cardId}/group-selections`),
  set: (walletId: number, cardId: number, groupId: number, spendCategoryIds: number[]) =>
    request<WalletCardGroupSelection[]>(
      `/wallets/${walletId}/cards/${cardId}/group-selections/${groupId}`,
      { method: 'PUT', body: JSON.stringify({ spend_category_ids: spendCategoryIds }) },
    ),
  delete: (walletId: number, cardId: number, groupId: number) =>
    request<void>(`/wallets/${walletId}/cards/${cardId}/group-selections/${groupId}`, {
      method: 'DELETE',
    }),
}

export const walletPortalShareApi = {
  list: (walletId: number) =>
    request<WalletPortalShare[]>(`/wallets/${walletId}/portal-shares`),
  upsert: (walletId: number, payload: { issuer_id: number; share: number }) =>
    request<WalletPortalShare>(`/wallets/${walletId}/portal-shares`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  delete: (walletId: number, issuerId: number) =>
    request<void>(`/wallets/${walletId}/portal-shares/${issuerId}`, { method: 'DELETE' }),
}

export const walletCardRotationOverrideApi = {
  list: (walletId: number, cardId: number) =>
    request<WalletCardRotationOverride[]>(
      `/wallets/${walletId}/cards/${cardId}/rotation-overrides`,
    ),
  add: (
    walletId: number,
    cardId: number,
    payload: { year: number; quarter: number; spend_category_id: number },
  ) =>
    request<WalletCardRotationOverride>(
      `/wallets/${walletId}/cards/${cardId}/rotation-overrides`,
      { method: 'POST', body: JSON.stringify(payload) },
    ),
  delete: (walletId: number, cardId: number, overrideId: number) =>
    request<void>(
      `/wallets/${walletId}/cards/${cardId}/rotation-overrides/${overrideId}`,
      { method: 'DELETE' },
    ),
}

// ─── Admin: Reference data CRUD ──────────────────────────────────────────────

export const adminApi = {
  createIssuer: (name: string) =>
    request<IssuerRead>('/admin/issuers', {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),
  createCurrency: (payload: {
    name: string
    reward_kind?: 'points' | 'cash'
    cents_per_point?: number
    partner_transfer_rate?: number | null
    cash_transfer_rate?: number | null
    converts_to_currency_id?: number | null
    converts_at_rate?: number | null
    no_transfer_cpp?: number | null
    no_transfer_rate?: number | null
  }) =>
    request<CurrencyRead>('/admin/currencies', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  createSpendCategory: (category: string) =>
    request<SpendCategory>('/admin/spend-categories', {
      method: 'POST',
      body: JSON.stringify({ category }),
    }),
  createCard: (payload: {
    name: string
    issuer_id: number
    currency_id: number
    co_brand_id?: number | null
    annual_fee?: number
    first_year_fee?: number | null
    business?: boolean
    network_tier_id?: number | null
    sub?: number | null
    sub_min_spend?: number | null
    sub_months?: number | null
    sub_spend_earn?: number | null
    annual_bonus?: number | null
    transfer_enabler?: boolean
    sub_recurrence_months?: number | null
    sub_family?: string | null
  }) =>
    request<Card>('/admin/cards', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  deleteCard: (cardId: number) =>
    request<void>(`/admin/cards/${cardId}`, { method: 'DELETE' }),
  addCardMultiplier: (cardId: number, payload: {
    category_id: number
    multiplier: number
    is_portal?: boolean
    cap_per_billing_cycle?: number | null
    cap_period_months?: number | null
    multiplier_group_id?: number | null
  }) =>
    request<Card>(`/admin/cards/${cardId}/multipliers`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  deleteCardMultiplier: (cardId: number, categoryId: number) =>
    request<void>(`/admin/cards/${cardId}/multipliers/${categoryId}`, { method: 'DELETE' }),
  listCardRotatingHistory: (cardId: number) =>
    request<CardRotatingHistoryRow[]>(`/admin/cards/${cardId}/rotating-history`),
  addCardRotatingHistory: (cardId: number, payload: {
    year: number
    quarter: number
    spend_category_id: number
  }) =>
    request<CardRotatingHistoryRow>(`/admin/cards/${cardId}/rotating-history`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  deleteCardRotatingHistory: (cardId: number, historyId: number) =>
    request<void>(`/admin/cards/${cardId}/rotating-history/${historyId}`, { method: 'DELETE' }),
}
