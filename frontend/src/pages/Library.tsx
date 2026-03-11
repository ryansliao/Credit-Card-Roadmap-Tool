import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Fragment, useState } from 'react'
import {
  cardsApi,
  currenciesApi,
  ecosystemsApi,
  issuersApi,
  type Card,
  type CardCreatePayload,
  type CurrencyRead,
  type EcosystemRead,
  type IssuerRead,
} from '../api/client'

type TabId = 'cards' | 'issuers' | 'currencies' | 'ecosystems'

// ─── Card form (add / edit) ─────────────────────────────────────────────────

const DEFAULT_CARD_FORM: CardCreatePayload = {
  name: '',
  issuer_id: 0,
  currency_id: 0,
  annual_fee: 0,
  sub_points: 0,
  sub_min_spend: null,
  sub_months: null,
  sub_spend_points: 0,
  annual_bonus_points: 0,
  ecosystem_memberships: [],
  multipliers: [],
  credits: [],
}

interface CardFormModalProps {
  open: boolean
  onClose: () => void
  initial?: CardCreatePayload & { id?: number }
  issuers: IssuerRead[]
  currencies: CurrencyRead[]
  ecosystems: EcosystemRead[]
  onSubmit: (payload: CardCreatePayload) => void
  isSubmitting: boolean
  error?: string | null
}

