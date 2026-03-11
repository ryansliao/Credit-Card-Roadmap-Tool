import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import {
  cardsApi,
  spendApi,
  walletsApi,
  type AddCardToWalletPayload,
  type WalletResultResponse,
} from '../api/client'
import SpendTable from '../components/SpendTable'
import WalletSummary from '../components/WalletSummary'

const DEFAULT_USER_ID = 1

// ─── Create wallet modal ─────────────────────────────────────────────────────

function CreateWalletModal({
  onClose,
  onCreate,
  isLoading,
}: {
  onClose: () => void
  onCreate: (name: string, description: string) => void
  isLoading: boolean
}) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-slate-800 border border-slate-600 rounded-xl p-6 w-96 shadow-xl">
        <h2 className="text-lg font-semibold text-white mb-4">New Wallet</h2>
        <div className="space-y-3">
          <div>
            <label className="text-xs text-slate-400 mb-1 block">Name *</label>
            <input
              autoFocus
              className="w-full bg-slate-700 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg outline-none focus:border-indigo-500"
              placeholder="e.g. Main wallet"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div>
            <label className="text-xs text-slate-400 mb-1 block">Description</label>
            <input
              className="w-full bg-slate-700 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg outline-none focus:border-indigo-500"
              placeholder="Optional"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
        </div>
        <div className="flex gap-2 mt-5">
          <button
            className="flex-1 bg-slate-700 hover:bg-slate-600 text-white text-sm py-2 rounded-lg"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            disabled={!name.trim() || isLoading}
            className="flex-1 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm py-2 rounded-lg"
            onClick={() => onCreate(name.trim(), description.trim())}
          >
            {isLoading ? 'Creating…' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Add card to wallet modal ────────────────────────────────────────────────

function AddCardModal({
  onClose,
  onAdd,
  isLoading,
}: {
  onClose: () => void
  onAdd: (payload: AddCardToWalletPayload) => void
  isLoading: boolean
}) {
  const { data: cards } = useQuery({ queryKey: ['cards'], queryFn: cardsApi.list })
  const [cardId, setCardId] = useState<number | ''>('')
  const [addedDate, setAddedDate] = useState(
    () => new Date().toISOString().slice(0, 10)
  )
  const [subPoints, setSubPoints] = useState<string>('')
  const [subMinSpend, setSubMinSpend] = useState<string>('')
  const [subMonths, setSubMonths] = useState<string>('')

  // When a card is selected, fill SUB fields with that card's default values
  useEffect(() => {
    if (!cardId || !cards) return
    const card = cards.find((c) => c.id === cardId)
    if (!card) return
    setSubPoints(card.sub_points != null ? String(card.sub_points) : '')
    setSubMinSpend(card.sub_min_spend != null ? String(card.sub_min_spend) : '')
    setSubMonths(card.sub_months != null ? String(card.sub_months) : '')
  }, [cardId, cards])

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-slate-800 border border-slate-600 rounded-xl p-6 w-96 shadow-xl max-h-[90vh] overflow-y-auto">
        <h2 className="text-lg font-semibold text-white mb-4">Add Card to Wallet</h2>
        <div className="space-y-3">
          <div>
            <label className="text-xs text-slate-400 mb-1 block">Card *</label>
            <select
              className="w-full bg-slate-700 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg outline-none focus:border-indigo-500"
              value={cardId}
              onChange={(e) => setCardId(e.target.value ? Number(e.target.value) : '')}
            >
              <option value="">Select a card…</option>
              {cards?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-slate-400 mb-1 block">Date added *</label>
            <input
              type="date"
              className="w-full bg-slate-700 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg outline-none focus:border-indigo-500"
              value={addedDate}
              onChange={(e) => setAddedDate(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-slate-400 mb-1 block">SUB points override (pts)</label>
              <input
                type="number"
                min={0}
                className="w-full bg-slate-700 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg outline-none focus:border-indigo-500"
                placeholder="Use card default"
                value={subPoints}
                onChange={(e) => setSubPoints(e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Min spend override ($)</label>
              <input
                type="number"
                min={0}
                className="w-full bg-slate-700 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg outline-none focus:border-indigo-500"
                placeholder="Use card default"
                value={subMinSpend}
                onChange={(e) => setSubMinSpend(e.target.value)}
              />
            </div>
          </div>
          <div>
            <label className="text-xs text-slate-400 mb-1 block">Months to achieve (mo)</label>
            <input
              type="number"
              min={0}
              className="w-full bg-slate-700 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg outline-none focus:border-indigo-500"
              placeholder="Use card default"
              value={subMonths}
              onChange={(e) => setSubMonths(e.target.value)}
            />
          </div>
        </div>
        <div className="flex gap-2 mt-5">
          <button
            className="flex-1 bg-slate-700 hover:bg-slate-600 text-white text-sm py-2 rounded-lg"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            disabled={!cardId || isLoading}
            className="flex-1 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm py-2 rounded-lg"
            onClick={() =>
              onAdd({
                card_id: cardId as number,
                added_date: addedDate,
                sub_points: subPoints ? Number(subPoints) : undefined,
                sub_min_spend: subMinSpend ? Number(subMinSpend) : undefined,
                sub_months: subMonths ? Number(subMonths) : undefined,
              })
            }
          >
            {isLoading ? 'Adding…' : 'Add Card'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Main page ───────────────────────────────────────────────────────────────

export default function WalletTool() {
  const queryClient = useQueryClient()
  const [selectedWalletId, setSelectedWalletId] = useState<number | null>(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showAddCardModal, setShowAddCardModal] = useState(false)
  const [projectionYears, setProjectionYears] = useState(2)
  const [projectionMonths, setProjectionMonths] = useState(0)
  const [referenceDate, setReferenceDate] = useState('')
  const [spendOverrides, setSpendOverrides] = useState<Record<string, number>>({})
  const [result, setResult] = useState<WalletResultResponse | null>(null)

  const { data: wallets, isLoading: walletsLoading } = useQuery({
    queryKey: ['wallets', DEFAULT_USER_ID],
    queryFn: () => walletsApi.list(DEFAULT_USER_ID),
  })

  const { data: spend, isLoading: spendLoading } = useQuery({
    queryKey: ['spend'],
    queryFn: spendApi.list,
  })

  const createWalletMutation = useMutation({
    mutationFn: (payload: { name: string; description: string }) =>
      walletsApi.create({
        user_id: DEFAULT_USER_ID,
        name: payload.name,
        description: payload.description || null,
      }),
    onSuccess: (wallet) => {
      queryClient.invalidateQueries({ queryKey: ['wallets'] })
      setSelectedWalletId(wallet.id)
      setShowCreateModal(false)
    },
  })

  const addCardMutation = useMutation({
    mutationFn: ({ walletId, payload }: { walletId: number; payload: AddCardToWalletPayload }) =>
      walletsApi.addCard(walletId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wallets'] })
      setShowAddCardModal(false)
    },
  })

  const removeCardMutation = useMutation({
    mutationFn: ({ walletId, cardId }: { walletId: number; cardId: number }) =>
      walletsApi.removeCard(walletId, cardId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wallets'] })
    },
  })

  const resultsMutation = useMutation({
    mutationFn: (walletId: number) =>
      walletsApi.results(walletId, {
        reference_date: referenceDate || undefined,
        projection_years: projectionYears,
        projection_months: projectionMonths,
        spend_overrides: Object.keys(spendOverrides).length > 0 ? spendOverrides : undefined,
      }),
    onSuccess: setResult,
  })

  const selectedWallet = wallets?.find((w) => w.id === selectedWalletId)

  function handleSpendChange(category: string, value: number) {
    setSpendOverrides((prev) => ({ ...prev, [category]: value }))
  }

  function calculate() {
    if (selectedWalletId != null) resultsMutation.mutate(selectedWalletId)
  }

  if (walletsLoading) {
    return (
      <div className="max-w-screen-xl mx-auto">
        <div className="text-center text-slate-400 py-20">Loading wallets…</div>
      </div>
    )
  }

  return (
    <div className="max-w-screen-xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Wallet Tool</h1>
        <p className="text-slate-400 text-sm mt-1">
          Manage wallets, add cards with sign-up bonus and min spend, and calculate EV and
          opportunity cost over your chosen time frame.
        </p>
      </div>

      <div className="flex gap-6">
        {/* Left: Wallet list */}
        <div className="w-56 shrink-0 bg-slate-900 border border-slate-700 rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-slate-200">Wallets</h2>
            <button
              className="text-indigo-400 hover:text-indigo-300 text-sm"
              onClick={() => setShowCreateModal(true)}
            >
              + New
            </button>
          </div>
          <ul className="space-y-1">
            {wallets?.map((w) => (
              <li key={w.id}>
                <button
                  className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                    selectedWalletId === w.id
                      ? 'bg-indigo-600 text-white'
                      : 'text-slate-300 hover:bg-slate-800'
                  }`}
                  onClick={() => {
                    setSelectedWalletId(w.id)
                    setResult(null)
                  }}
                >
                  {w.name}
                </button>
              </li>
            ))}
            {wallets?.length === 0 && (
              <li className="text-slate-500 text-sm py-2">No wallets yet. Create one.</li>
            )}
          </ul>
        </div>

        {/* Main: Selected wallet detail or empty state */}
        <div className="flex-1 min-w-0">
          {!selectedWallet ? (
            <div className="bg-slate-900 border border-slate-700 rounded-xl p-8 text-center text-slate-500">
              Select a wallet or create one to get started.
            </div>
          ) : (
            <>
              {/* Time frame & Calculate */}
              <div className="mb-4 flex flex-wrap items-center gap-4">
                <div className="flex items-center gap-2">
                  <label className="text-sm text-slate-400">Projection</label>
                  <select
                    className="bg-slate-800 border border-slate-600 text-white text-sm rounded-lg px-3 py-1.5"
                    value={projectionYears}
                    onChange={(e) => setProjectionYears(Number(e.target.value))}
                  >
                    {[1, 2, 3, 4, 5].map((n) => (
                      <option key={n} value={n}>
                        {n} yr
                      </option>
                    ))}
                  </select>
                  <select
                    className="bg-slate-800 border border-slate-600 text-white text-sm rounded-lg px-3 py-1.5"
                    value={projectionMonths}
                    onChange={(e) => setProjectionMonths(Number(e.target.value))}
                  >
                    {Array.from({ length: 12 }, (_, i) => (
                      <option key={i} value={i}>
                        {i} mo
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex items-center gap-2">
                  <label className="text-sm text-slate-400">As of</label>
                  <input
                    type="date"
                    className="bg-slate-800 border border-slate-600 text-white text-sm rounded-lg px-3 py-1.5"
                    value={referenceDate}
                    onChange={(e) => setReferenceDate(e.target.value)}
                  />
                </div>
                <button
                  onClick={calculate}
                  disabled={
                    resultsMutation.isPending || (selectedWallet?.wallet_cards?.length ?? 0) === 0
                  }
                  className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium text-sm px-5 py-2 rounded-lg transition-colors"
                >
                  {resultsMutation.isPending ? 'Calculating…' : 'Calculate'}
                </button>
              </div>

              <div className="grid grid-cols-[280px_1fr_320px] gap-6">
                {/* Spend */}
                <div className="bg-slate-900 border border-slate-700 rounded-xl p-4">
                  <h2 className="text-sm font-semibold text-slate-200 mb-3">Annual Spend</h2>
                  <p className="text-xs text-slate-500 mb-3">Click a value to edit.</p>
                  {spend && (
                    <SpendTable
                      categories={spend}
                      overrides={spendOverrides}
                      onChange={handleSpendChange}
                    />
                  )}
                  {spendLoading && (
                    <div className="text-slate-500 text-sm">Loading…</div>
                  )}
                </div>

                {/* Cards in wallet */}
                <div className="bg-slate-900 border border-slate-700 rounded-xl p-4">
                  <div className="flex items-center justify-between mb-3">
                    <h2 className="text-sm font-semibold text-slate-200">Cards in wallet</h2>
                    <button
                      className="text-indigo-400 hover:text-indigo-300 text-sm"
                      onClick={() => setShowAddCardModal(true)}
                    >
                      + Add card
                    </button>
                  </div>
                  <ul className="space-y-2">
                    {selectedWallet.wallet_cards?.map((wc) => (
                      <li
                        key={wc.id}
                        className="flex items-center justify-between bg-slate-800 rounded-lg px-3 py-2"
                      >
                        <div>
                          <p className="text-sm font-medium text-white">
                            {wc.card_name ?? `Card #${wc.card_id}`}
                          </p>
                          <p className="text-xs text-slate-400">
                            Added {wc.added_date}
                            {(wc.sub_points != null || wc.sub_min_spend != null) && (
                              <span className="ml-1">
                                · SUB:{' '}
                                {wc.sub_points != null ? `${(wc.sub_points / 1000).toFixed(0)}k` : '—'} pts
                                {wc.sub_min_spend != null && ` / $${wc.sub_min_spend.toLocaleString()}`}
                                {wc.sub_months != null && ` in ${wc.sub_months} mo`}
                              </span>
                            )}
                          </p>
                        </div>
                        <button
                          className="text-slate-500 hover:text-red-400 text-sm"
                          onClick={() =>
                            removeCardMutation.mutate({
                              walletId: selectedWallet.id,
                              cardId: wc.card_id,
                            })
                          }
                          disabled={removeCardMutation.isPending}
                        >
                          Remove
                        </button>
                      </li>
                    ))}
                    {!selectedWallet.wallet_cards?.length && (
                      <li className="text-slate-500 text-sm py-4 text-center">
                        No cards. Add cards to calculate EV.
                      </li>
                    )}
                  </ul>
                </div>

                {/* Results */}
                <div className="bg-slate-900 border border-slate-700 rounded-xl p-4">
                  <h2 className="text-sm font-semibold text-slate-200 mb-3">Results</h2>
                  {resultsMutation.isError && (
                    <div className="text-red-400 text-sm bg-red-950 border border-red-700 rounded-lg p-3 mb-3">
                      {resultsMutation.error?.message}
                    </div>
                  )}
                  {result ? (
                    <WalletSummary result={result.wallet} />
                  ) : (
                    <div className="text-slate-500 text-sm text-center py-12">
                      Set projection and click Calculate to see EV and opportunity cost.
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {showCreateModal && (
        <CreateWalletModal
          onClose={() => setShowCreateModal(false)}
          onCreate={(name, description) =>
            createWalletMutation.mutate({ name, description })
          }
          isLoading={createWalletMutation.isPending}
        />
      )}

      {showAddCardModal && selectedWallet && (
        <AddCardModal
          onClose={() => setShowAddCardModal(false)}
          onAdd={(payload) =>
            addCardMutation.mutate({ walletId: selectedWallet.id, payload })
          }
          isLoading={addCardMutation.isPending}
        />
      )}
    </div>
  )
}
