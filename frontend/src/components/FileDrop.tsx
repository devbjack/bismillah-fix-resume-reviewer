import { FileUp } from 'lucide-react'
import { useId, useState, type DragEvent } from 'react'

interface Props {
  multiple?: boolean
  label: string
  hint: string
  onFiles: (files: File[]) => void
  disabled?: boolean
}

/** A real file input, enlarged into a drop zone. Keyboard and screen readers get the native input. */
export function FileDrop({ multiple, label, hint, onFiles, disabled }: Props) {
  const id = useId()
  const [over, setOver] = useState(false)

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setOver(false)
    if (!disabled) onFiles(Array.from(e.dataTransfer.files))
  }

  return (
    <label
      htmlFor={id}
      onDragOver={(e) => {
        e.preventDefault()
        setOver(true)
      }}
      onDragLeave={() => setOver(false)}
      onDrop={onDrop}
      className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border border-dashed px-6 py-8 text-center transition-colors duration-150 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-aubergine ${
        over ? 'border-aubergine bg-lavender' : 'border-aubergine-mute bg-white hover:bg-lavender/60'
      } ${disabled ? 'pointer-events-none opacity-50' : ''}`}
    >
      <FileUp className="size-6 text-aubergine" aria-hidden />
      <span className="font-semibold text-ink">{label}</span>
      <span className="text-sm text-ink-mute">{hint}</span>
      <input
        id={id}
        type="file"
        accept="application/pdf,.pdf"
        multiple={multiple}
        disabled={disabled}
        className="sr-only"
        onChange={(e) => {
          onFiles(Array.from(e.target.files ?? []))
          e.target.value = ''
        }}
      />
    </label>
  )
}
