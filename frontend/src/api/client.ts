// Typed API client — all calls go through /api which Vite proxies to FastAPI in dev.
// In production the React build is served by FastAPI directly, so /api is the same origin.

const BASE = import.meta.env.VITE_API_BASE ?? '/api'

const TOKEN_KEY = 'auth_token'

export function getAuthToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setAuthToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearAuthToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAuthToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init?.headers as Record<string, string>),
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  const res = await fetch(`${BASE}${path}`, { ...init, headers })
  if (res.status === 401) {
    clearAuthToken()
    window.location.href = '/'
    throw new Error('Session expired')
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(detail?.detail ?? `HTTP ${res.status}`)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

// ─── Auth types ──────────────────────────────────────────────────────────────

export interface AuthUser {
  id: number
  username: string | null
  name: string
  email: string | null
  picture: string | null
  token?: string | null
  needs_username?: boolean
}

export const authApi = {
  googleSignIn: (credential: string) =>
    request<AuthUser>('/auth/google', {
      method: 'POST',
      body: JSON.stringify({ credential }),
    }),
  register: (username: string, email: string | null, password: string) =>
    request<AuthUser>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, email, password }),
    }),
  login: (identifier: string, password: string) =>
    request<AuthUser>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ identifier, password }),
    }),
  setUsername: (username: string) =>
    request<AuthUser>('/auth/username', {
      method: 'PATCH',
      body: JSON.stringify({ username }),
    }),
  me: () => request<AuthUser>('/auth/me'),
}

// ─── Types (mirror Pydantic schemas) ─────────────────────────────────────────

