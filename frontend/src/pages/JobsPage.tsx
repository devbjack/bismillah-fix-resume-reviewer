import { ChevronRight, FileText } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { createJob, listJobs, type Job } from '../api'
import { FileDrop } from '../components/FileDrop'
import { Button, Notice, inputClass } from '../components/ui'

const dateFmt = new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short', year: 'numeric' })

export function JobsPage() {
  const [jobs, setJobs] = useState<Job[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    listJobs().then(setJobs, (e: Error) => setLoadError(e.message))
  }, [])

  return (
    <div className="mx-auto grid max-w-7xl gap-10 px-4 py-10 sm:px-6 lg:grid-cols-[1fr_400px]">
      <section aria-labelledby="jobs-heading">
        <h1 id="jobs-heading" className="text-[32px] font-bold leading-tight tracking-[-0.256px]">
          Jobs
        </h1>
        <p className="mt-2 max-w-prose text-ink-mute">
          Each job ranks its applicants against its own requirements.
        </p>
        <div className="mt-6">
          {loadError ? (
            <Notice tone="error">Couldn't load jobs: {loadError}. Is the backend running?</Notice>
          ) : jobs === null ? (
            <ul aria-label="Loading jobs" className="divide-y divide-hairline border-y border-hairline">
              {[0, 1, 2].map((i) => (
                <li key={i} className="flex h-[68px] items-center gap-4 px-2">
                  <div className="h-4 w-48 animate-pulse rounded bg-hairline" />
                </li>
              ))}
            </ul>
          ) : jobs.length === 0 ? (
            <div className="rounded-xl bg-cream px-6 py-10 text-center">
              <FileText className="mx-auto size-7 text-aubergine" aria-hidden />
              <p className="mt-3 font-semibold">No jobs yet</p>
              <p className="mx-auto mt-1 max-w-sm text-sm text-ink-mute">
                Create one from a job-requirement PDF. You'll check the requirements before any resume is scored.
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-hairline border-y border-hairline">
              {jobs.map((job) => (
                <li key={job.id}>
                  <Link
                    to={`/jobs/${job.id}`}
                    className="group flex min-h-[68px] items-center gap-4 px-2 transition-colors duration-150 hover:bg-lavender"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-semibold text-ink">{job.name}</p>
                      <p className="text-sm text-ink-mute">Created {dateFmt.format(new Date(job.created_at))}</p>
                    </div>
                    <span
                      className={`rounded-pill px-3 py-1 text-xs font-bold ${
                        job.status === 'confirmed' ? 'bg-success/10 text-success' : 'bg-cream text-ink'
                      }`}
                    >
                      {job.status === 'confirmed' ? 'Requirements confirmed' : 'Draft'}
                    </span>
                    <ChevronRight className="size-5 text-ink-mute transition-transform duration-150 group-hover:translate-x-0.5" aria-hidden />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
      <NewJobForm />
    </div>
  )
}

function NewJobForm() {
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!name.trim() || !file) return
    setBusy(true)
    setError(null)
    try {
      const { job, warning } = await createJob(name.trim(), file)
      navigate(`/jobs/${job.id}`, { state: { warning } })
    } catch (err) {
      setError((err as Error).message)
      setBusy(false)
    }
  }

  return (
    <section aria-labelledby="new-job-heading" className="self-start rounded-xl border border-hairline p-6 lg:p-8">
      <h2 id="new-job-heading" className="text-[22px] font-semibold leading-snug">
        New job
      </h2>
      <form onSubmit={submit} className="mt-5 flex flex-col gap-5">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="job-name" className="text-sm font-semibold">
            Job title
          </label>
          <input
            id="job-name"
            className={inputClass}
            value={name}
            maxLength={120}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Backend Developer"
            required
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <span className="text-sm font-semibold">Job requirement PDF</span>
          {file ? (
            <div className="flex items-center gap-3 rounded-lg bg-cream px-4 py-3">
              <FileText className="size-5 shrink-0 text-aubergine" aria-hidden />
              <span className="min-w-0 flex-1 truncate text-sm">{file.name}</span>
              <button type="button" className="cursor-pointer text-sm text-link hover:text-link-hover hover:underline" onClick={() => setFile(null)}>
                Change
              </button>
            </div>
          ) : (
            <FileDrop label="Choose or drop the PDF" hint="Text PDF, up to 10 MB" onFiles={(f) => setFile(f[0] ?? null)} />
          )}
        </div>
        {error && <Notice tone="error">{error}</Notice>}
        <Button type="submit" busy={busy} disabled={!name.trim() || !file}>
          {busy ? 'Reading requirements…' : 'Create job'}
        </Button>
        {busy && <p className="-mt-2 text-center text-xs text-ink-mute">The local AI is reading the PDF. This takes about 15 seconds.</p>}
      </form>
    </section>
  )
}
