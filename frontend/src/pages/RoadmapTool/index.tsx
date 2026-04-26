import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  scenariosApi,
  scenarioCardCreditApi,
  scenarioCategoryPriorityApi,
  scenarioCppApi,
  scenarioFutureCardsApi,
  scenarioOverlaysApi,
  scenarioPortalShareApi,
  walletApi,
  walletSpendApi,
  type CardCredit,
  type CardInstance,
  type CurrencyRead,
  type FutureCardCreatePayload,
  type FutureCardUpdatePayload,
  type RoadmapResponse,
  type RoadmapRuleStatus,
  type Scenario,
  type ScenarioCardCategoryPriority,
  type ScenarioCardCreditOverride,
  type ScenarioCardOverlay,
  type ScenarioPortalShareRead,
  type ScenarioSummary,
  type UpsertOverlayPayload,
  type WalletResultResponse,
  type WalletSpendItem,
  type WalletWithScenarios,
} from '../../api/client'
import { today } from '../../utils/format'
import { WalletCardModal } from '../../components/cards/WalletCardModal'
import { DeleteCardWarningModal } from '../../components/cards/DeleteCardWarningModal'
import { WalletSummaryStats } from './components/summary/WalletSummaryStats'
import { MethodologyInfoPopover } from './components/summary/MethodologyInfoPopover'
import { WalletTimelineChart } from './components/timeline/WalletTimelineChart'
import { SpendPanel } from './components/spend/SpendPanel'
import { ApplicationRuleWarningModal } from './components/ApplicationRuleWarningModal'
import { AddScenarioModal } from './components/AddScenarioModal'
import { ScenarioPicker } from './components/ScenarioPicker'
import { InfoIconButton } from '../../components/InfoPopover'
import { useCardLibrary } from './hooks/useCardLibrary'
import { useCreditLibrary } from '../../hooks/useCreditLibrary'
import { useToday } from '../../hooks/useToday'
import { useTravelPortals } from '../../hooks/useTravelPortals'
import { queryKeys } from '../../lib/queryKeys'
import { resolveScenarioCards, type ResolvedCard } from './lib/resolveScenarioCards'

type MainView = 'timeline' | 'spend'

type WalletCardModalOpen =
  | { mode: 'add-future' }
  | { mode: 'edit-overlay'; resolved: ResolvedCard }
  | { mode: 'edit-future'; resolved: ResolvedCard }

const SNAPSHOT_SIG_STORAGE_PREFIX = 'roadmap:snapshot-sig:'
function snapshotSigKey(scenarioId: number) {
  return `${SNAPSHOT_SIG_STORAGE_PREFIX}${scenarioId}`
}
function readStoredSnapshotSig(scenarioId: number): string | null {
  try {
    return localStorage.getItem(snapshotSigKey(scenarioId))
  } catch {
    return null
  }
}
function writeStoredSnapshotSig(scenarioId: number, sig: string) {
  try {
    localStorage.setItem(snapshotSigKey(scenarioId), sig)
  } catch {
    /* storage full or unavailable — stale flag falls back to in-session only */
  }
}

/** Serialize the scenario + projection inputs that drive the calculation.
 * Two calls return the same string iff no calc-relevant input changed, so
 * comparing against the snapshot from the last successful calc lets us
 * distinguish "truly out of date" from "edited and then reverted".
 *
 * Includes ``today`` because owned-card SUB earnability is derived from
 * ``opening_date + spend_rate`` against the current date — when the calendar
 * day rolls over, results computed on the prior day are stale. ``useToday``
 * re-renders the consumer just past midnight, which flips the signature
 * here and trips the "out of date" indicator. */
