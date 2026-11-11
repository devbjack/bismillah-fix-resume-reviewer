import { CircleX, LayoutDashboard, LoaderCircle, TriangleAlert } from 'lucide-react'
import { Link } from 'react-router'
import type { RankRow } from '../api'

interface Props {
  jobId: number
  rows: RankRow[]
  selectedId: number | null
  overviewSelected: boolean
}

export function ApplicantList({ jobId, rows, selectedId, overviewSelected }: Props) {
  const done = rows.filter((r) => r.status === 'done').length
  return (
    <nav aria-label="Ranked applicants" className="flex min-h-0 flex-1 flex-col">
      <div className="px-2 pt-3">
        <Link
          to={`/jobs/${jobId}`}
          aria-current={overviewSelected ? 'page' : undefined}
          className={`flex min-h-11 items-center gap-2.5 rounded-lg px-3 text-sm font-semibold transition-colors duration-150 ${
            overviewSelected ? 'bg-white shadow-[0_1px_4px_rgba(74,21,75,0.12)] ring-1 ring-aubergine' : 'hover:bg-white/70'
          }`}
        >
          <LayoutDashboard className="size-4 text-aubergine" aria-hidden />
          Overview
        </Link>
      </div>
      <div className="flex items-baseline justify-between border-t border-aubergine-mute/40 px-4 pb-3 pt-4 mt-3">
        <h2 className="text-sm font-bold tracking-[0.2px]">Applicants</h2>
        <span className="text-xs tabular-nums text-ink-mute">
          {done} ranked{rows.length > done ? ` of ${rows.length}` : ''}
        </span>
      </div>
      {rows.length === 0 && <p className="px-4 text-xs text-ink-mute">Applicants appear here once resumes are uploaded.</p>}
      <ol className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto px-2 pb-3">
        {rows.map((row) => {
          const selected = row.id === selectedId
          const failed = row.status === 'failed'
          return (
            <li key={row.id}>
              <Link
                to={`/jobs/${jobId}/applicants/${row.id}`}
                aria-current={selected ? 'true' : undefined}
                className={`grid min-h-12 grid-cols-[2rem_1fr_auto] items-center gap-2 rounded-lg px-2 py-2 transition-colors duration-150 ${
                  selected ? 'bg-white shadow-[0_1px_4px_rgba(74,21,75,0.12)] ring-1 ring-aubergine' : 'hover:bg-white/70'
                } ${failed ? 'text-ink-mute' : ''}`}
              >
                <span className="text-right text-sm tabular-nums text-ink-mute">{row.rank ?? ''}</span>
                <span className="min-w-0">
                  <span className={`block truncate text-sm ${selected ? 'font-semibold' : ''}`}>{row.filename}</span>
                  {failed && <span className="block truncate text-xs">{row.error}</span>}
                </span>
                <span className="flex items-center gap-1.5">
                  {row.status === 'done' && row.flagged && (
                    <TriangleAlert className="size-4 text-error" aria-label="Probably missing a must-have" />
                  )}
                  {row.status === 'done' && (
                    <span className="w-8 text-right font-bold tabular-nums text-aubergine">{row.score}</span>
                  )}
                  {row.status === 'queued' && (
                    <LoaderCircle className="size-4 animate-spin text-ink-mute" aria-label="Scoring" />
                  )}
                  {failed && <CircleX className="size-4" aria-label="Could not be scored" />}
                </span>
              </Link>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
