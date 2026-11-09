import { ChevronDown, CircleCheck, CircleX, TriangleAlert } from 'lucide-react'
import { useEffect, useState } from 'react'
import { getApplicant, type ApplicantDetail, type ReqResult } from '../api'
import { Notice, TypeChip } from './ui'

const MET = 0.5

interface Props {
  applicantId: number
  /** changes when the applicant is re-scored, so the panel refetches */
  version: string
}

export function ApplicantReview({ applicantId, version }: Props) {
  const [detail, setDetail] = useState<ApplicantDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    setError(null)
    getApplicant(applicantId).then(
      (d) => live && setDetail(d),
      (e: Error) => live && setError(e.message),
    )
    return () => {
      live = false
    }
  }, [applicantId, version])

  if (error) return <Notice tone="error">Couldn't load this applicant: {error}</Notice>
  if (!detail || detail.id !== applicantId) return <ReviewSkeleton />

  return (
    <article aria-labelledby="applicant-heading">
      <header className="flex flex-wrap items-end gap-x-8 gap-y-4 border-b border-hairline pb-6">
        <div className="min-w-0 flex-1">
          <h2 id="applicant-heading" className="truncate text-2xl font-bold tracking-[-0.096px]">
            {detail.filename}
          </h2>
          {detail.status === 'done' && (
            <p className="mt-1 text-sm text-ink-mute tabular-nums">
              {detail.must_met} of {detail.must_total} must-haves met
            </p>
          )}
        </div>
        {detail.status === 'done' && (
          <p className="flex items-baseline gap-1 leading-none" aria-label={`Score ${detail.score} out of 100`}>
            <span className="text-[50px] font-bold tracking-[-0.6px] text-aubergine tabular-nums">{detail.score}</span>
            <span className="text-lg text-ink-mute">/100</span>
          </p>
        )}
      </header>

      {detail.status === 'queued' && (
        <p className="mt-6 text-ink-mute" role="status">
          This resume is waiting to be scored. Its review appears here when it's done.
        </p>
      )}
      {detail.status === 'failed' && (
        <div className="mt-6">
          <Notice tone="error">
            Couldn't score this resume: {detail.error}. It stays in the list so nothing is silently dropped.
          </Notice>
        </div>
      )}
      {detail.status === 'done' && (
        <>
          {detail.flagged && (
            <div className="mt-6 flex items-start gap-3 rounded-lg bg-error/8 px-4 py-3 text-sm text-error">
              <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
              <p>Probably missing at least one must-have. Check the evidence before ruling them out.</p>
            </div>
          )}
          <ul className="@container mt-4 divide-y divide-hairline">
            {detail.results.map((r) => (
              <RequirementRow key={r.requirement_id} result={r} />
            ))}
          </ul>
          <p className="mt-6 max-w-prose text-xs leading-relaxed text-ink-mute">
            Each percentage is the AI's estimated probability that the resume meets the requirement; 50% or more counts as met.
            The quote is the resume passage it was given. Advice only: you make the decision.
          </p>
        </>
      )}
    </article>
  )
}

function RequirementRow({ result }: { result: ReqResult }) {
  const [open, setOpen] = useState(false)
  const met = result.probability >= MET
  const pct = Math.round(result.probability * 100)
  const panelId = `evidence-${result.requirement_id}`

  return (
    <li>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((o) => !o)}
        className="grid w-full cursor-pointer grid-cols-[minmax(0,1fr)_4.5rem_auto] items-center gap-x-3 gap-y-2.5 rounded-lg px-2 py-3.5 text-left transition-colors duration-150 hover:bg-lavender/60 @2xl:grid-cols-[minmax(0,1fr)_minmax(9rem,14rem)_4.5rem_auto]"
      >
        {/* chip sits inline so the text wraps under it on narrow panels instead of squeezing beside it */}
        <span className="min-w-0 text-[15px] leading-snug">
          <TypeChip type={result.type} className="mr-2 align-[1px]" />
          {result.text}
        </span>
        <ProbabilityBar value={result.probability} met={met} />
        <span
          className={`col-start-2 row-start-1 flex items-center justify-end gap-1.5 text-sm font-bold tabular-nums @2xl:col-start-auto @2xl:row-start-auto ${met ? 'text-success' : 'text-error'}`}
        >
          {met ? <CircleCheck className="size-4" aria-hidden /> : <CircleX className="size-4" aria-hidden />}
          {pct}%<span className="sr-only">{met ? ', met' : ', not met'}</span>
        </span>
        <ChevronDown
          className={`col-start-3 row-start-1 size-4 text-ink-mute transition-transform duration-200 @2xl:col-start-auto @2xl:row-start-auto ${open ? 'rotate-180' : ''}`}
          aria-hidden
        />
      </button>
      <div id={panelId} hidden={!open} className="px-2 pb-4">
        <blockquote className="whitespace-pre-line rounded-lg bg-cream px-4 py-3 text-sm leading-relaxed text-ink">
          {result.evidence}
        </blockquote>
      </div>
    </li>
  )
}

/** Signature: every bar carries the 50% threshold tick, so "met" reads from position, not colour alone. */
function ProbabilityBar({ value, met }: { value: number; met: boolean }) {
  return (
    <span className="relative col-span-full row-start-2 block h-2 rounded-pill bg-hairline @2xl:col-span-1 @2xl:row-start-auto" aria-hidden>
      <span
        className={`absolute inset-y-0 left-0 rounded-pill ${met ? 'bg-aubergine' : 'bg-aubergine-mute'}`}
        style={{ width: `${Math.max(2, value * 100)}%` }}
      />
      <span className="absolute -top-1 left-1/2 h-4 w-px bg-ink/40" />
    </span>
  )
}

function ReviewSkeleton() {
  return (
    <div aria-label="Loading applicant" className="animate-pulse">
      <div className="h-7 w-64 rounded bg-hairline" />
      <div className="mt-3 h-4 w-40 rounded bg-hairline" />
      {[0, 1, 2, 3, 4].map((i) => (
        <div key={i} className="mt-6 h-5 rounded bg-hairline" />
      ))}
    </div>
  )
}
