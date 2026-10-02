import { LogIn } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router'

import { errorMessage } from '@/api/client'
import { Spinner } from '@/components/common/Spinner'
import { useAuth } from '@/hooks/useAuth'

const DEMO_PASSWORD = 'geobid123'
const DEMO_ACCOUNTS = [
  { email: 'advertiser1@geobid.local', name: 'Aurora Coffee', role: 'Advertiser' },
  { email: 'advertiser2@geobid.local', name: 'Nimbus Mobile', role: 'Advertiser' },
  { email: 'advertiser3@geobid.local', name: 'Zenith Realty', role: 'Advertiser' },
  { email: 'advertiser4@geobid.local', name: 'Metro Mart', role: 'Advertiser' },
  { email: 'advertiser5@geobid.local', name: 'Swift Fitness', role: 'Advertiser' },
  { email: 'owner1@geobid.local', name: 'Kondapur Media Pvt Ltd', role: 'Pole owner' },
  { email: 'owner2@geobid.local', name: 'HITEC Outdoor Networks', role: 'Pole owner' },
  { email: 'admin@geobid.local', name: 'GeoBid Admin', role: 'Admin' },
]

export function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/map'

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (user) return <Navigate to={from} replace />

  const signIn = async (e: string, p: string) => {
    setSubmitting(true)
    setError(null)
    try {
      await login(e, p)
      navigate(from, { replace: true })
    } catch (err) {
      setError(errorMessage(err, 'Sign-in failed'))
    } finally {
      setSubmitting(false)
    }
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    void signIn(email, password)
  }

  return (
    <div className="flex min-h-full items-start justify-center overflow-y-auto px-4 py-12 sm:items-center">
      <div className="grid w-full max-w-3xl gap-6 md:grid-cols-[1fr_1fr]">
        <form onSubmit={onSubmit} className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h1 className="text-lg font-semibold tracking-tight">Sign in to GeoBid</h1>
          <p className="mt-1 text-sm text-slate-500">Bid on digital pole inventory in real time.</p>

          <label className="mt-6 block text-sm font-medium" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            type="text"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-200"
          />
          <label className="mt-4 block text-sm font-medium" htmlFor="password">
            Password
          </label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-200"
          />

          {error && <p className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>}

          <button
            type="submit"
            disabled={submitting}
            className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-slate-900 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60"
          >
            {submitting ? <Spinner className="size-4 border-slate-500 border-t-white" /> : <LogIn className="size-4" />}
            Sign in
          </button>
        </form>

        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-sm font-semibold">Demo accounts</h2>
          <p className="mt-1 text-xs text-slate-500">
            Password for all: <code className="rounded bg-slate-100 px-1 py-0.5">{DEMO_PASSWORD}</code>. Click to sign in.
          </p>
          <ul className="mt-4 divide-y divide-slate-100">
            {DEMO_ACCOUNTS.map((a) => (
              <li key={a.email}>
                <button
                  type="button"
                  disabled={submitting}
                  onClick={() => {
                    setEmail(a.email)
                    setPassword(DEMO_PASSWORD)
                    void signIn(a.email, DEMO_PASSWORD)
                  }}
                  className="flex w-full items-center gap-3 rounded-md px-2 py-2 text-left hover:bg-slate-50 disabled:opacity-60"
                >
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium">{a.name}</span>
                    <span className="block truncate text-xs text-slate-500">{a.email}</span>
                  </span>
                  <span className="ml-auto shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
                    {a.role}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
