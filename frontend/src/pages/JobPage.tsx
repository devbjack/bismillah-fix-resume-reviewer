import { ArrowLeft, Download, Settings2, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link, Navigate, useLocation, useNavigate, useParams } from 'react-router'
import { deleteJob, exportUrl, getJob, getRanking, getStatus, type Job, type RankRow, type Status } from '../api'
import { ApplicantList } from '../components/ApplicantList'
import { ApplicantReview } from '../components/ApplicantReview'
import { Overview } from '../components/Overview'
import { SetupView } from '../components/SetupView'
import { Button, Notice, buttonClass } from '../components/ui'

type View = 'overview' | 'applicant' | 'setup'

export function JobPage() {
  const params = useParams()
  const jobId = Number(params.jobId)
  const applicantParam = params.applicantId ? Number(params.applicantId) : null
  const navigate = useNavigate()
  const location = useLocation()
  const warning = (location.state as { warning?: string | null } | null)?.warning
  const view: View = applicantParam !== null ? 'applicant' : location.pathname.endsWith('/setup') ? 'setup' : 'overview'

  const [job, setJob] = useState<Job | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [rows, setRows] = useState<RankRow[]>([])
  const [rowsLoaded, setRowsLoaded] = useState(false)
  const [status, setStatus] = useState<Status>({ done: 0, total: 0 })
  const [deleting, setDeleting] = useState(false)
  const [syncError, setSyncError] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  // never rejects: a failed refresh shows a notice instead of freezing the progress silently
  const refresh = useCallback(async () => {
    try {
      const [s, r] = await Promise.all([getStatus(jobId), getRanking(jobId)])
      setStatus(s)
      setRows(r)
      setRowsLoaded(true)
      setSyncError(null)
    } catch (e) {
      setSyncError((e as Error).message)
    }
  }, [jobId])

  useEffect(() => {
    getJob(jobId).then(setJob, () => setNotFound(true))
    refresh()
  }, [jobId, refresh])

  // poll once a second while resumes are still being scored
  // also keep polling while any row still reads queued: status and ranking are fetched concurrently
  const scoring = status.done < status.total || rows.some((r) => r.status === 'queued')
  useEffect(() => {
    if (!scoring) return
    const t = setInterval(refresh, 1000)
    return () => clearInterval(t)
  }, [scoring, refresh])

  async function remove() {
    if (!job || !confirm(`Delete "${job.name}" and all ${status.total} uploaded resumes? This can't be undone.`)) return
    setDeleting(true)
    setDeleteError(null)
    try {
      await deleteJob(job.id)
      navigate('/')
    } catch (e) {
      setDeleteError((e as Error).message)
      setDeleting(false)
    }
  }

  if (notFound) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
        <Notice>This job doesn't exist anymore.</Notice>
        <Link to="/" className="mt-4 inline-block text-link hover:text-link-hover hover:underline">
          Back to jobs
        </Link>
      </div>
    )
  }
  if (!job) return <div className="mx-auto mt-10 h-8 max-w-7xl animate-pulse rounded bg-hairline px-4" aria-label="Loading job" />

  // a job without confirmed requirements has nothing to summarize yet
  if (job.status === 'draft' && view === 'overview') {
    return <Navigate to={`/jobs/${jobId}/setup`} replace state={location.state} />
  }
  const selected = rows.find((r) => r.id === applicantParam)
  // wait for the ranking before judging a deep link, then send old or foreign links to the overview
  if (view === 'applicant' && rowsLoaded && !selected) return <Navigate to={`/jobs/${jobId}`} replace />

  const pct = status.total ? Math.round((100 * status.done) / status.total) : 0

  return (
    // one minmax(0,1fr) row caps both columns at the window height so each scrolls on its own
    <div className="md:grid md:h-[calc(100dvh-3.5rem)] md:grid-cols-[300px_minmax(0,1fr)] md:grid-rows-[minmax(0,1fr)]">
      <aside className="flex max-h-[40vh] flex-col border-b border-hairline bg-cream md:max-h-none md:border-b-0 md:border-r">
        <ApplicantList jobId={jobId} rows={rows} selectedId={selected?.id ?? null} overviewSelected={view === 'overview'} />
      </aside>

      <div className="min-w-0 md:overflow-y-auto">
        <header className="z-10 border-b md:sticky md:top-0 border-hairline bg-white/95 px-5 py-4 backdrop-blur-sm sm:px-8">
          <Link to="/" className="inline-flex items-center gap-1.5 rounded-sm text-sm text-link hover:text-link-hover hover:underline">
            <ArrowLeft className="size-4" aria-hidden />
            All jobs
          </Link>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <h1 className="mr-auto min-w-0 text-[26px] font-bold leading-tight tracking-[-0.2px]">{job.name}</h1>
            {status.total > 0 && scoring && (
              <div className="flex w-44 flex-col gap-1">
                <span className="text-xs tabular-nums text-ink-mute">
                  {status.done} of {status.total} scored
                </span>
                <div
                  role="progressbar"
                  aria-label="Scoring progress"
                  aria-valuemin={0}
                  aria-valuemax={status.total}
                  aria-valuenow={status.done}
                  className="h-1.5 overflow-hidden rounded-pill bg-hairline"
                >
                  <div className="h-full rounded-pill bg-aubergine transition-[width] duration-500 ease-out" style={{ width: `${pct}%` }} />
                </div>
              </div>
            )}
            <Link to={`/jobs/${jobId}/setup`} aria-current={view === 'setup' ? 'page' : undefined} className={buttonClass('secondary', 'sm')}>
              <Settings2 className="size-4" aria-hidden />
              Setup
            </Link>
            {rows.length > 0 && (
              <a href={exportUrl(jobId)} className={buttonClass('secondary', 'sm')}>
                <Download className="size-4" aria-hidden />
                Export CSV
              </a>
            )}
            <Button variant="danger" size="sm" onClick={remove} busy={deleting}>
              <Trash2 className="size-4" aria-hidden />
              Delete job
            </Button>
          </div>
        </header>

        <div className="flex flex-col gap-5 p-5 sm:p-8">
          {syncError && <Notice>Lost contact with the app: {syncError}. Is it still running?</Notice>}
          {deleteError && <Notice>Couldn't delete this job: {deleteError}</Notice>}
          {view === 'overview' && <Overview jobId={jobId} version={`${status.done}/${status.total}`} />}
          {view === 'setup' && (
            <SetupView
              job={job}
              status={status}
              warning={warning}
              onSaved={(saved) => {
                setJob(saved)
                refresh()
              }}
              onUploaded={refresh}
            />
          )}
          {view === 'applicant' &&
            (selected ? (
              <ApplicantReview applicantId={selected.id} version={`${selected.status}:${selected.score}:${selected.error}`} />
            ) : (
              <div className="h-40 animate-pulse rounded-xl bg-hairline" aria-label="Loading applicant" />
            ))}
        </div>
      </div>
    </div>
  )
}
