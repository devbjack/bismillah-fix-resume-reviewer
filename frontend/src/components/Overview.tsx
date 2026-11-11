import { ChevronRight } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router'
import { getSummary, type Summary } from '../api'
import { CoverageBars, Donut, Histogram } from './charts'
import { Notice, buttonClass } from './ui'

interface Props {
  jobId: number
  /** changes whenever scoring progress changes, so the summary refetches */
  version: string
}

export function Overview({ jobId, version }: Props) {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    getSummary(jobId).then(
      (s) => {
        if (live) {
          setSummary(s)
          setError(null)
        }
      },
      (e: Error) => live && setError(e.message),
    )
    return () => {
      live = false
    }
  }, [jobId, version])

  if (error) return <Notice>Couldn't load the summary: {error}</Notice>
  if (!summary) return <OverviewSkeleton />

  if (summary.total === 0) {
    return (
      <div className="rounded-xl bg-cream px-6 py-12 text-center">
        <p className="font-semibold">Upload resumes in Setup to see the summary.</p>
        <Link to={`/jobs/${jobId}/setup`} className={`${buttonClass('primary')} mt-5`}>
          Go to Setup
        </Link>
      </div>
    )
  }

  const s = summary
  const share = s.scored ? Math.round((100 * s.qualified) / s.scored) : null
  const review = (id: number) => `/jobs/${jobId}/applicants/${id}`

  return (
    <div className="flex flex-col gap-5">
      <h2 className="sr-only">Overview</h2>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Tile label="Applicants" value={s.total} caption={`${s.scored} scored`} />
        <Tile label="Qualified" value={share === null ? '–' : `${share}%`} caption={`${s.qualified} of ${s.scored}`} />
        <Tile
          label="Best score"
          value={s.best ? s.best.score : '–'}
          caption={
            s.best ? (
              <Link to={review(s.best.id)} className="block truncate text-link hover:text-link-hover hover:underline">
                {s.best.filename}
              </Link>
            ) : (
              'none scored yet'
            )
          }
        />
        <Tile label="Average" value={s.average_score === null ? '–' : Math.round(s.average_score)} caption={`of ${s.scored} scored`} />
        <Tile label="Failed" value={s.failed} caption="couldn't be read" />
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <Panel title="Qualified candidates" note="Every must-have met">
          <Donut qualified={s.qualified} notQualified={s.scored - s.qualified} failed={s.failed} />
        </Panel>
        <Panel title="Score distribution" note="Applicants per 10-point band" className="lg:col-span-2">
          <Histogram bins={s.histogram} />
        </Panel>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Panel title="Requirement coverage" note="Share of scored applicants who meet each one">
          <CoverageBars rows={s.coverage} />
        </Panel>
        <Panel title="Top 5 qualified">
          {s.top.length === 0 ? (
            <p className="text-sm text-ink-mute">No one meets every must-have yet. Applicants marked ⚠ in the list are the closest.</p>
          ) : (
            <ol className="divide-y divide-hairline">
              {s.top.map((t, i) => (
                <li key={t.id}>
                  <Link
                    to={review(t.id)}
                    className="group grid min-h-12 grid-cols-[1.5rem_minmax(0,1fr)_auto_auto] items-center gap-3 rounded-lg px-2 py-2 transition-colors duration-150 hover:bg-lavender"
                  >
                    <span className="text-sm tabular-nums text-ink-mute">{i + 1}</span>
                    <span className="truncate text-sm font-semibold">{t.filename}</span>
                    <span className="text-xs tabular-nums text-ink-mute">
                      {t.must_met}/{t.must_total} must-haves
                    </span>
                    <span className="flex items-center gap-1 font-bold tabular-nums text-aubergine">
                      {t.score}
                      <ChevronRight className="size-4 text-ink-mute transition-transform duration-150 group-hover:translate-x-0.5" aria-hidden />
                    </span>
                  </Link>
                </li>
              ))}
            </ol>
          )}
        </Panel>
      </div>
    </div>
  )
}

function Tile({ label, value, caption }: { label: string; value: ReactNode; caption: ReactNode }) {
  return (
    <div className="min-w-0 rounded-xl border border-hairline px-4 py-4">
      <p className="text-sm font-semibold text-ink-mute">{label}</p>
      <p className="mt-1 text-[40px] font-bold leading-none tracking-[-0.5px] text-aubergine tabular-nums">{value}</p>
      <div className="mt-2 text-sm text-ink-mute">{caption}</div>
    </div>
  )
}

function Panel({ title, note, className = '', children }: { title: string; note?: string; className?: string; children: ReactNode }) {
  return (
    <section className={`min-w-0 rounded-xl border border-hairline p-5 ${className}`}>
      <h3 className="font-semibold">{title}</h3>
      {note && <p className="mt-0.5 text-sm text-ink-mute">{note}</p>}
      <div className="mt-4">{children}</div>
    </section>
  )
}

function OverviewSkeleton() {
  return (
    <div className="flex animate-pulse flex-col gap-5" aria-label="Loading summary">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        {[0, 1, 2, 3, 4].map((i) => (
          <div key={i} className="h-[118px] rounded-xl bg-hairline" />
        ))}
      </div>
      <div className="grid gap-5 lg:grid-cols-3">
        <div className="h-64 rounded-xl bg-hairline" />
        <div className="h-64 rounded-xl bg-hairline lg:col-span-2" />
      </div>
    </div>
  )
}
