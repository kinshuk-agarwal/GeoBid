import { FlaskConical } from 'lucide-react'

/** Persistent reminder that footfall values are simulated. */
export function SyntheticNotice({ title, compact = false }: { title?: string; compact?: boolean }) {
  return (
    <span
      title={title ?? 'Footfall values simulate an upstream model. They are not real measurements.'}
      className={`inline-flex items-center gap-1.5 rounded-md bg-violet-50 font-medium text-violet-800 ring-1 ring-inset ring-violet-200 ${
        compact ? 'px-1.5 py-0.5 text-[11px]' : 'px-2 py-1 text-xs'
      }`}
    >
      <FlaskConical className="size-3.5" />
      Synthetic footfall data — POC
    </span>
  )
}
