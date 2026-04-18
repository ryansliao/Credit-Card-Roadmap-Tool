import { InfoPopover } from '../../../../components/InfoPopover'

interface Props {
  onClose: () => void
}

export function MethodologyInfoPopover({ onClose }: Props) {
  return (
    <InfoPopover title="Calculation Methodology" onClose={onClose}>
      <div>
        <p className="text-slate-300 font-medium mb-1">Category allocation</p>
        <p>
          Each spend category is awarded to the card(s) with the highest
          {' '}<span className="font-mono text-[11px] text-slate-300">multiplier x CPP x earn_bonus_factor + secondary_bonus</span>.
          Tied cards split the category dollars evenly. The LP optimizer
          solves this per time segment when cards have date context.
        </p>
      </div>
      <div>
        <p className="text-slate-300 font-medium mb-1">Time segmentation</p>
        <p>
          When cards have open/close dates, the projection window is split
          into segments at every card activation, closure, SUB earn, and
          cap period boundary. Each segment solves its own allocation with
          only the cards active during that period.
        </p>
      </div>
      <div>
        <p className="text-slate-300 font-medium mb-1">Currency upgrades</p>
        <p>
          If a card's currency converts to a higher-value currency earned by
          another wallet card (e.g. UR Cash to Chase UR via Sapphire), the
          earn is converted at the upgrade rate and valued at the target CPP.
        </p>
      </div>
      <div>
        <p className="text-slate-300 font-medium mb-1">SUB tracking</p>
        <p>
          The SUB planner schedules spend across cards to hit sign-up bonus
          minimums before their deadlines. Cards needing extra spend get
          priority allocation during their SUB window. The opportunity cost
          of redirecting spend is tracked separately.
        </p>
      </div>
      <div>
        <p className="text-slate-300 font-medium mb-1">Bilt 2.0 housing</p>
        <p>
          Cards with the Bilt housing mechanic choose between tiered
          housing earn (0.5x-1.25x on rent/mortgage based on non-housing
          spend ratio) and Bilt Cash mode (three-tier bonus on non-housing
          from converting Bilt Cash via housing payments). The calculator
          picks whichever mode yields higher dollar value.
        </p>
      </div>
      <div>
        <p className="text-slate-300 font-medium mb-1">Housing processing fee</p>
        <p>
          Rent and mortgage payments via credit card typically incur a ~3%
          processing fee from the payment platform. Cards that waive this
          fee (Bilt) compete at full value on housing categories; other
          cards are penalized by the fee amount, which usually makes their
          1-1.5x earn net-negative.
        </p>
      </div>
      <div>
        <p className="text-slate-300 font-medium mb-1">Foreign spend</p>
        <p>
          When a wallet-level foreign spend percentage is set, eligible
          categories are split into domestic and foreign buckets. Cards
          without a foreign transaction fee and on Visa/Mastercard networks
          are preferred for the foreign portion.
        </p>
      </div>
      <div>
        <p className="text-slate-300 font-medium mb-1">EAF formula</p>
        <p className="px-2 py-1 bg-slate-800 rounded font-mono text-[11px] text-slate-300 leading-snug">
          (earn x cpp + sub + credits - fees) / years
        </p>
        <p className="mt-1">
          A negative EAF means the card returns more value than it costs.
          One-time benefits (SUB, first-year bonus) are amortised over the
          projection duration.
        </p>
      </div>
    </InfoPopover>
  )
}
