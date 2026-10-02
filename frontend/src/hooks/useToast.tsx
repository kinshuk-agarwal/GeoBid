import { AlertTriangle, CheckCircle2, Info, X } from 'lucide-react'
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

type Tone = 'info' | 'success' | 'warning'

interface Toast {
  id: number
  tone: Tone
  title: string
  body?: string
}

interface ToastApi {
  notify: (t: Omit<Toast, 'id'>, ms?: number) => void
}

const ToastContext = createContext<ToastApi | null>(null)

const TONE: Record<Tone, { icon: typeof Info; className: string }> = {
  info: { icon: Info, className: 'text-sky-600' },
  success: { icon: CheckCircle2, className: 'text-emerald-600' },
  warning: { icon: AlertTriangle, className: 'text-amber-600' },
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const dismiss = useCallback((id: number) => setToasts((ts) => ts.filter((t) => t.id !== id)), [])

  const notify = useCallback(
    (t: Omit<Toast, 'id'>, ms = 5000) => {
      const id = Date.now() + Math.random()
      setToasts((ts) => [...ts.slice(-3), { ...t, id }])
      setTimeout(() => dismiss(id), ms)
    },
    [dismiss],
  )

  const api = useMemo(() => ({ notify }), [notify])

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-0 z-[2000] flex flex-col items-center gap-2 p-4 sm:bottom-auto sm:left-auto sm:top-16 sm:items-end"
      >
        {toasts.map((t) => {
          const { icon: Icon, className } = TONE[t.tone]
          return (
            <div
              key={t.id}
              role="status"
              className="pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-xl bg-white p-3.5 shadow-lg ring-1 ring-slate-200"
            >
              <Icon className={`mt-0.5 size-5 shrink-0 ${className}`} />
              <div className="min-w-0 flex-1">
                <div className="text-sm font-semibold">{t.title}</div>
                {t.body && <div className="mt-0.5 text-xs text-slate-600">{t.body}</div>}
              </div>
              <button
                onClick={() => dismiss(t.id)}
                aria-label="Dismiss"
                className="rounded p-0.5 text-slate-400 hover:text-slate-700"
              >
                <X className="size-4" />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>')
  return ctx
}
