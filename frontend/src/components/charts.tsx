import type { Summary } from '../api'
import { TypeChip } from './ui'

const pct = (part: number, whole: number) => (whole ? Math.round((100 * part) / whole) : null)

const RADIUS = 48
const RING = 2 * Math.PI * RADIUS

interface DonutProps {
  qualified: number
  notQualified: number
  failed: number
}

/** Qualified / missing a must-have / could not score, as SVG ring segments starting at 12 o'clock. */
export function Donut({ qualified, notQualified, failed }: DonutProps) {
  const slices = [
    { label: 'Qualified', count: qualified, color: 'var(--color-success)' },
    { label: 'Missing a must-have', count: notQualified, color: 'var(--color-aubergine-mute)' },
    { label: 'Could not score', count: failed, color: 'var(--color-error)' },
  ]
  const total = qualified + notQualified + failed
  const share = pct(qualified, qualified + notQualified)
  let offset = 0

  return (
    <div className="flex flex-wrap items-center gap-6">
      <svg
        viewBox="0 0 120 120"
        className="size-36 shrink-0"
        role="img"
        aria-label={`${share ?? 'No'}${share === null ? '' : '%'} qualified: ${qualified} of ${qualified + notQualified} scored, ${failed} could not be scored`}
      >
        <circle cx="60" cy="60" r={RADIUS} fill="none" stroke="var(--color-hairline)" strokeWidth="14" />
        <g transform="rotate(-90 60 60)">
          {slices.map((s) => {
            if (!s.count || !total) return null
            const length = (RING * s.count) / total
            const el = (
              <circle
                key={s.label}
                cx="60"
                cy="60"
                r={RADIUS}
                fill="none"
                stroke={s.color}
                strokeWidth="14"
                strokeDasharray={`${length} ${RING - length}`}
                strokeDashoffset={-offset}
              />
            )
            offset += length
            return el
          })}
        </g>
        <text x="60" y="66" textAnchor="middle" className="fill-ink text-[22px] font-bold tabular-nums">
          {share === null ? '–' : `${share}%`}
        </text>
      </svg>
      <ul className="flex flex-col gap-2 text-sm">
        {slices.map((s) => (
          <li key={s.label} className="flex items-center gap-2">
            <span className="size-3 shrink-0 rounded-[3px]" style={{ background: s.color }} aria-hidden />
            <span>{s.label}</span>
            <span className="font-bold tabular-nums">{s.count}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

const bandLabel = (i: number) => (i === 9 ? '90–100' : `${i * 10}–${i * 10 + 9}`)

/** Ten score bands; an empty band keeps a 2px stub so the axis still reads. */
export function Histogram({ bins }: { bins: number[] }) {
  const max = Math.max(...bins, 1)
  const described = bins.map((n, i) => (n ? `${bandLabel(i)}: ${n}` : null)).filter(Boolean)
  return (
    <div>
      <div
        role="img"
        aria-label={described.length ? `Score distribution. ${described.join(', ')}` : 'No scores yet'}
        className="flex h-40 items-end gap-1.5 border-b border-hairline"
      >
        {bins.map((n, i) => (
          <div
            key={i}
            title={`${bandLabel(i)}: ${n} applicant${n === 1 ? '' : 's'}`}
            className="flex h-full flex-1 cursor-default items-end"
          >
            <div
              className={`w-full rounded-t-sm ${n ? 'bg-aubergine transition-colors duration-150 hover:bg-aubergine-press' : 'bg-hairline'}`}
              style={{ height: n ? `${(100 * n) / max}%` : '2px' }}
            />
          </div>
        ))}
      </div>
      <div className="mt-1.5 flex justify-between text-[11px] tabular-nums text-ink-mute" aria-hidden>
        {[0, 20, 40, 60, 80, 100].map((t) => (
          <span key={t}>{t}</span>
        ))}
      </div>
    </div>
  )
}

/** Share of scored applicants meeting each requirement; must-haves come first from the API. */
export function CoverageBars({ rows }: { rows: Summary['coverage'] }) {
  return (
    <ul className="flex flex-col gap-3.5">
      {rows.map((r) => {
        const share = pct(r.met, r.scored)
        return (
          <li key={r.requirement_id} className="flex flex-col gap-1.5">
            <div className="flex items-start justify-between gap-3 text-sm">
              <span className="min-w-0 leading-snug">
                <TypeChip type={r.type} className="mr-2 align-[1px]" />
                {r.text}
              </span>
              <span className="shrink-0 tabular-nums text-ink-mute">
                {share === null ? '–' : `${r.met} of ${r.scored} · ${share}%`}
              </span>
            </div>
            <div className="h-2 rounded-pill bg-hairline" aria-hidden>
              <div className="h-full rounded-pill bg-aubergine" style={{ width: `${share ?? 0}%` }} />
            </div>
          </li>
        )
      })}
    </ul>
  )
}
