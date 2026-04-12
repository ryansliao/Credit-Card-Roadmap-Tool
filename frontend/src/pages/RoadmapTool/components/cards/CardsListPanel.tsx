import { useState } from 'react'
import type {
  RoadmapResponse,
  UpdateWalletCardPayload,
  Wallet,
  WalletCard,
  WalletCardPanel,
} from '../../../../api/client'
import { today } from '../../../../utils/format'

function CardPhoto({ slug, name }: { slug: string | null; name: string }) {
  const [failed, setFailed] = useState(false)
  if (!slug || failed) {
    return (
      <div className="w-full h-full bg-gradient-to-br from-slate-700 to-slate-800 flex items-center justify-center">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-slate-500">
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

const PANEL_LABELS: Record<WalletCardPanel, string> = {
  in_wallet: 'In Wallet',
  future_cards: 'Future Cards',
  considering: 'Considering',
}

const PANEL_DRAG_CLASSES: Record<WalletCardPanel, string> = {
  in_wallet: 'border-emerald-500 bg-emerald-950/20',
  future_cards: 'border-sky-500 bg-sky-950/20',
  considering: 'border-indigo-500 bg-indigo-950/20',
}

const PANEL_DOT_CLASSES: Record<WalletCardPanel, string> = {
  in_wallet: 'bg-emerald-400',
  future_cards: 'bg-sky-400',
  considering: 'bg-amber-400',
}

/** Newest opening / PC date first; cards with no date sort last. */
function compareWalletCardsByOpeningNewestFirst(a: WalletCard, b: WalletCard): number {
  const da = a.added_date?.trim() ?? ''
  const db = b.added_date?.trim() ?? ''
  if (!da && !db) return 0
  if (!da) return 1
  if (!db) return -1
  return db.localeCompare(da)
}

interface Props {
  wallet: Wallet
  roadmap: RoadmapResponse | undefined
  /** When true, the In Wallet panel is read-only (no edit/remove/drag/close).
   *  Future Cards and Considering remain fully interactive. */
  inWalletLocked?: boolean
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
  panel,
  onSetCloseCard,
  onSetCloseDateInput,
  onUpdateCard,
  onRemoveCard,
  onEditCard,
  draggable,
  locked,
}: {
  wc: WalletCard
  closeCardId: number | null
  closeDateInput: string
  isUpdating: boolean
  isRemoving: boolean
  panel: WalletCardPanel
  onSetCloseCard: (cardId: number | null) => void
  onSetCloseDateInput: (v: string) => void
  onUpdateCard: (cardId: number, payload: UpdateWalletCardPayload) => void
  onRemoveCard: (cardId: number) => void
  onEditCard: (wc: WalletCard) => void
  draggable: boolean
  locked?: boolean
}) {
  const isClosed = !!wc.closed_date
  const isFuture = panel === 'future_cards'

  return (
    <li
      draggable={draggable}
      onDragStart={(e) => {
        e.dataTransfer.setData('text/plain', String(wc.card_id))
        e.dataTransfer.effectAllowed = 'move'
      }}
      className={`bg-slate-800 rounded-lg px-3 py-2 ${isClosed ? 'opacity-50' : ''} ${draggable ? 'cursor-grab active:cursor-grabbing' : ''}`}
    >
      <div className="flex items-center justify-between gap-3">
        {/* Card photo */}
        <div className="w-[72px] h-11 shrink-0 rounded overflow-hidden bg-slate-700/50">
          <CardPhoto slug={wc.photo_slug} name={wc.card_name ?? `Card #${wc.card_id}`} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className={`text-sm font-medium ${isClosed ? 'text-slate-400 line-through' : 'text-white'}`}>
              {wc.card_name ?? `Card #${wc.card_id}`}
            </p>
            <span
              className={`inline-block w-2 h-2 rounded-full shrink-0 ${
                isClosed ? 'bg-red-500' : PANEL_DOT_CLASSES[panel]
              }`}
              title={isClosed ? `Closed ${wc.closed_date}` : PANEL_LABELS[panel]}
            />
            {wc.acquisition_type === 'product_change' && (
              <span className="text-[10px] font-medium bg-violet-900/60 text-violet-300 border border-violet-700/50 rounded px-1.5 py-0.5">
                Product Change
              </span>
            )}
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            {wc.acquisition_type === 'product_change' ? 'PC Date:' : 'Opening Date: '} {wc.added_date}
          </p>
          {isClosed && wc.closed_date && (
            <p className="text-xs text-slate-500 mt-0.5">Closed Date: {wc.closed_date}</p>
          )}
          {isFuture && wc.sub_projected_earn_date && (
            <p className="text-xs text-slate-500 mt-0.5">
              SUB Projected: {wc.sub_projected_earn_date}
            </p>
          )}
        </div>
        {!locked && (
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
        )}
      </div>
    </li>
  )
}

export function CardsListPanel({
  wallet,
  roadmap,
  inWalletLocked,
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
  const inWalletCards = walletCards
    .filter((wc) => wc.panel === 'in_wallet')
    .sort(compareWalletCardsByOpeningNewestFirst)
  const futureCards = walletCards
    .filter((wc) => wc.panel === 'future_cards')
    .sort(compareWalletCardsByOpeningNewestFirst)
  const consideringCards = walletCards
    .filter((wc) => wc.panel === 'considering')
    .sort(compareWalletCardsByOpeningNewestFirst)

  const [dragOverPanel, setDragOverPanel] = useState<WalletCardPanel | null>(null)

  function handleDrop(targetPanel: WalletCardPanel, e: React.DragEvent) {
    e.preventDefault()
    setDragOverPanel(null)
    if (inWalletLocked && targetPanel === 'in_wallet') return
    const cardId = Number(e.dataTransfer.getData('text/plain'))
    if (!cardId) return
    const wc = walletCards.find((c) => c.card_id === cardId)
    if (!wc || wc.panel === targetPanel) return
    onUpdateCard(cardId, { panel: targetPanel })
  }

  function handleDragOver(targetPanel: WalletCardPanel, e: React.DragEvent) {
    if (inWalletLocked && targetPanel === 'in_wallet') return
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    if (dragOverPanel !== targetPanel) setDragOverPanel(targetPanel)
  }

  function handleDragLeave(targetPanel: WalletCardPanel, e: React.DragEvent) {
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
      {/* h-7 matches the Wallet Summary header so the In Wallet panel top
          lines up with the top of the summary statistics row. */}
      <div className="h-7 flex items-center justify-between mb-3 shrink-0">
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
        {(
          [
            ['considering', consideringCards],
            ['future_cards', futureCards],
            ['in_wallet', inWalletCards],
          ] as const
        ).map(([panel, cards]) => {
          const isLocked = inWalletLocked && panel === 'in_wallet'
          return (
            <div
              key={panel}
              className={`rounded-lg border transition-colors ${
                dragOverPanel === panel ? PANEL_DRAG_CLASSES[panel] : 'border-slate-700/50'
              }`}
              onDragOver={(e) => handleDragOver(panel, e)}
              onDragLeave={(e) => handleDragLeave(panel, e)}
              onDrop={(e) => handleDrop(panel, e)}
            >
              <div className="px-3 pt-2 pb-1">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  {PANEL_LABELS[panel]}
                  {isLocked && (
                    <span className="ml-1.5 text-slate-600" title="Managed in My Wallets">
                      <svg className="inline w-3 h-3 -mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                        <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                      </svg>
                    </span>
                  )}
                </p>
              </div>
              <ul className="space-y-2 px-2 pb-2">
                {cards.length === 0 && (
                  <li className="text-slate-600 text-xs py-2 text-center">No Cards Added</li>
                )}
                {cards.map((wc) => (
                  <CardItem
                    key={wc.id}
                    wc={wc}
                    panel={panel}
                    draggable={!isLocked}
                    locked={isLocked}
                    {...sharedCardProps}
                  />
                ))}
              </ul>
            </div>
          )
        })}
      </div>
    </div>
  )
}
