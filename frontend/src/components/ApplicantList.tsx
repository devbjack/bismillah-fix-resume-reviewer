import { CircleX, LoaderCircle, TriangleAlert } from 'lucide-react'
import { Link } from 'react-router'
import type { RankRow } from '../api'

interface Props {
  jobId: number
  rows: RankRow[]
  selectedId: number | null
}

export function ApplicantList({ jobId, rows, selectedId }: Props) {
  const done = rows.filter((r) => r.status === 'done').length
  return (
    <nav aria-label="Ranked applicants" className="flex min-h-0 flex-col">
      <div className="flex items-baseline justify-between px-4 pb-3 pt-4">
        <h2 className="text-sm font-bold tracking-[0.2px]">Applicants</h2>
        <span className="text-xs tabular-nums text-ink-mute">
          {done} ranked{rows.length > done ? ` of ${rows.length}` : ''}
        </span>
      </div>
      <ol className="flex flex-col gap-0.5 overflow-y-auto px-2 pb-3">
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
