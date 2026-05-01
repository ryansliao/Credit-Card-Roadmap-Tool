import type { ReactNode, HTMLAttributes } from 'react'

type Variant = 'panel' | 'inset' | 'bare'
type Padding = 'none' | 'sm' | 'md' | 'lg'

interface Props extends Omit<HTMLAttributes<HTMLDivElement>, 'children'> {
  variant?: Variant
  padding?: Padding
  /** Apply --shadow-card. Default false (editorial leans on borders). */
  elevated?: boolean
  children: ReactNode
}

const VARIANT_CLASS: Record<Variant, string> = {
  panel: 'bg-surface border border-divider shadow-card',
  inset: 'bg-surface-2 border border-divider',
  bare: 'bg-transparent',
}
const PADDING_CLASS: Record<Padding, string> = {
  none: '',
  sm: 'p-3',
  md: 'p-5',
  lg: 'p-7',
}

export function Surface({
  variant = 'panel',
  padding = 'md',
  elevated = false,
  className = '',
  children,
  ...rest
}: Props) {
  return (
    <div
      {...rest}
      className={`rounded-lg ${VARIANT_CLASS[variant]} ${PADDING_CLASS[padding]} ${elevated ? 'shadow-card' : ''} ${className}`}
    >
      {children}
    </div>
  )
}
