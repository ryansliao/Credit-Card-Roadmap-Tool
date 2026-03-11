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
}

export interface CardCredit {
  credit_name: string
  credit_value: number
}

export interface IssuerRead {
  id: number
  name: string
  co_brand_partner: string | null
  network: string | null
}

export interface CurrencyRead {
  id: number
  issuer_id: number | null
  name: string
  cents_per_point: number
  is_cashback: boolean
  is_transferable: boolean
  converts_to_points?: boolean
  converts_to_currency_id?: number | null
  issuer?: IssuerRead | null
}

export interface EcosystemCurrencyRead {
  currency_id: number
  currency?: CurrencyRead | null
}

export interface EcosystemRead {
  id: number
  name: string
  points_currency_id: number
  cashback_currency_id: number | null
  points_currency?: CurrencyRead | null
  cashback_currency?: CurrencyRead | null
  ecosystem_currencies: EcosystemCurrencyRead[]  // additional only
}

export interface CardEcosystemMembership {
  ecosystem_id: number
  key_card: boolean
  ecosystem?: EcosystemRead | null
}

export interface Card {
  id: number
  name: string
  issuer: IssuerRead
  currency_obj: CurrencyRead
  issuer_id: number
  currency_id: number
  annual_fee: number
  sub_points: number
  sub_min_spend: number | null
  sub_months: number | null
  sub_spend_points: number
  annual_bonus_points: number
  ecosystem_memberships: CardEcosystemMembership[]
  multipliers: CardMultiplier[]
  credits: CardCredit[]
}

export interface SpendCategory {
  id: number
  category: string
  annual_spend: number
}

export interface CardResult {
  card_id: number
  card_name: string
  selected: boolean
  annual_ev: number
  second_year_ev: number
  total_points: number
  annual_point_earn: number
  credit_valuation: number
  annual_fee: number
  sub_points: number
  annual_bonus_points: number
  sub_extra_spend: number
  sub_spend_points: number
  sub_opp_cost_dollars: number
  sub_opp_cost_gross_dollars: number
  avg_spend_multiplier: number
  cents_per_point: number
  effective_currency_name: string
}

export interface WalletResult {
  years_counted: number
  total_annual_ev: number
  total_points_earned: number
  total_annual_pts: number
  currency_pts: Record<string, number>
  card_results: CardResult[]
}

export interface ScenarioCard {
  id: number
  scenario_id: number
  card_id: number
  card_name: string | null
  start_date: string | null
  end_date: string | null
  years_counted: number
}

export interface Scenario {
  id: number
  name: string
  description: string | null
  as_of_date: string | null
  scenario_cards: ScenarioCard[]
}

export interface ScenarioResult {
  scenario_id: number
  scenario_name: string
  as_of_date: string | null
  wallet: WalletResult
}

// ─── Wallets (Wallet Tool) ───────────────────────────────────────────────────

export interface WalletCard {
  id: number
  wallet_id: number
  card_id: number
  card_name: string | null
  added_date: string
  sub_points: number | null
  sub_min_spend: number | null
  sub_months: number | null
  sub_spend_points: number | null
  years_counted: number
}

export interface Wallet {
  id: number
  user_id: number
  name: string
  description: string | null
  as_of_date: string | null
  wallet_cards: WalletCard[]
}

