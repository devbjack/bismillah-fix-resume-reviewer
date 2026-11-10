import { Pencil, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { saveRequirements, type Job, type ReqType, type Requirement } from '../api'
import { Button, Notice, TypeChip, inputClass } from './ui'

const DEFAULT_WEIGHT: Record<ReqType, number> = { must: 2, nice: 1 }

interface Props {
  job: Job
  hasApplicants: boolean
  onSaved: (job: Job) => void
}

export function RequirementsEditor({ job, hasApplicants, onSaved }: Props) {
  const reqs = job.requirements ?? []
  const [editing, setEditing] = useState(job.status === 'draft')

  if (!editing) {
    const musts = reqs.filter((r) => r.type === 'must').length
    return (
      <section aria-labelledby="req-heading" className="rounded-xl border border-hairline p-5 sm:p-6">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <h2 id="req-heading" className="text-lg font-semibold">
            Requirements
          </h2>
          <span className="text-sm text-ink-mute">
            {reqs.length} confirmed · {musts} must-have
          </span>
          <Button variant="secondary" size="sm" className="ml-auto" onClick={() => setEditing(true)}>
            <Pencil className="size-3.5" aria-hidden />
            Edit
          </Button>
        </div>
        <ul className="mt-4 flex flex-wrap gap-2">
          {reqs.map((r) => (
            <li key={r.id} className="flex max-w-full items-center gap-2 rounded-pill bg-cream py-1 pl-1 pr-3 text-sm">
              <TypeChip type={r.type} />
              <span className="truncate">{r.text}</span>
            </li>
          ))}
        </ul>
      </section>
    )
  }

  return (
    <EditorForm
      job={job}
      hasApplicants={hasApplicants}
      onCancel={job.status === 'confirmed' ? () => setEditing(false) : undefined}
      onSaved={(saved) => {
        setEditing(false)
        onSaved(saved)
      }}
    />
  )
}

function EditorForm({ job, hasApplicants, onCancel, onSaved }: Props & { onCancel?: () => void }) {
  const [rows, setRows] = useState<Requirement[]>(() => (job.requirements ?? []).map((r) => ({ ...r })))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const invalid = rows.length === 0 || rows.some((r) => !r.text.trim() || !(r.weight > 0))
  const update = (i: number, patch: Partial<Requirement>) =>
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)))

  async function save() {
    setBusy(true)
    setError(null)
    try {
      onSaved(await saveRequirements(job.id, rows))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section aria-labelledby="req-edit-heading" className="rounded-xl border border-hairline p-5 sm:p-6">
      <h2 id="req-edit-heading" className="text-lg font-semibold">
        Check the requirements
      </h2>
      <p className="mt-1 max-w-prose text-sm text-ink-mute">
        Every score is built from this list. Fix anything the AI misread, mark what is a must-have, and set how much each one counts.
      </p>

      <div className="mt-5 hidden grid-cols-[1fr_10rem_5.5rem_2.75rem] gap-3 px-1 text-xs font-semibold text-ink-mute sm:grid" aria-hidden>
        <span>Requirement</span>
        <span>Type</span>
        <span>Weight</span>
      </div>
      <ol className="mt-2 flex flex-col gap-3 sm:gap-2">
        {rows.map((r, i) => (
          <li key={i} className="grid grid-cols-[1fr_auto] gap-2 rounded-lg bg-cream/50 p-2 sm:grid-cols-[1fr_10rem_5.5rem_2.75rem] sm:gap-3 sm:bg-transparent sm:p-0">
            <input
              aria-label={`Requirement ${i + 1}`}
              className={`${inputClass} col-span-2 sm:col-span-1`}
              value={r.text}
              maxLength={200}
              onChange={(e) => update(i, { text: e.target.value })}
            />
            <select
              aria-label={`Type of requirement ${i + 1}`}
              className={`${inputClass} cursor-pointer`}
              value={r.type}
              onChange={(e) => {
                const type = e.target.value as ReqType
                update(i, { type, weight: DEFAULT_WEIGHT[type] })
              }}
            >
              <option value="must">Must-have</option>
              <option value="nice">Nice-to-have</option>
            </select>
            <input
              aria-label={`Weight of requirement ${i + 1}`}
              type="number"
              min={0.5}
              step={0.5}
              className={`${inputClass} tabular-nums`}
              value={r.weight}
              onChange={(e) => update(i, { weight: Number(e.target.value) })}
            />
            <button
              type="button"
              aria-label={`Remove requirement ${i + 1}`}
              className="col-start-2 row-start-2 grid size-11 cursor-pointer place-items-center justify-self-end rounded-pill text-ink-mute transition-colors duration-150 hover:bg-error/10 hover:text-error sm:col-start-auto sm:row-start-auto"
              onClick={() => setRows((rs) => rs.filter((_, j) => j !== i))}
            >
              <Trash2 className="size-4" aria-hidden />
            </button>
          </li>
        ))}
      </ol>
      {rows.length === 0 && (
        <p className="mt-3 rounded-lg bg-cream px-4 py-3 text-sm">No requirements yet. Add at least one to start scoring.</p>
      )}

      <Button
        variant="secondary"
        size="sm"
        className="mt-4"
        disabled={rows.length >= 20}
        onClick={() => setRows((rs) => [...rs, { text: '', type: 'must', weight: DEFAULT_WEIGHT.must }])}
      >
        <Plus className="size-4" aria-hidden />
        Add requirement
      </Button>
      {rows.length >= 20 && <p className="mt-2 text-xs text-ink-mute">20 requirements is the maximum.</p>}

      {error && (
        <div className="mt-4">
          <Notice>{error}</Notice>
        </div>
      )}
      <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-hairline pt-5">
        <Button onClick={save} busy={busy} disabled={invalid}>
          {hasApplicants ? 'Save and re-score everyone' : 'Confirm requirements'}
        </Button>
        {onCancel && (
          <Button variant="secondary" onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
        )}
        {invalid && rows.length > 0 && <span className="text-sm text-ink-mute">Every requirement needs text and a weight above 0.</span>}
      </div>
    </section>
  )
}
