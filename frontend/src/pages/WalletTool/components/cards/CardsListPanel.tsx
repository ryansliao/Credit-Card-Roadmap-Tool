import { useState } from 'react'
import type {
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

function SubBadge({ wc }: { wc: WalletCard }) {
  if (!wc.sub) return null
  if (wc.sub_projected_earn_date) {
    return (
      <span className="text-xs px-1.5 py-0.5 rounded bg-emerald-900/50 text-emerald-300 border border-emerald-700/50">
        SUB Earned
      </span>
    )
  }
  return (
    <span className="text-xs px-1.5 py-0.5 rounded bg-red-900/50 text-red-300 border border-red-700/50">
      SUB Not Earned
    </span>
  )
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

function CardItem({
  wc,
  closeCardId,
  closeDateInput,
  isUpdating,
  isRemoving,
  isInWallet,
  onSetCloseCard,
  onSetCloseDateInput,
  onUpdateCard,
  onRemoveCard,
  onEditCard,
  draggable,
}: {
  wc: WalletCard
  closeCardId: number | null
  closeDateInput: string
  isUpdating: boolean
  isRemoving: boolean
  isInWallet: boolean
  onSetCloseCard: (cardId: number | null) => void
  onSetCloseDateInput: (v: string) => void
  onUpdateCard: (cardId: number, payload: UpdateWalletCardPayload) => void
  onRemoveCard: (cardId: number) => void
  onEditCard: (wc: WalletCard) => void
  draggable: boolean
}) {
  const isClosed = !!wc.closed_date

  return (
    <li
      draggable={draggable}
      onDragStart={(e) => {
        e.dataTransfer.setData('text/plain', String(wc.card_id))
        e.dataTransfer.effectAllowed = 'move'
      }}
      className={`bg-slate-800 rounded-lg px-3 py-2 ${isClosed ? 'opacity-50' : ''} ${draggable ? 'cursor-grab active:cursor-grabbing' : ''}`}
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
            {isInWallet && <SubBadge wc={wc} />}
            {wc.acquisition_type === 'product_change' && (
              <span className="text-[10px] font-medium bg-violet-900/60 text-violet-300 border border-violet-700/50 rounded px-1.5 py-0.5">
                PC
              </span>
            )}
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            {wc.acquisition_type === 'product_change' ? 'PC Date:' : 'Opening Date: '} {wc.added_date}
          </p>
          {isInWallet && wc.sub_projected_earn_date && (
            <p className="text-xs text-slate-500 mt-0.5">
              SUB Earned: {wc.sub_projected_earn_date}
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
  const walletCards = wallet.wallet_cards ?? []
  const onDeckCards = walletCards
    .filter((wc) => wc.panel === 'on_deck' && !wc.closed_date)
    .sort(compareWalletCardsByOpeningNewestFirst)
  const inWalletCards = walletCards
    .filter((wc) => wc.panel === 'in_wallet' && !wc.closed_date)
    .sort(compareWalletCardsByOpeningNewestFirst)
  const closedCards = walletCards
    .filter((wc) => !!wc.closed_date)
    .sort(compareWalletCardsByOpeningNewestFirst)

  const [dragOverPanel, setDragOverPanel] = useState<'on_deck' | 'in_wallet' | null>(null)

  function handleDrop(targetPanel: 'on_deck' | 'in_wallet', e: React.DragEvent) {
    e.preventDefault()
    setDragOverPanel(null)
    const cardId = Number(e.dataTransfer.getData('text/plain'))
    if (!cardId) return
    const wc = walletCards.find((c) => c.card_id === cardId)
    if (!wc || wc.panel === targetPanel) return
    onUpdateCard(cardId, { panel: targetPanel })
  }

  function handleDragOver(targetPanel: 'on_deck' | 'in_wallet', e: React.DragEvent) {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    if (dragOverPanel !== targetPanel) setDragOverPanel(targetPanel)
  }

  function handleDragLeave(targetPanel: 'on_deck' | 'in_wallet', e: React.DragEvent) {
    if (e.currentTarget.contains(e.relatedTarget as Node)) return
    if (dragOverPanel === targetPanel) setDragOverPanel(null)
  }

  const sharedCardProps = {
    closeCardId,
    closeDateInput,
    isUpdating,
    isRemoving,
    onSetCloseCard,
    onSetCloseDateInput,
    onUpdateCard,
    onRemoveCard,
    onEditCard,
  }

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
      <div className="min-h-0 overflow-y-auto flex-1 flex flex-col gap-4">
        {/* On Deck panel */}
        <div
          className={`rounded-lg border transition-colors ${
            dragOverPanel === 'on_deck'
              ? 'border-indigo-500 bg-indigo-950/20'
              : 'border-slate-700/50'
          }`}
          onDragOver={(e) => handleDragOver('on_deck', e)}
          onDragLeave={(e) => handleDragLeave('on_deck', e)}
          onDrop={(e) => handleDrop('on_deck', e)}
        >
          <div className="px-3 pt-2 pb-1">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">On Deck</p>
          </div>
          <ul className="space-y-2 px-2 pb-2">
            {onDeckCards.length === 0 && (
              <li className="text-slate-600 text-xs py-2 text-center">No Cards Added</li>
            )}
            {onDeckCards.map((wc) => (
              <CardItem
                key={wc.id}
                wc={wc}
                isInWallet={false}
                draggable
                {...sharedCardProps}
              />
            ))}
          </ul>
        </div>

        {/* In Wallet panel */}
        <div
          className={`rounded-lg border transition-colors ${
            dragOverPanel === 'in_wallet'
              ? 'border-emerald-500 bg-emerald-950/20'
              : 'border-slate-700/50'
          }`}
          onDragOver={(e) => handleDragOver('in_wallet', e)}
          onDragLeave={(e) => handleDragLeave('in_wallet', e)}
          onDrop={(e) => handleDrop('in_wallet', e)}
        >
          <div className="px-3 pt-2 pb-1">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">In Wallet</p>
          </div>
          <ul className="space-y-2 px-2 pb-2">
            {inWalletCards.length === 0 && (
              <li className="text-slate-600 text-xs py-2 text-center">No Cards Added</li>
            )}
            {inWalletCards.map((wc) => (
              <CardItem
                key={wc.id}
                wc={wc}
                isInWallet
                draggable
                {...sharedCardProps}
              />
            ))}
          </ul>
        </div>

        {/* Closed Cards panel */}
        {closedCards.length > 0 && (
          <div className="rounded-lg border border-slate-700/50">
            <div className="px-3 pt-2 pb-1">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Closed Cards</p>
            </div>
            <ul className="space-y-2 px-2 pb-2">
              {closedCards.map((wc) => (
                <CardItem
                  key={wc.id}
                  wc={wc}
                  isInWallet={wc.panel === 'in_wallet'}
                  draggable={false}
                  {...sharedCardProps}
                />
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}