function scenarioCalcSignature(
  today: string,
  resolvedCards: ResolvedCard[],
  foreignSpendPercent: number,
  durationYears: number,
  durationMonths: number,
  spendItems: WalletSpendItem[] | undefined,
  scenarioCurrencies: CurrencyRead[] | undefined,
  portalShares: ScenarioPortalShareRead[] | undefined,
  categoryPriorities: ScenarioCardCategoryPriority[] | undefined,
  creditOverridesByInstanceId: Map<number, ScenarioCardCreditOverride[]>,
  creditLibraryById: Map<number, CardCredit>,
): string {
  // Only serialize cards that would participate in the calc. Disabled cards
  // are filtered by the backend's active-instance predicate, so edits to
  // them can't change results — leave them out of the signature so those
  // edits don't falsely trip the "out of date" warning.
  const cards = resolvedCards
    .filter((wc) => wc.is_enabled)
    .map((wc) => ({
      instance_id: wc.instance_id,
      card_id: wc.card_id,
      is_enabled: wc.is_enabled,
      added_date: wc.added_date,
      closed_date: wc.closed_date,
      sub_points: wc.sub_points,
      sub_min_spend: wc.sub_min_spend,
      sub_months: wc.sub_months,
      sub_spend_earn: wc.sub_spend_earn,
      annual_bonus: wc.annual_bonus,
      annual_fee: wc.annual_fee,
      first_year_fee: wc.first_year_fee,
      secondary_currency_rate: wc.secondary_currency_rate,
      sub_earned_date: wc.sub_earned_date,
      product_changed_date: wc.product_changed_date,
      transfer_enabler: wc.transfer_enabler,
      acquisition_type: wc.acquisition_type,
      pc_from_instance_id: wc.pc_from_instance_id,
      panel: wc.panel,
      is_future: wc.is_future,
      is_overlay_modified: wc.is_overlay_modified,
    }))
    .sort((a, b) => a.instance_id - b.instance_id)
  const spend = [...(spendItems ?? [])]
    .map((it) => ({
      user_spend_category_id: it.user_spend_category_id,
      amount: it.amount,
    }))
    .sort((a, b) => (a.user_spend_category_id ?? 0) - (b.user_spend_category_id ?? 0))
  const activeInstanceIds = new Set(cards.map((c) => c.instance_id))
  const cppOverrides = [...(scenarioCurrencies ?? [])]
    .map((c) => ({
      currency_id: c.id,
      cpp: c.user_cents_per_point ?? c.cents_per_point,
    }))
    .sort((a, b) => a.currency_id - b.currency_id)
  const portals = [...(portalShares ?? [])]
    .map((p) => ({ travel_portal_id: p.travel_portal_id, share: p.share }))
    .sort((a, b) => a.travel_portal_id - b.travel_portal_id)
  // Key category priorities by card_instance_id so they stay stable across
  // add/remove cycles, and skip priorities on disabled cards.
  const prioritiesByInstanceId = new Map<number, number[]>()
  for (const pr of categoryPriorities ?? []) {
    if (!activeInstanceIds.has(pr.card_instance_id)) continue
    const list = prioritiesByInstanceId.get(pr.card_instance_id) ?? []
    list.push(pr.spend_category_id)
    prioritiesByInstanceId.set(pr.card_instance_id, list)
  }
  const priorities = [...prioritiesByInstanceId.entries()]
    .map(([instanceId, ids]) => ({
      instance_id: instanceId,
      ids: [...ids].sort((a, b) => a - b),
    }))
    .sort((a, b) => a.instance_id - b.instance_id)
  // Per-instance credit overrides — same treatment as priorities: drop
  // disabled cards, sort by library credit id for stability. Library-level
  // calc inputs (currency, year-1 exclusion, one-time flag) are pulled in
  // here so editing them in the credit picker also flips the signature.
  const credits: {
    instance_id: number
    overrides: {
      library_credit_id: number
      value: number
      currency_id: number | null
      excludes_first_year: boolean
      is_one_time: boolean
    }[]
  }[] = []
  for (const [instanceId, rows] of creditOverridesByInstanceId) {
    if (!activeInstanceIds.has(instanceId)) continue
    credits.push({
      instance_id: instanceId,
      overrides: [...rows]
        .map((o) => {
          const lib = creditLibraryById.get(o.library_credit_id)
          return {
            library_credit_id: o.library_credit_id,
            value: o.value,
            currency_id: lib?.credit_currency_id ?? null,
            excludes_first_year: lib?.excludes_first_year ?? false,
            is_one_time: lib?.is_one_time ?? false,
          }
        })
        .sort((a, b) => a.library_credit_id - b.library_credit_id),
    })
  }
  credits.sort((a, b) => a.instance_id - b.instance_id)
  return JSON.stringify({
    today,
    durationYears,
    durationMonths,
    foreign_spend_percent: foreignSpendPercent,
    cards,
    spend,
    cppOverrides,
    portals,
    priorities,
    credits,
  })
}

