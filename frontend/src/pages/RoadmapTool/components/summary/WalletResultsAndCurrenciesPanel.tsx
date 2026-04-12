import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import type { CardResult, WalletResult } from '../../../../api/client'
import { walletCppApi, walletsApi } from '../../../../api/client'
import { formatCashRewardUnits, formatMoney, formatPoints } from '../../../../utils/format'
import { queryKeys } from '../../lib/queryKeys'
import { CurrencySettingsDropdown } from '../summary/CurrencySettingsDropdown'
import { SpendTabContent } from '../spend/SpendTabContent'
import { InfoIconButton, InfoPopover } from '../../../../components/InfoPopover'

function CardPhoto({ slug, name }: { slug: string | null; name: string }) {
  const [failed, setFailed] = useState(false)
  if (!slug || failed) {
    return (
      <div className="w-full h-full bg-gradient-to-br from-slate-700 to-slate-800 flex items-center justify-center">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-slate-500">
          <rect x="1" y="4" width="22" height="16" rx="2" ry="2" />
          <line x1="1" y1="10" x2="23" y2="10" />
        </svg>
      </div>
    )
  }
  return (
    <img
      src={`/photos/${slug}.png`}
      alt={name}
      className="w-full h-full object-contain"
      onError={() => setFailed(true)}
    />
  )
}

type StatTopic = 'eaf' | 'income' | 'fees' | 'methodology' | null

type WalletSummaryTab = 'summary' | 'spend'

/** Annual point income for a card (excludes SUB points). */
function cardAnnualPointIncome(c: CardResult, totalYears: number): number {
  return (c.total_points - c.sub_points - c.sub_spend_earn) / totalYears
}

interface Props {
  walletId: number | null
  result: WalletResult | null
  resultsError: Error | null
  isCalculating: boolean
  durationYears: number
  durationMonths: number
  photoSlugs?: Record<number, string | null>
  onOpenSettings: () => void
  onCppChange: () => void
  onSpendChange: () => void
}

