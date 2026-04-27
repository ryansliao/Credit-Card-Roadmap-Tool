/**
 * Three-tier client-side resolution for scenario card display.
 *
 * The roadmap tool needs to render a unified list of cards = owned (the
 * user's actual cards on the wallet) + future (CardInstance rows scoped to
 * the active scenario). Owned cards may be hypothetically modified by a
 * ScenarioCardOverlay; the resolution rule is:
 *
 *   overlay.<f> ?? card_instance.<f> ?? library_card.<f>
 *
 * For future instances, the overlay tier doesn't apply — the instance is
 * already scenario-scoped. For owned instances without an overlay row, the
 * instance's own values stand.
 *
 * This module produces a `ResolvedCard` view shaped like the legacy
 * `WalletCard` so the existing timeline / spend / summary components can
 * keep consuming the same prop shape without per-component rewrites.
 */

import type {
  Card,
  CardInstance,
  ScenarioCardOverlay,
  WalletCard,
  WalletCardAcquisitionType,
  WalletCardPanel,
} from '../../../api/client'

export interface ResolvedCard extends WalletCard {
  /** The CardInstance.id this resolved view was built from. */
  instance_id: number
  /** True when scenario_id is non-null on the source instance. */
  is_future: boolean
  /** True when an overlay layer modified this owned card in the active scenario. */
  is_overlay_modified: boolean
  /** For future-card PCs: the parent CardInstance.id that this card was changed
   * from. The legacy `pc_from_card_id` on `WalletCard` is null in the new
   * model — consumers wanting the "from" library card_id should look it up via
   * this id in the resolved card list. */
  pc_from_instance_id: number | null
  /** Wallet-level credit overrides on the source instance. Empty for future
   * cards (which have no owned/wallet context). Used to seed the credits
   * tab in the scenario modal so users see the inherited values rather
   * than an empty list. */
  wallet_credit_overrides: { library_credit_id: number; value: number }[]
}

function _coalesce<T>(...values: (T | null | undefined)[]): T | null {
  for (const v of values) {
    if (v !== null && v !== undefined) return v
  }
  return null
}

function _libValue<K extends keyof Card>(lib: Card | undefined, key: K): Card[K] | null {
  if (!lib) return null
  const v = lib[key]
  return v === undefined ? null : v
}

/**
 * Apply three-tier resolution to one card instance.
 *
 * @param instance the CardInstance row (owned or scenario-scoped)
 * @param overlay  the matching ScenarioCardOverlay, if any (owned-only)
 * @param lib      the library Card row keyed by `instance.card_id`
 */
export function resolveCardInstance(
  instance: CardInstance,
  overlay: ScenarioCardOverlay | null,
  lib: Card | undefined,
): ResolvedCard {
  const isFuture = instance.scenario_id !== null
  const isOverlayModified = overlay !== null
  // For future cards, overlay always null (caller passes null already).
  const ov = overlay
  // Resolve each field. Numbers/dates/booleans use the same overlay → instance
  // → library cascade as the backend's ScenarioResolver._resolve_effective.
  const sub_points = _coalesce(ov?.sub_points, instance.sub_points, _libValue(lib, 'sub_points'))
  const sub_min_spend = _coalesce(ov?.sub_min_spend, instance.sub_min_spend, _libValue(lib, 'sub_min_spend'))
  const sub_months = _coalesce(ov?.sub_months, instance.sub_months, _libValue(lib, 'sub_months'))
  const sub_spend_earn = _coalesce(ov?.sub_spend_earn, instance.sub_spend_earn, _libValue(lib, 'sub_spend_earn'))
  const annual_bonus = _coalesce(ov?.annual_bonus, instance.annual_bonus, _libValue(lib, 'annual_bonus'))
  const annual_fee = _coalesce(ov?.annual_fee, instance.annual_fee, _libValue(lib, 'annual_fee'))
  const first_year_fee = _coalesce(ov?.first_year_fee, instance.first_year_fee, _libValue(lib, 'first_year_fee'))
  const secondary_currency_rate = _coalesce(
    ov?.secondary_currency_rate,
    instance.secondary_currency_rate,
    _libValue(lib, 'secondary_currency_rate'),
  )
  const sub_earned_date = _coalesce(ov?.sub_earned_date, instance.sub_earned_date)
  // closed_date_clear on the overlay forces the card active in this scenario
  // even when the underlying instance is closed. Mirrors the backend's
  // ScenarioResolver._resolve_effective.
  const closed_date = ov?.closed_date_clear
    ? null
    : _coalesce(ov?.closed_date, instance.closed_date)
  const product_change_date = _coalesce(ov?.product_change_date, instance.product_change_date)
  // is_enabled is a boolean — cascade-coalesce against null sentinel only.
  const is_enabled =
    ov?.is_enabled !== null && ov?.is_enabled !== undefined
      ? ov.is_enabled
      : instance.is_enabled

  // Acquisition type encoded by date columns: product_change_date != null → PC.
  const acquisition_type: WalletCardAcquisitionType =
    product_change_date !== null ? 'product_change' : 'opened'

  // The legacy WalletCard exposes `pc_from_card_id` (library card_id). The new
  // model uses pc_from_instance_id (CardInstance.id). Downstream consumers
  // only use this in the spend tab to find the "from" card; we surface
  // `pc_from_instance_id` on the extended ResolvedCard but keep
  // `pc_from_card_id` null so old logic doesn't accidentally exclude cards.
  const pc_from_card_id: number | null = null

  return {
    // Use instance.id as the wallet_card.id surrogate. Downstream code that
    // expects a stable id-per-row (modal keying, etc.) uses this.
    id: instance.id,
    instance_id: instance.id,
    is_future: isFuture,
    is_overlay_modified: isOverlayModified,
    pc_from_instance_id: instance.pc_from_instance_id,
    wallet_id: instance.wallet_id,
    card_id: instance.card_id,
    card_name: instance.card_name,
    added_date: instance.opening_date,
    sub_points,
    sub_min_spend,
    sub_months,
    sub_spend_earn,
    annual_bonus,
    years_counted: instance.years_counted,
    annual_fee,
    first_year_fee,
    secondary_currency_rate,
    sub_earned_date,
    closed_date,
    product_changed_date: product_change_date,
    transfer_enabler: instance.transfer_enabler,
    acquisition_type,
    pc_from_card_id,
    panel: instance.panel as WalletCardPanel,
    is_enabled,
    photo_slug: instance.photo_slug,
    issuer_name: instance.issuer_name,
    network_tier_name: instance.network_tier_name,
    credit_totals: instance.credit_totals,
    wallet_credit_overrides: instance.credit_overrides ?? [],
  }
}

