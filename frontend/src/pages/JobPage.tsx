import { ArrowLeft, Download, Trash2, Users } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router'
import { deleteJob, exportUrl, getJob, getRanking, getStatus, type Job, type RankRow, type Status } from '../api'
import { ApplicantList } from '../components/ApplicantList'
import { ApplicantReview } from '../components/ApplicantReview'
import { RequirementsEditor } from '../components/RequirementsEditor'
import { ResumeUpload } from '../components/ResumeUpload'
import { Button, Notice, buttonClass } from '../components/ui'

export function JobPage() {
  const params = useParams()
  const jobId = Number(params.jobId)
  const applicantParam = params.applicantId ? Number(params.applicantId) : null
  const navigate = useNavigate()
  const warning = (useLocation().state as { warning?: string | null } | null)?.warning

  const [job, setJob] = useState<Job | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [rows, setRows] = useState<RankRow[]>([])
  const [status, setStatus] = useState<Status>({ done: 0, total: 0 })
  const [deleting, setDeleting] = useState(false)

  const refresh = useCallback(async () => {
    const [s, r] = await Promise.all([getStatus(jobId), getRanking(jobId)])
    setStatus(s)
    setRows(r)
  }, [jobId])

  useEffect(() => {
    getJob(jobId).then(setJob, () => setNotFound(true))
    refresh().catch(() => {})
  }, [jobId, refresh])

  // poll once a second while resumes are still being scored
  // also keep polling while any row still reads queued: status and ranking are fetched concurrently
  const scoring = status.done < status.total || rows.some((r) => r.status === 'queued')
  useEffect(() => {
    if (!scoring) return
    const t = setInterval(() => refresh().catch(() => {}), 1000)
    return () => clearInterval(t)
  }, [scoring, refresh])

  async function remove() {
    if (!job || !confirm(`Delete "${job.name}" and all ${status.total} uploaded resumes? This can't be undone.`)) return
    setDeleting(true)
    await deleteJob(job.id)
    navigate('/')
  }

  if (notFound) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
        <Notice tone="error">This job doesn't exist anymore.</Notice>
        <Link to="/" className="mt-4 inline-block text-link hover:text-link-hover hover:underline">
          Back to jobs
        </Link>
      </div>
    )
  }
  if (!job) return <div className="mx-auto mt-10 h-8 max-w-7xl animate-pulse rounded bg-hairline px-4" aria-label="Loading job" />

  const selectedId = applicantParam ?? rows.find((r) => r.status === 'done')?.id ?? rows[0]?.id ?? null
  const selected = rows.find((r) => r.id === selectedId)

  return (
    <div className="mx-auto max-w-7xl px-4 pb-16 pt-6 sm:px-6">
      <Link to="/" className="inline-flex items-center gap-1.5 rounded-sm text-sm text-link hover:text-link-hover hover:underline">
        <ArrowLeft className="size-4" aria-hidden />
        All jobs
      </Link>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <h1 className="mr-auto text-[32px] font-bold leading-tight tracking-[-0.256px]">{job.name}</h1>
        {rows.length > 0 && (
          <a href={exportUrl(job.id)} className={buttonClass('secondary', 'sm')}>
            <Download className="size-4" aria-hidden />
            Export CSV
          </a>
        )}
        <Button variant="danger" size="sm" onClick={remove} busy={deleting}>
          <Trash2 className="size-4" aria-hidden />
          Delete job
        </Button>
      </div>

      <div className="mt-6 flex flex-col gap-5">
        {warning && job.status === 'draft' && <Notice tone="error">{warning}</Notice>}
        <RequirementsEditor
          key={job.status + (job.requirements ?? []).map((r) => r.id).join(',')}
          job={job}
          hasApplicants={status.total > 0}
          onSaved={(saved) => {
            setJob(saved)
            refresh().catch(() => {})
          }}
        />
        {job.status === 'confirmed' && <ResumeUpload jobId={job.id} status={status} onUploaded={() => refresh().catch(() => {})} />}
      </div>

      {rows.length > 0 && (
        <section aria-label="Results" className="mt-8 overflow-hidden rounded-xl border border-hairline md:grid md:grid-cols-[320px_minmax(0,1fr)]">
          <div className="border-b border-hairline bg-cream md:max-h-[calc(100dvh-7rem)] md:border-b-0 md:border-r md:sticky md:top-0">
            <ApplicantList jobId={job.id} rows={rows} selectedId={selectedId} />
          </div>
          <div className="min-w-0 p-5 sm:p-8">
            {selected ? (
              <ApplicantReview applicantId={selected.id} version={`${selected.status}:${selected.score}:${selected.error}`} />
            ) : (
              <p className="text-ink-mute">Select an applicant to see their review.</p>
            )}
          </div>
        </section>
      )}
      {job.status === 'confirmed' && rows.length === 0 && (
        <div className="mt-8 flex items-center gap-3 rounded-xl bg-cream px-5 py-6 text-sm">
          <Users className="size-5 shrink-0 text-aubergine" aria-hidden />
          <p>Upload resumes above. Applicants appear here, ranked by score, as soon as each one is scored.</p>
        </div>
      )}
    </div>
  )
}