export function WalletResultsAndCurrenciesPanel({
  walletId,
  result,
  resultsError,
  isCalculating,
  durationYears,
  durationMonths,
  photoSlugs,
  onOpenSettings,
  onCppChange,
  onSpendChange,
}: Props) {
  const [editingCurrencyId, setEditingCurrencyId] = useState<number | null>(null)
  const [activeTab, setActiveTab] = useState<WalletSummaryTab>('summary')
  const [showBiltCashInfo, setShowBiltCashInfo] = useState(false)
  const [statTopic, setStatTopic] = useState<StatTopic>(null)

  const { data: currencies = [], isLoading: currenciesLoading } = useQuery({
    queryKey: queryKeys.walletCurrencies(walletId),
    queryFn: () => walletCppApi.listCurrencies(walletId!),
    enabled: walletId != null,
  })

  const { data: balances = [], isLoading: balancesLoading } = useQuery({
    queryKey: queryKeys.walletCurrencyBalances(walletId),
    queryFn: () => walletsApi.listCurrencyBalances(walletId!),
    enabled: walletId != null,
  })

  // Bilt Cash is shown nested under Bilt Rewards rather than as its own
  // top-level entry in the wallet summary.
  const sortedBalances = useMemo(
    () =>
      [...balances]
        .filter((b) => b.currency_name !== 'Bilt Cash')
        .sort(
          (a, b) => b.balance - a.balance || a.currency_name.localeCompare(b.currency_name)
        ),
    [balances]
  )

  const biltCashBalance = useMemo(
    () => balances.find((b) => b.currency_name === 'Bilt Cash') ?? null,
    [balances]
  )

  const cppForName = (name: string) => {
    const c = currencies.find((x) => x.name === name)
    return c ? c.user_cents_per_point ?? c.cents_per_point : 1
  }

  const rewardKindForName = (name: string): 'points' | 'cash' => {
    const c = currencies.find((x) => x.name === name)
    return (c?.reward_kind ?? 'points') === 'cash' ? 'cash' : 'points'
  }

  const totalYears = Math.max(durationYears + durationMonths / 12, 1 / 12)

  const selectedCards = result?.card_results.filter((c) => c.selected) ?? []
  const totalAnnualFees = selectedCards.reduce((s, c) => s + c.annual_fee, 0)
  const totalEffectiveAF = selectedCards.reduce((s, c) => s + c.effective_annual_fee, 0)
  const totalAnnualPoints = selectedCards.reduce(
    (s, c) => s + cardAnnualPointIncome(c, totalYears),
    0
  )

  const cardsByCurrency = useMemo(() => {
    if (!result) return {} as Record<string, CardResult[]>
    const grouped = result.card_results
      .filter((c) => c.selected)
      .reduce(
        (acc, card) => {
          const cur = card.effective_currency_name
          acc[cur] = [...(acc[cur] ?? []), card]
          return acc
        },
        {} as Record<string, CardResult[]>
      )
    for (const cur of Object.keys(grouped)) {
      grouped[cur].sort((a, b) => a.effective_annual_fee - b.effective_annual_fee)
    }
    return grouped
  }, [result])


  const isLoading = currenciesLoading || (walletId != null && balancesLoading)

  return (
    <div className="flex h-full min-w-0 min-h-0 items-stretch">
      {/* Binder-style icon tabs sitting outside the panel on the left, near the top */}
      {walletId != null && (
        <div className="shrink-0 flex flex-col gap-1 pt-6 z-10">
          {([
            {
              key: 'summary' as const,
              label: 'Summary',
              icon: (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="3" width="7" height="9" rx="1" />
                  <rect x="14" y="3" width="7" height="5" rx="1" />
                  <rect x="14" y="12" width="7" height="9" rx="1" />
                  <rect x="3" y="16" width="7" height="5" rx="1" />
                </svg>
              ),
            },
            {
              key: 'spend' as const,
              label: 'Spend',
              icon: (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="12" y1="1" x2="12" y2="23" />
                  <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
                </svg>
              ),
            },
          ]).map((tab) => {
            const isActive = activeTab === tab.key
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveTab(tab.key)}
                className={`px-2 py-3 rounded-l-md border border-r-0 transition-colors ${
                  isActive
                    ? 'bg-slate-900 text-indigo-300 border-slate-700 -mr-px'
                    : 'bg-slate-800/70 text-slate-400 border-slate-800 hover:text-slate-200 hover:bg-slate-800'
                }`}
                aria-pressed={isActive}
                aria-label={tab.label}
                title={tab.label}
              >
                {tab.icon}
              </button>
            )
          })}
        </div>
      )}

      <div className="bg-slate-900 border border-slate-700 rounded-xl p-4 min-w-0 min-h-0 flex-1 flex flex-col overflow-hidden">
      {/* h-7 keeps this header the same height as the Cards panel header so the
          top of the summary statistics row lines up with the top of the In Wallet panel. */}
      <div className="shrink-0 h-7 flex items-center justify-between mb-3">
        <div className="flex items-center gap-1">
          <h2 className="text-sm font-semibold text-slate-200">Wallet Summary</h2>
          <InfoIconButton onClick={() => setStatTopic('methodology')} label="Calculation methodology" />
        </div>
        {walletId != null && (
          <div className="flex items-center gap-6">
            <button
              type="button"
              onClick={onOpenSettings}
              className="p-1 rounded transition-colors text-slate-500 hover:text-slate-200 hover:bg-slate-700"
              title="Wallet Settings"
              aria-label="Open wallet settings"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="4" y1="6" x2="20" y2="6"/>
                <circle cx="8" cy="6" r="2.5" fill="currentColor" stroke="none"/>
                <line x1="4" y1="12" x2="20" y2="12"/>
                <circle cx="16" cy="12" r="2.5" fill="currentColor" stroke="none"/>
                <line x1="4" y1="18" x2="20" y2="18"/>
                <circle cx="10" cy="18" r="2.5" fill="currentColor" stroke="none"/>
              </svg>
            </button>
          </div>
        )}
      </div>
      <div className="flex flex-col flex-1 min-h-0 min-w-0 overflow-y-auto pr-0.5 -mr-0.5">
        {walletId == null ? (
          <div className="text-slate-500 text-sm py-4">Select a wallet.</div>
        ) : (
          <>
            {/* Top stats */}
            <div className="space-y-3">
              {resultsError && (
                <div className="text-red-400 text-sm bg-red-950 border border-red-700 rounded-lg p-3">
                  {resultsError.message}
                </div>
              )}
              {result || isCalculating ? (
                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-indigo-900/40 border border-indigo-700 rounded-xl p-3 text-center">
                    <div className="flex items-center justify-center gap-1">
                      <p className="text-[10px] text-indigo-300 uppercase tracking-wider">Effective Annual Fee</p>
                      <InfoIconButton onClick={() => setStatTopic('eaf')} label="How Effective Annual Fee is calculated" />
                    </div>
                    {result ? (
                      <p className={`text-xl font-bold mt-0.5 ${totalEffectiveAF < 0 ? 'text-emerald-400' : 'text-indigo-100'}`}>{formatMoney(totalEffectiveAF)}</p>
                    ) : (
                      <div className="h-7 mt-0.5 flex items-center justify-center">
                        <div className="h-4 w-16 bg-indigo-800/50 rounded animate-pulse" />
                      </div>
                    )}
                  </div>
                  <div className="bg-slate-800 border border-slate-700 rounded-xl p-3 text-center">
                    <div className="flex items-center justify-center gap-1">
                      <p className="text-[10px] text-slate-400 uppercase tracking-wider">Annual Point Income</p>
                      <InfoIconButton onClick={() => setStatTopic('income')} label="How Annual Point Income is calculated" />
                    </div>
                    {result ? (
                      <p className="text-xl font-bold text-white mt-0.5">{formatPoints(Math.round(totalAnnualPoints))}</p>
                    ) : (
                      <div className="h-7 mt-0.5 flex items-center justify-center">
                        <div className="h-4 w-16 bg-slate-700/50 rounded animate-pulse" />
                      </div>
                    )}
                  </div>
                  <div className="bg-slate-800 border border-slate-700 rounded-xl p-3 text-center">
                    <div className="flex items-center justify-center gap-1">
                      <p className="text-[10px] text-slate-400 uppercase tracking-wider">Total Annual Fees</p>
                      <InfoIconButton onClick={() => setStatTopic('fees')} label="How Total Annual Fees is calculated" />
                    </div>
                    {result ? (
                      <p className="text-xl font-bold text-red-400 mt-0.5">{formatMoney(totalAnnualFees)}</p>
                    ) : (
                      <div className="h-7 mt-0.5 flex items-center justify-center">
                        <div className="h-4 w-16 bg-slate-700/50 rounded animate-pulse" />
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="text-slate-500 text-xs text-center py-2">
                  Add cards to see effective annual fee (credits, SUB and fees amortised over your projection).
                </div>
              )}
            </div>

            {/* Currencies + Cards combined (Summary tab) */}
            {activeTab === 'summary' && isLoading ? (
              <div className="flex flex-1 min-h-0 items-center justify-center text-slate-500 text-sm">
                Loading…
              </div>
            ) : activeTab === 'summary' ? (
              <div className="flex flex-col flex-1 min-h-0 pt-3">
                <ul className="space-y-2">
                  {sortedBalances.map((b) => {
                  const cpp = cppForName(b.currency_name)
                  const rk = rewardKindForName(b.currency_name)
                  const isCash = rk === 'cash'
                  const estValue = b.balance > 0 ? (b.balance * cpp) / 100 : 0
                  const cards = cardsByCurrency[b.currency_name] ?? []
                  const currencyAnnualPts = cards.reduce(
                    (s, c) => s + cardAnnualPointIncome(c, totalYears),
                    0
                  )
                  const hasResultData = result != null && cards.length > 0
                  const isEditing = editingCurrencyId === b.currency_id
                  const rowCurrency = currencies.find((c) => c.id === b.currency_id) ?? null

                  return (
                    <li key={b.id} className="bg-slate-800/80 rounded-lg overflow-hidden">
                      {/* Currency header row */}
                      <div className="px-2.5 py-2">
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-1 min-w-0">
                            <span
                              className="text-sm font-semibold text-white truncate"
                              title={b.currency_name}
                            >
                              {b.currency_name}
                            </span>
                            {b.currency_name === 'Bilt Rewards' && (
                              <InfoIconButton
                                onClick={() => setShowBiltCashInfo(true)}
                                label="How Bilt Rewards and Bilt Cash are calculated"
                              />
                            )}
                          </div>
                          <div className="flex items-center shrink-0">
                            {hasResultData && (
                              <>
                                <span className="text-xs text-slate-500 tabular-nums">
                                  {isCash
                                    ? `+${formatMoney((currencyAnnualPts * cpp) / 100)} /Year`
                                    : `+${formatPoints(Math.round(currencyAnnualPts))} Pts/Year`}
                                </span>
                                <span className="text-slate-600 mx-2">·</span>
                              </>
                            )}
                            <span className="text-sm font-semibold text-slate-300 tabular-nums">
                              {isCash
                                ? formatCashRewardUnits(b.balance, cpp)
                                : `${formatPoints(b.balance)} Pts`}
                            </span>
                            <button
                              type="button"
                              onClick={() =>
                                setEditingCurrencyId(isEditing ? null : b.currency_id)
                              }
                              style={{ marginLeft: '0.5rem' }}
                              className={`p-1 rounded transition-colors ${
                                isEditing
                                  ? 'text-indigo-300 bg-slate-700'
                                  : 'text-slate-500 hover:text-slate-200 hover:bg-slate-700'
                              }`}
                              aria-label="Edit currency"
                              aria-expanded={isEditing}
                              title="Edit"
                            >
                              <svg
                                width="13"
                                height="13"
                                viewBox="0 0 24 24"
                                fill="none"
                                stroke="currentColor"
                                strokeWidth="2"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                className={`transition-transform ${isEditing ? 'rotate-180' : ''}`}
                              >
                                <polyline points="6 9 12 15 18 9" />
                              </svg>
                            </button>
                          </div>
                        </div>
                        {!hasResultData && !isCash && estValue > 0 ? (
                          <div className="text-xs text-slate-500 mt-0.5 tabular-nums">
                            ≈ {formatMoney(estValue)}
                          </div>
                        ) : !hasResultData && isCash && estValue > 0 ? (
                          <div className="text-xs text-slate-500 mt-0.5 tabular-nums">
                            {formatMoney(estValue)} Face Value
                          </div>
                        ) : null}
                        {/* Nested Bilt Cash row, only on Bilt Rewards */}
                        {b.currency_name === 'Bilt Rewards' && biltCashBalance && (() => {
                          const biltCashAnnual = cards.reduce(
                            (s, c) =>
                              s + (c.secondary_currency_name === 'Bilt Cash'
                                ? (c.secondary_currency_value_dollars || 0) / totalYears
                                : 0),
                            0
                          )
                          const biltCashCpp = cppForName('Bilt Cash')
                          return (
                            <div className="mt-1.5 pt-1.5 border-t border-slate-700/40 flex items-center justify-between gap-2">
                              <div className="flex items-center gap-1 min-w-0">
                                <span className="text-xs text-slate-400 truncate">Bilt Cash</span>
                              </div>
                              <div className="flex items-center shrink-0">
                                {hasResultData && biltCashAnnual > 0 && (
                                  <>
                                    <span className="text-xs text-slate-500 tabular-nums">
                                      +{formatMoney(biltCashAnnual)} /Year
                                    </span>
                                    <span className="text-slate-600 mx-2">·</span>
                                  </>
                                )}
                                <span className="text-xs font-semibold text-slate-300 tabular-nums">
                                  {formatCashRewardUnits(biltCashBalance.balance, biltCashCpp)}
                                </span>
                              </div>
                            </div>
                          )
                        })()}
                      </div>

                      {/* Inline currency settings dropdown */}
                      {isEditing && rowCurrency != null && (
                        <CurrencySettingsDropdown
                          walletId={walletId}
                          currency={rowCurrency}
                          balance={b}
                          onCppChange={onCppChange}
                        />
                      )}

                      {/* Nested card rows */}
                      {cards.length > 0 && (
                        <div className="border-t border-slate-700/60">
                          {cards.map((card, idx) => {
                            const cardYears = card.card_active_years || totalYears
                            const cardEffectiveAF = card.card_effective_annual_fee
                            const isLast = idx === cards.length - 1
                            const cardIsCash = (card.effective_reward_kind ?? 'points') === 'cash'
                            const annualPts = cardAnnualPointIncome(card, cardYears)
                            const annualPtsDisplay = cardIsCash
                              ? `+${formatMoney((annualPts * card.cents_per_point) / 100)}`
                              : `+${formatPoints(Math.round(annualPts))}`
                            const annualPtsUnit = cardIsCash ? ' /Year' : ' Pts/Year'
                            return (
                              <div
                                key={card.card_id}
                                className={`bg-slate-900/40 ${!isLast ? 'border-b border-slate-700/40' : ''}`}
                              >
                                {/* Card header row */}
                                <div className="px-3 py-1.5 flex items-center gap-3">
                                  <div className="w-[72px] h-11 shrink-0 rounded overflow-hidden bg-slate-700/50">
                                    <CardPhoto slug={photoSlugs?.[card.card_id] ?? null} name={card.card_name} />
                                  </div>
                                  <div className="min-w-0 flex-1">
                                    <p
                                      className="text-sm font-medium text-slate-200 truncate"
                                      title={card.card_name}
                                    >
                                      {card.card_name}
                                    </p>
                                    <p className="text-xs text-slate-500 mt-0.5">
                                      {formatMoney(card.annual_fee)} Annual Fee
                                      {card.credit_valuation !== 0 && (
                                        <>
                                          <span className="text-slate-600 mx-1">·</span>
                                          <span>{formatMoney(card.credit_valuation)} Credit Value</span>
                                        </>
                                      )}
                                    </p>
                                  </div>
                                  <div className="flex flex-col items-end justify-center shrink-0 gap-0.5">
                                    <span className="text-xs text-slate-500 tabular-nums">
                                      {annualPtsDisplay}{annualPtsUnit}
                                    </span>
                                    {card.secondary_currency_name && card.secondary_currency_net_earn > 0 && (
                                      <span className="text-xs text-indigo-400/70 tabular-nums">
                                        +{formatPoints(Math.round(card.secondary_currency_net_earn / cardYears))} {card.secondary_currency_name}/Year
                                        {card.accelerator_activations > 0 && (
                                          <span className="text-slate-500"> · {card.accelerator_activations}x Accelerator</span>
                                        )}
                                      </span>
                                    )}
                                    <p className={`text-sm font-semibold tabular-nums ${cardEffectiveAF <= 0 ? 'text-emerald-400' : 'text-slate-200'}`}>
                                      {formatMoney(cardEffectiveAF)} <span className="text-xs font-normal text-slate-500">EAF</span>
                                    </p>
                                  </div>
                                </div>
                              </div>
                            )
                          })}
                        </div>
                      )}
                    </li>
                  )
                  })}
                </ul>
                {sortedBalances.length === 0 && (
                  <p className="text-slate-500 text-xs pt-3">
                    Add a card that earns a currency to see it here.
                  </p>
                )}
              </div>
            ) : null}

            {/* Spend tab content */}
            {activeTab === 'spend' && (
              <SpendTabContent
                walletId={walletId}
                selectedCards={selectedCards}
                isTotal={false}
                totalYears={totalYears}
                onSpendChange={onSpendChange}
              />
            )}

          </>
        )}
      </div>

      </div>

      {showBiltCashInfo && (
        <InfoPopover title="How Bilt Rewards Are Calculated" onClose={() => setShowBiltCashInfo(false)} zIndex="z-50">
          <p>
            Bilt 2.0 cards offer two mutually exclusive earning modes on housing.
            The calculator evaluates both and picks whichever produces more value
            for your wallet.
          </p>
          <div>
            <p className="text-slate-300 font-medium mb-1">Tiered housing mode</p>
            <p>
              Earn Bilt Points directly on Rent / Mortgage, scaled by how much
              non-housing you put on the card relative to housing:
            </p>
            <p className="mt-1 px-2 py-1 bg-slate-800 rounded font-mono text-[11px] text-slate-300 leading-snug">
              {'< 25%  → 0x + 3,000 pts/yr floor'}<br />
              {'< 50%  → 0.5x'}<br />
              {'< 75%  → 0.75x'}<br />
              {'< 100% → 1.0x'}<br />
              {'≥ 100% → 1.25x'}
            </p>
            <p className="mt-1">
              No Bilt Cash is earned in this mode.
            </p>
          </div>
          <div>
            <p className="text-slate-300 font-medium mb-1">Bilt Cash mode</p>
            <p>
              Non-housing spend earns the card's base category multiplier
              (e.g. Palladium 2x) plus a three-tier Bilt Cash bonus. Housing
              earns no direct points — its value is baked into Tier 1.
            </p>
            <p className="mt-1 text-slate-400">
              <span className="text-slate-300">Tier 1</span> — first
              {' '}<span className="text-slate-300">0.75 × housing</span> dollars
              of non-housing. Earns <span className="text-slate-300">+1.33x</span>
              {' '}bonus (4% Bilt Cash → Bilt Points at
              {' '}<span className="text-slate-300">$30 : 1,000 pts</span>, redeemed
              at housing-payment time).
              <br />
              Palladium effective: <span className="text-slate-300">3.33x</span>
            </p>
            <p className="mt-1 text-slate-400">
              <span className="text-slate-300">Tier 2</span> — next
              {' '}<span className="text-slate-300">$25,000</span> (5 × $5,000
              Point Accelerator activations, Obsidian &amp; Palladium only).
              Earns <span className="text-slate-300">+1x</span> bonus, self-funded
              by the Bilt Cash the Tier 2 spend itself generates.
              <br />
              Palladium effective: <span className="text-slate-300">3x</span>
            </p>
            <p className="mt-1 text-slate-400">
              <span className="text-slate-300">Tier 3</span> — remaining non-housing.
              Base multiplier only; excess Bilt Cash has no redemption path.
              <br />
              Palladium effective: <span className="text-slate-300">2x</span>
            </p>
          </div>
          <div>
            <p className="text-slate-300 font-medium mb-1">The Bilt Cash counter</p>
            <p>
              The nested "Bilt Cash" balance shows the gross Bilt Cash points
              earned (4% of non-housing allocated to Bilt cards). Its dollar
              value is already captured in the Bilt Rewards line above via the
              tier conversions — the counter is informational, not additive.
            </p>
          </div>
          <div>
            <p className="text-slate-300 font-medium mb-1">Example: $24k rent, $20k non-housing</p>
            <p>
              Tier 1 = <span className="text-slate-300">min($20k, 0.75 × $24k) = $18k</span>
              {' '}at 3.33x (Palladium). Tier 2 = remaining
              {' '}<span className="text-slate-300">$2k</span> at 3x. No Tier 3.
              Tiered mode would give
              {' '}<span className="text-slate-300">$24k × 1.0x = 24,000 pts</span>,
              which is less than Bilt Cash mode's effective bonus, so the
              calculator picks Bilt Cash for this wallet.
            </p>
          </div>
        </InfoPopover>
      )}

      {statTopic === 'eaf' && (
        <InfoPopover title="Effective Annual Fee" onClose={() => setStatTopic(null)}>
          <p>
            The wallet's net annual cost (or value) after credits, sign-up
            bonuses, and category earn are subtracted from annual fees.
            A negative value means the wallet returns more than it costs.
          </p>
          <div>
            <p className="text-slate-300 font-medium mb-1">Per-card formula</p>
            <p className="px-2 py-1 bg-slate-800 rounded font-mono text-[11px] text-slate-300 leading-snug">
              −(category_earn × cpp + sub/years + credits − fees) / years
            </p>
            <p className="mt-1">
              One-time benefits (SUB, first-year bonus, one-time credits)
              are amortised over the projection duration. Recurring credits
              and category earn count fully each year.
            </p>
          </div>
          <div>
            <p className="text-slate-300 font-medium mb-1">Wallet total</p>
            <p>
              Sum of every selected card's individual EAF. Each category's
              spend is allocated to the card with the best
              {' '}<span className="font-mono text-[11px] text-slate-300">multiplier × CPP</span>,
              so the same dollar isn't double-counted across cards.
            </p>
          </div>
        </InfoPopover>
      )}

      {statTopic === 'income' && (
        <InfoPopover title="Annual Point Income" onClose={() => setStatTopic(null)}>
          <p>
            Points and miles earned per year from category spend across all
            selected cards (excludes one-time SUB bonuses).
          </p>
          <div>
            <p className="text-slate-300 font-medium mb-1">How it's allocated</p>
            <p>
              Each spend category goes to the card(s) with the highest
              {' '}<span className="font-mono text-[11px] text-slate-300">multiplier × CPP</span>{' '}
              score. Tied cards split the category dollars evenly. Annual
              bonuses (fixed and percentage-based) are added on top.
            </p>
          </div>
          <div>
            <p className="text-slate-300 font-medium mb-1">Currency upgrades</p>
            <p>
              When a card's currency converts to another currency in the
              wallet (e.g. Chase Freedom UR Cash → Chase UR with a Sapphire),
              earn is converted at the upgrade rate and valued at the
              target's CPP.
            </p>
          </div>
          <div>
            <p className="text-slate-300 font-medium mb-1">SUB exclusion</p>
            <p>
              Sign-up bonuses are not counted here — they show up in the
              currency balance totals and contribute to EAF as one-time
              amortised benefits.
            </p>
          </div>
        </InfoPopover>
      )}

      {statTopic === 'fees' && (
        <InfoPopover title="Total Annual Fees" onClose={() => setStatTopic(null)}>
          <p>
            Sum of the listed annual fee for every active card in the wallet,
            before any credits, sign-up bonuses, or category earn are netted
            out. This is what you'd pay your issuers each year.
          </p>
          <div>
            <p className="text-slate-300 font-medium mb-1">First-year fee</p>
            <p>
              Cards with a first-year fee waiver still appear at their full
              annual fee here. The waiver is reflected in the EAF
              calculation, where year-1 uses the waived fee and subsequent
              years use the recurring fee.
            </p>
          </div>
          <div>
            <p className="text-slate-300 font-medium mb-1">Future cards</p>
            <p>
              Cards in the <span className="text-slate-300">future</span> panel
              count once they become active inside the projection window.
              Cards in the <span className="text-slate-300">considering</span>{' '}
              panel are excluded from this total.
            </p>
          </div>
        </InfoPopover>
      )}

      {statTopic === 'methodology' && (
        <InfoPopover title="Calculation Methodology" onClose={() => setStatTopic(null)}>
          <div>
            <p className="text-slate-300 font-medium mb-1">Category allocation</p>
            <p>
              Each spend category is awarded to the card(s) with the highest
              {' '}<span className="font-mono text-[11px] text-slate-300">multiplier x CPP x earn_bonus_factor + secondary_bonus</span>.
              Tied cards split the category dollars evenly. The LP optimizer
              solves this per time segment when cards have date context.
            </p>
          </div>
          <div>
            <p className="text-slate-300 font-medium mb-1">Time segmentation</p>
            <p>
              When cards have open/close dates, the projection window is split
              into segments at every card activation, closure, SUB earn, and
              cap period boundary. Each segment solves its own allocation with
              only the cards active during that period.
            </p>
          </div>
          <div>
            <p className="text-slate-300 font-medium mb-1">Currency upgrades</p>
            <p>
              If a card's currency converts to a higher-value currency earned by
              another wallet card (e.g. UR Cash to Chase UR via Sapphire), the
              earn is converted at the upgrade rate and valued at the target CPP.
            </p>
          </div>
          <div>
            <p className="text-slate-300 font-medium mb-1">SUB tracking</p>
            <p>
              The SUB planner schedules spend across cards to hit sign-up bonus
              minimums before their deadlines. Cards needing extra spend get
              priority allocation during their SUB window. The opportunity cost
              of redirecting spend is tracked separately.
            </p>
          </div>
          <div>
            <p className="text-slate-300 font-medium mb-1">Bilt 2.0 housing</p>
            <p>
              Cards with the Bilt housing mechanic choose between tiered
              housing earn (0.5x-1.25x on rent/mortgage based on non-housing
              spend ratio) and Bilt Cash mode (three-tier bonus on non-housing
              from converting Bilt Cash via housing payments). The calculator
              picks whichever mode yields higher dollar value.
            </p>
          </div>
          <div>
            <p className="text-slate-300 font-medium mb-1">Housing processing fee</p>
            <p>
              Rent and mortgage payments via credit card typically incur a ~3%
              processing fee from the payment platform. Cards that waive this
              fee (Bilt) compete at full value on housing categories; other
              cards are penalized by the fee amount, which usually makes their
              1-1.5x earn net-negative.
            </p>
          </div>
          <div>
            <p className="text-slate-300 font-medium mb-1">Foreign spend</p>
            <p>
              When a wallet-level foreign spend percentage is set, eligible
              categories are split into domestic and foreign buckets. Cards
              without a foreign transaction fee and on Visa/Mastercard networks
              are preferred for the foreign portion.
            </p>
          </div>
          <div>
            <p className="text-slate-300 font-medium mb-1">EAF formula</p>
            <p className="px-2 py-1 bg-slate-800 rounded font-mono text-[11px] text-slate-300 leading-snug">
              (earn x cpp + sub + credits - fees) / years
            </p>
            <p className="mt-1">
              A negative EAF means the card returns more value than it costs.
              One-time benefits (SUB, first-year bonus) are amortised over the
              projection duration.
            </p>
          </div>
        </InfoPopover>
      )}

    </div>
  )
}