/**
 * Build the active card list for a scenario by merging owned + future
 * instances with the matching overlays applied.
 *
 * @param ownedInstances     wallet.card_instances (scenario_id === null)
 * @param futureInstances    scenarios/{id}/future-cards
 * @param overlays           scenarios/{id}/overlays
 * @param libraryCardsById   library Card lookup
 */
export function resolveScenarioCards(
  ownedInstances: CardInstance[],
  futureInstances: CardInstance[],
  overlays: ScenarioCardOverlay[],
  libraryCardsById: Map<number, Card>,
): ResolvedCard[] {
  const overlayByInstanceId = new Map<number, ScenarioCardOverlay>()
  for (const ov of overlays) overlayByInstanceId.set(ov.card_instance_id, ov)
  const out: ResolvedCard[] = []
  for (const inst of ownedInstances) {
    const ov = overlayByInstanceId.get(inst.id) ?? null
    out.push(resolveCardInstance(inst, ov, libraryCardsById.get(inst.card_id)))
  }
  for (const inst of futureInstances) {
    // Overlays don't target future cards.
    out.push(resolveCardInstance(inst, null, libraryCardsById.get(inst.card_id)))
  }

  // PC-derived close on source instances: when an enabled future PC card
  // carries pc_from_instance_id, treat the source as closed at the PC's
  // product_change_date for display (timeline bar end, spend allocation).
  // Mirrors ScenarioResolver in the backend so the timeline / spend / calc
  // all agree, and gives "only close if the PC card is enabled" for free
  // (disabled rows are skipped). PC derivation runs after the standard
  // overlay resolution, so it wins over closed_date_clear in the rare case
  // of a force-open overlay competing with a PC pointing at the same card —
  // matching the backend's resolution order.
  const pcCloseBySource = new Map<number, string>()
  for (const r of out) {
    if (!r.is_future) continue
    if (!r.is_enabled) continue
    if (r.acquisition_type !== 'product_change') continue
    if (r.pc_from_instance_id == null) continue
    if (!r.product_changed_date) continue
    const cur = pcCloseBySource.get(r.pc_from_instance_id)
    if (cur == null || r.product_changed_date < cur) {
      pcCloseBySource.set(r.pc_from_instance_id, r.product_changed_date)
    }
  }
  if (pcCloseBySource.size > 0) {
    for (const r of out) {
      const pcClose = pcCloseBySource.get(r.instance_id)
      if (pcClose == null) continue
      if (r.closed_date == null || pcClose < r.closed_date) {
        r.closed_date = pcClose
      }
    }
  }
  return out
}
