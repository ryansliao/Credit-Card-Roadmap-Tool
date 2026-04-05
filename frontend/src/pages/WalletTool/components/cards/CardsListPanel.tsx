import type {
  RoadmapCardStatus,
  RoadmapResponse,
  UpdateWalletCardPayload,
  Wallet,
  WalletCard,
} from '../../../../api/client'
import { today } from '../../../../utils/format'

/** Newest opening / PC date first; cards with no date sort last. */
function compareWalletCardsByOpeningNewestFirst(a: WalletCard, b: WalletCard): number {
  const da = a.added_date?.trim() ?? ''
  const db = b.added_date?.trim() ?? ''
  if (!da && !db) return 0
  if (!da) return 1
  if (!db) return -1
  return db.localeCompare(da)
}

function SubRoadmapBadge({ rm }: { rm: RoadmapCardStatus | undefined }) {
  if (!rm || rm.sub_status === 'no_sub') return null
  if (rm.sub_status === 'earned') {
    return (
      <span className="text-xs px-1.5 py-0.5 rounded bg-emerald-900/50 text-emerald-300 border border-emerald-700/50">
        SUB Earned
      </span>
    )
  }
  if (rm.sub_status === 'pending') {
    return (
      <span className="text-xs px-1.5 py-0.5 rounded bg-orange-900/50 text-orange-300 border border-orange-700/50">
        SUB Pending
      </span>
    )
  }
  if (rm.sub_status === 'expired') {
    return (
      <span className="text-xs px-1.5 py-0.5 rounded bg-red-900/50 text-red-300 border border-red-700/50">
        SUB Missed
      </span>
    )
  }
  return null
}

interface Props {
  wallet: Wallet
  roadmap: RoadmapResponse | undefined
  closeCardId: number | null
  closeDateInput: string
  isUpdating: boolean
  isRemoving: boolean
  onSetCloseCard: (cardId: number | null) => void
  onSetCloseDateInput: (v: string) => void
  onUpdateCard: (cardId: number, payload: UpdateWalletCardPayload) => void
  onRemoveCard: (cardId: number) => void
  onEditCard: (wc: WalletCard) => void
  onAddCard: () => void
}

