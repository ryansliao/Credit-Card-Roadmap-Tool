import { useState } from 'react'
import { ModalBackdrop } from '../../../../components/ModalBackdrop'
import { InfoIconButton, InfoPopover } from '../../../../components/InfoPopover'

function formatDuration(years: number, months: number): string {
  const total = years * 12 + months
  const y = Math.floor(total / 12)
  const m = total % 12
  if (y === 0) return `${m} Months`
  if (m === 0) return `${y} Years`
  return `${y} Years, ${m} Months`
}

type InfoTopic = 'duration' | 'foreign' | null

interface Props {
  durationYears: number
  durationMonths: number
  foreignSpendPercent: number
  onDurationChange: (years: number, months: number) => void
  onDurationCommit: (years: number, months: number) => void
  onForeignSpendChange: (pct: number) => void
  onForeignSpendCommit: (pct: number) => void
  onClose: () => void
}

export function WalletSettingsModal({
  durationYears,
  durationMonths,
  foreignSpendPercent,
  onDurationChange,
  onDurationCommit,
  onForeignSpendChange,
  onForeignSpendCommit,
  onClose,
}: Props) {
  const [localForeign, setLocalForeign] = useState(foreignSpendPercent)
  const [infoTopic, setInfoTopic] = useState<InfoTopic>(null)

  return (
    <ModalBackdrop onClose={onClose} label="Wallet Settings" className="w-full max-w-lg">
      <div className="bg-slate-900 border border-slate-700 rounded-xl p-5 space-y-5">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-200">Wallet Settings</h3>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-500 hover:text-slate-200 transition-colors"
            aria-label="Close"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Duration slider */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-1">
              <span className="text-xs text-slate-400">Duration</span>
              <InfoIconButton onClick={() => setInfoTopic('duration')} label="How duration affects calculation" />
            </div>
            <span className="text-xs font-medium text-slate-200 tabular-nums">
              {formatDuration(durationYears, durationMonths)}
            </span>
          </div>
          <input
            type="range"
            min={1}
            max={60}
            value={durationYears * 12 + durationMonths}
            onChange={(e) => {
              const total = Number(e.target.value)
              onDurationChange(Math.floor(total / 12), total % 12)
            }}
            onMouseUp={(e) => {
              const total = Number((e.target as HTMLInputElement).value)
              onDurationCommit(Math.floor(total / 12), total % 12)
            }}
            onTouchEnd={(e) => {
              const total = Number((e.target as HTMLInputElement).value)
              onDurationCommit(Math.floor(total / 12), total % 12)
            }}
            className="w-full h-1.5 accent-indigo-500 cursor-pointer"
          />
          <div className="flex justify-between text-[10px] text-slate-600 mt-1">
            <span>1M</span>
            <span>1Y</span>
            <span>2Y</span>
            <span>3Y</span>
            <span>4Y</span>
            <span>5Y</span>
          </div>
        </div>

        {/* Foreign spend percentage slider */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-1">
              <span className="text-xs text-slate-400">Foreign Spend</span>
              <InfoIconButton onClick={() => setInfoTopic('foreign')} label="How foreign spend affects calculation" />
            </div>
            <span className="text-xs font-medium text-slate-200 tabular-nums">
              {Math.round(localForeign)}%
            </span>
          </div>
          <input
            type="range"
            min={0}
            max={100}
            value={localForeign}
            onChange={(e) => {
              const v = Number(e.target.value)
              setLocalForeign(v)
              onForeignSpendChange(v)
            }}
            onMouseUp={(e) => {
              const v = Number((e.target as HTMLInputElement).value)
              onForeignSpendCommit(v)
            }}
            onTouchEnd={(e) => {
              const v = Number((e.target as HTMLInputElement).value)
              onForeignSpendCommit(v)
            }}
            className="w-full h-1.5 accent-indigo-500 cursor-pointer"
          />
          <div className="flex justify-between text-[10px] text-slate-600 mt-1">
            <span>0%</span>
            <span>25%</span>
            <span>50%</span>
            <span>75%</span>
            <span>100%</span>
          </div>
        </div>
      </div>

      {infoTopic === 'duration' && (
        <InfoPopover title="Duration" onClose={() => setInfoTopic(null)}>
          <p>
            How long to project the wallet's value. The calculator amortizes
            one-time benefits (sign-up bonuses, first-year bonuses, first-year
            fee waivers, one-time credits) across this period to produce an
            average annual EAF.
          </p>
          <div>
            <p className="text-slate-300 font-medium mb-1">Effect on EAF</p>
            <p>
              Longer durations spread one-time benefits thinner, so cards with
              big SUBs look less valuable per year. Recurring benefits (annual
              fees, statement credits, category earn) are unaffected.
            </p>
          </div>
          <div>
            <p className="text-slate-300 font-medium mb-1">Effect on roadmap</p>
            <p>
              Cards with future <span className="text-slate-300">added_date</span> only count from when they
              become active, so a longer window lets future cards contribute
              proportionally more to the wallet total.
            </p>
          </div>
        </InfoPopover>
      )}

      {infoTopic === 'foreign' && (
        <InfoPopover title="Foreign Spend" onClose={() => setInfoTopic(null)}>
          <p>
            Percentage of your total spend that occurs as foreign transactions.
            Each spend category is split: the foreign portion is allocated
            separately from the domestic portion.
          </p>
          <div>
            <p className="text-slate-300 font-medium mb-1">FTF priority</p>
            <p>
              Foreign spend goes to no-FTF cards first. If any no-FTF Visa or
              Mastercard exists in the wallet, it gets priority over no-FTF
              cards on other networks (e.g. American Express).
            </p>
          </div>
          <div>
            <p className="text-slate-300 font-medium mb-1">Per-category multiplier</p>
            <p>
              On the foreign portion of a category, the eligible card earns
              {' '}<span className="font-mono text-[11px] text-slate-300">max(category_mult, foreign_transactions_mult)</span>.
              So a card with a "Foreign Transactions" multiplier (e.g. Atmos
              Summit at 3x) earns its full bonus on foreign Groceries even if
              its normal Groceries rate is lower.
            </p>
          </div>
          <div>
            <p className="text-slate-300 font-medium mb-1">Fallback</p>
            <p>
              If every card in the wallet charges a foreign transaction fee,
              cards compete normally and the user incurs the ~3% fee on the
              winning card's foreign spend.
            </p>
          </div>
        </InfoPopover>
      )}
    </ModalBackdrop>
  )
}
