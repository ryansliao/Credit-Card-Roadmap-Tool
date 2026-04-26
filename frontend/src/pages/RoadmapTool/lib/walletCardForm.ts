import type {
  Card,
  FutureCardUpdatePayload,
  OwnedCardUpdatePayload,
  UpsertOverlayPayload,
} from '../../../api/client'

export function parseOptionalInt(s: string): number | null {
  const t = s.trim()
  if (!t) return null
  const n = Number.parseInt(t, 10)
  return Number.isNaN(n) ? NaN : n
}

export function buildWalletCardFields(
  subPoints: string,
  subMinSpend: string,
  subMonths: string,
  annualBonus: string,
  annualFee: string,
  firstYearFee: string
):
  | {
      ok: true
      sub_points: number | null
      sub_min_spend: number | null
      sub_months: number | null
      annual_bonus: number | null
      annual_fee: number | null
      first_year_fee: number | null
    }
  | { ok: false; message: string } {
  const sub = parseOptionalInt(subPoints)
  if (subPoints.trim() !== '' && (Number.isNaN(sub!) || sub! < 0)) {
    return { ok: false, message: 'SUB points must be a non-negative integer or empty.' }
  }
  const sub_min_spend = parseOptionalInt(subMinSpend)
  if (subMinSpend.trim() !== '' && (Number.isNaN(sub_min_spend!) || sub_min_spend! < 0)) {
    return { ok: false, message: 'SUB min spend must be a non-negative integer or empty.' }
  }
  const sub_months = parseOptionalInt(subMonths)
  if (subMonths.trim() !== '' && (Number.isNaN(sub_months!) || sub_months! < 0)) {
    return { ok: false, message: 'SUB months must be a non-negative integer or empty.' }
  }
  const annual_bonus = parseOptionalInt(annualBonus)
  if (annualBonus.trim() !== '' && (Number.isNaN(annual_bonus!) || annual_bonus! < 0)) {
    return { ok: false, message: 'Annual bonus must be a non-negative integer or empty.' }
  }

  const afRaw = annualFee.trim()
  let annual_fee: number | null
  if (afRaw === '') {
    annual_fee = null
  } else {
    annual_fee = Number.parseFloat(afRaw)
    if (Number.isNaN(annual_fee) || annual_fee < 0) {
      return { ok: false, message: 'Annual fee must be a non-negative number or empty.' }
    }
  }

  const fyRaw = firstYearFee.trim()
  let first_year_fee: number | null
  if (fyRaw === '') {
    first_year_fee = null
  } else {
    const fy = Number.parseFloat(fyRaw)
    if (Number.isNaN(fy) || fy < 0) {
      return { ok: false, message: 'First-year fee must be a non-negative number or empty.' }
    }
    first_year_fee = fy
  }

  return {
    ok: true,
    sub_points: subPoints.trim() === '' ? null : sub,
    sub_min_spend: subMinSpend.trim() === '' ? null : sub_min_spend,
    sub_months: subMonths.trim() === '' ? null : sub_months,
    annual_bonus: annualBonus.trim() === '' ? null : annual_bonus,
    annual_fee,
    first_year_fee,
  }
}

/** When a parsed value matches the library default, store null on the row
 * (inherit). Used so unmodified inputs become null on the wire. */
function intOverride(parsed: number | null, lib: number | null | undefined): number | null {
  if (parsed === null) return null
  if (lib != null && parsed === lib) return null
  return parsed
}

function floatOverride(parsed: number | null, lib: number | null | undefined): number | null {
  if (parsed === null) return null
  if (lib != null && Math.abs(parsed - lib) < 1e-9) return null
  return parsed
}

export type BuiltWalletFields = Extract<
  ReturnType<typeof buildWalletCardFields>,
  { ok: true }
>

/** Build a payload for updating an OWNED CardInstance (Profile/WalletTab).
 * Uses absolute opening_date/closed_date and lets the user-set fields fall
 * to null when they match the library default. */