export function CardsListPanel({
  wallet,
  roadmap,
  closeCardId,
  closeDateInput,
  isUpdating,
  isRemoving,
  onSetCloseCard,
  onSetCloseDateInput,
  onUpdateCard,
  onRemoveCard,
  onEditCard,
  onAddCard,
}: Props) {
  const todayIso = today()
  const walletCards = wallet.wallet_cards ?? []
  const ownedCards = walletCards
    .filter((wc) => (wc.added_date?.trim() ?? '') <= todayIso)
    .sort(compareWalletCardsByOpeningNewestFirst)
  const prospectiveCards = walletCards
    .filter((wc) => (wc.added_date?.trim() ?? '') > todayIso)
    .sort(compareWalletCardsByOpeningNewestFirst)

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl p-4 min-w-0 min-h-0 h-full flex flex-col overflow-hidden">
      <div className="flex items-center justify-between mb-3 shrink-0">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-slate-200">Cards</h2>
          {roadmap && (
            <span
              className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                roadmap.five_twenty_four_eligible
                  ? 'bg-emerald-900/60 text-emerald-300 border border-emerald-700'
                  : 'bg-red-900/60 text-red-300 border border-red-700'
              }`}
              title={`${roadmap.five_twenty_four_count} personal cards opened in last 24 months`}
            >
              5/24: {roadmap.five_twenty_four_count}/5
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={onAddCard}
          className="p-1 rounded text-slate-500 hover:text-indigo-400 hover:bg-slate-800 transition-colors shrink-0"
          aria-label="Add card"
          title="Add card"
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
        </button>
      </div>
      <div className="min-h-0 overflow-y-auto flex-1 flex flex-col gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1.5">Future</p>
          <ul className="space-y-2">
            {prospectiveCards.length === 0 && (
              <li className="text-slate-600 text-xs py-2 text-center">No Cards Added</li>
            )}
            {prospectiveCards.map((wc) => {
          const rm: RoadmapCardStatus | undefined = roadmap?.cards.find(
            (c) => c.wallet_card_id === wc.id
          )
          const isClosed = !!wc.closed_date
          return (
            <li
              key={wc.id}
              className={`bg-slate-800 rounded-lg px-3 py-2 ${isClosed ? 'opacity-50' : ''}`}
            >
              <div className="flex justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span
                      className={`inline-block w-2 h-2 rounded-full shrink-0 ${isClosed ? 'bg-slate-500' : 'bg-emerald-400'}`}
                      title={isClosed ? `Closed ${wc.closed_date}` : 'Active'}
                    />
                    <p className={`text-sm font-medium ${isClosed ? 'text-slate-400 line-through' : 'text-white'}`}>
                      {wc.card_name ?? `Card #${wc.card_id}`}
                    </p>
                    <SubRoadmapBadge rm={rm} />
                    {wc.acquisition_type === 'product_change' && (
                      <span className="text-[10px] font-medium bg-violet-900/60 text-violet-300 border border-violet-700/50 rounded px-1.5 py-0.5">
                        PC
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {wc.acquisition_type === 'product_change' ? 'PC date' : 'Opened'} {wc.added_date}
                  </p>
                  {wc.sub_projected_earn_date && (
                    <p className="text-xs text-slate-500 mt-0.5">
                      SUB projected earned {wc.sub_projected_earn_date}
                    </p>
                  )}
                </div>
                <div className="flex flex-col items-end justify-between gap-1 shrink-0 self-stretch">
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      className="p-1 rounded text-slate-500 hover:text-slate-200 hover:bg-slate-700"
                      aria-label="Edit card"
                      title="Edit"
                      onClick={() => onEditCard(wc)}
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
                    <button
                      type="button"
                      className="p-1 rounded text-slate-600 hover:text-red-400 hover:bg-red-950/40 disabled:opacity-50"
                      aria-label="Remove card from wallet"
                      title="Remove"
                      onClick={() => onRemoveCard(wc.card_id)}
                      disabled={isRemoving}
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
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                      </svg>
                    </button>
                  </div>
                  <div className="flex justify-end items-center gap-2 flex-wrap max-w-[min(100%,18rem)]">
                    {!isClosed && (
                      <>
                        {closeCardId === wc.card_id ? (
                          <span className="flex items-center gap-1 flex-wrap justify-end">
                            <input
                              type="date"
                              value={closeDateInput}
                              onChange={(e) => onSetCloseDateInput(e.target.value)}
                              className="bg-slate-700 border border-slate-500 text-white text-xs rounded px-1.5 py-0.5"
                            />
                            <button
                              className="text-xs text-amber-400 hover:text-amber-300"
                              disabled={isUpdating}
                              onClick={() =>
                                onUpdateCard(wc.card_id, { closed_date: closeDateInput || today() })
                              }
                            >
                              Save
                            </button>
                            <button
                              className="text-xs text-slate-500 hover:text-slate-300"
                              onClick={() => { onSetCloseCard(null); onSetCloseDateInput('') }}
                            >
                              Cancel
                            </button>
                          </span>
                        ) : (
                          <button
                            className="text-xs text-slate-500 hover:text-amber-400"
                            onClick={() => {
                              onSetCloseCard(wc.card_id)
                              onSetCloseDateInput(today())
                            }}
                          >
                            Close card
                          </button>
                        )}
                      </>
                    )}
                    {isClosed && (
                      <button
                        className="text-xs text-slate-500 hover:text-emerald-400"
                        disabled={isUpdating}
                        onClick={() => onUpdateCard(wc.card_id, { closed_date: null })}
                      >
                        Reopen
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </li>
          )
        })}
          </ul>
        </div>
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1.5">Owned</p>
          <ul className="space-y-2">
            {ownedCards.length === 0 && (
              <li className="text-slate-600 text-xs py-2 text-center">No Cards Added</li>
            )}
            {ownedCards.map((wc) => {
                const rm: RoadmapCardStatus | undefined = roadmap?.cards.find(
                  (c) => c.wallet_card_id === wc.id
                )
                const isClosed = !!wc.closed_date
                return (
                  <li
                    key={wc.id}
                    className={`bg-slate-800 rounded-lg px-3 py-2 ${isClosed ? 'opacity-50' : ''}`}
                  >
                    <div className="flex justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span
                            className={`inline-block w-2 h-2 rounded-full shrink-0 ${isClosed ? 'bg-slate-500' : 'bg-emerald-400'}`}
                            title={isClosed ? `Closed ${wc.closed_date}` : 'Active'}
                          />
                          <p className={`text-sm font-medium ${isClosed ? 'text-slate-400 line-through' : 'text-white'}`}>
                            {wc.card_name ?? `Card #${wc.card_id}`}
                          </p>
                          <SubRoadmapBadge rm={rm} />
                          {wc.acquisition_type === 'product_change' && (
                            <span className="text-[10px] font-medium bg-violet-900/60 text-violet-300 border border-violet-700/50 rounded px-1.5 py-0.5">
                              PC
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-slate-400 mt-0.5">
                          {wc.acquisition_type === 'product_change' ? 'PC date' : 'Opened'} {wc.added_date}
                        </p>
                        {wc.sub_projected_earn_date && !wc.sub_earned_date && (
                          <p className="text-xs text-slate-500 mt-0.5">
                            SUB projected earned {wc.sub_projected_earn_date}
                          </p>
                        )}
                        {wc.sub != null && (
                          <div className="flex items-center gap-1.5 mt-1.5">
                            <span className="text-xs text-slate-400">SUB earned</span>
                            <button
                              type="button"
                              role="switch"
                              aria-checked={!!wc.sub_earned_date}
                              disabled={isUpdating}
                              className={`relative inline-flex h-4 w-7 items-center rounded-full transition-colors cursor-pointer disabled:opacity-50 ${
                                wc.sub_earned_date ? 'bg-emerald-600' : 'bg-slate-600'
                              }`}
                              onClick={() =>
                                onUpdateCard(wc.card_id, {
                                  sub_earned_date: wc.sub_earned_date ? null : today(),
                                })
                              }
                            >
                              <span
                                className={`inline-block h-3 w-3 rounded-full bg-white transition-transform ${
                                  wc.sub_earned_date ? 'translate-x-3.5' : 'translate-x-0.5'
                                }`}
                              />
                            </button>
                          </div>
                        )}
                      </div>
                      <div className="flex flex-col items-end justify-between gap-1 shrink-0 self-stretch">
                        <div className="flex items-center gap-1">
                          <button
                            type="button"
                            className="p-1 rounded text-slate-500 hover:text-slate-200 hover:bg-slate-700"
                            aria-label="Edit card"
                            title="Edit"
                            onClick={() => onEditCard(wc)}
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
                          <button
                            type="button"
                            className="p-1 rounded text-slate-600 hover:text-red-400 hover:bg-red-950/40 disabled:opacity-50"
                            aria-label="Remove card from wallet"
                            title="Remove"
                            onClick={() => onRemoveCard(wc.card_id)}
                            disabled={isRemoving}
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
                              <polyline points="3 6 5 6 21 6" />
                              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                            </svg>
                          </button>
                        </div>
                        <div className="flex justify-end items-center gap-2 flex-wrap max-w-[min(100%,18rem)]">
                          {!isClosed && (
                            <>
                              {closeCardId === wc.card_id ? (
                                <span className="flex items-center gap-1 flex-wrap justify-end">
                                  <input
                                    type="date"
                                    value={closeDateInput}
                                    onChange={(e) => onSetCloseDateInput(e.target.value)}
                                    className="bg-slate-700 border border-slate-500 text-white text-xs rounded px-1.5 py-0.5"
                                  />
                                  <button
                                    className="text-xs text-amber-400 hover:text-amber-300"
                                    disabled={isUpdating}
                                    onClick={() =>
                                      onUpdateCard(wc.card_id, { closed_date: closeDateInput || today() })
                                    }
                                  >
                                    Save
                                  </button>
                                  <button
                                    className="text-xs text-slate-500 hover:text-slate-300"
                                    onClick={() => { onSetCloseCard(null); onSetCloseDateInput('') }}
                                  >
                                    Cancel
                                  </button>
                                </span>
                              ) : (
                                <button
                                  className="text-xs text-slate-500 hover:text-amber-400"
                                  onClick={() => {
                                    onSetCloseCard(wc.card_id)
                                    onSetCloseDateInput(today())
                                  }}
                                >
                                  Close card
                                </button>
                              )}
                            </>
                          )}
                          {isClosed && (
                            <button
                              className="text-xs text-slate-500 hover:text-emerald-400"
                              disabled={isUpdating}
                              onClick={() => onUpdateCard(wc.card_id, { closed_date: null })}
                            >
                              Reopen
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  </li>
                )
            })}
          </ul>
        </div>
      </div>
    </div>
  )
}