function CardFormModal({
  open,
  onClose,
  initial,
  issuers,
  currencies,
  ecosystems,
  onSubmit,
  isSubmitting,
  error,
}: CardFormModalProps) {
  const [form, setForm] = useState<CardCreatePayload>(initial ?? DEFAULT_CARD_FORM)
  const isEdit = initial?.id != null
  const currenciesForIssuer = form.issuer_id
    ? currencies.filter((c) => c.issuer_id === form.issuer_id || c.issuer_id == null)
    : []
  const singleMembership = (form.ecosystem_memberships ?? [])[0]
  const ecosystemId = singleMembership?.ecosystem_id ?? 0

  if (!open) return null

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.name.trim() || !form.issuer_id || !form.currency_id) return
    onSubmit(form)
  }

  const setEcosystem = (id: number) => {
    setForm((f) => ({
      ...f,
      ecosystem_memberships: id ? [{ ecosystem_id: id, key_card: false }] : [],
    }))
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="bg-slate-900 border border-slate-700 rounded-xl shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto m-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-5 border-b border-slate-700">
          <h3 className="text-lg font-bold text-white">{isEdit ? 'Edit card' : 'Add card'}</h3>
        </div>
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Name</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              className="w-full bg-slate-800 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg"
              required
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Issuer</label>
            <select
              value={form.issuer_id || ''}
              onChange={(e) => {
                const id = Number(e.target.value)
                setForm((f) => ({
                  ...f,
                  issuer_id: id,
                  currency_id: 0,
                }))
              }}
              className="w-full bg-slate-800 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg"
              required
            >
              <option value="">Select issuer</option>
              {issuers.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Currency</label>
            <select
              value={form.currency_id || ''}
              onChange={(e) =>
                setForm((f) => ({ ...f, currency_id: Number(e.target.value) }))
              }
              className="w-full bg-slate-800 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg"
              required
            >
              <option value="">Select currency</option>
              {currenciesForIssuer.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Ecosystem</label>
            <select
              value={ecosystemId || ''}
              onChange={(e) => setEcosystem(Number(e.target.value) || 0)}
              className="w-full bg-slate-800 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg"
            >
              <option value="">—</option>
              {ecosystems.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.name}
                </option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-400 mb-1">Annual fee ($)</label>
              <input
                type="number"
                min={0}
                step={1}
                value={form.annual_fee ?? 0}
                onChange={(e) =>
                  setForm((f) => ({ ...f, annual_fee: Number(e.target.value) || 0 }))
                }
                className="w-full bg-slate-800 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">SUB points</label>
              <input
                type="number"
                min={0}
                value={form.sub_points ?? 0}
                onChange={(e) =>
                  setForm((f) => ({ ...f, sub_points: Number(e.target.value) || 0 }))
                }
                className="w-full bg-slate-800 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">SUB min spend ($)</label>
              <input
                type="number"
                min={0}
                step={1}
                value={form.sub_min_spend ?? ''}
                onChange={(e) => {
                  const v = e.target.value
                  setForm((f) => ({ ...f, sub_min_spend: v === '' ? null : Number(v) || 0 }))
                }}
                placeholder="Optional"
                className="w-full bg-slate-800 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">SUB spend window (mo.)</label>
              <input
                type="number"
                min={0}
                step={1}
                value={form.sub_months ?? ''}
                onChange={(e) => {
                  const v = e.target.value
                  setForm((f) => ({ ...f, sub_months: v === '' ? null : Number(v) || 0 }))
                }}
                placeholder="Optional"
                className="w-full bg-slate-800 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg"
              />
            </div>
          </div>
          {error && (
            <p className="text-red-400 text-sm bg-red-950/50 border border-red-800 rounded-lg px-3 py-2">
              {error}
            </p>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg bg-slate-700 text-slate-200 hover:bg-slate-600"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !form.name.trim() || !form.issuer_id || !form.currency_id}
              className="px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50"
            >
              {isSubmitting ? 'Saving…' : isEdit ? 'Save' : 'Add'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ─── Cards tab ───────────────────────────────────────────────────────────────

function CardsTab() {
  const queryClient = useQueryClient()
  const { data: cards, isLoading } = useQuery({
    queryKey: ['cards'],
    queryFn: cardsApi.list,
  })
  const { data: issuers = [] } = useQuery({
    queryKey: ['issuers'],
    queryFn: issuersApi.list,
  })
  const { data: currencies = [] } = useQuery({
    queryKey: ['currencies'],
    queryFn: currenciesApi.list,
  })
  const { data: ecosystems = [] } = useQuery({
    queryKey: ['ecosystems'],
    queryFn: ecosystemsApi.list,
  })
  const [search, setSearch] = useState('')
  const [issuerFilter, setIssuerFilter] = useState('All')
  const [addModalOpen, setAddModalOpen] = useState(false)
  const [editCardId, setEditCardId] = useState<number | null>(null)
  const [tableEditMode, setTableEditMode] = useState(false)
  // Inline table editing: which cell is focused and its current value (for PATCH on blur)
  const [editingCell, setEditingCell] = useState<{
    cardId: number
    field: string
    value: string | number | null
  } | null>(null)
  const [expandedCardId, setExpandedCardId] = useState<number | null>(null)

  const createCard = useMutation({
    mutationFn: cardsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cards'] })
      setAddModalOpen(false)
    },
  })
  const updateCard = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<CardCreatePayload> }) =>
      cardsApi.update(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cards'] })
      setAddModalOpen(false)
      setEditCardId(null)
    },
  })
  const deleteCard = useMutation({
    mutationFn: cardsApi.delete,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['cards'] }),
  })

  const issuerNames = ['All', ...Array.from(new Set(cards?.map((c) => c.issuer.name) ?? [])).sort()]
  const filtered =
    cards?.filter((c) => {
      const matchSearch =
        c.name.toLowerCase().includes(search.toLowerCase()) ||
        c.issuer.name.toLowerCase().includes(search.toLowerCase())
      const matchIssuer = issuerFilter === 'All' || c.issuer.name === issuerFilter
      return matchSearch && matchIssuer
    }) ?? []

  const cellValue = (card: Card, field: string): string | number => {
    if (editingCell?.cardId === card.id && editingCell?.field === field)
      return editingCell.value ?? ''
    switch (field) {
      case 'name':
        return card.name
      case 'annual_fee':
        return card.annual_fee
      case 'sub_points':
        return card.sub_points
      case 'sub_min_spend':
        return card.sub_min_spend ?? ''
      case 'sub_months':
        return card.sub_months ?? ''
      case 'annual_bonus_points':
        return card.annual_bonus_points
      default:
        return ''
    }
  }

  const patchCell = (card: Card, field: string, value: string | number | null) => {
    const payload: Partial<CardCreatePayload> = {}
    if (field === 'name') payload.name = value === null ? card.name : String(value)
    else if (field === 'annual_fee') payload.annual_fee = value === null || value === '' ? 0 : Number(value)
    else if (field === 'sub_points') payload.sub_points = value === null || value === '' ? 0 : Number(value)
    else if (field === 'sub_min_spend') payload.sub_min_spend = value === null || value === '' ? null : Number(value)
    else if (field === 'sub_months') payload.sub_months = value === null || value === '' ? null : Number(value)
    else if (field === 'annual_bonus_points') payload.annual_bonus_points = value === null || value === '' ? 0 : Number(value)
    if (Object.keys(payload).length) updateCard.mutate({ id: card.id, payload })
  }

  const handleDeleteRow = (card: Card) => {
    if (!window.confirm(`Delete card "${card.name}"? This will remove it from all wallets and scenarios.`))
      return
    deleteCard.mutate(card.id)
  }

  const cardToPayload = (card: Card): CardCreatePayload & { id?: number } => ({
    id: card.id,
    name: card.name,
    issuer_id: card.issuer_id,
    currency_id: card.currency_id,
    annual_fee: card.annual_fee,
    sub_points: card.sub_points,
    sub_min_spend: card.sub_min_spend,
    sub_months: card.sub_months,
    sub_spend_points: card.sub_spend_points,
    annual_bonus_points: card.annual_bonus_points,
    ecosystem_memberships: card.ecosystem_memberships?.length
      ? [{ ecosystem_id: card.ecosystem_memberships[0].ecosystem_id, key_card: false }]
      : [],
    multipliers: card.multipliers,
    credits: card.credits,
  })

  const handleCardSubmit = (payload: CardCreatePayload) => {
    if (editCardId != null) {
      updateCard.mutate({ id: editCardId, payload })
      setEditCardId(null)
    } else {
      createCard.mutate(payload)
    }
  }

  const currenciesByIssuer = (issuerId: number) =>
    currencies.filter((c) => c.issuer_id === issuerId || c.issuer_id == null)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3 flex-wrap">
          <input
            className="bg-slate-800 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg outline-none focus:border-indigo-500 w-56"
            placeholder="Search cards…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <div className="flex flex-wrap gap-1">
            {issuerNames.map((iss) => (
              <button
                key={iss}
                type="button"
                onClick={() => setIssuerFilter(iss)}
                className={`text-xs px-2.5 py-1 rounded-full transition-colors ${
                  issuerFilter === iss
                    ? 'bg-indigo-600 text-white'
                    : 'bg-slate-800 text-slate-400 hover:text-white'
                }`}
              >
                {iss}
              </button>
            ))}
          </div>
        </div>
        <p className="text-slate-400 text-sm">Add or edit cards in the table.</p>
        <div className="flex items-center gap-2">
          {tableEditMode ? (
            <button
              type="button"
              onClick={() => {
                setTableEditMode(false)
                queryClient.invalidateQueries({ queryKey: ['cards'] })
              }}
              className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-500"
            >
              Save
            </button>
          ) : (
            <button
              type="button"
              onClick={() => setTableEditMode(true)}
              className="px-4 py-2 rounded-lg bg-slate-600 text-white text-sm font-medium hover:bg-slate-500"
            >
              Edit
            </button>
          )}
          <button
            type="button"
            onClick={() => setAddModalOpen(true)}
            className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-500"
          >
            Add card
          </button>
        </div>
      </div>
      {isLoading ? (
        <div className="text-slate-400 text-center py-20">Loading…</div>
      ) : (
        <div className="bg-slate-900 border border-slate-700 rounded-xl overflow-x-auto">
          <table className="w-full border-collapse text-sm table-fixed" style={{ minWidth: 0 }}>
            <thead>
              <tr className="border-b border-slate-700">
                <th className="text-left text-slate-400 font-medium px-3 py-2.5" style={{ width: '2%' }} aria-label="Expand" />
                <th className="text-left text-slate-400 font-medium px-3 py-2.5" style={{ width: tableEditMode ? '23%' : '25%' }}>Name</th>
                <th className="text-left text-slate-400 font-medium px-3 py-2.5" style={{ width: tableEditMode ? '20%' : '21%' }}>Issuer</th>
                <th className="text-left text-slate-400 font-medium px-3 py-2.5" style={{ width: tableEditMode ? '24%' : '26%' }}>Currency</th>
                <th className="text-left text-slate-400 font-medium px-3 py-2.5" style={{ width: tableEditMode ? '24%' : '26%' }}>Ecosystem</th>
                {tableEditMode && (
                  <th className="text-left text-slate-400 font-medium px-3 py-2.5" style={{ width: '5%' }} aria-label="Actions" />
                )}
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={tableEditMode ? 7 : 6} className="text-slate-500 px-3 py-8 text-center">
                    No cards match.
                  </td>
                </tr>
              ) : (
                filtered.map((card) => (
                  <Fragment key={card.id}>
                    <tr className="border-b border-slate-800 hover:bg-slate-800/50">
                      <td className="px-2 py-1 align-top overflow-hidden" style={{ width: '2%' }}>
                        <button
                          type="button"
                          onClick={() =>
                            setExpandedCardId((prev) => (prev === card.id ? null : card.id))
                          }
                          className="p-1 rounded text-slate-400 hover:bg-slate-700 hover:text-white transition-transform"
                          title={expandedCardId === card.id ? 'Collapse' : 'Expand fee & SUB'}
                          aria-expanded={expandedCardId === card.id}
                        >
                          <svg
                            className={`w-4 h-4 transition-transform ${expandedCardId === card.id ? 'rotate-90' : ''}`}
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                          </svg>
                        </button>
                      </td>
                      <td className="px-3 py-1 overflow-hidden" style={{ width: tableEditMode ? '29%' : '30%' }}>
                        <input
                          disabled={!tableEditMode}
                          className="w-full min-w-0 bg-slate-800 border border-slate-600 text-white px-2 py-1.5 rounded focus:border-indigo-500 outline-none disabled:opacity-60 disabled:cursor-not-allowed"
                          value={cellValue(card, 'name')}
                          onFocus={() =>
                            setEditingCell({ cardId: card.id, field: 'name', value: card.name })
                          }
                          onChange={(e) =>
                            setEditingCell((c) =>
                              c && c.cardId === card.id && c.field === 'name'
                                ? { ...c, value: e.target.value }
                                : c
                            )
                          }
                          onBlur={() => {
                            if (editingCell?.cardId === card.id && editingCell?.field === 'name')
                              patchCell(card, 'name', editingCell.value)
                            setEditingCell(null)
                          }}
                        />
                      </td>
                      <td className="px-3 py-1 overflow-hidden" style={{ width: tableEditMode ? '18%' : '20%' }}>
                        <select
                          disabled={!tableEditMode}
                          className="w-full min-w-0 bg-slate-800 border border-slate-600 text-white px-2 py-1.5 rounded focus:border-indigo-500 outline-none disabled:opacity-60 disabled:cursor-not-allowed"
                          value={card.issuer_id}
                          onChange={(e) => {
                            const issuerId = Number(e.target.value)
                            const curList = currenciesByIssuer(issuerId)
                            updateCard.mutate({
                              id: card.id,
                              payload: {
                                issuer_id: issuerId,
                                currency_id: curList[0]?.id ?? 0,
                              },
                            })
                          }}
                        >
                          {issuers.map((i) => (
                            <option key={i.id} value={i.id}>
                              {i.name}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-3 py-1 overflow-hidden" style={{ width: tableEditMode ? '23%' : '24%' }}>
                        <select
                          disabled={!tableEditMode}
                          className="w-full min-w-0 bg-slate-800 border border-slate-600 text-white px-2 py-1.5 rounded focus:border-indigo-500 outline-none disabled:opacity-60 disabled:cursor-not-allowed"
                          value={card.currency_id}
                          onChange={(e) =>
                            updateCard.mutate({
                              id: card.id,
                              payload: { currency_id: Number(e.target.value) },
                            })
                          }
                        >
                          {currenciesByIssuer(card.issuer_id).map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.name}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-3 py-1 overflow-hidden" style={{ width: tableEditMode ? '23%' : '24%' }}>
                        <div className="flex items-center gap-1 min-w-0">
                          <select
                            disabled={!tableEditMode}
                            className="w-full min-w-0 bg-slate-800 border border-slate-600 text-white px-2 py-1.5 rounded focus:border-indigo-500 outline-none disabled:opacity-60 disabled:cursor-not-allowed"
                            value={card.ecosystem_memberships?.[0]?.ecosystem_id ?? ''}
                            onChange={(e) => {
                              const id = Number(e.target.value)
                              updateCard.mutate({
                                id: card.id,
                                payload: {
                                  ecosystem_memberships: id ? [{ ecosystem_id: id, key_card: false }] : [],
                                },
                              })
                            }}
                          >
                            <option value="">—</option>
                            {ecosystems.map((e) => (
                              <option key={e.id} value={e.id}>
                                {e.name}
                              </option>
                            ))}
                          </select>
                        </div>
                      </td>
                      {tableEditMode && (
                        <td className="px-3 py-1 overflow-hidden" style={{ width: '5%' }}>
                          <button
                            type="button"
                            onClick={() => handleDeleteRow(card)}
                            className="text-xs px-2 py-1 rounded bg-red-900/60 text-red-200 hover:bg-red-800/60"
                            title="Delete card"
                          >
                            ×
                          </button>
                        </td>
                      )}
                    </tr>
                    {expandedCardId === card.id && (
                      <tr key={`${card.id}-details`} className="border-b border-slate-800 bg-slate-800/30">
                        <td colSpan={tableEditMode ? 7 : 6} className="px-3 py-3">
                          <div className="flex flex-wrap items-center gap-4">
                            <div className="flex items-center gap-2">
                              <label className="text-xs text-slate-400 whitespace-nowrap">Annual fee</label>
                              <input
                                type="number"
                                min={0}
                                step={1}
                                disabled={!tableEditMode}
                                className="w-20 bg-slate-800 border border-slate-600 text-white px-2 py-1.5 rounded text-sm disabled:opacity-60 disabled:cursor-not-allowed"
                                value={cellValue(card, 'annual_fee')}
                                onFocus={() =>
                                  setEditingCell({ cardId: card.id, field: 'annual_fee', value: card.annual_fee })
                                }
                                onChange={(e) =>
                                  setEditingCell((c) =>
                                    c && c.cardId === card.id && c.field === 'annual_fee'
                                      ? { ...c, value: e.target.value === '' ? '' : Number(e.target.value) }
                                      : c
                                  )
                                }
                                onBlur={() => {
                                  if (editingCell?.cardId === card.id && editingCell?.field === 'annual_fee')
                                    patchCell(card, 'annual_fee', editingCell.value)
                                  setEditingCell(null)
                                }}
                              />
                            </div>
                            <div className="flex items-center gap-2">
                              <label className="text-xs text-slate-400 whitespace-nowrap">SUB pts</label>
                              <input
                                type="number"
                                min={0}
                                disabled={!tableEditMode}
                                className="w-24 bg-slate-800 border border-slate-600 text-white px-2 py-1.5 rounded text-sm disabled:opacity-60 disabled:cursor-not-allowed"
                                value={cellValue(card, 'sub_points')}
                                onFocus={() =>
                                  setEditingCell({ cardId: card.id, field: 'sub_points', value: card.sub_points })
                                }
                                onChange={(e) =>
                                  setEditingCell((c) =>
                                    c && c.cardId === card.id && c.field === 'sub_points'
                                      ? { ...c, value: e.target.value === '' ? '' : Number(e.target.value) }
                                      : c
                                  )
                                }
                                onBlur={() => {
                                  if (editingCell?.cardId === card.id && editingCell?.field === 'sub_points')
                                    patchCell(card, 'sub_points', editingCell.value)
                                  setEditingCell(null)
                                }}
                              />
                            </div>
                            <div className="flex items-center gap-2">
                              <label className="text-xs text-slate-400 whitespace-nowrap">SUB min $</label>
                              <input
                                type="number"
                                min={0}
                                disabled={!tableEditMode}
                                className="w-24 bg-slate-800 border border-slate-600 text-white px-2 py-1.5 rounded text-sm disabled:opacity-60 disabled:cursor-not-allowed"
                                value={cellValue(card, 'sub_min_spend')}
                                onFocus={() =>
                                  setEditingCell({
                                    cardId: card.id,
                                    field: 'sub_min_spend',
                                    value: card.sub_min_spend,
                                  })
                                }
                                onChange={(e) =>
                                  setEditingCell((c) =>
                                    c && c.cardId === card.id && c.field === 'sub_min_spend'
                                      ? { ...c, value: e.target.value === '' ? '' : Number(e.target.value) }
                                      : c
                                  )
                                }
                                onBlur={() => {
                                  if (
                                    editingCell?.cardId === card.id &&
                                    editingCell?.field === 'sub_min_spend'
                                  )
                                    patchCell(card, 'sub_min_spend', editingCell.value)
                                  setEditingCell(null)
                                }}
                              />
                            </div>
                            <div className="flex items-center gap-2">
                              <label className="text-xs text-slate-400 whitespace-nowrap">SUB mo</label>
                              <input
                                type="number"
                                min={0}
                                disabled={!tableEditMode}
                                className="w-16 bg-slate-800 border border-slate-600 text-white px-2 py-1.5 rounded text-sm disabled:opacity-60 disabled:cursor-not-allowed"
                                value={cellValue(card, 'sub_months')}
                                onFocus={() =>
                                  setEditingCell({
                                    cardId: card.id,
                                    field: 'sub_months',
                                    value: card.sub_months,
                                  })
                                }
                                onChange={(e) =>
                                  setEditingCell((c) =>
                                    c && c.cardId === card.id && c.field === 'sub_months'
                                      ? { ...c, value: e.target.value === '' ? '' : Number(e.target.value) }
                                      : c
                                  )
                                }
                                onBlur={() => {
                                  if (
                                    editingCell?.cardId === card.id &&
                                    editingCell?.field === 'sub_months'
                                  )
                                    patchCell(card, 'sub_months', editingCell.value)
                                  setEditingCell(null)
                                }}
                              />
                            </div>
                            <div className="flex items-center gap-2">
                              <label className="text-xs text-slate-400 whitespace-nowrap">Ann. bonus</label>
                              <input
                                type="number"
                                min={0}
                                disabled={!tableEditMode}
                                className="w-24 bg-slate-800 border border-slate-600 text-white px-2 py-1.5 rounded text-sm disabled:opacity-60 disabled:cursor-not-allowed"
                                value={cellValue(card, 'annual_bonus_points')}
                                onFocus={() =>
                                  setEditingCell({
                                    cardId: card.id,
                                    field: 'annual_bonus_points',
                                    value: card.annual_bonus_points,
                                  })
                                }
                                onChange={(e) =>
                                  setEditingCell((c) =>
                                    c && c.cardId === card.id && c.field === 'annual_bonus_points'
                                      ? { ...c, value: e.target.value === '' ? '' : Number(e.target.value) }
                                      : c
                                  )
                                }
                                onBlur={() => {
                                  if (
                                    editingCell?.cardId === card.id &&
                                    editingCell?.field === 'annual_bonus_points'
                                  )
                                    patchCell(card, 'annual_bonus_points', editingCell.value)
                                  setEditingCell(null)
                                }}
                              />
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
      <CardFormModal
        key={editCardId ?? 'add'}
        open={addModalOpen}
        onClose={() => {
          setAddModalOpen(false)
          setEditCardId(null)
          createCard.reset()
          updateCard.reset()
        }}
        initial={editCardId != null && cards ? cardToPayload(cards.find((c) => c.id === editCardId)!) : undefined}
        issuers={issuers}
        currencies={currencies}
        ecosystems={ecosystems}
        onSubmit={handleCardSubmit}
        isSubmitting={createCard.isPending || updateCard.isPending}
        error={createCard.error?.message ?? updateCard.error?.message ?? null}
      />
    </div>
  )
}

// ─── Issuers tab ─────────────────────────────────────────────────────────────

function IssuersTab() {
  const queryClient = useQueryClient()
  const { data: issuers = [], isLoading } = useQuery({
    queryKey: ['issuers'],
    queryFn: issuersApi.list,
  })
  const [modalOpen, setModalOpen] = useState<'add' | 'edit' | null>(null)
  const [editing, setEditing] = useState<IssuerRead | null>(null)
  const [name, setName] = useState('')
  const [coBrandPartner, setCoBrandPartner] = useState('')
  const [network, setNetwork] = useState('')

  const resetForm = () => {
    setName('')
    setCoBrandPartner('')
    setNetwork('')
    setEditing(null)
  }

  const createIssuer = useMutation({
    mutationFn: (payload: { name: string; co_brand_partner?: string | null; network?: string | null }) =>
      issuersApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['issuers'] })
      setModalOpen(null)
      resetForm()
    },
  })
  const updateIssuer = useMutation({
    mutationFn: ({
      id,
      name: n,
      co_brand_partner,
      network,
    }: {
      id: number
      name: string
      co_brand_partner?: string | null
      network?: string | null
    }) => issuersApi.update(id, { name: n, co_brand_partner, network }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['issuers'] })
      setModalOpen(null)
      resetForm()
    },
  })
  const deleteIssuer = useMutation({
    mutationFn: issuersApi.delete,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['issuers'] }),
  })

  const handleDelete = (issuer: IssuerRead) => {
    if (!window.confirm(`Delete issuer "${issuer.name}"? This will fail if any cards use it.`))
      return
    deleteIssuer.mutate(issuer.id)
  }

  const openEdit = (issuer: IssuerRead) => {
    setEditing(issuer)
    setName(issuer.name)
    setCoBrandPartner(issuer.co_brand_partner ?? '')
    setNetwork(issuer.network ?? '')
    setModalOpen('edit')
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <p className="text-slate-400 text-sm">Add, edit, or remove issuers (issuer, co-brand partner, network).</p>
        <button
          type="button"
          onClick={() => {
            resetForm()
            setModalOpen('add')
          }}
          className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-500"
        >
          Add issuer
        </button>
      </div>
      {isLoading ? (
        <div className="text-slate-400 text-center py-20">Loading…</div>
      ) : (
        <div className="bg-slate-900 border border-slate-700 rounded-xl overflow-hidden">
          {issuers.length === 0 ? (
            <p className="text-slate-500 text-sm p-4">No issuers yet. Add one to get started.</p>
          ) : (
            <ul className="divide-y divide-slate-800">
              {issuers.map((issuer) => (
                <li
                  key={issuer.id}
                  className="flex items-center justify-between px-4 py-3 hover:bg-slate-800/50 gap-4"
                >
                  <div className="min-w-0">
                    <span className="text-white font-medium">{issuer.name}</span>
                    {(issuer.co_brand_partner || issuer.network) && (
                      <div className="flex flex-wrap items-center gap-2 mt-0.5">
                        {issuer.co_brand_partner && (
                          <span className="text-xs text-slate-400">
                            Co-brand: {issuer.co_brand_partner}
                          </span>
                        )}
                        {issuer.network && (
                          <span className="text-xs px-2 py-0.5 rounded bg-slate-700 text-slate-300">
                            {issuer.network}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      type="button"
                      onClick={() => openEdit(issuer)}
                      className="text-sm px-3 py-1.5 rounded-lg bg-slate-700 text-slate-200 hover:bg-slate-600"
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDelete(issuer)}
                      className="text-sm px-3 py-1.5 rounded-lg bg-red-900/60 text-red-200 hover:bg-red-800/60"
                    >
                      Delete
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {modalOpen !== null && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
          onClick={() => setModalOpen(null)}
        >
          <div
            className="bg-slate-900 border border-slate-700 rounded-xl p-5 w-full max-w-sm m-4"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-bold text-white mb-3">
              {modalOpen === 'add' ? 'Add issuer' : 'Edit issuer'}
            </h3>
            <form
              onSubmit={(e) => {
                e.preventDefault()
                const n = name.trim()
                if (!n) return
                const payload = {
                  name: n,
                  co_brand_partner: coBrandPartner.trim() || null,
                  network: network.trim() || null,
                }
                if (modalOpen === 'add') createIssuer.mutate(payload)
                else if (editing) updateIssuer.mutate({ id: editing.id, ...payload })
                setModalOpen(null)
              }}
              className="space-y-3"
            >
              <div>
                <label className="block text-xs text-slate-400 mb-1">Issuer</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Chase, Amex"
                  className="w-full bg-slate-800 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg"
                  required
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Co-brand partner (optional)</label>
                <input
                  type="text"
                  value={coBrandPartner}
                  onChange={(e) => setCoBrandPartner(e.target.value)}
                  placeholder="e.g. United, Delta"
                  className="w-full bg-slate-800 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Network (optional)</label>
                <input
                  type="text"
                  value={network}
                  onChange={(e) => setNetwork(e.target.value)}
                  placeholder="e.g. Visa, Mastercard, Amex"
                  className="w-full bg-slate-800 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg"
                />
              </div>
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setModalOpen(null)}
                  className="px-4 py-2 rounded-lg bg-slate-700 text-slate-200 hover:bg-slate-600"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createIssuer.isPending || updateIssuer.isPending || !name.trim()}
                  className="px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50"
                >
                  {modalOpen === 'add' ? 'Add' : 'Save'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      {deleteIssuer.isError && (
        <p className="text-red-400 text-sm">{deleteIssuer.error?.message}</p>
      )}
    </div>
  )
}

// ─── Currencies tab ──────────────────────────────────────────────────────────

function CurrenciesTab() {
  const queryClient = useQueryClient()
  const { data: currencies = [], isLoading } = useQuery({
    queryKey: ['currencies'],
    queryFn: currenciesApi.list,
  })
  const { data: issuers = [] } = useQuery({
    queryKey: ['issuers'],
    queryFn: issuersApi.list,
  })
  const [modalOpen, setModalOpen] = useState<'add' | 'edit' | null>(null)
  const [editing, setEditing] = useState<CurrencyRead | null>(null)
  const [form, setForm] = useState<{
    issuer_id: number | null
    name: string
    cents_per_point: number
    is_cashback: boolean
    is_transferable: boolean
  }>({
    issuer_id: null,
    name: '',
    cents_per_point: 1,
    is_cashback: false,
    is_transferable: true,
  })

  const createCurrency = useMutation({
    mutationFn: currenciesApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['currencies'] })
      setModalOpen(null)
      setForm({
        issuer_id: null,
        name: '',
        cents_per_point: 1,
        is_cashback: false,
        is_transferable: true,
      })
    },
  })
  const updateCurrency = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: { name?: string; issuer_id?: number | null; cents_per_point?: number; is_cashback?: boolean; is_transferable?: boolean } }) =>
      currenciesApi.update(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['currencies'] })
      setModalOpen(null)
      setEditing(null)
    },
  })
  const deleteCurrency = useMutation({
    mutationFn: currenciesApi.delete,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['currencies'] }),
  })

  const handleDelete = (c: CurrencyRead) => {
    if (!window.confirm(`Delete currency "${c.name}"? This will fail if any card uses it.`))
      return
    deleteCurrency.mutate(c.id)
  }

  const openEdit = (c: CurrencyRead) => {
    setEditing(c)
    setForm({
      issuer_id: c.issuer_id ?? null,
      name: c.name,
      cents_per_point: c.cents_per_point,
      is_cashback: c.is_cashback,
      is_transferable: c.is_transferable,
    })
    setModalOpen('edit')
  }

  const issuerName = (c: CurrencyRead) =>
    c.issuer?.name ?? (c.issuer_id != null ? issuers.find((i) => i.id === c.issuer_id)?.name ?? `#${c.issuer_id}` : '—')

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <p className="text-slate-400 text-sm">Add, edit, or remove currencies.</p>
        <button
          type="button"
          onClick={() => {
            setEditing(null)
            setForm({
              issuer_id: null,
              name: '',
              cents_per_point: 1,
              is_cashback: false,
              is_transferable: true,
            })
            setModalOpen('add')
          }}
          className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-500"
        >
          Add currency
        </button>
      </div>
      {isLoading ? (
        <div className="text-slate-400 text-center py-20">Loading…</div>
      ) : (
        <div className="bg-slate-900 border border-slate-700 rounded-xl overflow-hidden">
          {currencies.length === 0 ? (
            <p className="text-slate-500 text-sm p-4">No currencies yet. Add one to get started.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-700 text-left text-slate-400">
                    <th className="px-4 py-3">Name</th>
                    <th className="px-4 py-3">Issuer</th>
                    <th className="px-4 py-3">¢/pt</th>
                    <th className="px-4 py-3">Cashback</th>
                    <th className="px-4 py-3">Transferable</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {currencies.map((c) => (
                    <tr key={c.id} className="border-b border-slate-800 hover:bg-slate-800/30">
                      <td className="px-4 py-3 text-white font-medium">{c.name}</td>
                      <td className="px-4 py-3 text-slate-300">{issuerName(c)}</td>
                      <td className="px-4 py-3 text-slate-300">{c.cents_per_point}</td>
                      <td className="px-4 py-3 text-slate-300">{c.is_cashback ? 'Yes' : 'No'}</td>
                      <td className="px-4 py-3 text-slate-300">{c.is_transferable ? 'Yes' : 'No'}</td>
                      <td className="px-4 py-3 text-right">
                        <button
                          type="button"
                          onClick={() => openEdit(c)}
                          className="text-slate-300 hover:text-white mr-2"
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDelete(c)}
                          className="text-red-400 hover:text-red-300"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
      {modalOpen !== null && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
          onClick={() => setModalOpen(null)}
        >
          <div
            className="bg-slate-900 border border-slate-700 rounded-xl p-5 w-full max-w-md max-h-[90vh] overflow-y-auto m-4"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-bold text-white mb-3">
              {modalOpen === 'add' ? 'Add currency' : 'Edit currency'}
            </h3>
            <form
              onSubmit={(e) => {
                e.preventDefault()
                if (!form.name.trim()) return
                const payload = {
                  name: form.name.trim(),
                  issuer_id: form.issuer_id ?? undefined,
                  cents_per_point: form.cents_per_point,
                  is_cashback: form.is_cashback,
                  is_transferable: form.is_transferable,
                }
                if (modalOpen === 'add') {
                  createCurrency.mutate(payload)
                } else if (editing) {
                  updateCurrency.mutate({
                    id: editing.id,
                    payload,
                  })
                }
              }}
              className="space-y-3"
            >
              <div>
                <label className="block text-xs text-slate-400 mb-1">Issuer (optional, e.g. leave empty for Cash)</label>
                <select
                  value={form.issuer_id ?? ''}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, issuer_id: e.target.value ? Number(e.target.value) : null }))
                  }
                  className="w-full bg-slate-800 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg"
                >
                  <option value="">—</option>
                  {issuers.map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Name</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  className="w-full bg-slate-800 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg"
                  placeholder="e.g. Chase UR, Amex MR, Cash"
                  required
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Cents per point</label>
                  <input
                    type="number"
                    min={0}
                    step={0.01}
                    value={form.cents_per_point}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, cents_per_point: Number(e.target.value) || 0 }))
                    }
                    className="w-full bg-slate-800 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg"
                  />
                </div>
              </div>
              <div className="flex gap-4">
                <label className="flex items-center gap-2 text-slate-300">
                  <input
                    type="checkbox"
                    checked={form.is_cashback}
                    onChange={(e) => setForm((f) => ({ ...f, is_cashback: e.target.checked }))}
                    className="rounded border-slate-600"
                  />
                  Cashback
                </label>
                <label className="flex items-center gap-2 text-slate-300">
                  <input
                    type="checkbox"
                    checked={form.is_transferable}
                    onChange={(e) => setForm((f) => ({ ...f, is_transferable: e.target.checked }))}
                    className="rounded border-slate-600"
                  />
                  Transferable
                </label>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setModalOpen(null)}
                  className="px-4 py-2 rounded-lg bg-slate-700 text-slate-200 hover:bg-slate-600"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createCurrency.isPending || updateCurrency.isPending || !form.name.trim()}
                  className="px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50"
                >
                  {modalOpen === 'add' ? 'Add' : 'Save'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      {deleteCurrency.isError && (
        <p className="text-red-400 text-sm">{deleteCurrency.error?.message}</p>
      )}
    </div>
  )
}