export interface CardMultiplier {
  category: string
  multiplier: number
  cap_per_billing_cycle?: number | null
  /** Length of one cap period in calendar months: 1=monthly, 3=quarterly, 6=semi-annual, 12=annual. */
  cap_period_months?: number | null
  is_portal?: boolean
  /** When true, this multiplier stacks on the card's base rate for the category instead of replacing it. */
  is_additive?: boolean
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

/** A portal multiplier on a card, expanded through the spend-category hierarchy.
 * A card with a portal row set on a parent (e.g. "Travel") emits one entry per
 * descendant (Hotels, Airlines, Flights, ...) so callers can key by leaf name
 * without walking the tree themselves. */
export interface CardPortalPremium {
  category: string
  multiplier: number
  is_additive: boolean
  /** The explicit portal-row category this entry was expanded from. */
  source_category: string
}

export interface TravelPortal {
  id: number
  name: string
  card_ids: number[]
}

/** A standardized statement credit in the global library (e.g. Priority Pass). */
export interface CardCredit {
  id: number
  credit_name: string
  /** Default dollar value (null = varies by card, see card_values). */
  value: number | null
  /** When true, this credit is not counted in the first year (e.g. anniversary free nights). */
  excludes_first_year: boolean
  /** When true, this credit is counted only once (not annually). */
  is_one_time: boolean
  /** Currency this credit is denominated in. Cash = dollar credit, points currency = converted via CPP. */
  credit_currency_id: number | null
  /** IDs of cards in the global library that natively offer this credit. */
  card_ids: number[]
  /** Per-card issuer-stated values: {card_id: dollar_value}. */
  card_values: Record<number, number>
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
  photo_slug?: string | null
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
  sub_points: number | null
  sub_min_spend: number | null
  sub_months: number | null
  sub_spend_earn: number | null
  sub_cash: number | null
  sub_secondary_points: number | null
  annual_bonus: number | null
  transfer_enabler: boolean
  secondary_currency_id: number | null
  secondary_currency_rate: number | null
  secondary_currency_cap_rate: number | null
  secondary_currency_obj: CurrencyRead | null
  accelerator_cost: number | null
  accelerator_spend_limit: number | null
  accelerator_bonus_multiplier: number | null
  accelerator_max_activations: number | null
  photo_slug: string | null
  foreign_transaction_fee: boolean
  sub_recurrence_months: number | null
  sub_family: string | null
  multipliers: CardMultiplier[]
  multiplier_groups: CardMultiplierGroup[]
  /** Portal multipliers pre-expanded through the spend-category hierarchy. */
  portal_premiums: CardPortalPremium[]
}

export interface SpendCategory {
  id: number
  category: string
  parent_id: number | null
  is_system: boolean
  is_housing: boolean
  is_foreign_eligible: boolean
  children: SpendCategory[]
}

export interface SpendCategoryFlat {
  id: number
  category: string
  parent_id: number | null
  is_system: boolean
  is_housing: boolean
  is_foreign_eligible: boolean
}

export interface UserSpendCategoryMapping {
  id: number
  earn_category_id: number
  default_weight: number
  earn_category: SpendCategoryFlat
}

export interface UserSpendCategory {
  id: number
  name: string
  description: string | null
  display_order: number
  is_system: boolean
  mappings: UserSpendCategoryMapping[]
}

export interface WalletSpendItem {
  id: number
  wallet_id: number
  user_spend_category_id: number | null
  user_spend_category: UserSpendCategory | null
  amount: number
  // Legacy fields for backward compatibility
  spend_category_id: number | null
  spend_category: SpendCategory | null
}

export interface CreateWalletSpendItemPayload {
  user_spend_category_id: number
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
  card_effective_annual_fee: number
  card_active_years: number
  total_points: number
  /** Per-active-year earn rate (for per-card display). */
  annual_point_earn: number
  /** Window-basis earn rate (total_card_earn / wallet_window_years, no SUB). Use for wallet/currency-group aggregation so summing stays on the wallet window. */
  annual_point_earn_window: number
  credit_valuation: number
  annual_fee: number
  first_year_fee: number | null
  sub_points: number
  annual_bonus: number
  annual_bonus_percent: number
  annual_bonus_first_year_only: boolean
  sub_extra_spend: number
  sub_spend_earn: number
  sub_opp_cost_dollars: number
  sub_opp_cost_gross_dollars: number
  /** Dollars/year from SUB terms baked into effective_annual_fee.
   * Frontend adds this to EAF when the "Include SUBs" toggle is off, so
   * toggling is a pure display switch (no recalculation required). */
  sub_eaf_contribution: number
  /** Card-year basis variant, paired with card_effective_annual_fee. */
  card_sub_eaf_contribution: number
  avg_spend_multiplier: number
  cents_per_point: number
  effective_currency_name: string
  effective_currency_id?: number
  effective_reward_kind?: 'points' | 'cash'
  effective_currency_photo_slug?: string | null
  category_earn: CategoryEarnItem[]
  /** Effective multiplier per spend category (top-N + manual group selections applied). */
  category_multipliers?: Record<string, number>
  secondary_currency_earn: number
  secondary_currency_name: string
  secondary_currency_id: number
  accelerator_activations: number
  accelerator_bonus_points: number
  accelerator_cost_points: number
  secondary_currency_net_earn: number
  secondary_currency_value_dollars: number
  photo_slug: string | null
}

export interface WalletResult {
  years_counted: number
  total_effective_annual_fee: number
  total_points_earned: number
  /** Total points earned across the wallet window ÷ window years (not a sum of per-card rates). */
  point_income: number
  /** Sum of CardResult.sub_eaf_contribution across selected cards. */
  total_sub_eaf_contribution?: number
  total_cash_reward_dollars?: number
  total_reward_value_usd?: number
  currency_pts: Record<string, number>
  /** Same as currency_pts but keyed by currency id (stable vs renames). */
  currency_pts_by_id?: Record<string, number>
  /** Wallet calc window in years (fractional). */
  wallet_window_years?: number
  /** Per-currency active window in years, keyed by effective currency id.
   * Spans earliest card open → latest close among selected cards earning
   * the currency, clamped to the wallet window. Use to annualize per-currency
   * income over the currency's own window. */
  currency_window_years?: Record<string, number>
  secondary_currency_pts: Record<string, number>
  secondary_currency_pts_by_id?: Record<string, number>
  card_results: CardResult[]
}

// ─── Legacy WalletCard compat shape ──────────────────────────────────────────
//
// The ResolvedCard view (lib/resolveScenarioCards.ts) extends WalletCard so
// downstream subcomponents (timeline, spend, summary) can keep consuming the
// same field shape they did before scenarios. There is no API endpoint that
// returns one of these — they're a client-side composition target only.

export type WalletCardAcquisitionType = 'opened' | 'product_change'
export type WalletCardPanel = 'in_wallet' | 'future_cards' | 'considering'

export interface WalletCard {
  id: number
  wallet_id: number
  card_id: number
  card_name: string | null
  added_date: string
  sub_points: number | null
  sub_min_spend: number | null
  sub_months: number | null
  sub_spend_earn: number | null
  annual_bonus: number | null
  years_counted: number
  annual_fee: number | null
  first_year_fee: number | null
  secondary_currency_rate: number | null
  sub_earned_date: string | null
  sub_projected_earn_date: string | null
  closed_date: string | null
  product_changed_date: string | null
  transfer_enabler: boolean
  acquisition_type: WalletCardAcquisitionType
  pc_from_card_id: number | null
  panel: WalletCardPanel
  is_enabled: boolean
  photo_slug: string | null
  issuer_name: string | null
  network_tier_name: string | null
  credit_totals: CreditTotalByCurrency[]
}

export interface CreditTotalByCurrency {
  kind: 'cash' | 'points'
  currency_id: number | null
  currency_name: string | null
  value: number
}

export interface WalletResultResponse {
  wallet_id: number
  wallet_name: string
  /** Set when this response came from a scenario endpoint. */
  scenario_id?: number | null
  scenario_name?: string | null
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

// ─── Currencies ───────────────────────────────────────────────────────────────

export const currenciesApi = {
  list: () => request<CurrencyRead[]>('/currencies'),
}

// ─── Issuers ──────────────────────────────────────────────────────────────────

export interface IssuerApplicationRuleRead {
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
    request<IssuerApplicationRuleRead[]>('/issuers/application-rules'),
}

// ─── Cards ────────────────────────────────────────────────────────────────────

export const cardsApi = {
  list: () => request<Card[]>('/cards'),
}

// ─── Standardized credit library ─────────────────────────────────────────────

export interface CreateCreditPayload {
  credit_name: string
  value?: number | null
  excludes_first_year?: boolean
  is_one_time?: boolean
  credit_currency_id?: number | null
  card_values?: Record<number, number>
}

export interface UpdateCreditPayload {
  credit_name?: string
  value?: number | null
  excludes_first_year?: boolean
  is_one_time?: boolean
  credit_currency_id?: number | null
  card_values?: Record<number, number>
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


export const travelPortalApi = {
  list: () => request<TravelPortal[]>(`/travel-portals`),
  create: (payload: { name: string; card_ids?: number[] }) =>
    request<TravelPortal>(`/admin/travel-portals`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  update: (
    portalId: number,
    payload: { name?: string; card_ids?: number[] },
  ) =>
    request<TravelPortal>(`/admin/travel-portals/${portalId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  delete: (portalId: number) =>
    request<void>(`/admin/travel-portals/${portalId}`, { method: 'DELETE' }),
}

// ─── Admin: Reference data CRUD ──────────────────────────────────────────────

export const adminApi = {
  listCardRotatingHistory: (cardId: number) =>
    request<CardRotatingHistoryRow[]>(`/admin/cards/${cardId}/rotating-history`),
}

// ─────────────────────────────────────────────────────────────────────────────
// Scenario / CardInstance — new model
// ─────────────────────────────────────────────────────────────────────────────

export type CardInstancePanel = 'in_wallet' | 'future_cards' | 'considering'

export interface CardInstance {
  id: number
  wallet_id: number
  /** NULL = owned (managed via Profile/WalletTab); set = future card scoped to that scenario. */
  scenario_id: number | null
  card_id: number
  card_name: string
  transfer_enabler: boolean
  photo_slug: string | null
  issuer_name: string | null
  network_tier_name: string | null
  /** Account opening date — preserved across product changes. */
  opening_date: string
  /** When this card became its current product via PC. NULL = fresh open. */
  product_change_date: string | null
  closed_date: string | null
  sub_points: number | null
  sub_min_spend: number | null
  sub_months: number | null
  sub_spend_earn: number | null
  annual_bonus: number | null
  annual_bonus_percent: number | null
  annual_bonus_first_year_only: boolean | null
  years_counted: number
  annual_fee: number | null
  first_year_fee: number | null
  secondary_currency_rate: number | null
  sub_earned_date: string | null
  sub_projected_earn_date: string | null
  pc_from_instance_id: number | null
  panel: CardInstancePanel
  is_enabled: boolean
  credit_totals: CreditTotalByCurrency[]
}

export interface OwnedCardCreatePayload {
  card_id: number
  opening_date: string
}

export interface OwnedCardUpdatePayload {
  opening_date?: string
  closed_date?: string | null
  product_change_date?: string | null
  sub_points?: number | null
  sub_min_spend?: number | null
  sub_months?: number | null
  sub_spend_earn?: number | null
  years_counted?: number
  annual_bonus?: number | null
  annual_bonus_percent?: number | null
  annual_bonus_first_year_only?: boolean | null
  annual_fee?: number | null
  first_year_fee?: number | null
  secondary_currency_rate?: number | null
  sub_earned_date?: string | null
  sub_projected_earn_date?: string | null
}

export interface FutureCardCreatePayload extends OwnedCardCreatePayload {
  product_change_date?: string | null
  closed_date?: string | null
  sub_points?: number | null
  sub_min_spend?: number | null
  sub_months?: number | null
  sub_spend_earn?: number | null
  years_counted?: number
  annual_bonus?: number | null
  annual_bonus_percent?: number | null
  annual_bonus_first_year_only?: boolean | null
  annual_fee?: number | null
  first_year_fee?: number | null
  secondary_currency_rate?: number | null
  sub_earned_date?: string | null
  sub_projected_earn_date?: string | null
  pc_from_instance_id?: number | null
  panel?: CardInstancePanel
  is_enabled?: boolean
  /** Optional priority category pins to set immediately after create. */
  priority_category_ids?: number[]
}

export interface FutureCardUpdatePayload extends OwnedCardUpdatePayload {
  pc_from_instance_id?: number | null
  panel?: CardInstancePanel
  is_enabled?: boolean
}

export interface Scenario {
  id: number
  wallet_id: number
  name: string
  description: string | null
  is_default: boolean
  start_date: string | null
  end_date: string | null
  duration_years: number
  duration_months: number
  window_mode: 'duration' | 'end'
  include_subs: boolean
  last_calc_timestamp: string | null
  created_at: string
  updated_at: string
}

export interface ScenarioSummary {
  id: number
  wallet_id: number
  name: string
  description: string | null
  is_default: boolean
  updated_at: string
}

export interface CreateScenarioPayload {
  name: string
  description?: string | null
  copy_from_scenario_id?: number | null
}

export interface UpdateScenarioPayload {
  name?: string
  description?: string | null
  start_date?: string | null
  end_date?: string | null
  duration_years?: number
  duration_months?: number
  window_mode?: 'duration' | 'end'
  include_subs?: boolean
}

export interface ScenarioCardOverlay {
  id: number
  scenario_id: number
  card_instance_id: number
  closed_date: string | null
  product_change_date: string | null
  sub_earned_date: string | null
  sub_projected_earn_date: string | null
  sub_points: number | null
  sub_min_spend: number | null
  sub_months: number | null
  sub_spend_earn: number | null
  annual_bonus: number | null
  annual_bonus_percent: number | null
  annual_bonus_first_year_only: boolean | null
  annual_fee: number | null
  first_year_fee: number | null
  secondary_currency_rate: number | null
  is_enabled: boolean | null
}

export type UpsertOverlayPayload = Partial<Omit<ScenarioCardOverlay, 'id' | 'scenario_id' | 'card_instance_id'>>

export interface ScenarioPortalShareRead {
  id: number
  scenario_id: number
  travel_portal_id: number
  share: number
}

export interface ScenarioCardCategoryPriority {
  id: number
  scenario_id: number
  card_instance_id: number
  spend_category_id: number
  category_name: string
}

export interface ScenarioCardCreditOverride {
  id: number
  scenario_id: number
  card_instance_id: number
  library_credit_id: number
  credit_name: string
  value: number
}

export interface WalletWithScenarios {
  id: number
  user_id: number
  name: string
  description: string | null
  foreign_spend_percent: number
  card_instances: CardInstance[]
  scenarios: ScenarioSummary[]
}

// ─── Wallet (singular) ───────────────────────────────────────────────────────

export const walletApi = {
  /** Get the user's single wallet (auto-creates on first call). */
  get: () => request<WalletWithScenarios>('/wallet'),
  update: (payload: { name?: string; description?: string | null; foreign_spend_percent?: number }) =>
    request<WalletWithScenarios>('/wallet', {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
}

// ─── Owned card instances (Profile/WalletTab) ────────────────────────────────

export const ownedCardInstancesApi = {
  list: () => request<CardInstance[]>('/wallet/card-instances'),
  create: (payload: OwnedCardCreatePayload) =>
    request<CardInstance>('/wallet/card-instances', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  update: (instanceId: number, payload: OwnedCardUpdatePayload) =>
    request<CardInstance>(`/wallet/card-instances/${instanceId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  delete: (instanceId: number) =>
    request<void>(`/wallet/card-instances/${instanceId}`, { method: 'DELETE' }),
}

// ─── Wallet spend (singular wallet) ───────────────────────────────────────────

export const walletSpendApi = {
  list: () => request<WalletSpendItem[]>('/wallet/spend-items'),
  create: (payload: CreateWalletSpendItemPayload) =>
    request<WalletSpendItem>('/wallet/spend-items', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  update: (itemId: number, payload: UpdateWalletSpendItemPayload) =>
    request<WalletSpendItem>(`/wallet/spend-items/${itemId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  delete: (itemId: number) =>
    request<void>(`/wallet/spend-items/${itemId}`, { method: 'DELETE' }),
}

// ─── Scenarios ────────────────────────────────────────────────────────────────

export const scenariosApi = {
  list: () => request<ScenarioSummary[]>('/scenarios'),
  get: (id: number) => request<Scenario>(`/scenarios/${id}`),
  create: (payload: CreateScenarioPayload) =>
    request<Scenario>('/scenarios', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  update: (id: number, payload: UpdateScenarioPayload) =>
    request<Scenario>(`/scenarios/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  delete: (id: number) =>
    request<void>(`/scenarios/${id}`, { method: 'DELETE' }),
  makeDefault: (id: number) =>
    request<Scenario>(`/scenarios/${id}/make-default`, { method: 'POST' }),
  results: (
    id: number,
    params?: {
      start_date?: string
      reference_date?: string
      end_date?: string
      duration_years?: number
      duration_months?: number
      projection_years?: number
      projection_months?: number
      spend_overrides?: Record<string, number>
    },
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
      `/scenarios/${id}/results${qs ? `?${qs}` : ''}`,
    )
  },
  latestResults: (id: number) =>
    request<WalletResultResponse | null>(`/scenarios/${id}/results/latest`),
  roadmap: (id: number, asOfDate?: string) => {
    const qs = asOfDate ? `?as_of_date=${asOfDate}` : ''
    return request<RoadmapResponse>(`/scenarios/${id}/roadmap${qs}`)
  },
}

// ─── Scenario future cards ────────────────────────────────────────────────────

export const scenarioFutureCardsApi = {
  list: (scenarioId: number) =>
    request<CardInstance[]>(`/scenarios/${scenarioId}/future-cards`),
  create: (scenarioId: number, payload: FutureCardCreatePayload) =>
    request<CardInstance>(`/scenarios/${scenarioId}/future-cards`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  update: (scenarioId: number, instanceId: number, payload: FutureCardUpdatePayload) =>
    request<CardInstance>(`/scenarios/${scenarioId}/future-cards/${instanceId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  delete: (scenarioId: number, instanceId: number) =>
    request<void>(`/scenarios/${scenarioId}/future-cards/${instanceId}`, {
      method: 'DELETE',
    }),
}

// ─── Scenario card overlays ───────────────────────────────────────────────────

export const scenarioOverlaysApi = {
  list: (scenarioId: number) =>
    request<ScenarioCardOverlay[]>(`/scenarios/${scenarioId}/overlays`),
  upsert: (scenarioId: number, cardInstanceId: number, payload: UpsertOverlayPayload) =>
    request<ScenarioCardOverlay>(`/scenarios/${scenarioId}/overlays/${cardInstanceId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  clear: (scenarioId: number, cardInstanceId: number) =>
    request<void>(`/scenarios/${scenarioId}/overlays/${cardInstanceId}`, {
      method: 'DELETE',
    }),
}

// ─── Scenario CPP overrides ───────────────────────────────────────────────────

export const scenarioCppApi = {
  listCurrencies: (scenarioId: number) =>
    request<CurrencyRead[]>(`/scenarios/${scenarioId}/currencies`),
  set: (scenarioId: number, currencyId: number, centsPerPoint: number) =>
    request<void>(`/scenarios/${scenarioId}/currencies/${currencyId}/cpp`, {
      method: 'PUT',
      body: JSON.stringify({ cents_per_point: centsPerPoint }),
    }),
  delete: (scenarioId: number, currencyId: number) =>
    request<void>(`/scenarios/${scenarioId}/currencies/${currencyId}/cpp`, {
      method: 'DELETE',
    }),
}

// ─── Scenario portal shares ───────────────────────────────────────────────────

export const scenarioPortalShareApi = {
  list: (scenarioId: number) =>
    request<ScenarioPortalShareRead[]>(`/scenarios/${scenarioId}/portal-shares`),
  upsert: (scenarioId: number, payload: { travel_portal_id: number; share: number }) =>
    request<ScenarioPortalShareRead>(`/scenarios/${scenarioId}/portal-shares`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  delete: (scenarioId: number, travelPortalId: number) =>
    request<void>(`/scenarios/${scenarioId}/portal-shares/${travelPortalId}`, {
      method: 'DELETE',
    }),
}

// ─── Scenario category priorities ─────────────────────────────────────────────

export const scenarioCategoryPriorityApi = {
  list: (scenarioId: number) =>
    request<ScenarioCardCategoryPriority[]>(`/scenarios/${scenarioId}/category-priorities`),
  set: (scenarioId: number, instanceId: number, spendCategoryIds: number[]) =>
    request<ScenarioCardCategoryPriority[]>(
      `/scenarios/${scenarioId}/card-instances/${instanceId}/category-priorities`,
      {
        method: 'PUT',
        body: JSON.stringify({ spend_category_ids: spendCategoryIds }),
      },
    ),
  delete: (scenarioId: number, instanceId: number) =>
    request<void>(
      `/scenarios/${scenarioId}/card-instances/${instanceId}/category-priorities`,
      { method: 'DELETE' },
    ),
}

// ─── Scenario per-instance credit overrides ──────────────────────────────────

export const scenarioCardCreditApi = {
  list: (scenarioId: number, instanceId: number) =>
    request<ScenarioCardCreditOverride[]>(
      `/scenarios/${scenarioId}/card-instances/${instanceId}/credits`,
    ),
  upsert: (
    scenarioId: number,
    instanceId: number,
    libraryCreditId: number,
    payload: { value: number },
  ) =>
    request<ScenarioCardCreditOverride>(
      `/scenarios/${scenarioId}/card-instances/${instanceId}/credits/${libraryCreditId}`,
      { method: 'PUT', body: JSON.stringify(payload) },
    ),
  delete: (scenarioId: number, instanceId: number, libraryCreditId: number) =>
    request<void>(
      `/scenarios/${scenarioId}/card-instances/${instanceId}/credits/${libraryCreditId}`,
      { method: 'DELETE' },
    ),
}
