import { UserPlus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router'

import { errorMessage } from '@/api/client'
import { Spinner } from '@/components/common/Spinner'
import { useAuth } from '@/hooks/useAuth'

const MIN_PASSWORD = 8
const input =
  'mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-200'

/** New advertiser account. Admin accounts can't be created here. */
export function SignupPage() {
  const { user, register } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (user) return <Navigate to={from ?? '/map'} replace />

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (password.length < MIN_PASSWORD) return setError(`Password must be at least ${MIN_PASSWORD} characters.`)
    if (password !== confirm) return setError('Passwords don’t match.')
    setSubmitting(true)
    setError(null)
    try {
      await register(name.trim(), email.trim(), password)
      navigate(from ?? '/map', { replace: true })
    } catch (err) {
      setError(errorMessage(err, 'Sign-up failed'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-full items-start justify-center overflow-y-auto px-4 py-12 sm:items-center">
      <form onSubmit={onSubmit} className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="text-lg font-semibold tracking-tight">Create an advertiser account</h1>
        <p className="mt-1 text-sm text-slate-500">Bid for seats on digital poles near your customers.</p>

        <label className="mt-6 block text-sm font-medium" htmlFor="name">
          Company or brand name
        </label>
        <input id="name" value={name} onChange={(e) => setName(e.target.value)} required minLength={2} maxLength={120} autoComplete="organization" className={input} />

        <label className="mt-4 block text-sm font-medium" htmlFor="email">
          Email
        </label>
        <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" className={input} />

        <label className="mt-4 block text-sm font-medium" htmlFor="password">
          Password
        </label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          autoComplete="new-password"
          className={input}
        />
        <p className="mt-1 text-xs text-slate-500">At least {MIN_PASSWORD} characters.</p>

        <label className="mt-4 block text-sm font-medium" htmlFor="confirm">
          Confirm password
        </label>
        <input id="confirm" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required autoComplete="new-password" className={input} />

        {error && <p className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-slate-900 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60"
        >
          {submitting ? <Spinner className="size-4 border-slate-500 border-t-white" /> : <UserPlus className="size-4" />}
          Create account
        </button>

        <p className="mt-4 text-center text-sm text-slate-500">
          Already have an account?{' '}
          <Link to="/login" state={location.state} className="font-medium text-slate-900 underline-offset-2 hover:underline">
            Sign in
          </Link>
        </p>
      </form>
    </div>
  )
}
