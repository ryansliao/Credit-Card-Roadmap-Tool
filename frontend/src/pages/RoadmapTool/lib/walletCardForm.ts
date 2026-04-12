import type { Card, UpdateWalletCardPayload, WalletCardAcquisitionType } from '../../../api/client'

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

/** When a parsed value matches the library default, store null on the wallet row (inherit). */
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

/** Map form state + library card to a PATCH payload (null = inherit library where applicable). */
export function walletFormToUpdatePayload(
  built: BuiltWalletFields,
  lib: Card,
  addedDate: string,
  acquisitionType: WalletCardAcquisitionType,
  secondaryCurrencyRate?: number | null,
): UpdateWalletCardPayload {
  return {
    added_date: addedDate,
    acquisition_type: acquisitionType,
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
