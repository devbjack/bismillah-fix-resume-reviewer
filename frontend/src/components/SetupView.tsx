import { Users } from 'lucide-react'
import type { Job, Status } from '../api'
import { RequirementsEditor } from './RequirementsEditor'
import { ResumeUpload } from './ResumeUpload'
import { Notice } from './ui'

interface Props {
  job: Job
  status: Status
  onSaved: (job: Job) => void
  onUploaded: () => void
  warning?: string | null
}

export function SetupView({ job, status, onSaved, onUploaded, warning }: Props) {
  return (
    <div className="flex flex-col gap-5">
      {warning && job.status === 'draft' && <Notice>{warning}</Notice>}
      <RequirementsEditor
        key={job.status + (job.requirements ?? []).map((r) => r.id).join(',')}
        job={job}
        hasApplicants={status.total > 0}
        onSaved={onSaved}
      />
      {job.status === 'confirmed' && <ResumeUpload jobId={job.id} status={status} onUploaded={onUploaded} />}
      {job.status === 'confirmed' && status.total === 0 && (
        <div className="flex items-center gap-3 rounded-xl bg-cream px-5 py-6 text-sm">
          <Users className="size-5 shrink-0 text-aubergine" aria-hidden />
          <p>Upload resumes above. Applicants appear in the list on the left, ranked by score, as soon as each one is scored.</p>
        </div>
      )}
    </div>
  )
}
