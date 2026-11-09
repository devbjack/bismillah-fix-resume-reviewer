import { useState } from 'react'
import { uploadResumes, type Status, type UploadResult } from '../api'
import { FileDrop } from './FileDrop'
import { Notice } from './ui'

interface Props {
  jobId: number
  status: Status
  onUploaded: () => void
}

export function ResumeUpload({ jobId, status, onUploaded }: Props) {
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<UploadResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const scoring = status.done < status.total
  const pct = status.total ? Math.round((100 * status.done) / status.total) : 0

  async function upload(files: File[]) {
    if (!files.length) return
    setBusy(true)
    setError(null)
    try {
      setResult(await uploadResumes(jobId, files))
      onUploaded()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section aria-labelledby="upload-heading" className="rounded-xl border border-hairline p-5 sm:p-6">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h2 id="upload-heading" className="text-lg font-semibold">
          Resumes
        </h2>
        {status.total > 0 && (
          <span className="text-sm text-ink-mute tabular-nums">
            {status.total} uploaded{scoring ? '' : ', all scored'}
          </span>
        )}
      </div>

      <div className="mt-4 grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:items-center">
        <FileDrop
          multiple
          disabled={busy}
          label={busy ? 'Uploading…' : 'Choose or drop resume PDFs'}
          hint="English text PDFs · up to 100 at once · 10 MB each"
          onFiles={upload}
        />
        {status.total > 0 && (
          <div>
            <div className="flex items-baseline justify-between text-sm">
              <span className="font-semibold">{scoring ? 'Scoring resumes' : 'Scoring finished'}</span>
              <span className="tabular-nums text-ink-mute">
                {status.done} of {status.total}
              </span>
            </div>
            <div
              role="progressbar"
              aria-label="Scoring progress"
              aria-valuemin={0}
              aria-valuemax={status.total}
              aria-valuenow={status.done}
              className="mt-2 h-2.5 overflow-hidden rounded-pill bg-hairline"
            >
              <div className="h-full rounded-pill bg-aubergine transition-[width] duration-500 ease-out" style={{ width: `${pct}%` }} />
            </div>
            {scoring && <p className="mt-2 text-xs text-ink-mute">You can browse finished applicants while the rest are scored.</p>}
          </div>
        )}
      </div>

      {error && (
        <div className="mt-4">
          <Notice tone="error">{error}</Notice>
        </div>
      )}
      {result && result.rejected.length > 0 && (
        <div className="mt-4">
          <Notice tone="error">
            <p className="font-semibold">
              {result.rejected.length} file{result.rejected.length > 1 ? 's' : ''} skipped
              {result.accepted.length > 0 && `, ${result.accepted.length} added`}
            </p>
            <ul className="mt-1 list-disc pl-5">
              {result.rejected.map((r, i) => (
                <li key={i}>{r.reason}</li>
              ))}
            </ul>
          </Notice>
        </div>
      )}
    </section>
  )
}