// ─── Ecosystems tab ───────────────────────────────────────────────────────────

function EcosystemsTab() {
  const queryClient = useQueryClient()
  const { data: ecosystems = [], isLoading } = useQuery({
    queryKey: ['ecosystems'],
    queryFn: ecosystemsApi.list,
  })
  const { data: currencies = [] } = useQuery({
    queryKey: ['currencies'],
    queryFn: currenciesApi.list,
  })
  const [modalOpen, setModalOpen] = useState<'add' | 'edit' | null>(null)
  const [editing, setEditing] = useState<EcosystemRead | null>(null)
  const [form, setForm] = useState({
    name: '',
    points_currency_id: 0,
    additional_currency_ids: [] as number[],
  })

  const createEcosystem = useMutation({
    mutationFn: ecosystemsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ecosystems'] })
      setModalOpen(null)
      setForm({ name: '', points_currency_id: 0, additional_currency_ids: [] })
    },
  })
  const updateEcosystem = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: { name?: string; points_currency_id?: number; additional_currency_ids?: number[] } }) =>
      ecosystemsApi.update(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ecosystems'] })
      setModalOpen(null)
      setEditing(null)
    },
  })
  const deleteEcosystem = useMutation({
    mutationFn: ecosystemsApi.delete,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['ecosystems'] }),
  })

  const handleDelete = (e: EcosystemRead) => {
    if (!window.confirm(`Delete ecosystem "${e.name}"? Card memberships will be removed.`)) return
    deleteEcosystem.mutate(e.id)
  }

  const openEdit = (eco: EcosystemRead) => {
    setEditing(eco)
    setForm({
      name: eco.name,
      points_currency_id: eco.points_currency_id,
      additional_currency_ids: (eco.ecosystem_currencies ?? []).map((ec) => ec.currency_id),
    })
    setModalOpen('edit')
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <p className="text-slate-400 text-sm">
          Ecosystems define which cards unlock conversion (key cards) and which earn as points when a key is in wallet.
        </p>
        <button
          type="button"
          onClick={() => {
            setEditing(null)
            setForm({ name: '', points_currency_id: currencies[0]?.id ?? 0, additional_currency_ids: [] })
            setModalOpen('add')
          }}
          className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-500"
        >
          Add ecosystem
        </button>
      </div>
      {isLoading ? (
        <div className="text-slate-400 text-center py-20">Loading…</div>
      ) : (
        <div className="bg-slate-900 border border-slate-700 rounded-xl overflow-hidden">
          {ecosystems.length === 0 ? (
            <p className="text-slate-500 text-sm p-4">No ecosystems yet. Add one (e.g. Chase UR, Amex MR).</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-700 text-left text-slate-400">
                    <th className="px-4 py-3">Name</th>
                    <th className="px-4 py-3">Points currency</th>
                    <th className="px-4 py-3">Additional currencies</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {ecosystems.map((e) => (
                    <tr key={e.id} className="border-b border-slate-800 hover:bg-slate-800/30">
                      <td className="px-4 py-3 text-white font-medium">{e.name}</td>
                      <td className="px-4 py-3 text-slate-300">
                        {e.points_currency?.name ?? `#${e.points_currency_id}`}
                      </td>
                      <td className="px-4 py-3 text-slate-300">
                        {(e.ecosystem_currencies ?? []).length
                          ? (e.ecosystem_currencies ?? []).map((ec) => ec.currency?.name ?? `#${ec.currency_id}`).join(', ')
                          : '—'}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button type="button" onClick={() => openEdit(e)} className="text-slate-300 hover:text-white mr-2">
                          Edit
                        </button>
                        <button type="button" onClick={() => handleDelete(e)} className="text-red-400 hover:text-red-300">
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
      {modalOpen !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setModalOpen(null)}>
          <div
            className="bg-slate-900 border border-slate-700 rounded-xl p-5 w-full max-w-md max-h-[90vh] overflow-y-auto m-4"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-bold text-white mb-3">
              {modalOpen === 'add' ? 'Add ecosystem' : 'Edit ecosystem'}
            </h3>
            <form
              onSubmit={(e) => {
                e.preventDefault()
                if (!form.name.trim() || !form.points_currency_id) return
                if (modalOpen === 'add') {
                  createEcosystem.mutate({
                    name: form.name.trim(),
                    points_currency_id: form.points_currency_id,
                    additional_currency_ids: form.additional_currency_ids.length ? form.additional_currency_ids : undefined,
                  })
                } else if (editing) {
                  updateEcosystem.mutate({
                    id: editing.id,
                    payload: {
                      name: form.name.trim(),
                      points_currency_id: form.points_currency_id,
                      additional_currency_ids: form.additional_currency_ids,
                    },
                  })
                }
              }}
              className="space-y-3"
            >
              <div>
                <label className="block text-xs text-slate-400 mb-1">Name</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  className="w-full bg-slate-800 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg"
                  placeholder="e.g. Chase UR, Amex MR"
                  required
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Points currency</label>
                <select
                  value={form.points_currency_id || ''}
                  onChange={(e) => setForm((f) => ({ ...f, points_currency_id: Number(e.target.value) }))}
                  className="w-full bg-slate-800 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg"
                  required
                >
                  <option value="">Select currency</option>
                  {currencies.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Additional currencies</label>
                <p className="text-xs text-slate-500 mb-1">Currencies that convert to this ecosystem’s points when a key card is in wallet.</p>
                <div className="flex flex-wrap gap-2 max-h-24 overflow-y-auto p-2 bg-slate-800 border border-slate-600 rounded-lg">
                  {currencies
                    .filter((c) => !form.additional_currency_ids.includes(c.id))
                    .map((c) => (
                      <button
                        key={c.id}
                        type="button"
                        onClick={() => setForm((f) => ({ ...f, additional_currency_ids: [...f.additional_currency_ids, c.id] }))}
                        className="text-xs px-2 py-1 rounded bg-slate-700 text-slate-200 hover:bg-slate-600"
                      >
                        + {c.name}
                      </button>
                    ))}
                  {form.additional_currency_ids.map((cid) => {
                    const c = currencies.find((x) => x.id === cid)
                    return (
                      <span key={cid} className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded bg-slate-700 text-slate-200">
                        {c?.name ?? cid}
                        <button
                          type="button"
                          onClick={() => setForm((f) => ({ ...f, additional_currency_ids: f.additional_currency_ids.filter((id) => id !== cid) }))}
                          className="text-slate-400 hover:text-white"
                        >
                          ×
                        </button>
                      </span>
                    )
                  })}
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setModalOpen(null)} className="px-4 py-2 rounded-lg bg-slate-700 text-slate-200 hover:bg-slate-600">
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createEcosystem.isPending || updateEcosystem.isPending || !form.name.trim() || !form.points_currency_id}
                  className="px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50"
                >
                  {modalOpen === 'add' ? 'Add' : 'Save'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Library page ─────────────────────────────────────────────────────────────

const TABS: { id: TabId; label: string }[] = [
  { id: 'cards', label: 'Cards' },
  { id: 'issuers', label: 'Issuers' },
  { id: 'currencies', label: 'Currencies' },
  { id: 'ecosystems', label: 'Ecosystems' },
]

export default function Library() {
  const [tab, setTab] = useState<TabId>('cards')

  return (
    <div className="max-w-screen-xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Library</h1>
        <p className="text-slate-400 text-sm mt-1">
          Manage cards, issuers, and currencies. Add, edit, or remove entries in each tab.
        </p>
      </div>
      <div className="flex gap-1 mb-6 border-b border-slate-700 pb-1">
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={`px-4 py-2 rounded-t-lg text-sm font-medium transition-colors ${
              tab === id
                ? 'bg-slate-800 text-white border border-slate-700 border-b-0 -mb-px'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === 'cards' && <CardsTab />}
      {tab === 'issuers' && <IssuersTab />}
      {tab === 'currencies' && <CurrenciesTab />}
      {tab === 'ecosystems' && <EcosystemsTab />}
    </div>
  )
}
