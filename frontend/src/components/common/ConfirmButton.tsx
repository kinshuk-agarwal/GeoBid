import { useEffect, useState } from 'react'

interface Props {
  label: string
  confirmLabel?: string
  icon?: React.ReactNode
  /** Primary actions are filled; the rest are outlined. */
  primary?: boolean
  onConfirm: () => Promise<void>
}

/** A button that needs a second click within 3 s (browser confirm() is unreliable). */
export function ConfirmButton({ label, confirmLabel = 'Confirm?', icon, primary = false, onConfirm }: Props) {
  const [armed, setArmed] = useState(false)
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    if (!armed) return
    const t = setTimeout(() => setArmed(false), 3000)
    return () => clearTimeout(t)
  }, [armed])
  return (
    <button
      disabled={busy}
      onClick={async () => {
        if (!armed) return setArmed(true)
        setBusy(true)
        try {
          await onConfirm()
        } finally {
          setBusy(false)
          setArmed(false)
        }
      }}
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-md px-2 py-1 text-[11px] font-medium ring-1 disabled:opacity-50 ${
        armed
          ? 'bg-red-600 text-white ring-red-600'
          : primary
            ? 'bg-slate-900 text-white ring-slate-900 hover:bg-slate-800'
            : 'text-slate-700 ring-slate-200 hover:bg-slate-50'
      }`}
    >
      {icon}
      {armed ? confirmLabel : label}
    </button>
  )
}