export default function RoadmapToolPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { scenarioId: scenarioIdParam } = useParams<{ scenarioId?: string }>()
  const requestedScenarioId = scenarioIdParam ? Number(scenarioIdParam) : null
  const [walletCardModal, setWalletCardModal] = useState<WalletCardModalOpen | null>(null)
  const [durationYears, setDurationYears] = useState(2)
  const [durationMonths, setDurationMonths] = useState(0)
  const [methodologyAnchor, setMethodologyAnchor] = useState<HTMLElement | null>(null)
  const [includeSubs, setIncludeSubs] = useState(true)
  const [result, setResult] = useState<WalletResultResponse | null>(null)
  // Signature of inputs at the last successful calc.
  const [snapshotSignature, setSnapshotSignature] = useState<string | null>(null)
  // Eager drift flag: set right after a mutation succeeds so the amber
  // "Calculate" button appears before the queries refetch.
  const [inSigDirty, setInSigDirty] = useState(false)
  const [mainView, setMainView] = useState<MainView>('timeline')
  const [applicationRuleWarnings, setApplicationRuleWarnings] = useState<RoadmapRuleStatus[] | null>(
    null
  )
  const [pendingRemoval, setPendingRemoval] = useState<
    | { mode: 'overlay'; instanceId: number; cardName: string }
    | { mode: 'future'; instanceId: number; cardName: string }
    | null
  >(null)
  const [showAddScenario, setShowAddScenario] = useState(false)
  const [addScenarioError, setAddScenarioError] = useState<string | null>(null)

  // Wallet (single per user) — provides owned card instances + scenario list
  // + foreign_spend_percent. The endpoint auto-creates the wallet + default
  // scenario on first call so this query never returns null for an
  // authenticated user.
  const { data: wallet, isLoading: walletLoading } = useQuery<WalletWithScenarios>({
    queryKey: queryKeys.myWalletWithScenarios(),
    queryFn: () => walletApi.get(),
  })

  const scenarios = wallet?.scenarios ?? []
  const defaultScenario = scenarios.find((s) => s.is_default) ?? scenarios[0] ?? null

  // Resolve which scenario to render. URL param wins; otherwise the wallet's
  // default. If neither is available (post-load empty wallet), fall back null.
  const activeScenarioId =
    requestedScenarioId != null && scenarios.some((s) => s.id === requestedScenarioId)
      ? requestedScenarioId
      : defaultScenario?.id ?? null

  // Redirect to the default scenario when no scenario id is in the URL.
  useEffect(() => {
    if (requestedScenarioId == null && defaultScenario != null) {
      navigate(`/roadmap-tool/scenarios/${defaultScenario.id}`, { replace: true })
    }
  }, [requestedScenarioId, defaultScenario, navigate])

  // Fall back to the default if the requested scenario doesn't exist (deleted).
  const fallbackMessage =
    requestedScenarioId != null &&
    scenarios.length > 0 &&
    !scenarios.some((s) => s.id === requestedScenarioId)
      ? `Scenario #${requestedScenarioId} is unavailable — showing your default scenario.`
      : null

  // Active scenario detail (calc config like duration / include_subs).
  const { data: scenarioDetail } = useQuery<Scenario>({
    queryKey: queryKeys.scenario(activeScenarioId),
    queryFn: () => scenariosApi.get(activeScenarioId!),
    enabled: activeScenarioId != null,
  })

  // Future cards scoped to the active scenario.
  const { data: futureCards = [] } = useQuery<CardInstance[]>({
    queryKey: queryKeys.scenarioFutureCards(activeScenarioId),
    queryFn: () => scenarioFutureCardsApi.list(activeScenarioId!),
    enabled: activeScenarioId != null,
  })

  // Per-scenario overlays applied to owned cards.
  const { data: overlays = [] } = useQuery<ScenarioCardOverlay[]>({
    queryKey: queryKeys.scenarioOverlays(activeScenarioId),
    queryFn: () => scenarioOverlaysApi.list(activeScenarioId!),
    enabled: activeScenarioId != null,
  })

  // Library cards lookup (used for three-tier resolution).
  const { data: libraryCards } = useCardLibrary()
  const libraryCardsById = useMemo(() => {
    const m = new Map<number, NonNullable<typeof libraryCards>[number]>()
    for (const c of libraryCards ?? []) m.set(c.id, c)
    return m
  }, [libraryCards])

  // Build the unified active card list with overlays layered in.
  const resolvedCards: ResolvedCard[] = useMemo(() => {
    if (!wallet) return []
    return resolveScenarioCards(
      wallet.card_instances ?? [],
      futureCards,
      overlays,
      libraryCardsById,
    )
  }, [wallet, futureCards, overlays, libraryCardsById])

  // Last persisted calculation. Hydrated once per scenario mount.
  const { data: latestResult, isFetched: latestResultFetched } = useQuery({
    queryKey: queryKeys.scenarioLatestResults(activeScenarioId),
    queryFn: () => scenariosApi.latestResults(activeScenarioId!),
    enabled: activeScenarioId != null,
    staleTime: Infinity,
  })

  // Wallet spend (no scenario variation).
  const { data: spendItems, isFetched: spendItemsFetched } = useQuery({
    queryKey: queryKeys.walletSpendItemsSingular(),
    queryFn: () => walletSpendApi.list(),
  })

  // Pull in the scenario-scoped override collections for signature tracking.
  const { data: scenarioCurrencies } = useQuery({
    queryKey: queryKeys.scenarioCurrencies(activeScenarioId),
    queryFn: () => scenarioCppApi.listCurrencies(activeScenarioId!),
    enabled: activeScenarioId != null,
  })
  const { data: portalShares } = useQuery({
    queryKey: queryKeys.scenarioPortalShares(activeScenarioId),
    queryFn: () => scenarioPortalShareApi.list(activeScenarioId!),
    enabled: activeScenarioId != null,
  })
  const { data: categoryPriorities } = useQuery({
    queryKey: queryKeys.scenarioCategoryPriorities(activeScenarioId),
    queryFn: () => scenarioCategoryPriorityApi.list(activeScenarioId!),
    enabled: activeScenarioId != null,
  })

  // Credits live on their own per-instance endpoint. Fan out a query per
  // enabled card so the main signature can see every credit value.
  const enabledInstanceIds = useMemo(
    () =>
      resolvedCards
        .filter((wc) => wc.is_enabled)
        .map((wc) => wc.instance_id)
        .sort((a, b) => a - b),
    [resolvedCards],
  )
  const creditQueries = useQueries({
    queries: enabledInstanceIds.map((instanceId) => ({
      queryKey: queryKeys.scenarioCardCredits(activeScenarioId, instanceId),
      queryFn: () => scenarioCardCreditApi.list(activeScenarioId!, instanceId),
      enabled: activeScenarioId != null,
    })),
  })
  const creditOverridesByInstanceId = useMemo(() => {
    const m = new Map<number, ScenarioCardCreditOverride[]>()
    enabledInstanceIds.forEach((instanceId, idx) => {
      const rows = creditQueries[idx]?.data
      if (rows) m.set(instanceId, rows)
    })
    return m
  }, [creditQueries, enabledInstanceIds])

  const foreignSpendPercent = wallet?.foreign_spend_percent ?? 0
  const todayStr = useToday()

  // Credit library is also a calc input via per-credit currency / year-1
  // exclusion / one-time flags, so we read its data here (not just warm
  // the cache) and feed it into the signature below.
  const { data: creditLibrary } = useCreditLibrary()
  const creditLibraryById = useMemo(() => {
    const m = new Map<number, CardCredit>()
    for (const c of creditLibrary ?? []) m.set(c.id, c)
    return m
  }, [creditLibrary])

  const currentSignature = useMemo(
    () =>
      scenarioCalcSignature(
        todayStr,
        resolvedCards,
        foreignSpendPercent,
        durationYears,
        durationMonths,
        spendItems,
        scenarioCurrencies,
        portalShares,
        categoryPriorities,
        creditOverridesByInstanceId,
        creditLibraryById,
      ),
    [
      todayStr,
      resolvedCards,
      foreignSpendPercent,
      durationYears,
      durationMonths,
      spendItems,
      scenarioCurrencies,
      portalShares,
      categoryPriorities,
      creditOverridesByInstanceId,
      creditLibraryById,
    ],
  )
  const signatureMatchesSnapshot =
    snapshotSignature !== null && currentSignature === snapshotSignature

  // Whether a given card instance is calc-relevant: either it was
  // calculated in the last result, or it would be calculated by the next
  // calc (is_enabled). Both sides key on instance.id (= ResolvedCard.id =
  // CardResult.card_id under the new model).
  const isCardRelevant = useMemo(() => {
    const lastCalcIds = new Set<number>(
      (result?.wallet.card_results ?? [])
        .filter((cr) => cr.selected)
        .map((cr) => cr.card_id),
    )
    const activeIds = new Set<number>(
      resolvedCards.filter((wc) => wc.is_enabled).map((wc) => wc.id),
    )
    return (instanceId: number) =>
      lastCalcIds.has(instanceId) || activeIds.has(instanceId)
  }, [result, resolvedCards])

  useEffect(() => {
    if (inSigDirty && signatureMatchesSnapshot) {
      setInSigDirty(false)
    }
  }, [inSigDirty, signatureMatchesSnapshot])

  const isStale =
    inSigDirty ||
    (snapshotSignature !== null && currentSignature !== snapshotSignature)

  const hasNeverCalculated =
    latestResultFetched && latestResult == null && result == null
  const hasEnabledCards = resolvedCards.some((wc) => wc.is_enabled)
  const needsInitialCalc = hasNeverCalculated && hasEnabledCards
  const needsCalculate = isStale || needsInitialCalc

  useTravelPortals()

  const createScenarioMutation = useMutation({
    mutationFn: (payload: {
      name: string
      description: string | null
      copy_from_scenario_id: number | null
    }) => scenariosApi.create(payload),
    onSuccess: async (newScenario) => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.myWalletWithScenarios() })
      setShowAddScenario(false)
      setAddScenarioError(null)
      navigate(`/roadmap-tool/scenarios/${newScenario.id}`)
    },
    onError: (err) => {
      setAddScenarioError(err instanceof Error ? err.message : String(err))
    },
  })

  const makeDefaultMutation = useMutation({
    mutationFn: (id: number) => scenariosApi.makeDefault(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.myWalletWithScenarios() })
    },
  })

  const deleteScenarioMutation = useMutation({
    mutationFn: (id: number) => scenariosApi.delete(id),
    onSuccess: async (_data, deletedId) => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.myWalletWithScenarios() })
      if (deletedId === activeScenarioId) {
        // Backend auto-spawns a fresh default if this was the last one;
        // navigating to /roadmap-tool re-resolves to the new default.
        navigate('/roadmap-tool', { replace: true })
      }
    },
  })

  const addFutureCardMutation = useMutation({
    mutationFn: ({
      scenarioId,
      payload,
    }: {
      scenarioId: number
      payload: FutureCardCreatePayload
    }) => scenarioFutureCardsApi.create(scenarioId, payload),
    onSuccess: async (data, { scenarioId, payload }) => {
      const prev = queryClient.getQueryData<RoadmapResponse>(
        queryKeys.scenarioRoadmap(scenarioId),
      )
      const prevViolatedIds = new Set(
        (prev?.rule_statuses ?? []).filter((r) => r.is_violated).map((r) => r.rule_id),
      )

      const addedActive = data.is_enabled !== false

      if (payload.priority_category_ids && payload.priority_category_ids.length > 0) {
        await scenarioCategoryPriorityApi.set(
          scenarioId,
          data.id,
          payload.priority_category_ids,
        )
        queryClient.invalidateQueries({
          queryKey: queryKeys.scenarioCategoryPriorities(scenarioId),
        })
      }

      queryClient.invalidateQueries({
        queryKey: queryKeys.scenarioFutureCards(scenarioId),
      })
      setWalletCardModal(null)
      if (addedActive) setInSigDirty(true)

      try {
        await queryClient.invalidateQueries({
          queryKey: queryKeys.scenarioRoadmap(scenarioId),
        })
        const fresh = await queryClient.fetchQuery({
          queryKey: queryKeys.scenarioRoadmap(scenarioId),
          queryFn: () => scenariosApi.roadmap(scenarioId),
        })
        const newlyViolated = fresh.rule_statuses.filter(
          (r) => r.is_violated && !prevViolatedIds.has(r.rule_id),
        )
        if (newlyViolated.length > 0) {
          setApplicationRuleWarnings(newlyViolated)
        }
      } catch {
        /* roadmap optional for add flow */
      }
    },
  })

  const updateFutureCardMutation = useMutation({
    mutationFn: ({
      scenarioId,
      instanceId,
      payload,
    }: {
      scenarioId: number
      instanceId: number
      payload: FutureCardUpdatePayload
    }) => scenarioFutureCardsApi.update(scenarioId, instanceId, payload),
    onSuccess: (data, { scenarioId, instanceId }) => {
      const wasRelevant = isCardRelevant(data.id)
      const isNowActive = data.is_enabled
      queryClient.invalidateQueries({
        queryKey: queryKeys.scenarioFutureCards(scenarioId),
      })
      queryClient.invalidateQueries({ queryKey: queryKeys.scenarioRoadmap(scenarioId) })
      queryClient.invalidateQueries({
        queryKey: queryKeys.scenarioCardCredits(scenarioId, instanceId),
      })
      if (wasRelevant || isNowActive) setInSigDirty(true)
    },
  })

  const deleteFutureCardMutation = useMutation({
    mutationFn: ({
      scenarioId,
      instanceId,
    }: {
      scenarioId: number
      instanceId: number
    }) => scenarioFutureCardsApi.delete(scenarioId, instanceId),
    onSuccess: (_data, { scenarioId, instanceId }) => {
      const wc = resolvedCards.find((c) => c.instance_id === instanceId)
      const wasRelevant = wc ? isCardRelevant(wc.instance_id) : false
      queryClient.invalidateQueries({
        queryKey: queryKeys.scenarioFutureCards(scenarioId),
      })
      if (wasRelevant) setInSigDirty(true)
    },
  })

  const upsertOverlayMutation = useMutation({
    mutationFn: ({
      scenarioId,
      instanceId,
      payload,
    }: {
      scenarioId: number
      instanceId: number
      payload: UpsertOverlayPayload
    }) => scenarioOverlaysApi.upsert(scenarioId, instanceId, payload),
    onSuccess: (_data, { scenarioId, instanceId }) => {
      const wc = resolvedCards.find((c) => c.instance_id === instanceId)
      const wasRelevant = wc ? isCardRelevant(wc.instance_id) : false
      queryClient.invalidateQueries({
        queryKey: queryKeys.scenarioOverlays(scenarioId),
      })
      queryClient.invalidateQueries({
        queryKey: queryKeys.scenarioCardCredits(scenarioId, instanceId),
      })
      if (wasRelevant) setInSigDirty(true)
    },
  })

  const clearOverlayMutation = useMutation({
    mutationFn: ({
      scenarioId,
      instanceId,
    }: {
      scenarioId: number
      instanceId: number
    }) => scenarioOverlaysApi.clear(scenarioId, instanceId),
    onSuccess: (_data, { scenarioId, instanceId }) => {
      const wc = resolvedCards.find((c) => c.instance_id === instanceId)
      const wasRelevant = wc ? isCardRelevant(wc.instance_id) : false
      queryClient.invalidateQueries({
        queryKey: queryKeys.scenarioOverlays(scenarioId),
      })
      if (wasRelevant) setInSigDirty(true)
    },
  })

  const updateScenarioMutation = useMutation({
    mutationFn: ({
      scenarioId,
      include_subs,
    }: {
      scenarioId: number
      include_subs: boolean
    }) => scenariosApi.update(scenarioId, { include_subs }),
    onSuccess: (_data, { scenarioId }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.scenario(scenarioId) })
    },
  })

  const resultsMutation = useMutation({
    mutationFn: ({
      scenarioId,
      params,
    }: {
      scenarioId: number
      params: {
        start_date: string
        end_date?: string
        duration_years?: number
        duration_months?: number
      }
    }) => scenariosApi.results(scenarioId, params),
    onMutate: () => ({ signature: currentSignature }),
    onSuccess: (data, _vars, ctx) => {
      setResult(data)
      const sig = ctx?.signature ?? null
      setSnapshotSignature(sig)
      const scenarioIdForSnapshot = data.scenario_id ?? activeScenarioId
      if (sig != null && scenarioIdForSnapshot != null) {
        writeStoredSnapshotSig(scenarioIdForSnapshot, sig)
      }
      setInSigDirty(false)
      if (scenarioIdForSnapshot != null) {
        queryClient.setQueryData(
          queryKeys.scenarioLatestResults(scenarioIdForSnapshot),
          data,
        )
      }
      queryClient.invalidateQueries({ queryKey: queryKeys.myWalletWithScenarios() })
    },
  })

  function calculateNow() {
    runCalculation()
  }

  const { data: roadmap } = useQuery({
    queryKey: queryKeys.scenarioRoadmap(activeScenarioId),
    queryFn: () => scenariosApi.roadmap(activeScenarioId!),
    enabled: activeScenarioId != null,
  })

  // One-shot init: sync duration / include_subs from scenario detail.
  useEffect(() => {
    if (scenarioDetail == null) return
    setDurationYears(scenarioDetail.duration_years)
    setDurationMonths(scenarioDetail.duration_months)
    setIncludeSubs(scenarioDetail.include_subs)
  }, [scenarioDetail?.id])

  // Hydrate result state from the persisted snapshot exactly once per mount.
  const [hasHydrated, setHasHydrated] = useState(false)
  useEffect(() => {
    if (hasHydrated) return
    if (!latestResultFetched) return
    if (!spendItemsFetched) return
    if (!wallet) return
    if (activeScenarioId == null) return
    if (latestResult) {
      setResult(latestResult)
      const stored = readStoredSnapshotSig(activeScenarioId)
      setSnapshotSignature(
        stored ??
          scenarioCalcSignature(
            todayStr,
            resolvedCards,
            foreignSpendPercent,
            latestResult.duration_years,
            latestResult.duration_months,
            spendItems,
            scenarioCurrencies,
            portalShares,
            categoryPriorities,
            creditOverridesByInstanceId,
            creditLibraryById,
          ),
      )
    }
    setHasHydrated(true)
  }, [
    hasHydrated,
    latestResultFetched,
    latestResult,
    spendItemsFetched,
    spendItems,
    wallet,
    activeScenarioId,
    resolvedCards,
    foreignSpendPercent,
    scenarioCurrencies,
    portalShares,
    categoryPriorities,
    creditOverridesByInstanceId,
    creditLibraryById,
  ])

  // Reset hydration flag when switching scenarios so the persisted snapshot
  // for the new scenario can hydrate.
  useEffect(() => {
    setHasHydrated(false)
    setResult(null)
    setSnapshotSignature(null)
    setInSigDirty(false)
  }, [activeScenarioId])

  function runCalculation(years = durationYears, months = durationMonths) {
    if (activeScenarioId == null) return
    if (years * 12 + months === 0) return
    resultsMutation.mutate({
      scenarioId: activeScenarioId,
      params: { start_date: today(), duration_years: years, duration_months: months },
    })
  }

  // Helper: toggle is_enabled on an owned card via overlay or on a future card directly.
  function toggleCardEnabled(instanceId: number, enabled: boolean) {
    if (activeScenarioId == null) return
    const wc = resolvedCards.find((c) => c.instance_id === instanceId)
    if (!wc) return
    if (wc.is_future) {
      updateFutureCardMutation.mutate({
        scenarioId: activeScenarioId,
        instanceId,
        payload: { is_enabled: enabled },
      })
    } else {
      upsertOverlayMutation.mutate({
        scenarioId: activeScenarioId,
        instanceId,
        payload: { is_enabled: enabled },
      })
    }
  }

  const isBusy =
    addFutureCardMutation.isPending ||
    updateFutureCardMutation.isPending ||
    deleteFutureCardMutation.isPending ||
    upsertOverlayMutation.isPending ||
    clearOverlayMutation.isPending ||
    resultsMutation.isPending

  if (walletLoading) {
    return (
      <div className="max-w-screen-xl mx-auto w-full shrink-0">
        <div className="text-center text-slate-400 py-20">Loading wallet…</div>
      </div>
    )
  }

  return (
    <div className="max-w-screen-xl mx-auto w-full flex flex-col flex-1 min-h-0">
      {isBusy && (
        <div className="fixed top-0 left-0 right-0 z-50 h-0.5">
          <div className="h-full bg-indigo-500 animate-progress-bar" />
        </div>
      )}
      <header className="mb-3 shrink-0 flex items-start justify-between gap-4">
        <div className="min-w-0 flex items-center gap-3">
          <h1 className="text-2xl font-bold text-white shrink-0">Roadmap Tool</h1>
          {scenarios.length > 0 && (
            <ScenarioPicker
              scenarios={scenarios}
              currentId={activeScenarioId}
              onSelect={(id) => navigate(`/roadmap-tool/scenarios/${id}`)}
              onAddScenario={() => {
                setAddScenarioError(null)
                setShowAddScenario(true)
              }}
              onMakeDefault={(id) => makeDefaultMutation.mutate(id)}
              onDelete={(id) => deleteScenarioMutation.mutate(id)}
            />
          )}
        </div>
        {activeScenarioId != null && (
          <div className="shrink-0 flex items-center gap-2">
            <InfoIconButton
              onClick={(e) => {
                const anchor = e.currentTarget
                setMethodologyAnchor((cur) => (cur ? null : anchor))
              }}
              label="How the roadmap is calculated"
              size={18}
              active={!!methodologyAnchor}
            />
            <button
              type="button"
              onClick={calculateNow}
              disabled={resultsMutation.isPending || !needsCalculate}
              aria-live="polite"
              className={`px-4 py-2 rounded-lg text-sm font-semibold transition-colors ${
                resultsMutation.isPending
                  ? 'bg-slate-700 text-slate-400 cursor-wait'
                  : isStale
                  ? 'bg-amber-500 hover:bg-amber-400 text-slate-900 shadow-sm shadow-amber-900/40'
                  : needsInitialCalc
                  ? 'bg-indigo-500 hover:bg-indigo-400 text-white shadow-sm shadow-indigo-900/40'
                  : 'bg-slate-700 text-slate-500 cursor-not-allowed'
              }`}
              title={
                isStale
                  ? 'Results are out of date — click to recalculate'
                  : needsInitialCalc
                  ? 'Click to calculate your scenario'
                  : 'Results are up to date'
              }
            >
              {resultsMutation.isPending
                ? 'Calculating…'
                : needsCalculate
                ? 'Calculate'
                : 'Up to Date'}
            </button>
          </div>
        )}
      </header>

      {methodologyAnchor && (
        <MethodologyInfoPopover
          anchorEl={methodologyAnchor}
          onClose={() => setMethodologyAnchor(null)}
        />
      )}

      {fallbackMessage && (
        <div className="mb-3 shrink-0 px-3 py-2 rounded-md border border-amber-700/60 bg-amber-900/30 text-amber-200 text-sm">
          {fallbackMessage}
        </div>
      )}

      <div className="min-w-0 flex-1 min-h-0 flex flex-col">
        {!wallet || activeScenarioId == null ? (
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-8 text-center text-slate-500 shrink-0">
            Add cards and spending in your <Link to="/profile" className="text-indigo-400 hover:text-indigo-300">profile</Link> to get started.
          </div>
        ) : (
          <>
            <div className="mb-4 shrink-0">
              <WalletSummaryStats
                result={result?.wallet ?? null}
                roadmap={roadmap ?? null}
                isCalculating={resultsMutation.isPending}
                isStale={isStale}
                hasNeverCalculated={hasNeverCalculated}
                durationYears={durationYears}
                durationMonths={durationMonths}
                onDurationChange={(y, m) => {
                  setDurationYears(y)
                  setDurationMonths(m)
                  setInSigDirty(true)
                }}
                includeSubs={includeSubs}
                onIncludeSubsChange={(v) => {
                  setIncludeSubs(v)
                  if (activeScenarioId != null) {
                    updateScenarioMutation.mutate({
                      scenarioId: activeScenarioId,
                      include_subs: v,
                    })
                  }
                }}
                resultsError={
                  resultsMutation.isError
                    ? resultsMutation.error instanceof Error
                      ? resultsMutation.error
                      : new Error(String(resultsMutation.error))
                    : null
                }
              />
            </div>
            <div className="flex flex-1 min-h-0 min-w-0 items-stretch">
              {/* Binder-style tabs sit outside the panel on the left. */}
              <div className="shrink-0 flex flex-col gap-1 pt-6 z-10">
                {([
                  {
                    key: 'timeline' as const,
                    label: 'Timeline',
                    icon: (
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="3" y1="6" x2="21" y2="6" />
                        <line x1="3" y1="12" x2="14" y2="12" />
                        <line x1="3" y1="18" x2="18" y2="18" />
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
                  const isActive = mainView === tab.key
                  return (
                    <button
                      key={tab.key}
                      type="button"
                      onClick={() => setMainView(tab.key)}
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

              <div className="flex-1 min-w-0 min-h-0">
                {mainView === 'timeline' ? (
                  <WalletTimelineChart
                    scenarioId={activeScenarioId}
                    walletCards={resolvedCards}
                    result={result?.wallet ?? null}
                    roadmap={roadmap}
                    durationYears={durationYears}
                    durationMonths={durationMonths}
                    isUpdating={
                      updateFutureCardMutation.isPending ||
                      upsertOverlayMutation.isPending
                    }
                    isStale={isStale}
                    includeSubs={includeSubs}
                    onToggleEnabled={(instanceId, enabled) => {
                      toggleCardEnabled(instanceId, enabled)
                    }}
                    onEditCard={(wc) => {
                      if (wc.is_future) {
                        setWalletCardModal({ mode: 'edit-future', resolved: wc })
                      } else {
                        setWalletCardModal({ mode: 'edit-overlay', resolved: wc })
                      }
                    }}
                    onAddCard={() => setWalletCardModal({ mode: 'add-future' })}
                  />
                ) : (
                  <SpendPanel
                    selectedCards={result?.wallet.card_results.filter((c) => c.selected) ?? []}
                    walletCards={resolvedCards}
                    totalYears={Math.max(durationYears + durationMonths / 12, 1 / 12)}
                    isStale={isStale}
                  />
                )}
              </div>
            </div>

          </>
        )}
      </div>

      {applicationRuleWarnings && applicationRuleWarnings.length > 0 && (
        <ApplicationRuleWarningModal
          violations={applicationRuleWarnings}
          onClose={() => setApplicationRuleWarnings(null)}
        />
      )}

      {showAddScenario && (
        <AddScenarioModal
          isSubmitting={createScenarioMutation.isPending}
          errorMessage={addScenarioError}
          scenarios={scenarios as ScenarioSummary[]}
          onClose={() => {
            setShowAddScenario(false)
            setAddScenarioError(null)
          }}
          onSubmit={(payload) => {
            setAddScenarioError(null)
            createScenarioMutation.mutate(payload)
          }}
        />
      )}

      {pendingRemoval && activeScenarioId != null && (
        <DeleteCardWarningModal
          cardName={pendingRemoval.cardName}
          isLoading={
            deleteFutureCardMutation.isPending || clearOverlayMutation.isPending
          }
          onClose={() => setPendingRemoval(null)}
          onConfirm={() => {
            if (pendingRemoval.mode === 'future') {
              deleteFutureCardMutation.mutate(
                {
                  scenarioId: activeScenarioId,
                  instanceId: pendingRemoval.instanceId,
                },
                { onSuccess: () => setPendingRemoval(null) },
              )
            } else {
              clearOverlayMutation.mutate(
                {
                  scenarioId: activeScenarioId,
                  instanceId: pendingRemoval.instanceId,
                },
                { onSuccess: () => setPendingRemoval(null) },
              )
            }
          }}
        />
      )}

      {walletCardModal && wallet && activeScenarioId != null && (
        <WalletCardModal
          key={
            walletCardModal.mode === 'add-future'
              ? 'add'
              : walletCardModal.resolved.instance_id
          }
          mode={
            walletCardModal.mode === 'add-future'
              ? 'scenario-future'
              : walletCardModal.mode === 'edit-future'
              ? 'scenario-future'
              : 'overlay'
          }
          scenarioId={activeScenarioId}
          isAddFlow={walletCardModal.mode === 'add-future'}
          resolvedCard={
            walletCardModal.mode === 'add-future' ? undefined : walletCardModal.resolved
          }
          existingCardIds={resolvedCards.map((wc) => wc.card_id)}
          instanceLookup={resolvedCards.map((wc) => ({
            instance_id: wc.instance_id,
            card_id: wc.card_id,
            card_name: wc.card_name ?? `Card #${wc.card_id}`,
            opening_date: wc.added_date,
            pc_from_instance_id: wc.pc_from_instance_id,
            is_enabled: wc.is_enabled,
            acquisition_type: wc.acquisition_type,
          }))}
          onClose={() => setWalletCardModal(null)}
          onAddFuture={(payload) =>
            addFutureCardMutation.mutate({
              scenarioId: activeScenarioId,
              payload: { ...payload, panel: 'future_cards' },
            })
          }
          onSaveFuture={(payload) => {
            if (walletCardModal.mode !== 'edit-future') return
            updateFutureCardMutation.mutate(
              {
                scenarioId: activeScenarioId,
                instanceId: walletCardModal.resolved.instance_id,
                payload,
              },
              { onSuccess: () => setWalletCardModal(null) },
            )
          }}
          onSaveOverlay={(payload) => {
            if (walletCardModal.mode !== 'edit-overlay') return
            upsertOverlayMutation.mutate(
              {
                scenarioId: activeScenarioId,
                instanceId: walletCardModal.resolved.instance_id,
                payload,
              },
              { onSuccess: () => setWalletCardModal(null) },
            )
          }}
          onClearOverlay={() => {
            if (walletCardModal.mode !== 'edit-overlay') return
            clearOverlayMutation.mutate(
              {
                scenarioId: activeScenarioId,
                instanceId: walletCardModal.resolved.instance_id,
              },
              { onSuccess: () => setWalletCardModal(null) },
            )
          }}
          onRemoveFuture={(wc) => {
            setWalletCardModal(null)
            setPendingRemoval({
              mode: 'future',
              instanceId: wc.instance_id,
              cardName: wc.card_name ?? `Card #${wc.card_id}`,
            })
          }}
          isLoading={
            addFutureCardMutation.isPending ||
            updateFutureCardMutation.isPending ||
            upsertOverlayMutation.isPending
          }
        />
      )}
    </div>
  )
}
