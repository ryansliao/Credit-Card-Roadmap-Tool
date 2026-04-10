import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import type { CardResult, WalletResult } from '../../../../api/client'
import { walletCppApi, walletsApi } from '../../../../api/client'
import { formatCashRewardUnits, formatMoney, formatPoints } from '../../../../utils/format'
import { queryKeys } from '../../lib/queryKeys'
import { CurrencySettingsModal } from '../summary/CurrencySettingsModal'
import { SpendTabContent } from '../spend/SpendTabContent'
import { InfoIconButton, InfoPopover } from '../../../../components/InfoPopover'

type StatTopic = 'eaf' | 'income' | 'fees' | null

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

  const editingBalance = balances.find((b) => b.currency_id === editingCurrencyId) ?? null
  const editingCurrency = currencies.find((c) => c.id === editingCurrencyId) ?? null

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
                className={`p-2 rounded-l-md border border-r-0 transition-colors ${
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
        <h2 className="text-sm font-semibold text-slate-200">Wallet Summary</h2>
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
                      <InfoIconButton onClick={() => setStatTopic('eaf')} label="How Effective Annual Fee is calculated" size={11} />
                    </div>
                    {result ? (
                      <p className="text-xl font-bold text-indigo-100 mt-0.5">{formatMoney(totalEffectiveAF)}</p>
                    ) : (
                      <div className="h-7 mt-0.5 flex items-center justify-center">
                        <div className="h-4 w-16 bg-indigo-800/50 rounded animate-pulse" />
                      </div>
                    )}
                  </div>
                  <div className="bg-slate-800 border border-slate-700 rounded-xl p-3 text-center">
                    <div className="flex items-center justify-center gap-1">
                      <p className="text-[10px] text-slate-400 uppercase tracking-wider">Annual Point Income</p>
                      <InfoIconButton onClick={() => setStatTopic('income')} label="How Annual Point Income is calculated" size={11} />
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
                      <InfoIconButton onClick={() => setStatTopic('fees')} label="How Total Annual Fees is calculated" size={11} />
                    </div>
                    {result ? (
                      <p className="text-xl font-bold text-white mt-0.5">{formatMoney(totalAnnualFees)}</p>
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

                  return (
                    <li key={b.id} className="bg-slate-800/80 rounded-lg overflow-hidden">
                      {/* Currency header row */}
                      <div className="px-2.5 py-2">
                        <div className="flex items-center justify-between gap-2">
                          <span
                            className="text-sm font-semibold text-white truncate"
                            title={b.currency_name}
                          >
                            {b.currency_name}
                          </span>
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
                              onClick={() => setEditingCurrencyId(b.currency_id)}
                              style={{ marginLeft: '0.5rem' }}
                              className="p-1 rounded text-slate-500 hover:text-slate-200 hover:bg-slate-700 transition-colors"
                              aria-label="Edit currency"
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
                              >
                                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
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
                                <InfoIconButton
                                  onClick={() => setShowBiltCashInfo(true)}
                                  label="How Bilt Cash is calculated"
                                />
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

                      {/* Nested card rows */}
                      {cards.length > 0 && (
                        <div className="border-t border-slate-700/60">
                          {cards.map((card, idx) => {
                            const cardEffectiveAF = card.effective_annual_fee
                            const isLast = idx === cards.length - 1
                            const cardIsCash = (card.effective_reward_kind ?? 'points') === 'cash'
                            const annualPts = cardAnnualPointIncome(card, totalYears)
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
                                <div className="px-3 py-1.5 flex items-center gap-2">
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
                                    {card.secondary_currency_name && card.secondary_currency_net_earn > 0 && (
                                      <p className="text-xs text-indigo-400/70 mt-0.5">
                                        {formatPoints(Math.round(card.secondary_currency_net_earn / totalYears))} {card.secondary_currency_name}/Year
                                        {card.secondary_currency_value_dollars > 0 && (
                                          <span className="text-slate-500"> ≈ {formatMoney(card.secondary_currency_value_dollars / totalYears)}/Year</span>
                                        )}
                                        {card.accelerator_activations > 0 && (
                                          <span className="text-slate-500"> · {card.accelerator_activations}x Accelerator</span>
                                        )}
                                      </p>
                                    )}
                                  </div>
                                  <div className="flex items-center shrink-0">
                                    <span className="text-xs text-slate-500 tabular-nums">
                                      {annualPtsDisplay}{annualPtsUnit}
                                    </span>
                                    <span className="text-slate-600 mx-2">·</span>
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

      {editingCurrencyId != null && editingCurrency != null && (
        <CurrencySettingsModal
          walletId={walletId}
          currency={editingCurrency}
          balance={editingBalance}
          onClose={() => setEditingCurrencyId(null)}
          onCppChange={() => {
            onCppChange()
          }}
        />
      )}

      {showBiltCashInfo && (
        <InfoPopover title="How Bilt Cash is Calculated" onClose={() => setShowBiltCashInfo(false)} zIndex="z-50">
          <p>
            Bilt cards earn <span className="text-indigo-300">4% Bilt Cash</span> on all
            spend allocated to the card, on top of the regular Bilt Points multipliers.
          </p>
          <div>
            <p className="text-slate-300 font-medium mb-1">Conversion cap</p>
            <p>
              Bilt Cash can only be redeemed for value when paired with housing spend.
              The convertible amount is capped at:
            </p>
            <p className="mt-1 px-2 py-1 bg-slate-800 rounded font-mono text-[11px] text-slate-300">
              min(allocated_spend, 0.75 × housing_spend)
            </p>
            <p className="mt-1">
              Bilt Cash earned beyond this cap is valued at <span className="text-slate-300">$0</span>.
            </p>
          </div>
          <div>
            <p className="text-slate-300 font-medium mb-1">No housing spend?</p>
            <p>
              If your wallet has no <span className="text-slate-300">Rent</span> or
              {' '}<span className="text-slate-300">Mortgage</span> spend, Bilt Cash
              cannot convert and is excluded from allocation scoring entirely — so
              the calculator won't over-allocate spend to Bilt cards.
            </p>
          </div>
          <div>
            <p className="text-slate-300 font-medium mb-1">Example</p>
            <p>
              With <span className="text-slate-300">$24k</span> annual rent, the cap is
              {' '}<span className="text-slate-300">0.75 × $24k = $18k</span> of
              convertible non-housing spend. At 4%, that's
              {' '}<span className="text-slate-300">$720</span> of realizable Bilt Cash
              per year.
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

    </div>
  )
}