export function walletFormToOwnedUpdatePayload(
  built: BuiltWalletFields,
  lib: Card,
  openingDate: string,
  closedDate: string | null,
  productChangeDate: string | null,
  secondaryCurrencyRate?: number | null,
): OwnedCardUpdatePayload {
  return {
    opening_date: openingDate,
    closed_date: closedDate,
    product_change_date: productChangeDate,
    sub_points: intOverride(built.sub_points, lib.sub_points ?? undefined),
    sub_min_spend: intOverride(built.sub_min_spend, lib.sub_min_spend ?? undefined),
    sub_months: intOverride(built.sub_months, lib.sub_months ?? undefined),
    annual_bonus: intOverride(built.annual_bonus, lib.annual_bonus ?? undefined),
    annual_fee: floatOverride(built.annual_fee, lib.annual_fee),
    first_year_fee: floatOverride(built.first_year_fee, lib.first_year_fee ?? undefined),
    secondary_currency_rate: secondaryCurrencyRate !== undefined
      ? floatOverride(secondaryCurrencyRate, lib.secondary_currency_rate ?? undefined)
      : undefined,
  }
}

/** Build a payload for updating a SCENARIO FUTURE card. Same as owned but
 * may also include `pc_from_instance_id`, `is_enabled`, etc. */
export function walletFormToFutureUpdatePayload(
  built: BuiltWalletFields,
  lib: Card,
  openingDate: string,
  closedDate: string | null,
  productChangeDate: string | null,
  pcFromInstanceId: number | null,
  secondaryCurrencyRate?: number | null,
): FutureCardUpdatePayload {
  return {
    ...walletFormToOwnedUpdatePayload(
      built,
      lib,
      openingDate,
      closedDate,
      productChangeDate,
      secondaryCurrencyRate,
    ),
    pc_from_instance_id: pcFromInstanceId,
  }
}

/** Build an OVERLAY upsert payload. Overlays are sparse: only fields the
 * user explicitly modified relative to the underlying card_instance should
 * be sent. To keep the form simple, we currently send the user's typed
 * values where they differ from the resolved baseline (caller passes the
 * baseline). */
export function walletFormToOverlayUpsertPayload(
  built: BuiltWalletFields,
  baseline: {
    sub_points: number | null
    sub_min_spend: number | null
    sub_months: number | null
    annual_bonus: number | null
    annual_fee: number | null
    first_year_fee: number | null
    secondary_currency_rate: number | null
    closed_date: string | null
  },
  closedDate: string | null,
  secondaryCurrencyRate: number | null,
  isEnabled: boolean | null,
): UpsertOverlayPayload {
  function sameInt(a: number | null, b: number | null): boolean {
    if (a == null && b == null) return true
    if (a == null || b == null) return false
    return a === b
  }
  function sameFloat(a: number | null, b: number | null): boolean {
    if (a == null && b == null) return true
    if (a == null || b == null) return false
    return Math.abs(a - b) < 1e-9
  }
  // closed_date in an overlay can't express "force active" via null alone
  // — null means "inherit from underlying instance", so a scenario can't
  // override a closed owned card to be active without the explicit clear
  // flag. When the user picks Active in overlay mode, send
  // closed_date_clear=true; otherwise false.
  const closedDateClear = closedDate === null
  return {
    sub_points: sameInt(built.sub_points, baseline.sub_points) ? null : built.sub_points,
    sub_min_spend: sameInt(built.sub_min_spend, baseline.sub_min_spend) ? null : built.sub_min_spend,
    sub_months: sameInt(built.sub_months, baseline.sub_months) ? null : built.sub_months,
    annual_bonus: sameInt(built.annual_bonus, baseline.annual_bonus) ? null : built.annual_bonus,
    annual_fee: sameFloat(built.annual_fee, baseline.annual_fee) ? null : built.annual_fee,
    first_year_fee: sameFloat(built.first_year_fee, baseline.first_year_fee) ? null : built.first_year_fee,
    secondary_currency_rate: sameFloat(secondaryCurrencyRate, baseline.secondary_currency_rate)
      ? null
      : secondaryCurrencyRate,
    closed_date: closedDate === baseline.closed_date ? null : closedDate,
    closed_date_clear: closedDateClear,
    is_enabled: isEnabled,
  }
}