export interface WalletResultResponse {
  wallet_id: number
  wallet_name: string
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

export interface AddCardToWalletPayload {
  card_id: number
  added_date: string
  sub_points?: number | null
  sub_min_spend?: number | null
  sub_months?: number | null
  sub_spend_points?: number | null
  years_counted?: number
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
  removeCard: (walletId: number, cardId: number) =>
    request<void>(`/wallets/${walletId}/cards/${cardId}`, { method: 'DELETE' }),
  results: (
    walletId: number,
    params?: {
      reference_date?: string
      projection_years?: number
      projection_months?: number
      spend_overrides?: Record<string, number>
    }
  ) => {
    const search = new URLSearchParams()
    if (params?.reference_date) search.set('reference_date', params.reference_date)
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
}

// ─── Issuers ───────────────────────────────────────────────────────────────────

export interface IssuerCreatePayload {
  name: string
  co_brand_partner?: string | null
  network?: string | null
}

export interface IssuerUpdatePayload {
  name?: string
  co_brand_partner?: string | null
  network?: string | null
}

export const issuersApi = {
  list: () => request<IssuerRead[]>('/issuers'),
  create: (payload: IssuerCreatePayload) =>
    request<IssuerRead>('/issuers', { method: 'POST', body: JSON.stringify(payload) }),
  update: (id: number, payload: IssuerUpdatePayload) =>
    request<IssuerRead>(`/issuers/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  delete: (id: number) => request<void>(`/issuers/${id}`, { method: 'DELETE' }),
}

// ─── Currencies ───────────────────────────────────────────────────────────────

export interface CurrencyCreatePayload {
  issuer_id?: number | null
  name: string
  cents_per_point?: number
  is_cashback?: boolean
  is_transferable?: boolean
}

export interface CurrencyUpdatePayload {
  name?: string
  issuer_id?: number | null
  cents_per_point?: number
  is_cashback?: boolean
  is_transferable?: boolean
}

export const currenciesApi = {
  list: () => request<CurrencyRead[]>('/currencies'),
  create: (payload: CurrencyCreatePayload) =>
    request<CurrencyRead>('/currencies', { method: 'POST', body: JSON.stringify(payload) }),
  update: (id: number, payload: CurrencyUpdatePayload) =>
    request<CurrencyRead>(`/currencies/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  delete: (id: number) => request<void>(`/currencies/${id}`, { method: 'DELETE' }),
}

// ─── Ecosystems ────────────────────────────────────────────────────────────────

export interface EcosystemCreatePayload {
  name: string
  points_currency_id: number
  cashback_currency_id?: number | null
  additional_currency_ids?: number[]
}

export interface EcosystemUpdatePayload {
  name?: string
  points_currency_id?: number
  cashback_currency_id?: number | null
  additional_currency_ids?: number[]
}

export const ecosystemsApi = {
  list: () => request<EcosystemRead[]>('/ecosystems'),
  get: (id: number) => request<EcosystemRead>(`/ecosystems/${id}`),
  create: (payload: EcosystemCreatePayload) =>
    request<EcosystemRead>('/ecosystems', { method: 'POST', body: JSON.stringify(payload) }),
  update: (id: number, payload: EcosystemUpdatePayload) =>
    request<EcosystemRead>(`/ecosystems/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  delete: (id: number) => request<void>(`/ecosystems/${id}`, { method: 'DELETE' }),
}

// ─── Cards ────────────────────────────────────────────────────────────────────

export interface CardEcosystemMembershipPayload {
  ecosystem_id: number
  key_card: boolean
}

export interface CardCreatePayload {
  name: string
  issuer_id: number
  currency_id: number
  annual_fee?: number
  sub_points?: number
  sub_min_spend?: number | null
  sub_months?: number | null
  sub_spend_points?: number
  annual_bonus_points?: number
  ecosystem_memberships?: CardEcosystemMembershipPayload[]
  multipliers?: CardMultiplier[]
  credits?: CardCredit[]
}

export const cardsApi = {
  list: () => request<Card[]>('/cards'),
  get: (id: number) => request<Card>(`/cards/${id}`),
  create: (payload: CardCreatePayload) =>
    request<Card>('/cards', { method: 'POST', body: JSON.stringify(payload) }),
  update: (id: number, data: Partial<CardCreatePayload>) =>
    request<Card>(`/cards/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (id: number) => request<void>(`/cards/${id}`, { method: 'DELETE' }),
}

// ─── Spend categories ─────────────────────────────────────────────────────────

export const spendApi = {
  list: () => request<SpendCategory[]>('/spend'),
  update: (category: string, annual_spend: number) =>
    request<SpendCategory>(`/spend/${encodeURIComponent(category)}`, {
      method: 'PUT',
      body: JSON.stringify({ annual_spend }),
    }),
}

// ─── Calculation ──────────────────────────────────────────────────────────────

export interface CalculateRequest {
  years_counted: number
  selected_card_ids: number[]
  spend_overrides: Record<string, number>
}

export const calcApi = {
  calculate: (payload: CalculateRequest) =>
    request<WalletResult>('/calculate', { method: 'POST', body: JSON.stringify(payload) }),
}

// ─── Scenarios ────────────────────────────────────────────────────────────────

export interface CreateScenarioPayload {
  name: string
  description?: string
  as_of_date?: string
  cards?: { card_id: number; start_date?: string; end_date?: string; years_counted?: number }[]
}

export interface AddCardToScenarioPayload {
  card_id: number
  start_date?: string
  end_date?: string
  years_counted?: number
}

export const scenariosApi = {
  list: () => request<Scenario[]>('/scenarios'),
  get: (id: number) => request<Scenario>(`/scenarios/${id}`),
  create: (payload: CreateScenarioPayload) =>
    request<Scenario>('/scenarios', { method: 'POST', body: JSON.stringify(payload) }),
  update: (id: number, payload: Partial<CreateScenarioPayload>) =>
    request<Scenario>(`/scenarios/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  delete: (id: number) => request<void>(`/scenarios/${id}`, { method: 'DELETE' }),
  addCard: (scenarioId: number, payload: AddCardToScenarioPayload) =>
    request<ScenarioCard>(`/scenarios/${scenarioId}/cards`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  removeCard: (scenarioId: number, cardId: number) =>
    request<void>(`/scenarios/${scenarioId}/cards/${cardId}`, { method: 'DELETE' }),
  results: (id: number, referenceDate?: string) => {
    const qs = referenceDate ? `?reference_date=${referenceDate}` : ''
    return request<ScenarioResult>(`/scenarios/${id}/results${qs}`)
  },
}
