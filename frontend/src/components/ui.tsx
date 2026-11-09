import { LoaderCircle } from 'lucide-react'
import type { ButtonHTMLAttributes, ReactNode } from 'react'

type Variant = 'primary' | 'secondary' | 'outline' | 'danger'

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-aubergine text-white hover:bg-aubergine-press active:bg-aubergine-press',
  secondary: 'bg-lavender text-ink hover:bg-aubergine-mute/60',
  outline: 'bg-white text-aubergine ring-2 ring-inset ring-aubergine hover:bg-lavender',
  danger: 'bg-white text-error ring-1 ring-inset ring-hairline hover:ring-error',
}

const BASE =
  'inline-flex items-center justify-center gap-2 rounded-pill font-bold tracking-[0.2px] ' +
  'transition-colors duration-150 cursor-pointer disabled:cursor-not-allowed disabled:opacity-50'

export function buttonClass(variant: Variant = 'primary', size: 'md' | 'sm' = 'md') {
  const pad = size === 'md' ? 'min-h-11 px-7 py-2.5 text-base' : 'min-h-9 px-4 py-1.5 text-sm'
  return `${BASE} ${pad} ${VARIANTS[variant]}`
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: 'md' | 'sm'
  busy?: boolean
}

export function Button({ variant = 'primary', size = 'md', busy, children, className = '', disabled, ...rest }: ButtonProps) {
  return (
    <button className={`${buttonClass(variant, size)} ${className}`} disabled={disabled || busy} aria-busy={busy} {...rest}>
      {busy && <LoaderCircle className="size-4 animate-spin" aria-hidden />}
      {children}
    </button>
  )
}

export const inputClass =
  'w-full min-h-11 rounded-sm border border-hairline bg-white px-3 py-2.5 text-base text-ink ' +
  'placeholder:text-ink-mute focus:border-aubergine focus:outline-none focus-visible:outline-none ' +
  'focus:ring-2 focus:ring-aubergine/25 transition-colors duration-150'

export function TypeChip({ type, className = '' }: { type: 'must' | 'nice'; className?: string }) {
  return type === 'must' ? (
    <span className={`inline-flex shrink-0 items-center rounded-pill bg-aubergine px-2.5 py-1 text-[11px] font-bold leading-none tracking-[0.96px] text-white ${className}`}>
      MUST
    </span>
  ) : (
    <span className={`inline-flex shrink-0 items-center rounded-pill bg-cream px-2.5 py-1 text-[11px] font-bold leading-none tracking-[0.96px] text-ink ${className}`}>
      NICE
    </span>
  )
}

export function Notice({ tone = 'info', children }: { tone?: 'info' | 'error'; children: ReactNode }) {
  const styles = tone === 'error' ? 'bg-error/8 text-error' : 'bg-lavender text-ink'
  return (
    <div role={tone === 'error' ? 'alert' : 'status'} className={`rounded-lg px-4 py-3 text-sm leading-relaxed ${styles}`}>
      {children}
    </div>
  )
}
